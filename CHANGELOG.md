# Changelog

All notable changes to the ActiDoo Workflow Engine are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
releases correspond to the git tags of this repository.

## [Unreleased]

### Added

- Completed tasks show when they were submitted. `my_usertasks/{state}` carries
  the task's `completed_at`, and the task header prints date and time under the
  title. The admin workflow details page shows the same date per task in the
  task list, plus the instance's own start and completion time in its header.

### Fixed

- Cancelling a workflow that is already finished. `cancel_workflow_instance`
  answers a completed or already cancelled instance with 409
  `workflow_instance_already_finished` instead of reporting success and
  marking the closed instance as unsuccessful. The admin workflow details page
  no longer offers the button for a finished instance, and the task header
  hides it once the task or its instance is done.

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
