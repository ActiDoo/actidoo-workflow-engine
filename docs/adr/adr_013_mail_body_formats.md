# ADR 013: Mail Body Formats

**Status:** Implemented
**Date:** 2026-09-17

## Context

Every mail the engine sends is plain text. A service task builds the body as a Python string and hands it to `send_text_mail`; the engine's own notification mails come from Mako templates through the same function. Both transports were fixed to plain text: the Graph payload said `contentType: "Text"`, the SMTP path called `set_content` once.

Workflows want to point people at documents in OneDrive or SharePoint. Those links are several hundred characters long. In a plain-text mail they sit in the middle of the text, break across lines and cannot be hidden behind a word. The request was HTML mails, possibly Markdown.

## Decision Drivers

1. A link with a readable text instead of a bare URL in mails from service tasks.
2. A body that a workflow developer writes by hand in a Python string stays readable in the source, in the test log and in the plain-text part of the mail.
3. Values from forms end up in mail bodies. A user must not be able to inject markup, a tracking image or a link that poses as one of the engine's links.
4. No change for existing workflows and for the engine's own notification mails.

## Decision

**Markdown is the default rich format, HTML the escape hatch.** `send_mail` takes `body_format` with the values `text`, `markdown` and `html`; `send_text_mail` stays as the plain-text shorthand and keeps its behaviour. The same applies to the task helper: `sth.send_mail` and `sth.send_text_mail`. The notification templates are untouched and still go out as plain text; moving them to Markdown is a separate decision.

A Markdown body is rendered with `markdown-it-py` (GFM-like preset: tables, strikethrough, autolinked URLs, line breaks kept) with raw HTML disabled. Anything that looks like HTML in the body is shown literally, and the renderer's link validation drops `javascript:`, `vbscript:` and `data:` targets. The rendered document is sent as HTML; the Markdown source is sent as the plain-text alternative, so a client without HTML still shows a readable mail and the test log shows what the developer wrote.

An HTML body is sent as it is. The caller escapes; there is no sanitizer. Workflow code is Python that runs inside the backend and has the same trust as the rest of the engine, so a sanitizer would protect against the developer, not against the user. A developer who interpolates form data into an HTML body escapes it with `markupsafe.escape`; the documentation says so and recommends Markdown instead.

**Interpolated values are escaped for Markdown, not trusted.** Markdown with HTML off still reads `*`, `_`, `[`, `#` at line start and similar characters as markup, so a form value could add a heading or a link with a text of the user's choosing. `escape_markdown` backslash-escapes the inline characters and the line-start markers, passes `Markup` values through unchanged and is exposed as `sth.escape_markdown` for every value taken from task data.

Transport: Graph receives `contentType: "HTML"` and the HTML document (Graph has no alternative part; Outlook derives its own text). SMTP builds `multipart/alternative` with the plain text first and the HTML second; attachments turn it into `multipart/mixed` as before. A `text` body takes exactly the path it took before.

## Consequences

- A service task writes `[Open the offer](https://tenant.sharepoint.com/...)` and the recipient sees a short link. Bare URLs still become links, so an old text body sent as Markdown loses nothing.
- The plain-text part of a Markdown mail shows the backslashes that `escape_markdown` adds, for example `Jens\_Test`. Accepted: the HTML part is what almost every client shows, and the source must be a single string that serves both parts.
- `mock_send_text_mail` patches `send_mail`, which every send goes through, and records `body_format`.
- `markdown-it-py` and `linkify-it-py` become direct dependencies. `markdown-it-py` was already installed through `rich`.
- Rejected: a Python HTML sanitizer (`nh3`, `bleach`). It adds a dependency and a false sense of safety for a body whose author is trusted anyway; the risk sits in interpolated values, which Markdown with HTML disabled and `escape_markdown` handle.
- Open: the engine's notification templates could use the same path to replace their bare URLs with a link text. Left as is to keep this change free of side effects on existing mails.
