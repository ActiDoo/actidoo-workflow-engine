# Number ranges

Many workflows have to hand out a running number: a case number, a ticket number, a document number. The example on this page is a case workflow. Each new case gets `CASE-01000`, `CASE-01001` and so on. The number goes into the instance subtitle and to a downstream system.

A number range is a [data model](data-models.md). Its rows are the numbers that have been issued. The next number is derived from the rows already in the table, and each row records which workflow instance and which step got the number. Your project owns the table and its migration. A workflow declares the range in `DATA_MODELS` like any other model.

The issued numbers are shown under *Admin → Number ranges*: for each range the workflows that use it, the state of every scope, and the log of who got which number. A global admin sees all ranges; a workflow owner sees the ranges of their workflows. The reasoning behind the design is in [ADR 012](adr/adr_012_number_ranges.md).

## Define a range

Base the model on `NumberRangeMixin`. It brings all the columns a range needs, so you only write the numbering scheme.

```python
from actidoo_wfe.wf.models import NumberRangeMixin, extension_model_base
from actidoo_wfe.wf.registry_data_model import register_data_model

Base = extension_model_base("acme")


@register_data_model(name="CaseNumber")
class CaseNumber(Base, NumberRangeMixin):
    _ext_table = "case_number"  # -> table ext_acme_case_number

    @classmethod
    def next_value(cls, previous):
        return 1000 if previous is None else previous + 1

    @classmethod
    def format_number(cls, value, scope_key):
        return f"CASE-{value:05d}"
```

Register the model without `api=`. The numbers are read in the admin area, not on the Data page.

Each row has `value`, `formatted`, `scope_key`, `workflow_instance_id`, `workflow_instance_task_id`, `alloc_key` and `created_at`. The table needs a [migration](data-models.md#migrations) like every other data model table. If you replace an existing counter, insert its last number in the same migration. Otherwise the numbering starts over.

## Issue a number

Declare the range in the workflow module and give it a service task of its own:

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

Issue the number in one step and use it in the next. The reason: issuing a number blocks the sequence until the step's transaction commits. If the same step also calls an external system, all other instances wait for that call. And if the step fails and an admin retries it, only the posting runs again. The number stays the same, so the downstream system sees the same number twice instead of two different ones.

## Several numbers in one step

A failing service task does not roll back. The engine catches the exception, sets the task to error and commits. A number issued before the exception is therefore in the table. When an admin retries the task, the function runs from the start and asks for the number again. Each number is stored under a key within the task, and the same key returns the stored number instead of a new one.

Without `key`, the key is the position of the call: `#0`, `#1`. Two calls give two numbers, and the retry gets both back in the same order:

```python
main = sth.next_number("CaseNumber")
sub = sth.next_number("CaseNumber")
```

In a loop, use the item id as `key`. If the order of the items changes between runs, the position would pair the numbers with the wrong items:

```python
for item in items:
    item["number"] = sth.next_number("CaseNumber", key=item["id"])
```

## The scheme: four hooks

The scheme is four classmethods, each with a working default. You override the ones you need. The engine enforces uniqueness itself, so a mistake in a hook gives an odd number, never a duplicate.

| Hook | Job | Default |
|---|---|---|
| `number_scope(sth)` | which rows share one sequence | `""`: one global sequence |
| `reference_value(db, scope_key)` | the value `next_value` starts from | the highest `value` in the scope |
| `next_value(previous)` | the next candidate | `previous + 1`, starting at 1 |
| `format_number(value, scope_key)` | the number people see | `str(value)` |

Each recipe below is a complete scheme. Copy the methods into your model class.

### Restart every year

`number_scope` decides which rows share a sequence. A new year is a new scope and starts at 1.

```python
from actidoo_wfe.helpers.time import dt_now_naive


@classmethod
def number_scope(cls, sth):
    return str(dt_now_naive().year)


@classmethod
def format_number(cls, value, scope_key):
    return f"PX-{scope_key}-{value:05d}"
```

Gives `PX-2026-00001`, `PX-2026-00002`, and on 1 January `PX-2027-00001`. Put the year into the rendering: numbers are unique per scope, so without the year every year would produce the same strings.

### One sequence per site, taken from the form

`number_scope` gets the task helper, so the scope can come from task data.

```python
@classmethod
def number_scope(cls, sth):
    return sth.task_data["site"]


@classmethod
def format_number(cls, value, scope_key):
    return f"{scope_key}-{value:04d}"
```

Gives `BER-0001`, `BER-0002`, `HAM-0001`. Hamburg starts at 1 no matter how many Berlin numbers exist. A `KeyError` here fails the task, so check the field if it can be missing.

### Start value and step

`next_value` turns the highest number so far into the next one. `previous` is `None` while the scope is empty.

```python
@classmethod
def next_value(cls, previous):
    return 1000 if previous is None else previous + 10
```

Gives `1000`, `1010`, `1020`.

### Skip a reserved block

Same hook, one rule more. It is plain arithmetic, so it is easy to unit-test.

```python
@classmethod
def next_value(cls, previous):
    candidate = 1 if previous is None else previous + 1
    return 6000 if 5000 <= candidate < 6000 else candidate
```

Gives `4998`, `4999`, `6000`, `6001`.

### Check digit

`value` stays the plain sequence. The check digit is part of the rendering. The digit sum here is a placeholder; put in your own rule.

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

Gives `A0001` … `A9999`, then `B0001`. The sequence behind it stays `1, 2, 3, …`.

### Random numbers

A running number tells everyone how many cases you have. Random numbers do not. `next_value` ignores `previous`, and `reference_value` returns `None` because there is nothing to read.

```python
import random


@classmethod
def reference_value(cls, db, scope_key):
    return None


@classmethod
def next_value(cls, previous):
    return random.randrange(100_000, 1_000_000)
```

Gives `975733`, `454499`. A collision costs one more attempt. Keep the range much larger than the number of cases you expect, or raise `_number_max_attempts`.

### A block of numbers per site

Each site gets its own starting point. `next_value` cannot do this because it does not know the scope. `reference_value` knows the scope and may query the database. Take the highest number so far, but never go below the site's floor.

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

Gives `10001`, `10002` for Berlin and `20001` for Hamburg. If the blocks are configured rather than fixed, read the floor from a table instead of a dict.

### `value` is always an integer

The engine sorts and compares `value`. A string column would sort `"9"` above `"10"`, and a letter block would get stuck at `Z999`. Letters belong in `format_number`.

## What the engine guarantees

**A number is issued once.** Issuing inserts a row. The primary key `(scope_key, value)` rejects a duplicate, and the engine tries the next candidate, up to `_number_max_attempts`. Uniqueness does not depend on a lock or on your hooks.

**A retry does not consume a new number.** The number is recorded against the task occurrence and the call within it. An admin retry runs the same task and gets the same number. The children of a multi-instance activity and the passes of a loop are separate occurrences and get their own numbers.

**`reference_value` reads from its own transaction.** It sees the numbers this transaction has issued but not yet committed. After a collision the engine reads what other transactions committed and takes the higher of the two. So return a floor, a maximum or `None`, and do not take a lock yourself. A `with_for_update` deadlocks two concurrent first allocations on an empty scope; the details are in `allocate_number`.

## Rules

- **Never delete a row** from a number range table. A deleted row frees its number, and it gets issued again. Deleting a workflow instance is fine; data model rows stay.
- **Numbers have gaps.** A scheme may skip on purpose, and a number issued to a cancelled instance stays issued.
- **Put the scope into `format_number`** when numbers must be unique across scopes. Uniqueness is checked per scope. Plain padding under a yearly reset collides across years.
- **Keep the issuing step short.** `_number_lock_wait_timeout` raises the lock timeout of a range, but the wait is still for the other transaction to finish.

## Related

- [Data models](data-models.md)
- [Developing workflows](workflows.md): service functions, the task helper and the admin retry
- [ADR 012: Number ranges](adr/adr_012_number_ranges.md)
