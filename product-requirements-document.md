# Product Requirements Document (PRD)

**Title:** S/4HANA Sales Order Retrieval Agent  
**Date:** 2026-11-18  
**Owner:** Sales Operations / IT  
**Solution Category:** AI Agent

---

## Product Purpose & Value Proposition

**Elevator Pitch:**  
Sales representatives, customer service agents, and back-office staff currently spend up to 5 minutes manually navigating SAP S/4HANA to look up a single sales order. This AI agent lets any user ask in natural language — by order number or by attributes like customer name or date — and receive a complete, structured order summary in under 30 seconds.

**Business Need:**  
Accessing sales order information in S/4HANA requires users to log in, navigate multiple screens, and manually interpret data. This slows down customer-facing conversations, delays issue resolution, and creates unnecessary manual effort for every lookup. A conversational agent that surfaces order data instantly removes this friction for all user groups.

**Expected Value:**  
Sales order lookup time reduced from 5 minutes to under 30 seconds, enabling faster customer responses and more productive use of staff time.

**Product Objectives (Prioritized):**
1. Enable instant, natural-language retrieval of sales order data from S/4HANA On-Premise
2. Surface all relevant order information — header, line items, delivery, and billing — in a single interaction
3. Ensure reliable, secure connectivity to S/4HANA via BTP destination "s43"
4. Design the agent for extensibility to support future capabilities beyond order retrieval

---

## Business Metrics

| Metric | Baseline | Target | Timeline | Process / Capability | Source |
|--------|----------|--------|----------|----------------------|--------|
| Sales order lookup time | 5 minutes | 30 seconds | — | Order to Fulfill / Sales Order Retrieval | user |

---

## User Profiles & Personas

### Primary Persona: Alex — Sales Representative

Alex is a 32-year-old field sales rep who manages a portfolio of 60+ customer accounts. Throughout the day, customers call or message asking about the status of their orders — when it ships, what items are included, whether the price is correct. Alex currently has to log into S/4HANA, navigate to the order management module, and manually look up each order while keeping the customer waiting. Alex is comfortable with technology and uses a CRM daily, but finds SAP navigation cumbersome and slow. Success for Alex means being able to answer a customer's order question in real time without putting them on hold.

### Secondary Persona: Maria — Customer Service Agent

Maria handles 40–50 inbound customer inquiries per day via chat and phone. Many of these involve order status questions: where is my order, why is my invoice different from my quote, when will my delivery arrive. Maria needs fast, accurate answers without deep SAP expertise. She is frustrated by the time it takes to look up order details and by having to switch between multiple SAP screens to piece together a complete picture. Success for Maria means resolving order inquiries in a single turn without escalating to a SAP-trained colleague.

### Other User Types

- **Sales Manager**: Reviews team order activity, monitors fulfillment status, and tracks high-value orders.
- **Back-Office / Operations Staff**: Validates order correctness, reconciles discrepancies, processes order-related tasks.

---

## User Goals & Tasks

### For Alex (Sales Representative):

**Goals:**
- Answer customer order questions without putting them on hold
- Confirm order details (items, prices, delivery date) during sales calls

**Key Tasks:**
- Look up a sales order by number during a live customer call
- Search for an order by customer name or date when the order number is unknown
- Review line items and quantities to confirm what was ordered

### For Maria (Customer Service Agent):

**Goals:**
- Resolve order status inquiries in a single interaction
- Provide accurate delivery and billing information without SAP navigation expertise

**Key Tasks:**
- Retrieve full order summary (header, items, delivery, billing) from a single query
- Verify invoice/billing status against the order

---

## Goals and Non-Goals

### Goals (In Scope)

- Natural language lookup of sales orders by order number or by attributes (customer, date range, status)
- Retrieval of complete order data: header, line items, delivery/shipping, and billing/invoice status
- Secure connection to SAP S/4HANA On-Premise via BTP destination "s43"
- Read-only operations only — no data modifications
- Structured, human-readable response summarising all retrieved order data

### Non-Goals (Out of Scope)

- Creating, updating, or deleting sales orders
- Retrieving non-sales-order SAP data (purchase orders, financial postings, HR data)
- Real-time event streaming or push notifications
- Building a custom UI — the agent is accessed via chat/conversational interface
- Registering the S/4HANA system in the SAP Knowledge Graph cloud catalog

---

## Requirements

### Must-Have Requirements

**REQ-01**: Retrieve Sales Order by Order Number

- **Problem to Solve**: Users know the order number but must navigate multiple SAP screens to find the details.
- **User Story**: As a sales representative, I need to provide a sales order number and immediately receive full order details so that I can answer customer questions without delay.
- **Acceptance Criteria**:
  - Given a valid sales order number, when submitted to the agent, then the agent returns header, line items, delivery, and billing information within 30 seconds.
  - Given an invalid or non-existent order number, the agent returns a clear, friendly error message.
- **Maps to Objective**: Objective 1
- **Priority Rank**: 1

**REQ-02**: Search Sales Orders by Attributes

- **Problem to Solve**: Users sometimes don't know the order number and need to search by customer, date, or status.
- **User Story**: As a customer service agent, I need to search for sales orders using attributes like customer name or order date so that I can find the right order even without the order number.
- **Acceptance Criteria**:
  - Given a customer name and/or date range, when submitted to the agent, then the agent returns a list of matching sales orders with key header details.
  - Given no matching results, the agent clearly communicates that no orders were found.
- **Maps to Objective**: Objective 1
- **Priority Rank**: 2

**REQ-03**: Display Complete Order Header Information

- **Problem to Solve**: Users need a quick overview of key order-level attributes to confirm order identity and status.
- **User Story**: As a sales manager, I need to see the order date, status, customer name, and total value so that I can assess the order at a glance.
- **Acceptance Criteria**:
  - The agent response includes: sales order number, order date, order status, sold-to customer, and net order value.
- **Maps to Objective**: Objective 2
- **Priority Rank**: 3

**REQ-04**: Display Order Line Items

- **Problem to Solve**: Users need to verify what was ordered, in what quantities, and at what prices.
- **User Story**: As a sales representative, I need to see all line items with material descriptions, quantities, and prices so that I can confirm order accuracy with the customer.
- **Acceptance Criteria**:
  - The agent response includes each line item with: item number, material/product description, ordered quantity, unit of measure, and net price.
- **Maps to Objective**: Objective 2
- **Priority Rank**: 4

**REQ-05**: Display Delivery and Shipping Details

- **Problem to Solve**: Users need to know when and where an order ships to respond to delivery inquiries.
- **User Story**: As a customer service agent, I need to see delivery and shipping details so that I can tell the customer when their order will arrive.
- **Acceptance Criteria**:
  - The agent response includes: requested delivery date, shipping status, and delivery block (if any).
- **Maps to Objective**: Objective 2
- **Priority Rank**: 5

**REQ-06**: Display Billing and Invoice Status

- **Problem to Solve**: Users need to know whether an order has been invoiced and whether payment is outstanding.
- **User Story**: As a back-office staff member, I need to see billing and invoice status so that I can reconcile orders against financial records.
- **Acceptance Criteria**:
  - The agent response includes billing status and, where available, invoice reference.
  - If billing data requires an additional OData expand, the agent handles this transparently.
- **Maps to Objective**: Objective 2
- **Priority Rank**: 6

**REQ-07**: Secure Connectivity via BTP Destination "s43"

- **Problem to Solve**: The S/4HANA On-Premise system must be accessed securely without exposing credentials in the agent code.
- **User Story**: As an IT administrator, I need the agent to connect to S/4HANA via the configured BTP destination "s43" so that credentials and connectivity are managed centrally.
- **Acceptance Criteria**:
  - The agent uses the BTP destination "s43" for all calls to `API_SALES_ORDER_SRV`.
  - No hardcoded credentials appear in the agent source code.
- **Maps to Objective**: Objective 3
- **Priority Rank**: 7

---

## Solution Architecture

**Architecture Overview:**  
A Python-based AI agent (A2A protocol) connects to SAP S/4HANA On-Premise through a custom MCP server built from the `API_SALES_ORDER_SRV` EDMX specification. The BTP destination "s43" handles secure connectivity. The agent interprets natural language queries, invokes the appropriate MCP tool, and formats the retrieved OData data into a human-readable response.

**Key Components:**

- **AI Agent (Python, A2A protocol)**: Core reasoning layer; interprets user queries, decides which MCP tools to call, and formats the response
- **Custom MCP Server (`API_SALES_ORDER_SRV`)**: Generated from the S/4HANA `API_SALES_ORDER_SRV` EDMX spec; exposes tools for querying sales order entities (`A_SalesOrder`, `A_SalesOrderItem`, `A_SalesOrderScheduleLine`)
- **BTP Destination "s43"**: Secure connectivity layer to the SAP S/4HANA On-Premise system; manages authentication and routing
- **SAP S/4HANA On-Premise (`API_SALES_ORDER_SRV`)**: Source of truth for all sales order data

**Integration Points:**

- **S/4HANA On-Premise OData API**: Read-only; agent calls `GET` on `A_SalesOrder`, `A_SalesOrderItem`, `A_SalesOrderScheduleLine` entity sets; on demand per user query

**Deployment Environments:**

- Dev/QA: Connected to S/4HANA development or quality system via BTP destination
- Production: Connected to live S/4HANA system; read-only access enforced

### Agent Extensibility & Instrumentation

**Agent Extensibility:**
- The agent is designed with extension points to support additional tools in the future (e.g. quotation lookup, delivery tracking, credit memo retrieval)
- MCP tools are loosely coupled — new tools can be added to the MCP server without modifying the core agent reasoning logic
- The agent's system prompt and tool registry are externalised to support configuration-driven extensibility

**Business Step Instrumentation:**
- All six key milestones (defined in the Milestones section) are instrumented with structured log statements
- Log statements follow the pattern: `[MILESTONE_ID].[achieved|missed]: [description]`
- Instrumentation enables production monitoring, debugging, and business process observability via OpenTelemetry

### Automation & Agent Behaviour

**Automation Level:** Autonomous agent

**Actions the system performs without human approval:**
- Query S/4HANA OData API for sales order data
- Format and return the structured order summary to the user

**Actions that require human review or approval:**
- None (read-only agent; all actions are non-destructive)

**Model or engine used:** SAP Generative AI Hub (LLM for natural language understanding and response generation)

**Knowledge & data sources accessed:**
- SAP S/4HANA On-Premise `API_SALES_ORDER_SRV`: sales order master and transactional data; owned by the Sales Operations team

**Tools or connectors invoked:**
- `get_sales_order` MCP tool (read-only): retrieves sales order header data by order number from `A_SalesOrder`
- `get_sales_order_items` MCP tool (read-only): retrieves line items from `A_SalesOrderItem`
- `get_sales_order_schedule_lines` MCP tool (read-only): retrieves delivery schedule line data from `A_SalesOrderScheduleLine`

**Guardrails & fail-safes:**
- The agent is strictly read-only — no write, update, or delete operations are permitted at any layer
- If the BTP destination "s43" is unavailable, the agent returns a clear error message and does not retry in a loop
- If the OData API returns no results, the agent communicates this clearly without hallucinating order data
- The agent does not expose raw OData responses — all output is formatted and sanitised before presentation

---

## Milestones

### M1: User Query Received

- **Description**: The agent receives and understands the user's sales order lookup request
- **Achieved when**: The agent successfully parses a sales order number or search attributes from the user's input
- **Log on achievement**: `M1.achieved: user query received and parsed — order_number={value} or search_attributes={value}`
- **Log on miss**: `M1.missed: unable to parse sales order query from user input`

### M2: API Call Executed

- **Description**: The agent calls the S/4HANA `API_SALES_ORDER_SRV` via BTP destination "s43"
- **Achieved when**: The OData request is dispatched and a response (success or error) is received
- **Log on achievement**: `M2.achieved: OData API call executed successfully — endpoint=API_SALES_ORDER_SRV destination=s43`
- **Log on miss**: `M2.missed: OData API call failed — destination=s43 error={message}`

### M3: Header Data Retrieved

- **Description**: Sales order header information is successfully retrieved from `A_SalesOrder`
- **Achieved when**: The agent receives a non-empty response with order number, date, status, customer, and value
- **Log on achievement**: `M3.achieved: order header retrieved — sales_order={value} customer={value} status={value}`
- **Log on miss**: `M3.missed: order header not found or empty — sales_order={value}`

### M4: Line Items Retrieved

- **Description**: Order line items are successfully retrieved from `A_SalesOrderItem`
- **Achieved when**: The agent receives at least one item record with material, quantity, and price
- **Log on achievement**: `M4.achieved: line items retrieved — sales_order={value} item_count={value}`
- **Log on miss**: `M4.missed: no line items returned — sales_order={value}`

### M5: Delivery and Billing Details Retrieved

- **Description**: Delivery schedule line and billing status data are successfully retrieved
- **Achieved when**: The agent receives delivery date and billing status fields
- **Log on achievement**: `M5.achieved: delivery and billing details retrieved — sales_order={value}`
- **Log on miss**: `M5.missed: delivery or billing details unavailable — sales_order={value}`

### M6: Response Presented

- **Description**: The agent delivers a complete, formatted sales order summary to the user
- **Achieved when**: The agent sends the structured response covering all retrieved data sections
- **Log on achievement**: `M6.achieved: order summary presented to user — sales_order={value}`
- **Log on miss**: `M6.missed: response could not be delivered — sales_order={value}`

---

## Non-Functional Requirements

### Performance

- **Latency**: End-to-end response time under 30 seconds for 95% of queries
- **Throughput**: Designed to support concurrent queries from multiple users

### Reliability

- **Availability**: Dependent on BTP destination and S/4HANA availability
- **Fallback**: If the OData API is unreachable, the agent returns a clear, actionable error message

### Explainability

- **Traceability**: All OData calls are logged with request parameters and response metadata
- **Decision Logging**: Agent reasoning steps and tool calls are logged via OpenTelemetry spans
- **Uncertainty Communication**: The agent explicitly states when data is unavailable or incomplete rather than inferring or estimating

---

## Risks, Assumptions, and Dependencies

### Risks

- Billing detail retrieval may require an OData expand or additional API call not covered by `API_SALES_ORDER_SRV` alone — to be validated during specification
- S/4HANA On-Premise system availability directly impacts agent responsiveness; no caching layer is in scope

### Assumptions (Validate These)

- BTP destination "s43" is already configured and accessible from the BTP subaccount where the agent is deployed
- The `API_SALES_ORDER_SRV` OData service is activated and accessible on the S/4HANA On-Premise system
- Users access the agent through a Joule Studio-compatible chat interface

### Dependencies

- SAP BTP destination service (destination "s43")
- SAP S/4HANA On-Premise with `API_SALES_ORDER_SRV` activated (`/sap/opu/odata/sap/API_SALES_ORDER_SRV/`)
- SAP Generative AI Hub (LLM access for the agent)

---

## Appendix

### References

- SAP Sales Order OData API: `/sap/opu/odata/sap/API_SALES_ORDER_SRV/`
- SAP API Business Hub: `sap.s4:apiResource:API_SALES_ORDER_SRV:v1`
- SAP Lead to Cash E2E — Order to Fulfill sub-process (BPS-361)
- SAP BTP Destination Service documentation
