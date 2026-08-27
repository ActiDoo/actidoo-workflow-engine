# Operations

This page is for the operator who puts a finished workflow project in front of real users: build the Docker image, run the container, set the backend settings, and connect the identity provider, storage and mail. The mental model behind the components is on [Architecture](architecture.md); how the project itself is built is on [Workflow project](workflow-project.md).

The running example is an expense-approval workflow: an employee submits an expense, small amounts are auto-approved, larger ones go to a finance approver, and the approved expense is stored and recorded for finance. Nothing here is specific to it; the same steps ship any workflow project. The example just keeps the names concrete: package `acme`, workflow `ExpenseApproval`, the finance role `expense-approver`, an `o365` connector that writes approved expenses to an Excel workbook.

## Build the Docker image

A workflow project ships as its own Docker image built `FROM` the engine's [runtime image](glossary.md#runtime-image). The image installs the extension package with `pip` and keeps the engine's start command, so the container behaves like the plain runtime image plus your workflows. The template's `docker/Dockerfile` is minimal:

```dockerfile
ARG BASE_IMAGE=ghcr.io/actidoo/actidoo-workflow-engine:latest
FROM ${BASE_IMAGE}
COPY . /src
RUN pip install /src
```

```
docker build -f docker/Dockerfile -t acme:1.0 .
```

The engine base image is published as `ghcr.io/actidoo/actidoo-workflow-engine:<tag>`. Pin an explicit tag, not `latest`: the tag decides the engine version your workflows run on, and upgrading the engine means changing the tag and rebuilding. The template keeps the tag in `workflow-engine.version`, the Dockerfile build argument `BASE_IMAGE` and the devcontainer compose file in sync (see [Workflow project](workflow-project.md)).

## Run the container

Three variables decide where the application is reachable. The start script refuses to start when one is empty or when `BASE_URL` is not an absolute URL.

| Variable | Default | Meaning |
|---|---|---|
| `BASE_URL` | none, required | Public origin, scheme and host, for example `https://wfe.example.com`. |
| `FRONTEND_PATH` | `/wfe/` | Path of the browser application under `BASE_URL`. |
| `API_PATH` | `/api/` | Path of the API under `BASE_URL`; the backend also uses it as the prefix of all its routes. |

With the defaults the application answers at `https://wfe.example.com/wfe/` and the API at `https://wfe.example.com/api/`. Keep `BASE_URL` to scheme and host and put path prefixes into `FRONTEND_PATH` and `API_PATH`. From the three values the start script derives the frontend base URL (also handed to the backend as `FRONTEND_BASE_URL`, the URL used for links in mails) and the API base URL.

```
docker run -p 8080:8080 \
  -e BASE_URL=https://wfe.example.com \
  -e DB_HOST=... -e DB_USER=... -e DB_PASSWORD=... \
  -e OIDC_DISCOVERY_URL=... -e OIDC_CLIENT_ID=... -e OIDC_CLIENT_SECRET=... \
  -e WORKFLOWS='["ExpenseApproval"]' \
  acme:1.0
```

The `WORKFLOWS` list is what makes `ExpenseApproval` appear in the start list and be startable; a workflow the image ships but the list omits stays installed and invisible. At start the container:

1. Checks `BASE_URL`, `FRONTEND_PATH`, `API_PATH` and derives the base URLs.
2. Renders the runtime assets: writes the base URLs, `ENVIRONMENT_LABEL` and `APP_TITLE` into the browser application, applies branding, and fills the path placeholders in the assets and the nginx config.
3. Starts the backend and nginx under a supervisor that restarts either process when it exits.

The backend then runs its own startup (migrations, storage, extension scan, scheduler) and answers requests only after that finishes. It needs the database from the first step, so start the container after MySQL accepts connections.

Port 8080 is nginx; it serves the browser application and proxies the API. The backend listens on port 8000 inside the container only.

| Request path | nginx does |
|---|---|
| `<API_PATH>…` | proxies to the backend with sanitised forwarded headers |
| `<FRONTEND_PATH>…` | serves the file; unknown paths get `index.html` (SPA routing) |
| `/` | redirects to `<FRONTEND_PATH>` |
| anything else | 404 |

nginx honours `X-Forwarded-For`, `-Proto`, `-Host` and `-Port` only from the networks in `NGINX_REAL_IP_FROM`. Because the login callback URL the engine sends to the IdP is built from these values, a reverse proxy that terminates TLS must sit in a trusted network and forward `X-Forwarded-Proto: https` and the public host. Expense receipts travel inline in the form submit, so a single request can be large; `CLIENT_MAX_BODY_SIZE` (default `256m`) is the ceiling in the container, and the limit of your reverse proxy must be at least as high.

To brand the application, set `BRAND_PRIMARY_COLOR`, `APP_TITLE` and `ENVIRONMENT_LABEL`, and mount a logo at `/srv/frontend.template/branding/logo.svg` and a help page at `/srv/frontend.template/branding/help.<lang>.md`. Mount into the template folder, not `/srv/frontend`: that folder is wiped and re-copied at every start. Help markdown is rendered as raw HTML, so mount only trusted content.

### Run more than one container

Several containers can share one database. Sessions, the scheduler queue, messages and timers live in MySQL, so any container serves any user; one process is elected to schedule the cron jobs and every process works the queue. Migrations run under a database lock, so containers may start in parallel.

:::{warning}
Storage mode `LOCAL` writes attachments into the container's own file system and is **not shared** between containers. The expense receipts are attachments, so run more than one container only with an Azure Blob mode.
:::

There is no dedicated health endpoint. `GET <API_PATH>/version` needs no login, returns JSON and answers only once the backend has finished its startup, so it works as a readiness probe. `GET <FRONTEND_PATH>` is answered by nginx alone and says nothing about the backend.

## Settings

Every backend setting is an environment variable of the same name. The backend reads them once at process start, from these sources, first hit wins:

1. OS environment variables (names are case-insensitive).
2. Dotenv files in the working directory: `.env.defaults`, then the file named by `ENV_FILE` (default `.env`), then `.env.local`; a later file overrides an earlier one, missing files are ignored.
3. Docker secrets: a file named after the setting under `/run/secrets/`, for example `/run/secrets/db_password`.
4. The built-in default from the tables below.

| Value | Rule |
|---|---|
| Lists (`WORKFLOWS`, `CORS_ORIGINS`, `OAUTH_BEARER_ROLE_CLAIM_PATHS`, `EMAIL_OVERRIDE_RECIPIENTS_LIST`, `EMAIL_RECEIVERS_ERRONEOUS_TASKS`) | JSON array, for example `WORKFLOWS='["__ALL__"]'`. A comma-separated string stops the startup. |
| Claim lists (`OIDC_*_CLAIMS`, `OIDC_ROLES_CLAIM_PATHS`) | Plain string, entries separated by commas. |
| Booleans | `1`/`0`, `true`/`false`, `yes`/`no`, `on`/`off`; case-insensitive. |
| Fixed choices (`STORAGE_MODE`, `EMAIL_TRANSPORT`) | Any other value stops the startup. |
| Nested keys | Two underscores separate the levels; only `CONNECTORS__…` uses this. |
| Unknown key in a dotenv file | Stops the startup with a validation error. Unknown OS environment variables are ignored. |
| `${VAR}` inside a dotenv value | Replaced by the OS environment variable `VAR`; empty when `VAR` is unset. |

### General and paths

| Name | Type | Default | Meaning |
|---|---|---|---|
| `FRONTEND_BASE_URL` | string | `http://localhost:3000` | Public URL of the browser application; used for links in mails. The runtime image sets it from `BASE_URL` and `FRONTEND_PATH`. |
| `API_PATH` | string | `/api` | Path prefix of all backend routes; `/` means no prefix. In the runtime image this is the container's `API_PATH`. |
| `LOG_LEVEL` | string | `INFO` | Logging level for the server and the CLI. |
| `SHOW_TEST_WORKFLOWS` | bool | `false` | Registers the engine's bundled demo workflows and demo data models. Development and tests only. |
| `CORS_ORIGINS` | JSON list | `[]` | Allowed CORS origins (credentials allowed). An empty list disables CORS. |
| `PROXY_TRUSTED_NETWORKS` | JSON list of CIDRs | `["127.0.0.0/8","10.0.0.0/8","172.16.0.0/12","192.168.0.0/16"]` | Networks whose `X-Forwarded-*` headers are trusted. The runtime image fixes this to `["127.0.0.1/32"]` (see the runtime-image table). |

The session cookie `wfesess` is fixed by the engine: it is a server-side record, secure, HttpOnly, `SameSite=Lax`, and expires after 14 days. There are no environment settings for it.

### OIDC (browser login)

| Name | Type | Default | Meaning |
|---|---|---|---|
| `OIDC_DISCOVERY_URL` | string | empty | URL of the IdP metadata document (`…/.well-known/openid-configuration`). |
| `OIDC_CLIENT_ID` | string | empty | Client id for the browser login; also replaces `{client_id}` in the role claim paths. |
| `OIDC_CLIENT_SECRET` | string | empty | Client secret of that client. |
| `OIDC_SCOPES` | string | `openid profile email` | Space-separated scopes requested at login. |
| `OIDC_ROLES_CLAIM_PATHS` | claim list | `realm_access.roles,resource_access.{client_id}.roles,resource_access.*.roles,roles,groups,app_roles,appRoles` | Dotted claim paths whose string and list values are collected as the user's roles; `*` matches every key of an object. |
| `OIDC_USERNAME_CLAIMS` | claim list | `preferred_username,name,email,upn` | Claims tried in order for the user name. |
| `OIDC_EMAIL_CLAIMS` | claim list | `email,upn` | Claims tried in order for the e-mail address. |
| `OIDC_FIRST_NAME_CLAIMS` | claim list | `given_name,first_name` | Claims tried in order for the first name. |
| `OIDC_LAST_NAME_CLAIMS` | claim list | `family_name,last_name` | Claims tried in order for the last name. |
| `OIDC_FULL_NAME_CLAIMS` | claim list | `name` | Fallback when no first or last name matched; split at the first space. |
| `OIDC_USER_ID_CLAIMS` | claim list | `sub` | Claims tried in order for the stable IdP user id. |
| `OIDC_TOKEN_REFRESH_SKEW_SECONDS` | int | `60` | The access token is refreshed when it expires within this many seconds. |
| `VALIDATE_AND_PARSE_ACCESS_TOKEN` | bool | `true` | Verify the access token against the IdP's JWKS and merge its claims over the ID-token claims; `false` uses the ID-token claims only. |
| `AUTH_DEBUG_TOKEN_INTROSPECTION` | bool | `false` | The auth fallback page (`<API_PATH>/auth/`) shows the login state and, when logged in, the session claims. Never in production. |
| `AUTH_FALLBACK_REDIRECT` | string | unset | Redirect target of the auth fallback page when `FRONTEND_BASE_URL` is empty. |

### Bearer API (API v1)

| Name | Type | Default | Meaning |
|---|---|---|---|
| `OAUTH_BEARER_TOKEN_ENDPOINT` | string | empty | Token endpoint advertised in the OpenAPI documentation. A discovery URL is resolved to its token endpoint. |
| `OAUTH_BEARER_INTROSPECTION_ENDPOINT` | string | empty | Introspection endpoint used to validate every bearer token. A discovery URL is resolved to its introspection endpoint. |
| `OAUTH_BEARER_CLIENT_ID` | string | empty | Client used to authenticate the introspection call and required audience of the token; the token must carry the client role `wf-api` for it. |
| `OAUTH_BEARER_CLIENT_SECRET` | string | empty | Client secret of that client. |
| `OAUTH_BEARER_ROLE_CLAIM_PATHS` | JSON list | `["resource_access.{client_id}.roles","realm_access.roles","roles","groups","scp","scope"]` | Dotted claim paths tried in order; the first that yields roles wins. `{client_id}` is replaced. |

### Database

| Name | Type | Default | Meaning |
|---|---|---|---|
| `DB_DRIVER` | string | `mysql+pymysql` | Driver part of the database connection URI. |
| `DB_HOST` | string | `mysql` | Database host. |
| `DB_PORT` | int | `3306` | Database port. |
| `DB_USER` | string | `root` | Database user. |
| `DB_PASSWORD` | string | empty | Database password; URL-encoded into the connection URI. |
| `DB_NAME` | string | `app` | Database name. |
| `DB_QUERY` | string | empty | Extra query string appended to the connection URI, for example `charset=utf8mb4`. |
| `DB_ECHO` | bool | `false` | Log every SQL statement; debugging only. |
| `DB_SSL_CA` | string | empty | CA file for TLS to the database; TLS is used only when set. |

### Storage

| Name | Type | Default | Meaning |
|---|---|---|---|
| `STORAGE_MODE` | `LOCAL`, `AZURE_BLOB`, `AZURE_BLOB_TENANT` | `LOCAL` | Storage driver for attachments. |
| `STORAGE_LOCAL_UPLOAD_PATH` | path | `upload_dir` next to the backend | Directory for `LOCAL`; created when missing. |
| `STORAGE_AZURE_ACCOUNT_NAME` | string | unset | Storage account name (both Azure modes). |
| `STORAGE_AZURE_ACCOUNT_KEY` | string | unset | Account key (`AZURE_BLOB`) or service-principal client secret (`AZURE_BLOB_TENANT`). |
| `STORAGE_AZURE_TENANT_ID` | string | unset | Tenant id of the service principal (`AZURE_BLOB_TENANT`). |
| `STORAGE_AZURE_CLIENT_ID` | string | unset | Client id of the service principal (`AZURE_BLOB_TENANT`). |
| `STORAGE_AZURE_OVERRIDE_HOST` / `_PORT` / `_ENDPOINT` | string | unset | Host, port and endpoint suffix of a Blob emulator (`AZURE_BLOB`). |
| `STORAGE_AZURE_OVERRIDE_SECURE` | bool | `true` | Use HTTPS towards the override host. |
| `STORAGE_AZURE_OVERRIDE_PROXY_ENVS` | bool | `false` | Blank `http_proxy`/`https_proxy` while the Azure driver is created, then restore them. |

### Mail

| Name | Type | Default | Meaning |
|---|---|---|---|
| `EMAIL_TRANSPORT` | `GRAPH`, `SMTP` | `GRAPH` | Mail transport: Microsoft Graph or SMTP. |
| `EMAIL_CLIENT_ID` | string | empty | Graph: client id for the client-credentials flow. |
| `EMAIL_CLIENT_SECRET` | string | empty | Graph: client secret. |
| `EMAIL_SUBSCRIPTION_KEY` | string | empty | Graph: sent as query parameter `Subscription-Key` to the token and send endpoints. |
| `EMAIL_TOKEN_ENDPOINT` | string | empty | Graph: token endpoint for the client-credentials flow. |
| `EMAIL_SEND_ENDPOINT` | string | empty | Graph: send endpoint; one request per recipient. |
| `EMAIL_SMTP_HOST` | string | empty | SMTP: server host; required for SMTP. |
| `EMAIL_SMTP_PORT` | int | `25` | SMTP: server port. |
| `EMAIL_SMTP_USERNAME` | string | empty | SMTP: login user; login happens only when user or password is set. |
| `EMAIL_SMTP_PASSWORD` | string | empty | SMTP: login password. |
| `EMAIL_SMTP_USE_TLS` | bool | `false` | SMTP: upgrade the connection with STARTTLS. |
| `EMAIL_SMTP_USE_SSL` | bool | `false` | SMTP: connect with TLS from the start (SMTPS). |
| `EMAIL_FROM_ADDRESS` | string | empty | SMTP: sender address; falls back to `EMAIL_SMTP_USERNAME`. One of the two is required. |
| `EMAIL_SUBJECT_PREFIX` | string | `[WF] ` | Put in front of every subject. |
| `EMAIL_SUBJECT_SUFFIX` | string | empty | Appended to every subject. |
| `EMAIL_OVERRIDE_RECIPIENTS_ENABLE` | bool | `false` | Send every mail to the override list instead of the real recipients; with an empty list no one receives it. |
| `EMAIL_OVERRIDE_RECIPIENTS_LIST` | JSON list | `[]` | Override recipients. A non-empty list overrides even when the enable flag is `false`. |
| `EMAIL_SKIP` | bool | `false` | Log mails instead of sending them. Also the case in tests and while a debugger is attached. |
| `EMAIL_RECEIVERS_ERRONEOUS_TASKS` | JSON list | `[]` | Fixed addresses that get the erroneous-task mail and the daily reminder in `DEFAULT_LOCALE`; they cannot opt out. |
| `EMAIL_ERRONEOUS_TASKS_REMINDER_CRON` | cron | `0 7 * * *` | Schedule of the erroneous-task reminder, in the fixed time zone Europe/Berlin. Empty or invalid disables it. |
| `EMAIL_SIGNATURE` | text | `Best regards, / Workflow Engine` | Plain-text signature appended to every mail; not translated. |

### Locale

| Name | Type | Default | Meaning |
|---|---|---|---|
| `DEFAULT_LOCALE` | locale tag | `en-US` | Locale for users without one of their own, for service users, and for mail recipients without a user record. |

### Workflows

| Name | Type | Default | Meaning |
|---|---|---|---|
| `WORKFLOWS` | JSON list | `[""]` | Names of the workflow directories that are [activated](glossary.md#activated-workflow) (listed and startable). `["__ALL__"]` activates every workflow the providers serve; the default activates none. Read at startup. |

For the example, `WORKFLOWS='["ExpenseApproval"]'` activates the expense workflow and nothing else. Adding a second workflow later means adding its name to this list and restarting.

### Connectors

| Name | Type | Default | Meaning |
|---|---|---|---|
| `CONNECTORS__<TYPE>__<INSTANCE>__<KEY>` | string per key | none | One config key of a [connector instance](glossary.md#connector-instance), for example `CONNECTORS__JIRA__MAIN__URL`. Type and instance names are lower-cased. Every instance is checked against the type's config schema at startup (warnings only) and again when a service function opens it. |

The `post_expense` service task opens the `o365` connector instance named `finance`, so its config keys are set as `CONNECTORS__O365__FINANCE__<KEY>` (the exact keys come from the connector type's config schema; see [Connectors](connectors.md)).

### Runtime-image variables

These are read by the container's start script when it renders the browser application and the nginx config, not by the backend settings. `BASE_URL`, `FRONTEND_PATH` and `API_PATH` may also be given as build arguments and are then stored in the image.

| Name | Default | Meaning |
|---|---|---|
| `BASE_URL` | none, required | Absolute public URL of the deployment. The container does not start without it. |
| `FRONTEND_PATH` | `/wfe/` | Path of the browser application under `BASE_URL`. |
| `API_PATH` | `/api/` | Path of the backend under `BASE_URL`; also read by the backend as its route prefix. |
| `RENDER_RUNTIME_AT_BUILD` | `false` | Build argument: render the assets during the image build so the container can run read-only. |
| `RENDER_RUNTIME_WRITE` | unset | Forces (`1`, `true`) or skips (`0`, `false`) rendering at start. Unset renders unless the image was baked. |
| `NGINX_REAL_IP_FROM` | `10.0.0.0/8 172.16.0.0/12 192.168.0.0/16` | Comma- or space-separated CIDRs of proxies whose `X-Forwarded-*` headers nginx honours. When none is left, forwarded headers are ignored. |
| `CLIENT_MAX_BODY_SIZE` | `256m` | nginx request body limit. Attachments travel inline, so keep it large. |
| `BRAND_PRIMARY_COLOR` | unset | Six-digit hex colour that overrides the brand colour; an invalid value is ignored with a warning. |
| `ENVIRONMENT_LABEL` | unset | Short label such as `STAGING`, shown in red next to the start button. |
| `APP_TITLE` | unset | Title shown next to the logo; unset shows `Workflow Engine`. |

`PROXY_TRUSTED_NETWORKS` is fixed by the container to `["127.0.0.1/32"]`, so a value you set on the backend is overwritten; only the container-local nginx is trusted for forwarded headers, and nginx in turn trusts your proxy through `NGINX_REAL_IP_FROM`.

## Connect the identity provider

The engine mirrors users and roles in its own database, but the IdP is the source of truth: it logs users in through an [IdP](glossary.md#idp) (OpenID Connect) and refreshes the mirrored record and its roles from the token claims on every login. Nobody is created or granted a role in the engine itself. For the expense project you create these roles in the IdP and assign them:

| Role | Who gets it | Effect |
|---|---|---|
| `wf-user` | every employee; make it a default role | may open the application and call the BFF; without it a logged-in user sees "Missing authentication" |
| `wf-admin` | global administrators | see and administrate all workflows, instances, tasks and users |
| `wf-api` | the service account of a machine client | may call [API v1](glossary.md#api-v1) with a bearer token; a client role of the client in `OAUTH_BEARER_CLIENT_ID` |

On top of these three application roles, the expense workflow needs the free names its authors chose: the lane role `expense-approver` (members of the Finance lane who approve or reject), and the process-owner role `expense-admin` (the `wf-owner`, who administrates the expense instances and gets its erroneous-task reminders). These are ordinary IdP roles too — the engine only reads them from the token; it is the workflow's BPMN that gives them meaning. The Employee lane is the initiator lane and needs no role of its own, since anyone with `wf-user` may start an expense and becomes its initiator.

Create a confidential client with the authorization code flow and PKCE for the browser login, and set `OIDC_DISCOVERY_URL`, `OIDC_CLIENT_ID` and `OIDC_CLIENT_SECRET`. The engine derives the redirect URIs from the incoming request, so register these two (with the scheme and host of your deployment):

- Login callback: `<BASE_URL><API_PATH>auth/login_callback`
- Post-logout redirect: `<BASE_URL><API_PATH>auth/logout_callback`

Because the URIs come from the request, the reverse proxy must forward scheme and host correctly, or the IdP rejects the login with "invalid redirect URI".

After login the engine merges the ID-token claims with the access-token claims and reads the user fields and roles from them. The `OIDC_*_CLAIMS` and `OIDC_ROLES_CLAIM_PATHS` defaults fit Keycloak realm and client roles as well as plain `roles`/`groups` claims; adjust them when your token looks different. Every user needs an e-mail claim, because the engine stores users by e-mail and mails go to that address — the approval notification to `expense-approver` members, for example. When `VALIDATE_AND_PARSE_ACCESS_TOKEN` is `true` (the default) the access token must be a JWT signed by the IdP whose `aud` contains `OIDC_CLIENT_ID`; add an audience mapper when your IdP issues a different audience.

For machine submissions — say a travel-booking system that posts expenses without a person clicking through the form — external systems obtain a [bearer token](glossary.md#bearer-token) with the client-credentials grant and call `POST <API_PATH>/wfe/api/v1/send_message`. Point `OAUTH_BEARER_INTROSPECTION_ENDPOINT` (and `OAUTH_BEARER_TOKEN_ENDPOINT`) at the IdP, set `OAUTH_BEARER_CLIENT_ID` and `OAUTH_BEARER_CLIENT_SECRET`, create `wf-api` as a client role of that client and grant it to each machine client's service account. A missing or invalid token gives 401; a token without `wf-api` gives 403. The caller is represented as a [service user](glossary.md#service-user) without roles, so a message can only start a workflow whose initiator lane does not restrict starting to roles — which fits the expense workflow, since its Employee lane lets anyone start.

## Configure storage

Every expense carries a receipt, and receipts are [attachments](glossary.md#attachment). The engine stores attachments through one storage backend, chosen by `STORAGE_MODE`. In every mode it uses and creates one container named `attachment`. Wrong Azure credentials stop the backend at startup, when it looks the container up.

| `STORAGE_MODE` | Settings | Notes |
|---|---|---|
| `LOCAL` (default) | `STORAGE_LOCAL_UPLOAD_PATH` | A directory in the container's file system. Point it at a mounted volume, otherwise the files disappear with the container. Not shared between containers. |
| `AZURE_BLOB` | `STORAGE_AZURE_ACCOUNT_NAME`, `STORAGE_AZURE_ACCOUNT_KEY` | Storage account with an account key. |
| `AZURE_BLOB_TENANT` | `STORAGE_AZURE_ACCOUNT_NAME`, `STORAGE_AZURE_ACCOUNT_KEY` (the client secret), `STORAGE_AZURE_TENANT_ID`, `STORAGE_AZURE_CLIENT_ID` | Storage account with a service principal (Entra ID). |

`LOCAL` is fine for a single-container evaluation, but the moment finance runs two containers behind a load balancer, a receipt uploaded on one is invisible on the other — use an Azure Blob mode for any real deployment. When the container runs behind an outbound proxy that must not be used for the storage account, set `STORAGE_AZURE_OVERRIDE_PROXY_ENVS=true`.

## Mail and observability

The engine mails approvers when a task lands in their lane and mails admins when a task errors, so mail must work before you go live. Mail transport is `GRAPH` (Microsoft Graph, the default) or `SMTP`; any other value fails at startup. All engine mails are plain text. Graph fetches a client-credentials token and sends one request per recipient; SMTP sends one message with all recipients in `To`. `EMAIL_SUBJECT_PREFIX` (default `[WF] `) is put in front of every subject.

On test and staging systems, two switches sit in front of every mail, including the notification `post_expense` sends to finance:

| When | Then |
|---|---|
| `EMAIL_SKIP=true` | the mail is written to the log as a text block and not sent; also the case under a debugger and in tests |
| `EMAIL_OVERRIDE_RECIPIENTS_LIST` is a non-empty JSON list | every mail goes to those addresses instead of the real recipients |
| neither | the mail goes to its real recipients |

Set these on staging so a test run does not mail real users. The container log is the backend's output; nginx output is discarded. Every line is `<timestamp>\t[<LEVEL>]\t<message>`; `LOG_LEVEL` (default `INFO`) sets the level. Every request carries a correlation id: the engine reuses the header `X-Request-ID` when the caller or your proxy sends one and generates one otherwise, and returns it in the response header of the same name. The log lines do not include the id, so keep it on the proxy side to match a browser request with a proxy log entry.

Set `SENTRY_DSN` to report unhandled exceptions to Sentry; `SENTRY_TRACES_SAMPLE_RATE` (default `1.0`) controls performance tracing and should be lowered in production. `GET <API_PATH>/version` returns the build's commit from the environment variable `CI_COMMIT_SHA` (`-` when unset); set it in your image build to make the commit visible.

When a service function raises — say `post_expense` cannot reach O365 — its task becomes an [erroneous task](glossary.md#erroneous-task): the branch stops, other branches continue, the workflow owners (`expense-admin`) get a mail at once, and admins and owners get the daily reminder until it is fixed. Members of `wf-admin` and the workflow owners find these under Admin, "Erroneous Running Tasks". Opening the task shows the recorded stack trace, lets you edit the task data, and offers "Try again", which reruns the task; on success the workflow instance continues. A changed service function is picked up at the next run without redeploying instances, because only BPMN and forms are frozen into an instance.

## Related

- [Workflow project](workflow-project.md) — create the extension and its image
- [Architecture](architecture.md) — the components and the startup sequence
- [ADR 002](adr/adr_002_extension_architecture.md) — why a deployment is an image built on the runtime image
