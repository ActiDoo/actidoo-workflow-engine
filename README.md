# ActiDoo Workflow Engine

A workflow engine for the processes an organisation runs every day: an
expense that needs approval, a new employee to be onboarded, a contract to be
reviewed. You draw the process as a BPMN diagram and design the forms people
fill in. The engine takes it from there: it shows each task to the right
person, collects their input, runs your own code between the steps, sends
mails and keeps track of every case.

The engine is the platform; your processes are a separate package on top of it.
That way you update the engine and your processes independently.

![The first task of the expense-approval example](docs/img/form-enter-expense.png)

## Why this engine

- **One package.** Diagrams, forms, Python code, translations and tests live
  together, versioned in git and shipped as one Docker image.
- **Plain Python between the steps.** No workers, no job queue. A failed step
  waits for an administrator to fix the data and run it again.
- **People built in.** Lanes, roles from your identity provider, delegation,
  mails. Not something you build around the engine.
- **Data that outlives the process.** An approved expense stays as a record,
  with its own pages and actions that start the next workflow from it.
- **Small to run.** One image, one database, one identity provider.

## Getting started

Start with the docs: <https://actidoo.github.io/actidoo-workflow-engine/>

- [Architecture](docs/architecture.md) is the mental model: which parts exist
  and where state lives.
- [Workflow project](docs/workflow-project.md) takes you from the template in
  `examples/workflow-extension-template` to the first task in the browser.
- [Workflows](docs/workflows.md) covers the process model, forms, service
  tasks, messages, timers, translations and tests.
- [Operations](docs/operations.md) covers the image, deployment and settings.

The engine image is published as
`ghcr.io/actidoo/actidoo-workflow-engine:<tag>`. Pin a tag; the tag is the
engine version your workflows run on. Releases are listed in
[CHANGELOG.md](CHANGELOG.md).

## Working on the engine

The repository ships a devcontainer with MySQL and Keycloak. Open it in VS
Code, then:

```
cd backend && uvicorn actidoo_wfe.fastapi:app --reload
cd frontend && yarn wfe:dev
```

The app answers on <http://localhost:3500/wfe/>. Backend tests run with
`pytest` in `backend/`, frontend tests with `yarn test` in `frontend/`.

Architecture decisions are recorded in [docs/adr](docs/adr/index.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Pull requests need a signed CLA; the
bot on the PR explains how.

## License

Apache License 2.0, see [LICENSE](LICENSE). The ActiDoo name and logo are not
covered by the license, see [TRADEMARKS.md](TRADEMARKS.md). The licenses of
the bundled third-party software are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
