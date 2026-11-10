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

The admin task details get an attachments section listing every attachment reference in the task data with path, file name and type. The list comes from the task data because the failing task is usually a service task without a form, holding a file uploaded in an earlier user task. Global admins and workflow owners can download each attachment via the existing endpoint; PDFs and images open in a new tab like they do for users. Next to the download there are "Replace" and "Remove" buttons using the new endpoint.

An attachment is confidential if any upload field in the instance holding a file with this hash is marked `confidential: true`. The backend finds these fields through the tasks that stored the file and their forms. As the marking is read at request time, marking a field later also protects older uploads. Confidential attachments are listed and can be replaced or removed, but not downloaded; the admin download endpoint refuses them too, so the protection does not depend on the frontend. Users assigned to the task can still open them as before.

Every admin download, replacement and removal is logged with user, workflow instance, task and file name.

Replacing and removing works for any field of a task that is ready or in error; if the task needs a removed file, the retry fails again. The new file is linked to the instance and the task like a normal upload, then the task's references are cleaned up as on a submit. A file is only deleted when nothing references it anymore, so the old file stays as long as the completed task that uploaded it exists. After that the admin retries the failed task as usual.

## Consequences

- Admins can fix a broken upload themselves, without touching the service task.
- The confidential marking prevents opening a document by accident in the admin view. It does not protect against an admin who assigns a task to themselves or registers as a delegate, and can then download the file as a user.
- Process modelers have to mark sensitive upload fields. Existing workflows have no marking, so their attachments become viewable for admins until they are marked.
- One new admin endpoint plus tests. The admin download endpoint now rejects confidential attachments; both changes are additive for the frontend, so the BFF contract version ([ADR 011](adr_011_bff_contract_version.md)) stays the same.
- A replaced file usually stays in the storage, because the completed task that uploaded it still references it.
- Checking the confidential marking means loading the forms of the tasks that uploaded the file. This happens on every admin download and when the list is built.
- Changes and downloads are only logged, there is no history in the UI.
