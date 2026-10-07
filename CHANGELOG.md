# Changelog

All notable changes to the ActiDoo Workflow Engine are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
releases correspond to the git tags of this repository.

## [Unreleased]

This release makes empty values and form conditions consistent. A field has
one of three states: it has a value; it is `null` because the user cleared
it; or it is missing because it was never asked or is hidden. In conditions
and in the required check, `null` and missing both mean empty. Browser and
server now apply the same rules.

### Added

- **When** a service function reads an optional form field, for example to put
  it into a mail subject:
  - Before: `sth.task_data.get("comment", "")` returned `""` when the user
    never filled the field. A cleared field kept its old value, see below.
  - Now: a cleared field is `null`, so `.get("comment", "")` returns `None`.
    Use `sth.get_value("comment", "")`: it returns `""` when the field is
    missing, `null` or only spaces. The second argument is your own fallback,
    not the default value from the form. For a row of a dynamic list, use
    `get_value(row, "comment", "")` from
    `actidoo_wfe.wf.service_task_helper`.
- **When** a mail template shows a field that is `null`:
  - Before: the mail showed the word `None`.
  - Now: the mail shows nothing at that place.

### Changed

- **When** a user clears an optional field that had a value:
  - Before: the browser did not send a cleared text, number or date field or
    a removed file. The old value stayed in the task data.
  - Now: the browser sends `null` and the server stores it. The old value is
    gone. This works for text, number, date, select and a removed file. A
    multi select becomes an empty list. If a request leaves a field out, the
    stored value stays, as before.
- **When** the cleared field has a default:
  - Before: if clearing left a stored value unchanged, the next form showed
    that old value. If no value was stored, it showed the default.
  - Now: the field stays empty. A default only fills a field that was never
    answered.
- **When** a required field is sent empty:
  - Before: an empty text or only spaces counted as a value. A required multi
    select or dynamic list could be empty.
  - Now: empty is empty, also only spaces. Browser and server check the same
    way. A multi select or dynamic list needs at least one entry. Spaces
    around a real value are kept. This also applies while a required field
    with a `hide-if` is visible.
- **When** a `hide-if` checks if a field is empty, with `= null` or `= ""`:
  - Before: `= null` did not match empty text, and `= ""` did not match
    `null`. For a field that was never filled, `= ""` hid the field on the
    server but not in the browser. A multi select with nothing chosen never
    counted as empty.
  - Now: both forms find every empty field: missing, `null`, empty text, only
    spaces, or a multi select with nothing chosen. Browser and server agree.
- **When** a gateway condition on a sequence flow, with a leading `=`, uses a
  variable that is not in the task data:
  - Before: the task failed. Workflows needed a guard like
    `="approver" not in globals() or approver is None`. The word `null` did
    not work at all.
  - Now: the variable counts as `null`, like in a form's hide-if.
    `=approver = null` is enough. Old guards still work, and `null` works in
    all expressions. A missing name can make a condition true or false,
    depending on the comparison. An ordering comparison (`<`, `>`, `<=`,
    `>=`) with `null` is false. Timers, multi-instance collections and
    correlation keys still fail when a variable is missing. A missing field
    named `type`, `id` or `max` counts as `null` too; Python builtins remain
    available as functions and function arguments.
- **When** a gateway condition with a leading `=` checks a stored empty
  value:
  - Before: blank text and an empty list did not match `null`. Ordering blank
    text against a number could fail the task.
  - Now: `= null` and `= ""` match missing values, `null`, empty or
    whitespace-only text and empty lists. `!= null` and `!= ""` are false
    for them, and ordering comparisons are false.
- **When** a field or a whole dynamic list is marked `readonly` or `disabled`:
  - Before: `readonly` had no effect; users could edit it and the server took
    what the browser sent. Individual `disabled` fields were already protected
    on the server. Neither mark locked a whole dynamic list.
  - Now: the server keeps the stored value and ignores what the browser
    sends. A list is locked as a whole. If users should change such a field,
    remove `readonly`.
- **When** you copy an instance and its data breaks the current rules, for
  example an empty required field:
  - Before: the copy failed.
  - Now: the data goes into the form. The engine checks it when the user
    submits.
- **When** an instance was started before the update:
  - It keeps the form definitions from its start. No migration is needed.
  - At once: the required check, all `hide-if` fixes, gateway conditions, the
    mail output and copying an instance.
  - Only for new instances: cleared fields become `null`, required lists need
    one entry, `readonly` works like `disabled`, locked lists.

### Fixed

- **When** a user uploads a file after an earlier task removed it:
  - Before: uploading onto the stored `null` failed the submit.
  - Now: the new file replaces `null`, also inside a dynamic-list row.
- **When** a later task hides a field the user cleared:
  - Before: hiding removed a stored empty list. A later form could fill
    the field with its default again. An empty value sent for a hidden
    field could also overwrite stored data.
  - Now: stored `null` and empty lists stay empty while hidden. A submit
    writes nothing into a hidden field, including `null` or an empty list.
- **When** a `hide-if` compares a field that was never filled, like
  `=category = "a"`:
  - Before: the server said true and hid the dependent field. It dropped what
    the user typed there. The browser showed the field.
  - Now: browser and server both say false. The field stays visible and is
    checked.
- **When** a `hide-if` mixes fields from different levels with `or` or `and`,
  for example a field of a list row and a field outside the list:
  - Before: the server looked for all fields on the level of the first one.
    It hid or required the wrong fields.
  - Now: each comparison is checked on its own level, including nested
    combinations of `or` and `and` and conditions across more than two levels.
    Such a condition may contain at most 10 comparisons; more raise an error.
- **When** a `hide-if` uses `<`, `>`, `<=` or `>=`:
  - Before: the server read them as `=`. For `amount > 10`, the server hid the
    field at 10 and showed it at 20. The browser did the opposite.
  - Now: browser and server compare numbers the same way. A comparison with
    text, or a chain like `1 < amount < 5`, is rejected when the definition
    loads, as described below.
- **When** a form has a `hide-if` outside the supported subset, for example
  `contains(...)`, `in` or `not(...)`:
  - Before: the server could read the condition incorrectly or fail when
    the form was used.
  - Now: the workflow definition fails to load and is not offered for
    start. The log identifies the workflow, form and field.
- **When** a dynamic-list overview checks a row's `hide-if` against `""`:
  - Before: the overview could show a field that the form hid.
  - Now: the overview and the form use the same empty-value comparison.
- **When** a gateway condition with a leading `=` uses `not(...)`,
  one-argument `contains(...)` or a range outside `=` or `!=`:
  - Before: the condition could be true regardless of the data or fail
    without a useful explanation.
  - Now: the gateway enters the error state with a message explaining
    how to rewrite the condition.
- **When** a gateway condition compares with an open range, like
  `=amount = (1..5]`:
  - Before: the open endpoint could be treated as closed.
  - Now: the range excludes 1 and includes 5. `!=` respects the endpoints too.
- **When** a condition contains text in quotes, like `"true_positive"` or
  `"a=b"`:
  - Before: the engine changed the text before it checked the condition, to
    `"True_positive"` or `"a==b"`. The condition never matched. Variable names
    that contain true or false, like `is_true_flag`, were changed too.
  - Now: text in quotes and such names stay as written, in gateway conditions
    and in `hide-if`.

### Migration notes

Running instances need no data migration. Check your workflow project for
these points.

Workflow code:
- Read optional fields with `sth.get_value(key, default)` where you build
  text, a mail subject, a file name or a PDF. A cleared field is now `null`,
  and `task_data.get(key, default)` returns `None` for it.
- A project that uses `sth.get_value` needs this engine version or later.

Forms:
- Remove `readonly` from fields that users should change. The server now
  ignores what users enter there.
- Make a multi select or dynamic list optional if it may stay empty.
  Required now means at least one entry.
- Check `hide-if` conditions that compare with text in quotes, like
  `= "false"`. They now match, so the field may hide and its value is
  removed.
- Rewrite `hide-if` conditions outside the supported subset, including
  ordering comparisons with text, chains like `1 < x < 5`, `contains(...)`,
  `in` and `not(...)`. Their workflow definitions now fail to load.
- Split a `hide-if` that mixes list-row fields with other fields in more than
  10 comparisons, for example with a helper field set by a service task. It
  now raises an error.

Gateways:
- Guards like `="x" not in globals() or x is None` still work. You can write
  `=x = null` instead.
- Rewrite `not(x = 1)` as `x != 1`, use two arguments for `contains`, and
  write `x >= 1 and x <= 5` instead of `x in [1..5]` in conditions with a
  leading `=`.
- Check variable names in conditions. A missing name reads as `null`, so a
  typo can change the route. For example, `=aprover = null` is true when
  `aprover` is missing, even if `approver` has a value.

Tests:
- Send real values for required fields. `""` or only spaces now fail.

## [0.1.44] - 2026-09-23

### Changed

- Translations: the engine reads the `.po` catalogs directly and keeps them in
  memory, keyed by the file's modification time. There is no `.mo` file and no
  compile step any more; a saved `.po` takes effect on the next form load
  (workflow titles are cached until restart). A
  workflow project only has to list `workflows/**/*.po` in its package data,
  as the template now does. The pytest plugin collects every `.po` as a test
  of its own, so a file that cannot be parsed fails the test run instead of
  the deployment.

### Fixed

- Engine image: the global mail catalog was not part of the wheel, so every
  mail went out untranslated. The `.po` files are packaged now.

### Removed

- The `compile-all` command of `actidoo_wfe.wf.cli_i18n` and the functions
  `compile_po_to_mo`, `compile_all` and `compile_global_catalog`. Drop the
  call from your build; nothing replaces it.

## [0.1.43] - 2026-09-14

### Added

- Number ranges: a workflow can issue running business numbers - case,
  ticket or document numbers - without a hand-built counter (ADR 012). A
  range is a data model the project owns; the engine guarantees that a number
  is issued exactly once, also when instances run in parallel or an
  administrator re-runs a step.
- Admin: a page per number range shows which number went to which workflow
  instance and step, and when. Visible to global administrators and to the
  owners of the workflows that declare the range.
- Task deadlines: a user task in the BPMN can carry the properties `urgency`
  and `critical`, in days after the task became ready. Open tasks show a
  yellow or red clock once a threshold is passed, with the date in the task's
  info popover. The dates are fixed when the task is created; a later change
  of the workflow definition leaves running tasks alone.
- `EMAIL_REQUEST_TIMEOUT_SECONDS`: a limit for every call while sending mail,
  default 30 seconds. An unresponsive mail gateway no longer holds a workflow
  instance forever.

### Changed

- Task pages reworked: open and completed tasks are one list per tab with
  title, subtitle and an info popover (start date, instance id, deadline); the
  selected task is highlighted. Submit sits bottom right in a sticky bar,
  Reset and Delete bottom left; a workflow is deleted from there after a
  confirmation.
- "My workflows" is one list instead of separate "in progress" and
  "completed" tabs, sortable by state, with an option to show the instance id.
- One type scale and one page header across the app; icon-only buttons share
  one outlined look; link colors follow the branding palette; the focus ring
  on tabs and list items shows for keyboard focus only.
- Data tables: when a row's actions would not fit side by side, the column
  shows a menu instead.
- Instance subtitles may be up to 255 characters (was 50); lists clamp them
  to two lines.
- Admin: the non-functional "Skip tasks" button is gone.

### Fixed

- Admin retry of an erroneous task: the answer now tells the truth. A step
  that fails again returns 409 and keeps its new error message; a step that
  ran while a later step failed says so instead of blaming the retried step;
  a step already completed by an earlier request, or an instance still busy
  with the first retry, returns 409 instead of a server error. The frontend
  names the case and reloads the task.
- Dynamic lists: the collapsed row overview no longer shows fields that a
  `hide-if` condition hides for that row.
- Task header: lane roles without a trailing separator, "-" when no role is
  assigned.
- A second click on Delete while the first request is still running is
  ignored.

## [0.1.42] - 2026-09-02

### Added

- BFF contract-version check: the server refuses requests from clients whose
  BFF contract version does not match, so stale browser tabs fail fast instead
  of misbehaving; clients can explicitly opt out of the check.
- Browser-mode frontend test suite: workflow forms are exercised in a real
  browser (Vitest + React Testing Library) against a fake BFF, with form
  fixtures generated by a backend CLI command and verified in CI.

### Changed

- Documentation: the handbook was rewritten around building and operating a
  workflow project (still work in progress - treat it as a draft), and the
  docs build moved from MkDocs Material (end of life) to Sphinx with MyST
  and Furo.
- UI: secondary buttons use a gray design, and the abort action is
  labelled "Cancel".
- Engine: a file is saved only if the form has a place for it and the
  submission is accepted. Files sent into a field that is disabled, hidden or
  unknown, and files sent with a submission that is then rejected, are no
  longer saved at all. This closes a way to put arbitrary files into an
  instance's attachment list.


### Fixed

- Engine: dynamic-list rows could pick up values that belong to other rows.
  On submission the server merges stored, server-owned values (for example
  disabled fields) back into the submitted rows — and it matched rows by
  position. After deleting or reordering a row, those values therefore
  landed in the wrong rows, and a newly added row silently lost them. Rows
  now carry a stable id and are matched by it (ADR 010), which also makes
  deleting and reordering safe. Consequence: clients must send rows back
  with the ids they received — list submissions without row ids are
  rejected. Regression test:
  `test_row_identity_flow.py::test_deleting_a_middle_row_keeps_hidden_values_on_their_own_rows`.

- Engine: a `hide-if` condition on a whole dynamic list or attachment list
  was ignored. A hidden list could still demand its minimum number of items
  and block the submit, and data sent for it was stored even though the list
  was hidden. Hidden lists are now treated like hidden single fields: while
  hidden, nothing is demanded and nothing is stored. Regression tests:
  `test_validation_hide_if.py::test__hidden_list_does_not_enforce_min_items`
  and `::test__rows_submitted_for_a_hidden_list_are_stripped_without_error`.

- Engine: `this.` and `parent.` in `hide-if` conditions could silently read
  the wrong field. When the named row had no such field — a typo, or the
  field only exists further up — the server kept searching upwards and used
  a same-named field from an enclosing row or the top level. Example:
  `=this.flag = false` in a nested row, where `flag` only exists in the
  outer row — the server read the outer `flag`, hid the field and stripped
  its value, while the browser reads `this.flag` as empty and kept showing
  the field. Now `this.` and `parent.` look only at the level they name; a
  field that is absent there reads as `null`. Plain names without a keyword
  keep the old upward search. Regression test:
  `test_validation_hide_if.py::test__this_reference_does_not_reach_into_an_outer_row`.

- Engine: when two requests changed the same workflow instance at the same
  time (for example two tasks completed in parallel), both read the same
  stored state and the write that finished last silently discarded the
  other's changes. The instance row is now locked for every
  read-modify-write, so changes are applied one after the other.
  Regression test:
  `test_instance_concurrency.py::test_overlapping_submits_on_one_instance_do_not_discard_each_other`.

- Frontend: clicking Submit could do nothing at all — no error message, no
  submission. This happened when a required field sat inside a dynamic list
  row that had become hidden: the field was still validated, but not
  rendered, so its error had no place to appear. Validation errors of hidden
  fields are now discarded on submit, and hidden fields read as `null` in
  list-row conditions, matching the server. Regression test:
  `test-flow-dynamic-list-hidden.test.tsx` — "submits although a hidden
  inner list carries an empty required field".

- Frontend: the open-tasks list could show outdated entries — finished tasks
  still listed, new ones missing — because it kept showing the list cached
  from the last visit. It now reloads whenever the view is opened, keeping
  the old entries on screen until the fresh ones arrive. Regression test:
  `task-list-after-admin-change.test.tsx` — "shows a task the admin
  assigned to themselves after returning to the list".

- Engine: files were saved before the submission was checked. A rejected
  submission therefore left its file attached to the instance, where it stayed
  until that task was submitted successfully — the cleanup that would have
  removed it runs after the check the submission failed. A file sent into a
  field that the current step only displays turned up twice in the attachment
  list. Files are now saved after the submission is accepted. A file whose
  data URI the engine cannot read is reported as an error as well — it used to
  be dropped in silence, which left the old file in place under the new file's
  name. Regression tests: `test_upload7.py`, `test_bff_user.py`.

- Engine: a submission from someone who may not work on the task — like any
  request for a task the caller cannot access — now answers 403 instead of a
  server error. Such a request is also refused before its payload is read.

### Security

- Bumped `urllib3` from 2.6.3 to 2.7.0.

## [0.1.41] - 2026-07-24

Last release before this changelog was introduced. See the git history for
earlier changes.

[Unreleased]: https://github.com/ActiDoo/actidoo-workflow-engine/compare/v0.1.44...HEAD
[0.1.44]: https://github.com/ActiDoo/actidoo-workflow-engine/compare/v0.1.43...v0.1.44
[0.1.43]: https://github.com/ActiDoo/actidoo-workflow-engine/compare/v0.1.42...v0.1.43
[0.1.42]: https://github.com/ActiDoo/actidoo-workflow-engine/compare/v0.1.41...v0.1.42
[0.1.41]: https://github.com/ActiDoo/actidoo-workflow-engine/releases/tag/v0.1.41
