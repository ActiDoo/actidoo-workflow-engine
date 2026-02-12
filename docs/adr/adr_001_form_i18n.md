# ADR 001: Internationalization of Process Forms

**Status:** Accepted
**Date:** 2025-05-09

## Context
- Our processes include multiple JSON-based forms, which exist in different files but contain overlapping texts (e.g., submission and review of the same fields).
- The client expects already localized schemas from the backend.
- The business department maintains plain text in the JSON forms, translators work with exported templates.

## Decision Drivers

1. **Reusability**
   Texts should not be duplicated across each form file but should exist centrally per process.
2. **Change Detection**
   Only truly modified texts should trigger translation review (e.g., typo fixes), not all strings.
3. **Fallback Mechanism**
   If a translation is missing, the original text should be shown.
4. **Server-side Translation**
   The API delivers localized JSON (+ UI schema).

### Client-side Translation Considerations

Before committing to the final decision, we also discussed the trade-off between doing translation on the server versus the client side.
We discussed whether a client-side implementation was also feasible.
However, server-side translation was ultimately preferred for the following reasons:
- We need i18n logic on the server anyway (e.g., for string extraction, mail rendering, PDF generation).
- If translation logic is handled consistently in the backend, it ensures output consistency across forms, emails, and documents - regardless of frontend technology.
- Client-side support and fallback handling are unclear and may be incomplete.
- Maintaining all localization logic in the backend allows the process to remain encapsulated, which aligns with our architecture where process execution is handled entirely on the server side.

## Considered Options
- **Plain JSON Key-Value**
  - Pros: Simple format, native JSON usage.
  - Cons: No standard change detection, no built-in fallback, no fuzzy marking.
- **gettext (.pot/.po/.mo)**
  - Pros: Established template and merge mechanism, automatic fuzzy/obsolete marking, fallback to msgid.
  - Cons: Requires a compilation step, some learning curve for developers.

## Decision
We adopt the gettext format:
1. **Extraction:** All texts of a process are collected from JSON forms into a central `<Process>.pot` file.
2. **Translation:** Translators maintain one `<Process>.po` per locale. Changed entries are marked as "fuzzy", removed ones as "obsolete".
3. **Compilation:** CI/CD compiles all `.po` -> `.mo` using Babel. `.mo` files are not committed to the repository.
4. **Runtime:** The backend loads `<Process>.mo` based on the given locale and translates JSON schema and UI schema before sending them to the client.
5. **REST Interfaces:** Translations are performed exclusively on the server side.

The necessary technical components — especially the extraction and runtime translation — must still be implemented or completed within the project.

## Consequences
- **Centralization:** All texts of a process reside in one file -> encapsulated per process, no duplicated translation work across forms.
- **Change Review:** Only truly changed texts require translator review.
- **Fallback:** Missing translations fall back to the original text.
- **Locale Routing:** API endpoints must accept a locale parameter and forward it to the translation function.

## Open Questions
1. **Language codes vs. Locales**
   Should we support only language codes (`de`, `en`) or full locales (`de-CH`, `en-US`)?
2. **External options files / APIs**
   How do we translate dynamic dropdown options (CSV, REST)?
3. **How do we translate e.g. emails or generated PDF files?**
4. **Language detection & user profile**
   Should the locale be initialized from `Accept-Language`, persisted in the user profile, and be changeable via the UI? In some cases, the user's language is needed outside of a request context!

## Follow-up Considerations
1. While we do not have any requirement for locales instead of language codes, usage of locales might be beneficial for certain dialects e.g. in China.
2. Most external APIs support multi-language, therefore we need access to the user's preferred language inside the ServiceTaskHelper. When using CSVs for the dropdowns we require translated CSVs.
3. Mako (used for mail templates) already has gettext integration. Consider enforcing usage of mako templates instead of allowing the `sth.send_mail` function directly.
4. From 2. and 3. we get the requirement to persist the preferred language of a user in his profile. When it is not set, we default to `Accept-Language` header. The language should be selectable from within the frontend.

## Resolved Open Questions
1. **Language Codes vs. Locales**
   We support both. A full locale (e.g., `de-CH`) is stored for each user. When looking up translations:

   * First, attempt to find a locale-specific match.
   * Fallback to the base language (e.g., `de`).

2. **Dynamic Dropdowns (CSV / APIs)**

   * The implementation is up to the process. We provide the user's preferred language in the service task.

3. **Email & PDF Translation**

   * The implementation is up to the process. We provide the user's preferred language in the service task. Future work might include integrating the Babel-pipeline with mako templates or defining a filename pattern for template-translation.

4. **Language Detection & User Profile**

   * The user's preferred locale is stored as an attribute of the `User` object.
   * On user creation, the locale is initialized from the `Accept-Language` HTTP header.
   * The frontend must allow users to change their language preference explicitly.
