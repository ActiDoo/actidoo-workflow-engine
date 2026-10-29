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

`POST /admin/replace_attachment` with task id, hash and the new file as datauri. Without a file the attachment is removed. The backend stores the file via the existing upload handling and updates the reference in the task data.

The alternative, letting `replace_task_data` accept datauris, would save the endpoint, but the admin would still have to find the right spot in the raw JSON.

## Decision

The admin task details get an attachments section listing every attachment of the task with field, file name and type. Global admins and workflow owners can download each attachment via the existing endpoint; PDFs and images open in a new tab like they do for users. Next to the download there are a "Replace" and a "Remove" button using the new endpoint.

Attachments of fields marked `confidential: true` are listed with their metadata and can be replaced or removed, but not downloaded. The admin download endpoint also refuses them, so the protection does not depend on the frontend. Users who are assigned to the task can still open them as before.

Every admin download, replacement and removal is logged with user, workflow instance, task and file name.

Replacing and removing only works for tasks that are ready or in error, and required fields can only be replaced, not removed. The old file is not deleted, because other tasks of the instance may still point to it. After that the admin retries the failed task as usual.

## Consequences

- Admins can fix a broken upload themselves, without touching the service task.
- Process modelers have to mark sensitive upload fields. Existing workflows have no marking, so their attachments become viewable for admins until they are marked.
- One new admin endpoint plus tests. The admin download endpoint now rejects confidential attachments; both changes are additive for the frontend, so the BFF contract version ([ADR 011](adr_011_bff_contract_version.md)) stays the same.
- Replaced files stay in the storage. Cleaning up attachments nobody references anymore is not part of this.
- Changes and downloads are only logged, there is no history in the UI.
