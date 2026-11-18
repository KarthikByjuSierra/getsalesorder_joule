# Specification: sales-order-retrieval-agent

> **Guidelines**: Read all applicable guidelines before executing ANY tasks below:
> - [guidelines.md](../guidelines.md) — Universal execution rules
> - [guidelines-agent.md](../guidelines-agent.md) — Universal agent patterns
> - [guidelines-agent-python.md](../guidelines-agent-python.md) — Python implementation details
> - [guidelines-agent-skills.md](../guidelines-agent-skills.md) — Runtime skills patterns
> - [guidelines-agent-mcp.md](../guidelines-agent-mcp.md) — MCP integration patterns

---

## Data Dependencies

No Data Product ORD IDs. All data is sourced from SAP S/4HANA On-Premise via the Sales Order OData API.

**API in scope:**
- API Name: Sales Order (A2X)
- API ORD ID: `sap.s4:apiResource:API_SALES_ORDER_SRV:v1`
- Spec file: `specification/sales-order-retrieval-agent/api-specs/API_SALES_ORDER_SRV.edmx`
- BTP destination: `s43`

**MCP tool scope:**
```
MCP API: sap.s4:apiResource:API_SALES_ORDER_SRV:v1
MCP tool scope: read-only
Resources in scope: A_SalesOrder, A_SalesOrderItem, A_SalesOrderScheduleLine, A_SalesOrderPartner
```

---

## Basic Setup

- [x] Read `product-requirements-document.md` and `intent.md` before starting any task
- [x] Bootstrap agent code in `assets/sales-order-retrieval-agent/` using the `sap-agent-bootstrap` instructions from the agent skill (invoke from inside `assets/sales-order-retrieval-agent/`, using copy commands — do NOT create files manually)
- [x] Install dependencies, validate the agent starts and responds at `/.well-known/agent.json`

---

## Runtime Skills

> Read [guidelines-agent-skills.md](../guidelines-agent-skills.md) before deciding.

The agent handles straightforward OData lookups — no complex multi-step workflows or domain-specific compliance rules require a dedicated runtime skill. No runtime skills needed for this asset.

---

## Project-Specific Tasks

### System Prompt Configuration

- [x] Open `assets/sales-order-retrieval-agent/app/agent.py` and configure the agent system prompt with the following instructions:

  ```
  You are a Sales Order Retrieval Assistant for SAP S/4HANA.

  Your job is to help users retrieve complete sales order information.
  Users may provide:
  - A sales order number (e.g. "Get me sales order 1234567")
  - Search attributes such as customer name, date range, or order status

  For each retrieval, always return:
  1. Order header: sales order number, order date, order status, sold-to customer, net value
  2. Line items: item number, material description, ordered quantity, unit of measure, net price
  3. Delivery details: requested delivery date, shipping status, delivery block (if any)
  4. Billing status: billing status and invoice reference (where available)

  IMPORTANT: You MUST use tools to retrieve live data. Never fabricate, guess, or invent data.
  Relay tool errors verbatim without adding suggestions or workarounds.

  When calling tools that support pagination, always set the page size parameter (top) to a
  maximum of 100 items to prevent context overflow. Inform the user when this limit is applied.

  If a tool returns an error, report the error message exactly as received.
  Do not suggest workarounds or alternative approaches unless asked.

  When a sales order number is provided, query by exact order number.
  When search attributes are provided, filter using the available OData filter parameters.
  Always use the BTP destination 's43' for connectivity — this is configured at the platform level.
  ```

### Sales Order Header Retrieval

- [x] Implement task: retrieve sales order header by sales order number
  - Use the MCP tool corresponding to the `A_SalesOrder` entity set
  - Required fields: `SalesOrder`, `SalesOrderDate`, `SalesOrderType`, `SoldToParty`, `TotalNetAmount`, `TransactionCurrency`, `OverallSDProcessStatus`, `OverallDeliveryStatus`, `OverallBillingStatus`
  - If the order does not exist, return a clear message: "Sales order {number} was not found."

- [x] Implement task: search sales orders by attributes (customer, date range, status)
  - Use the MCP tool corresponding to the `A_SalesOrder` entity set with OData `$filter`
  - Supported filter attributes: `SoldToParty` (customer), `SalesOrderDate` (ge/le for date range), `OverallSDProcessStatus` (order status)
  - Return a summary list (order number, customer, date, status, total value) for each matching order
  - Limit results to a maximum of 100 items using `$top`

### Sales Order Line Items Retrieval

- [x] Implement task: retrieve line items for a sales order
  - Use the MCP tool corresponding to the `A_SalesOrderItem` entity set
  - Filter by `SalesOrder` key
  - Required fields: `SalesOrderItem`, `Material`, `SalesOrderItemText`, `RequestedQuantity`, `RequestedQuantityUnit`, `NetAmount`, `TransactionCurrency`
  - If no items are found, inform the user clearly

### Delivery Details Retrieval

- [x] Implement task: retrieve delivery schedule line details for a sales order
  - Use the MCP tool corresponding to the `A_SalesOrderScheduleLine` entity set
  - Filter by `SalesOrder` key
  - Required fields: `SalesOrder`, `SalesOrderItem`, `ScheduleLine`, `RequestedDeliveryDate`, `ConfirmedDeliveryDate`, `ScheduleLineOrderQuantity`
  - Also check `DeliveryBlockReason` on the header if available
  - If no schedule lines are found, include a note that delivery details are unavailable

### Billing Status Retrieval

- [x] Implement task: retrieve billing status for a sales order
  - Use `OverallBillingStatus` from the `A_SalesOrder` header entity (already retrieved in header step)
  - Translate status codes to human-readable labels:
    - `A` → "Not yet invoiced"
    - `B` → "Partially invoiced"
    - `C` → "Fully invoiced"
    - `D` → "Invoice cancelled"
  - If billing details require an expanded navigation property (e.g. `to_Item/to_BillingPlan`), use `$expand` in the header query

### Response Formatting

- [x] Implement response formatting: combine header, line items, delivery, and billing data into a single structured, human-readable summary
  - Format as a clear text summary with labeled sections:
    - **Order Header** — key order-level attributes
    - **Line Items** — table or list of items
    - **Delivery Details** — delivery dates and status
    - **Billing Status** — billing stage and invoice reference
  - Avoid raw OData JSON in user-facing responses
  - When presenting multiple matching orders (search result), use a compact list format

---

## Business Instrumentation

- [x] Implement the following milestones with structured logging and OpenTelemetry spans in `assets/sales-order-retrieval-agent/app/agent.py`. Extract business logic from `stream()` into a plain async helper to avoid `GeneratorExit` context errors. See [guidelines-agent-python.md](../guidelines-agent-python.md) for Python-specific implementation.

  | ID | Milestone | Log on achievement | Log on miss |
  |----|-----------|-------------------|-------------|
  | M1 | User query received | `M1.achieved: user query received and parsed — order_number={value} or search_attributes={value}` | `M1.missed: unable to parse sales order query from user input` |
  | M2 | API call executed | `M2.achieved: OData API call executed successfully — endpoint=API_SALES_ORDER_SRV destination=s43` | `M2.missed: OData API call failed — destination=s43 error={message}` |
  | M3 | Header data retrieved | `M3.achieved: order header retrieved — sales_order={value} customer={value} status={value}` | `M3.missed: order header not found or empty — sales_order={value}` |
  | M4 | Line items retrieved | `M4.achieved: line items retrieved — sales_order={value} item_count={value}` | `M4.missed: no line items returned — sales_order={value}` |
  | M5 | Delivery & billing details retrieved | `M5.achieved: delivery and billing details retrieved — sales_order={value}` | `M5.missed: delivery or billing details unavailable — sales_order={value}` |
  | M6 | Response presented | `M6.achieved: order summary presented to user — sales_order={value}` | `M6.missed: response could not be delivered — sales_order={value}` |

- [x] Verify `bootstrap(app)` is called after `app = server.build()` in `main.py`

---

## MCP Tool Integration

> Read [guidelines-agent-mcp.md](../guidelines-agent-mcp.md) for complete MCP integration patterns.
> This asset uses Path A (OData API spec file — no existing MCP server).

- [x] Confirm `specification/sales-order-retrieval-agent/api-specs/API_SALES_ORDER_SRV.edmx` exists and is non-empty
- [x] Invoke the `mcp-translation-file` skill to generate the MCP translation file from `specification/sales-order-retrieval-agent/api-specs/API_SALES_ORDER_SRV.edmx`
  - API ORD ID: `sap.s4:apiResource:API_SALES_ORDER_SRV:v1`
  - API type: `edmx`
  - Scope hint: read-only tools for `A_SalesOrder`, `A_SalesOrderItem`, `A_SalesOrderScheduleLine`, `A_SalesOrderPartner`
  - Output: `specification/sales-order-retrieval-agent/mcps/API_SALES_ORDER_SRV/`
- [x] Invoke the `setup-solution` skill to create/register the MCP server asset for the generated translation file
- [x] After `setup-solution` completes, read the generated MCP server `asset.yaml` and extract the exact `ordId` value
- [x] Wire MCP tool loading in `assets/sales-order-retrieval-agent/app/agent.py` using `get_mcp_tools()` from `mcp_providers.agw`. No direct HTTP clients.
- [x] Add the MCP server as a dependency in `assets/sales-order-retrieval-agent/asset.yaml` under `requires`
- [x] Generate `mcp-mock.json` using the `mcp-mock-config` skill (required before tests can run)

---

## Testing

> See [guidelines-agent-python.md](../guidelines-agent-python.md) for Python testing setup and patterns.

- [x] `conftest.py` sets only `IBD_TESTING=true`
- [x] Write unit tests in `assets/sales-order-retrieval-agent/tests/`:
  - `test_get_sales_order_header.py` — retrieval by order number, valid and not-found cases
  - `test_search_sales_orders.py` — search by customer, date range, and status filters
  - `test_get_sales_order_items.py` — line item retrieval, empty result case
  - `test_get_delivery_details.py` — schedule line retrieval, no schedule lines case
  - `test_get_billing_status.py` — billing status translation for all status codes (A/B/C/D)
- [x] Write one integration test: end-to-end agent flow with a full order query, using mocked LLM and mocked MCP tool responses (must run offline)
- [x] Run `pytest` from `assets/sales-order-retrieval-agent/` (no args) — coverage 79% (threshold met)
- [x] Run `pytest` again from `assets/sales-order-retrieval-agent/` to generate final `test_report.json`
- [x] Verify `test_report.json` exists in `assets/sales-order-retrieval-agent/`
