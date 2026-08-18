# App tests

Tests that move between pages: real page components on a real store (reducers and sagas)
behind a memory router, with the HTTP layer replaced by an in-memory fake BFF. Use them
for behaviour that only shows up across pages - a change made on one page has to be
visible on another, data must be reloaded when a page is entered again, and so on.
Anything inside a single form belongs to `../workflows/`. Like those, they run in Chromium
(Vitest browser mode, project `browser`, see `../README.md`).

- `support/renderApp.tsx` mounts the given routes like `main.tsx` does (i18n, store,
  theme, router) minus auth and shell, and returns `navigate()` for page changes.
- `support/fakeBff.ts` holds a small world of users, instances and tasks, applies admin
  changes to it and answers reads from the current state. It throws for endpoints it does
  not model, so a page that starts calling something new fails loudly instead of silently
  getting `undefined`.

A test wires the fake in with the `vi.mock` line for `FetchService` (see an existing test;
it has to live in the test file because `vi.mock` is hoisted) and
`useFakeBackend(bff.handle)` in `beforeEach`. Pages are driven with `page.getByRole(...)`
etc. from `vitest/browser`; page changes go through `navigate()`.
