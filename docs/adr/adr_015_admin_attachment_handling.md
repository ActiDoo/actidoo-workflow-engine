# ADR 015: Attachments in the Admin View

**Status:** Proposed
**Date:** 2026-10-29

## Context

In the admin view the data of a task is shown as JSON. For an uploaded file that is just a reference with id, hash, file name and mime type, so the admin can see that a file is there but cannot open it.

If a user uploads a wrong file, e.g. a PDF where the service task expects an image, the task fails. Today the only fix is to change the service task so it copes with the wrong file. What we actually want is that the admin opens the file, replaces or removes it, and runs the task again.

At the same time, attachments can be sensitive company documents such as contracts or personnel files. Being admin or owner of a workflow does not mean someone is cleared to read them.

The backend already has `POST /admin/download_attachment` for global admins and workflow owners (`require_workflow_admin_by_task_id`), but the frontend never calls it. With `replace_task_data` an admin can delete a reference by editing the JSON, which is easy to get wrong, and there is no way to upload a new file.

## Decision Drivers

1. Sensitive documents must not be readable in the admin view.
2. Everything else should be easy to look at, otherwise admins cannot find out why a task failed.
3. We need to be able to see afterwards who opened or changed an attachment.
4. Completed tasks keep the files they were completed with.

## Considered Options

### Marking sensitive upload fields in the form (chosen)

The process modeler sets the custom property `confidential: true` on an upload field. Attachments of such fields are never shown in the admin view, only their metadata. The person who builds the process knows best which documents are sensitive, and it needs no extra configuration on the customer side.

The downside is that a forgotten marking makes a document visible. The download log below at least shows who opened it.

### Separate role for opening attachments (rejected)

Only users with an extra role may open attachments. That works, but every customer would have to maintain another role per workflow, and the role says nothing about which document is sensitive. In practice it would either be given to all admins or to nobody.

### Metadata only, for all attachments (rejected)

Admins see file name, type and size but never the content. Safe, but for most documents that is not enough to understand an error.

### Admins and owners see everything (rejected)

What the existing endpoint does today. Simple, but it ignores sensitive documents.

### Separate endpoint for replacing (chosen)

`POST /admin/replace_attachment` with task id, the path of the reference in the task data and the new file as datauri. Without a file the attachment is removed. The path is needed because the same file can appear several times in the data, e.g. in two fields or twice in a list, and would have the same hash each time. The backend stores the file via the existing upload handling and updates the reference at that path.

The alternative, letting `replace_task_data` accept datauris, would save the endpoint, but the admin would still have to find the right spot in the raw JSON.

## Decision

The admin task details get an attachments section listing every attachment reference in the task data with its path, file name and type. The task that fails is usually a service task: it has no form, and the file was uploaded in an earlier user task whose data was passed on. So the list is built from the task data, not from the form or the uploads of the task itself. Global admins and workflow owners can download each attachment via the existing endpoint; PDFs and images open in a new tab like they do for users. Next to the download there are a "Replace" and a "Remove" button using the new endpoint.

Whether an attachment is confidential is decided by where it was uploaded. For every upload of a file with this hash in the instance, the backend takes the task that stored it, looks up the path of the file in that task's data and checks the field in that task's form. If any of these fields is marked `confidential: true`, the attachment is confidential. Files are stored once per hash, so the same file in a marked and an unmarked field is confidential. Because the marking is read from the form at the time of the request, marking a field later also protects files uploaded before.

Confidential attachments are listed with their metadata and can be replaced or removed, but not downloaded. The admin download endpoint also refuses them, so the protection does not depend on the frontend. Users who are assigned to the task can still open them as before.

Every admin download, replacement and removal is logged with user, workflow instance, task and file name.

Replacing and removing only works for tasks that are ready or in error. Removing is allowed for any field: if the task needs the file, it fails again on the retry. The new file is linked to the instance and to the task like a normal upload. References of the task that are no longer in its data are then cleaned up the same way as on a submit, and a file is only deleted when nothing references it anymore. The task that uploaded the original file is completed and keeps its reference, so the old file stays as long as that task exists. After that the admin retries the failed task as usual.

## Consequences

- Admins can fix a broken upload themselves, without touching the service task.
- Process modelers have to mark sensitive upload fields. Existing workflows have no marking, so their attachments become viewable for admins until they are marked.
- One new admin endpoint plus tests. The admin download endpoint now rejects confidential attachments; both changes are additive for the frontend, so the BFF contract version ([ADR 011](adr_011_bff_contract_version.md)) stays the same.
- A replaced file usually stays in the storage, because the completed task that uploaded it still references it.
- Checking the confidential marking means loading the forms of the tasks that uploaded the file. This happens on every admin download and when the list is built.
- Changes and downloads are only logged, there is no history in the UI.
