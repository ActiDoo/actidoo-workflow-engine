# Number ranges

A workflow often has to issue a running business number — a case, ticket or document number people quote outside the system. The running example is a case workflow that stamps each new case with `CASE-01000`, `CASE-01001` and so on, puts the number in the instance subtitle, and posts it to a downstream system.

A number range is a [data model](data-models.md) whose **rows are the issued numbers**. There is no counter to keep next to them: the next number is derived from the rows already there, and the same rows are the record of which workflow instance and which step received which number. It is a tier of its own, beside the plain, versioned and workflow-managed ones — a range is an append-only ledger, so the versioning those carry would be permanently `1` on every row. What the data model brings applies unchanged: your project owns the table and its migration, and a workflow declares its access in `DATA_MODELS`.

A range is **not** exposed through the data API. `register_data_model(api=...)` is for workflow-produced business records on the Data page; a range is the numbering machinery behind them. The log has a view of its own under *Admin → Number ranges*: per range the workflows that declare it and the state of every scope, and the allocation log itself, filterable by scope and linking each number to the workflow instance that received it. A global admin sees every range; a workflow owner sees the ranges a workflow of theirs declares.

## Define a range

Base the model on `NumberRangeMixin`. It brings every column a range needs — the issued `value` and its rendering, the scope, the provenance and the timestamp — so all you write is the scheme.

```python
from actidoo_wfe.wf.models import NumberRangeMixin, extension_model_base
from actidoo_wfe.wf.registry_data_model import register_data_model

Base = extension_model_base("acme")


@register_data_model(name="CaseNumber")  # no api= — a range is not a Data page record
class CaseNumber(Base, NumberRangeMixin):
    _ext_table = "case_number"  # -> table ext_acme_case_number

    @classmethod
    def next_value(cls, previous):
        return 1000 if previous is None else previous + 1

    @classmethod
    def format_number(cls, value, scope_key):
        return f"CASE-{value:05d}"
```

Every row then carries `value`, `formatted`, `scope_key`, `workflow_instance_id`, `workflow_instance_task_id`, `alloc_key` and `created_at` — which is the allocation log, in the same table. The table needs a [migration](data-models.md#migrations) like any other data model table. When you are replacing an existing counter, seed the last number it issued in the same revision — otherwise the numbering starts over.

## Issue a number: the two-task shape

Declare the range in the workflow module like any data model, and give it a service task of its own:

```python
DATA_MODELS = ["CaseNumber"]


def service_assign_case_number(sth):
    number = sth.next_number("CaseNumber")
    sth.set_task_data_key("case_number", number)
    sth.set_workflow_instance_subtitle(number)


def service_post_case(sth):
    with sth.get_connector("sap_ci", "cases") as sap:
        sap.post(case_number=sth.task_data["case_number"])
```

**Issue the number in its own short step and use it in the next one.** This is the shape to copy, and it is not a matter of taste — it solves three things at once:

- Issuing holds its sequence until the surrounding transaction commits. A step that issues a number and *then* calls an external system makes every concurrent issue wait for that call, and a wait that runs into the lock timeout leaves the task erroneous.
- Retrying an erroneous task re-runs the function from the start, so a step that issues and posts repeats the post as well. Splitting keeps the retry limited to the posting.
- The number itself stays stable across the retry either way (see below), so the downstream system sees the *same* number twice rather than two different ones.

## Several numbers in one step

Two calls without a key give two numbers — the helper counts the draws (`#0`, `#1`) so a retry replays the same sequence and gets both back:

```python
main = sth.next_number("CaseNumber")
sub = sth.next_number("CaseNumber")
```

Pass `key` where the call order is not a stable anchor, for instance a loop whose items may differ between attempts. The number is then tied to the thing rather than to the position:

```python
for item in items:
    item["number"] = sth.next_number("CaseNumber", key=item["id"])
```

## The scheme: four hooks

Everything a range varies is a classmethod with a working default. All four are safe to override: none of them carries the uniqueness guarantee, so a mistake produces a poor number, never a duplicate one.

| Hook | Job | Default |
|---|---|---|
| `number_scope(sth)` | which rows compete for one sequence | `""` — one global sequence |
| `reference_value(db, scope_key)` | the value `next_value` starts from | the highest `value` in the scope |
| `next_value(previous)` | the next candidate; pure arithmetic | `previous + 1`, starting at 1 |
| `format_number(value, scope_key)` | the number people see; pure | `str(value)` |

Each recipe below is one range's whole scheme — drop the methods into your model class and leave the other hooks alone.

### A number that restarts every year

`number_scope` decides which rows share a sequence. Rows in different scopes never see each other, so a new year begins at 1 again.

```python
from actidoo_wfe.helpers.time import dt_now_naive


@classmethod
def number_scope(cls, sth):
    return str(dt_now_naive().year)


@classmethod
def format_number(cls, value, scope_key):
    return f"PX-{scope_key}-{value:05d}"
```

Gives `PX-2026-00001`, `PX-2026-00002`, and on 1 January `PX-2027-00001`. Note that `format_number` puts the year into the rendering: uniqueness of the rendered number is enforced per scope, so without it every year would repeat the same strings.

### A separate sequence per site, taken from the form

`number_scope` receives the task helper, so the scope can come from task data.

```python
@classmethod
def number_scope(cls, sth):
    return sth.task_data["site"]


@classmethod
def format_number(cls, value, scope_key):
    return f"{scope_key}-{value:04d}"
```

Gives `BER-0001`, `BER-0002`, `HAM-0001` — Hamburg starts at 1 regardless of how many Berlin numbers exist. If the field may be missing, read it defensively; a `KeyError` here fails the task.

### A start value and a step

`next_value` turns the highest number so far into the next candidate. `previous` is `None` when the scope is still empty.

```python
@classmethod
def next_value(cls, previous):
    return 1000 if previous is None else previous + 10
```

Gives `1000`, `1010`, `1020`.

### A reserved band that must stay free

Same hook, one rule more. It is pure arithmetic — no database, no locking — so it is trivial to unit-test.

```python
@classmethod
def next_value(cls, previous):
    candidate = 1 if previous is None else previous + 1
    return 6000 if 5000 <= candidate < 6000 else candidate
```

Gives `4998`, `4999`, `6000`, `6001` — the block from 5000 to 5999 is skipped in one step.

### A check digit

`value` stays the dense sequence; the check digit belongs to the rendering. (A digit sum is the placeholder here — put your scheme's rule in.)

```python
@classmethod
def format_number(cls, value, scope_key):
    body = f"{value:07d}"
    check = sum(int(digit) for digit in body) % 10
    return f"{body}-{check}"
```

Gives `0000001-1`, `0000002-2`.

### Letter blocks

```python
@classmethod
def format_number(cls, value, scope_key):
    block, index = divmod(value - 1, 9999)
    return f"{chr(ord('A') + block)}{index + 1:04d}"
```

Gives `A0001` … `A9999`, then `B0001`. The sequence behind it stays `1, 2, 3, …`, which is what keeps the ordering intact when the letter rolls over.

### Numbers that do not reveal how many cases there are

A consecutive number tells everyone how much business you did. Scatter it instead: `next_value` ignores `previous`, and `reference_value` returns `None` because there is nothing to read.

```python
import random


@classmethod
def reference_value(cls, db, scope_key):
    return None


@classmethod
def next_value(cls, previous):
    return random.randrange(100_000, 1_000_000)
```

Gives `975733`, `454499`. A collision just costs one more attempt, so keep the range far larger than the number of cases you expect, and raise `_number_max_attempts` if it is tight.

### A separate block of numbers per site

`next_value` cannot do this: it gets the previous value, not the scope. Giving each scope its own starting point is exactly what `reference_value` is for — it is the one hook that sees the scope *and* may query. Take the highest number so far, but never go below the site's block floor.

```python
from sqlalchemy import select

SITE_BLOCKS = {"BER": 10_000, "HAM": 20_000}


@classmethod
def number_scope(cls, sth):
    return sth.task_data["site"]


@classmethod
def reference_value(cls, db, scope_key):
    statement = select(cls.value).where(cls.scope_key == scope_key).order_by(cls.value.desc()).limit(1)
    highest = db.scalars(statement).first()
    return max(highest or 0, SITE_BLOCKS[scope_key])
```

Gives `10001`, `10002` for Berlin and `20001` for Hamburg, interleaved in any order. This is the whole hook — what other transactions committed in the meantime is the engine's business, not yours (see [What the engine guarantees](#what-the-engine-guarantees) below). Read the floor from a table instead of a dict if the blocks are configured rather than fixed — this is the hook where a query belongs.

### Why `value` is always an integer

It is what the engine orders and compares, and a string column would order lexicographically, which breaks quietly and late — `"9"` sorts above `"10"`, and a letter block rolling over from `Z999` to `AA001` would stick on `Z999` forever. Letters belong in `format_number`.

## What the engine guarantees

**A number is issued once.** Issuing inserts a candidate row, and the primary key `(scope_key, value)` refuses a duplicate; the engine then tries the next candidate, up to `_number_max_attempts`. Uniqueness never depends on a lock, and therefore never on your hooks being right.

That the sequence *is* the primary key is a concurrency decision. A range has no surrogate id: when a duplicate is caught on a secondary index instead, InnoDB gap-locks the conflicting row in the clustered index, and with a random key those gaps land in random places, so concurrent allocations lock each other's insert positions crosswise and the retries deadlock. Measured on this allocator, five concurrent allocations into one scope failed about one time in seven that way; with the sequence as the clustered index, eighty out of eighty succeeded.

**Repeating the same work does not consume a new number.** The claim is recorded against the task occurrence and the draw within it. An administrator's retry runs the same task and gets the number it already has. The children of a multi-instance activity and the passes of a loop are separate occurrences and each get their own.

A custom `reference_value` returns what *this transaction* can see — its own session, including numbers it has issued itself and not yet committed. It does not go looking for what other transactions committed in the meantime, and it should not: the engine does that itself, on a separate pooled connection, and only after a collision has shown that somebody else is active. Deferring that second read to the retry is deliberate — an uncontended allocation never holds two connections at once, so it adds no pool pressure. The engine merges the two views by taking the higher, so a custom reference has to be one a higher committed value may override: a floor, a maximum, `None`. Do not use `with_for_update` to see fresh data yourself — on a scope with no rows it takes a gap lock, and two concurrent first allocations then deadlock, which is exactly the first two numbers of every new scope.

## Rules

- **Never delete a row** from a number range table. A deleted row releases its number to be issued a second time. Deleting a workflow instance is safe — data model rows do not go with it.
- **Numbers are not promised to be contiguous.** No number is silently consumed, but a scheme may skip on purpose, and a number issued to an instance that is later cancelled stays issued.
- **`format_number` must work the scope in** if numbers have to be unique across scopes. Uniqueness of the rendering is enforced per scope, so plain padding under a yearly reset would collide across years by construction — a collision no retry can resolve.
- **The log is read in the admin view, not on the Data page.** Which instance received which number, and when, is in the range's own table and shown under *Admin → Number ranges* — built for what an allocation log is read for: filtering by scope and jumping through to the issuing instance. The generic Data page would hide `workflow_instance_id` as a system column, which is why a range is never registered with `api=`.
- **Keep the issuing step short.** A range under real contention can raise its own lock timeout with `_number_lock_wait_timeout`, but that is padding, not a fix: the wait is for the competing transaction to finish.

## Related

- [Data models](data-models.md) — the extension point a number range is built on
- [Developing workflows](workflows.md) — service functions, the task helper and the admin retry
- [ADR 012: Number ranges](adr/adr_012_number_ranges.md)
