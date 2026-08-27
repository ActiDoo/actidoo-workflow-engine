# ADR 011: Client Contract Version for the BFF

**Status:** Implemented
**Date:** 2026-08-27

## Context

The BFF is unversioned: any browser tab that has the application loaded may call it, however long ago it fetched its bundle. A deploy does not reach those tabs — the bundle keeps running until the user reloads, which may be hours later or never.

That was tolerable while every change was additive. Row identity ([ADR 010](adr_010_dynamic_list_row_identity.md)) ended it. A bundle from before that change submits dynamic lists without row ids, and the engine cannot always tell the difference between "this client does not speak row identity" and "these rows are new". Where the stored rows already carry ids the submission is rejected — safe, but the user sees an error on a list they cannot repair. Where they do not, the submission falls back to the index merge, and deleting a row in the middle moves backend-owned values onto its neighbours. That is silent, and it is exactly the corruption ADR 010 removed.

The general shape of the problem outlives this one change: whenever the data contract between bundle and engine changes, a tab that survived the deploy is a client speaking a contract nobody serves any more.

## Decision Drivers

1. A client that may corrupt data must be stopped before it writes, not diagnosed afterwards.
2. The engine must not have to guess a client's capabilities from the shape of its payload.
3. A user must learn that their tab is stale without having to lose work first.
4. An unreachable or briefly failing backend must never lock anybody out.

## Decision

**The bundle declares its contract version on every BFF request, and the engine serves only an exact match.** The version is a single number, carried in a request header and hand-raised whenever a change makes an already-loaded bundle unsafe. Anything else - a lower version, a higher one, or no version at all - is refused for the whole BFF surface, with a distinct status that means "reload", not "log in".

The comparison is equality rather than a minimum, so a bundle *newer* than the engine is refused too. That is the rollback case: after the engine is rolled back, the browsers still hold the newer bundle, and a minimum check would wave it through to speak a contract the engine no longer knows.

Authentication, the machine-to-machine API and the version endpoint itself stay ungated. A blocked client has to remain able to find out that it is blocked, and why.

**The client also asks, rather than only being told.** The engine publishes its contract version on an unauthenticated endpoint, and a running tab polls it, so a stale tab is gated before the user invests more work into a form that can no longer be submitted. A failed request proves nothing about the contract and is ignored. Once a client has established that it is stale it stays gated until it is reloaded: during a rolling deploy a poll can reach old and new instances in turn, and a gate that reopens is worse than one that asks for a reload once.

## Considered Alternatives

- **Version the BFF routes and serve both contracts** — the honest way to keep old tabs working, but it doubles the surface that has to be written, tested and reasoned about for every breaking change, in order to keep serving clients whose user only has to press reload.
- **Infer the client from its payload** — the row-id case shows why this fails: the same payload can mean "old client" or "new rows", and the engine has to guess. Guessing wrong is the silent corruption this decision exists to prevent.
- **Derive the version from the build number** — couples an operational identifier to a data-contract guarantee. Every rebuild would then be a contract change, and the number that decides whether data is safe would be set by the pipeline rather than by the author of the change.

## Consequences

- Bumping the version deliberately locks out every tab that is still open. That is the point, and it is the cost: a breaking deploy produces a wave of users who have to reload.
