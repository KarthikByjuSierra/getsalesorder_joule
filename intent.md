# S/4HANA Sales Order Retrieval Agent

AI agent for retrieving sales order details from SAP S/4HANA On-Premise

## Business challenge

Sales representatives, customer service agents, sales managers, and back-office staff need a fast, conversational way to retrieve complete sales order details from SAP S/4HANA On-Premise. Currently, looking up an order takes around 5 minutes navigating the system manually. Users should be able to provide a sales order number or order attributes and immediately receive a structured summary covering header info, line items, delivery, and billing details.

## Business Goals & Success Criteria

| Metric | Baseline | Target | Timeline | Process / Capability | Source |
|--------|----------|--------|----------|----------------------|--------|
| Sales order lookup time | 5 minutes | 30 seconds | — | Order to Fulfill / Sales Order Retrieval | user |

## Key Milestones

1. **User query received** — User provides a sales order number or search criteria (e.g. customer, date range) to the agent
2. **API call executed** — Agent calls `API_SALES_ORDER_SRV` via BTP destination "s43" to fetch sales order data
3. **Header data retrieved** — Order header information (order date, status, customer, total value) is returned
4. **Line items retrieved** — Order items (materials, quantities, prices) are returned
5. **Delivery & billing details retrieved** — Shipping status and billing/invoice details are returned
6. **Response presented** — Agent formats and delivers a clear, structured summary to the user

## Business Architecture (RBA)

### End-to-End Process

Lead to Cash (E2E)

### Process Hierarchy

```
Lead to Cash (E2E)
└── Order to Fulfill (generic)
    └── Manage customer orders and contracts (generic) (BPS-361)
        └── Manage customer orders
└── Manage Customers and Channels (generic)
    └── Manage and operate sales channels (generic) (BPS-371)
        └── Manage marketplace channel
```

### Summary

Retrieving sales order details by order number or attributes maps to the "Order to Fulfill" sub-process within the "Lead to Cash" E2E, specifically the "Manage customer orders and contracts" business activity — covering the full order lifecycle from inquiry to fulfillment status.

## Fit Gap Analysis

| Requirement (business) | Standard asset(s) found | API ORD ID | MCP Server ORD ID | MCP Server Version | Webhook API ORD ID | Data Product ORD ID | Gap? | Notes / assumptions |
| ---------------------- | ----------------------- | ---------- | ----------------- | ------------------ | ------------------ | ------------------- | ---- | ------------------- |
| Retrieve sales order by order number | SAP S/4HANA On-Premise Sales Order OData API | `sap.s4:apiResource:API_SALES_ORDER_SRV:v1` | — | — | — | — | No | API available; no pre-built MCP server — custom MCP translation file will be generated. BTP destination "s43" configured. |
| Retrieve order header info (date, status, customer, value) | SAP S/4HANA On-Premise — `A_SalesOrder` entity set | `sap.s4:apiResource:API_SALES_ORDER_SRV:v1` | — | — | — | — | No | Covered by standard OData entity |
| Retrieve line items (materials, quantities, prices) | SAP S/4HANA On-Premise — `A_SalesOrderItem` entity set | `sap.s4:apiResource:API_SALES_ORDER_SRV:v1` | — | — | — | — | No | Covered by standard OData entity |
| Retrieve delivery & shipping details | SAP S/4HANA On-Premise — `A_SalesOrderScheduleLine` / delivery entities | `sap.s4:apiResource:API_SALES_ORDER_SRV:v1` | — | — | — | — | No | Covered by standard OData entity |
| Retrieve billing/invoice status | SAP S/4HANA On-Premise — `A_BillingDocumentItem` via related expand | `sap.s4:apiResource:API_SALES_ORDER_SRV:v1` | — | — | — | — | Maybe | Billing data may require expand or separate API call; to be confirmed during specification |

### Key findings

- The standard SAP `API_SALES_ORDER_SRV` OData service on S/4HANA On-Premise covers all retrieval requirements (header, items, schedule lines, partner functions)
- No pre-built MCP server exists for this API — a custom MCP translation file must be generated from the EDMX specification
- The BTP destination "s43" will be used as the connectivity layer to reach the on-premise system
- All APIs are marked unavailable in the SAP Knowledge Graph (on-premise system not registered in cloud catalog) — this is expected and does not block development
- The solution is read-only; no create/update/delete operations are required, simplifying scope and security posture
- Billing detail retrieval may require an additional OData expand or a secondary API call — to be validated during specification

## Recommendations

### AI Agent for S/4HANA Sales Order Retrieval

#### Executive Summary

Python A2A agent using S/4HANA OData API via BTP destination

#### Recommended Solution

A pro-code Python AI agent (A2A protocol) that exposes a natural language interface for sales order lookups. The agent uses a custom MCP tool generated from the `API_SALES_ORDER_SRV` EDMX spec to call the S/4HANA On-Premise OData service via the BTP destination "s43". Users can query by sales order number or by attributes (customer, date, status). The agent returns a structured summary of header, line items, delivery, and billing information.

#### Recommended solution category

AI Agent

#### Intent fit
95%
