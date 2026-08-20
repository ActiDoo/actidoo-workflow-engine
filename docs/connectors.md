# Connectors

This page is for extension developers who connect workflows to an external system (a cloud spreadsheet, an ERP, a data warehouse) and for operators who configure those connections per deployment. A [connector](glossary.md#connector) is code plus configuration: an extension registers a connector type, a deployment configures instances of it, and a service function opens a connection at run time. The engine ships no connector types of its own.

This handbook illustrates everything with one running example, an expense-approval workflow: an employee submits an expense, small amounts are auto-approved, and larger ones go to a finance approver. Its last step is a service task `post_expense` that, once an expense is approved, records it for the finance team as a new row in a shared Excel workbook in Microsoft 365. Reaching that workbook (the Excel API in Microsoft 365) from workflow code is exactly what a connector is for, so O365 is this page's illustration throughout.

## Type and instance

A connector type is code; a connector instance is configuration. They are joined only when workflow code asks for a connection. For O365 the type is the reusable code that talks to the Excel API; the instance `finance` points to the one workbook rows are appended to.

| | Connector type | Connector instance |
|---|---|---|
| Who provides it | The extension, in Python | The deployment, in env vars |
| Consists of | A name, a config schema and a factory | Values for the schema fields, under a type and instance name |
| How many | One per name across the engine and all extensions | Any number per type, for example one per tenant |

Splitting the two keeps credentials out of code and lets one type serve several systems of the same kind. See [ADR 003](adr/adr_003_connector_registry.md).

## Register a connector type

Write a config schema as a Pydantic model with one field per configuration value, using lower-case field names. Values arrive from environment variables and their names are lower-cased on the way in, so a field `clientId` would never receive a value.

Write a factory that takes a validated config object and returns a context manager whose value is the connection handle (a client object). Decorate it with `@register_connector_type`, using a lower-case type name. The engine never looks inside the handle; the factory decides how the connection opens and closes.

```python
class O365Config(BaseModel):
    tenant_id: str
    client_id: str
    client_secret: str

@register_connector_type(name="o365", config_schema=O365Config)
@contextlib.contextmanager
def o365_connector(config: O365Config):
    ...  # yield the client, close it when the with-block ends
```

The module must sit in the scanned package. The decorator registers at import time and again during the [Venusian scan](glossary.md#venusian-scan).

| When | Then |
|---|---|
| The name is new, or registered again with the same factory | Registered (the duplicate is ignored) |
| The same name is registered with a different factory | Registration fails; during the scan the engine does not start |

## Configure an instance

A deployment sets each instance with one variable per field. The double underscore separates the levels:

```
CONNECTORS__O365__FINANCE__CLIENT_ID=00000000-0000-0000-0000-000000000000
```

This sets the field `client_id` of the instance `finance` of type `o365`. Add one variable per further field — `TENANT_ID`, `CLIENT_SECRET` — and repeat for each instance; several instances of one type are allowed, for example a second workbook for another department. Type, instance and field names all arrive lower-cased. The whole map can also be given as one JSON value in `CONNECTORS`, and the variables can live in the dotenv files (see [operations](operations.md)).

At startup, after the scan, the engine checks every configured instance against its type's schema and writes a warning per problem: an unknown type, an instance that is not a group of fields, or values the schema rejects. None of these stop the engine; the check only surfaces typos early. The binding decision is made at use time.

## Use it from workflow code

Workflow code never imports a connector type. A [service function](glossary.md#service-function), options function or validation function asks its [task helper](glossary.md#task-helper) for a connection by type and instance name and uses it in a `with` block. All three helpers (`sth`, `oth`, `vth`) offer the same call, so `post_expense` reaches the finance workbook like this:

```python
with sth.get_connector("o365", "finance") as o365:
    ...
```

Resolution is lazy and runs on every call: look up the type, read the instance configuration, validate it against the schema, then call the factory. The engine does not cache or pool connections.

| When | Then |
|---|---|
| Type registered, instance configured, config valid | The factory runs; the `with` block receives the handle |
| Type not registered | The call fails, listing the registered types |
| Instance not configured | The call fails, listing the configured instances of the type |
| Config rejected by the schema | The call fails with the schema's validation error |

In a service function the error makes the service task an [erroneous task](glossary.md#erroneous-task) that an admin retries once the configuration is fixed. If the `finance` instance is missing a secret, the expense is already stored and only the workbook row waits for the fix and retry. Because the check happens at use time, a workflow that never touches a misconfigured instance keeps working. Pass the instance name through task data rather than hard-coding it when a deployment has several instances.

## Mock it in tests

Tests do not need a real external system. In `conftest.py`, at module scope, declare each instance your tests touch — for the expense flow that is the `finance` workbook:

```python
mock_o365_finance = mock_connector_instance(
    "o365", "finance",
    defaults={"add_row": {"index": 42}},
)
```

The call returns a pytest fixture; request it in a test to get the mock and assert the calls made on it — for example that `post_expense` appended one row. With at least one declaration, every lookup from workflow code returns the mock instead of calling the factory; a lookup of an undeclared pair fails with the same "instance not found" error as in production, so a forgotten mock surfaces at once. Without declarations the real resolution runs. Declaring the same pair twice fails.

## Related

- [Workflows](workflows.md) — the `post_expense` service function that calls this connector
- [Operations](operations.md) — where settings and dotenv files are loaded from
- [Data models](data-models.md) — the other resource a service function reaches through the task helper
- [ADR 003: Connector registry](adr/adr_003_connector_registry.md)
