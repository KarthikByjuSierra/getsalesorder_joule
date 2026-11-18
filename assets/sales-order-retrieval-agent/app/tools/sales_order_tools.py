"""Native Python tools for SAP S/4HANA Sales Order OData API (API_SALES_ORDER_SRV).

Implements all 17 operations as LangChain StructuredTool instances. Each tool
makes an authenticated async OData GET request via BTP destination "S43" through
the BTP Connectivity Transparent Proxy using SAP Cloud SDK 0.62.0.

Authentication
--------------
The user JWT is extracted by JWTContextMiddleware (main.py) and stored in a
per-request ContextVar via set_user_token(). Each tool reads it via _token() →
get_user_token() and passes it to call_odata(user_token=...). The client then
forwards it as "Authorization: Bearer <jwt>" on the proxy request for principal
propagation / OAuth2UserTokenExchange. No credentials are hardcoded.

Connectivity
------------
All OData calls are routed through the BTP Connectivity Transparent Proxy
(create_client(use_default_proxy=True)). The proxy pod handles Cloud Connector
tunnel selection. Direct TCP to the on-premise virtual host is never attempted.

Destination: "S43" (case-sensitive).

Input validation
----------------
- $top is clamped to [1, 100]. Negative values raise ToolException.
- $skip must be non-negative. Negative values raise ToolException.
- String key values containing apostrophes are escaped per OData V2 convention
  (single-quote → double-single-quote) before being embedded in URL key predicates.

Batch
-----
OData V2 multipart $batch is NOT supported. The batch tool (tool 2) returns an
explicit "not supported" error. Use individual tools instead.

Tools implemented:
  Metadata / batch:
    1.  get_metadata_api_sales_order_srv
    2.  batch_for_api_sales_order_srv           (unsupported — returns error)

  A_SalesOrder:
    3.  list_a_salesorder_for_api_sales_order_srv
    4.  get_a_salesorder_for_api_sales_order_srv
    5.  count_a_salesorder_for_api_sales_order_srv

  A_SalesOrderBillingPlan:
    6.  get_a_salesorderbillingplan_for_api_sales_order_srv

  A_SalesOrderBillingPlanItem:
    7.  list_a_salesorderbillingplanitem_for_api_sales_order_srv
    8.  get_a_salesorderbillingplanitem_for_api_sales_order_srv

  A_SalesOrderHeaderPartner:
    9.  list_a_salesorderheaderpartner_for_api_sales_order_srv
    10. get_a_salesorderheaderpartner_for_api_sales_order_srv
    11. count_a_salesorderheaderpartner_for_api_sales_order_srv

  A_SalesOrderItem:
    12. list_a_salesorderitem_for_api_sales_order_srv
    13. get_a_salesorderitem_for_api_sales_order_srv
    14. count_a_salesorderitem_for_api_sales_order_srv

  A_SalesOrderScheduleLine:
    15. list_a_salesorderscheduleline_for_api_sales_order_srv
    16. get_a_salesorderscheduleline_for_api_sales_order_srv
    17. count_a_salesorderscheduleline_for_api_sales_order_srv
"""
from __future__ import annotations

import logging
from typing import Optional

from langchain_core.tools import StructuredTool, ToolException
from pydantic import BaseModel, Field

from mcp_providers.agw import get_user_token
from tools.s4_odata_client import call_odata

logger = logging.getLogger(__name__)

_DEST = "S43"


def _token() -> str | None:
    """Return the per-request user JWT from the ContextVar (may be None in IBD_TESTING mode).

    The JWT is set by JWTContextMiddleware for every inbound request.
    Python's ContextVar is async-task-scoped: concurrent requests each have
    their own isolated copy — no cross-request token leakage is possible.
    """
    return get_user_token()


def _escape_odata_string(value: str) -> str:
    """Escape a string value for safe embedding in an OData V2 key predicate.

    OData V2 key predicates wrap string values in single quotes:
        A_SalesOrder('10')
    Values that themselves contain single quotes must double them:
        A_SalesOrder('O''Reilly')   ← the apostrophe in O'Reilly

    Args:
        value: Raw string value (e.g. from user input or tool argument).

    Returns:
        Escaped string safe for embedding between single quotes in a key predicate.
    """
    return value.replace("'", "''")


def _validate_pagination(
    top: Optional[int],
    skip: Optional[int],
) -> tuple[Optional[int], Optional[int]]:
    """Validate and clamp OData pagination parameters.

    Rules:
    - $top must be in [1, 100]. Negative values raise ToolException.
      Zero is clamped to 1 (a $top=0 request is semantically empty).
      Values > 100 are clamped to 100 to prevent context overflow.
    - $skip must be non-negative. Negative values raise ToolException.

    Args:
        top:  Raw $top value from tool input (may be None).
        skip: Raw $skip value from tool input (may be None).

    Returns:
        (validated_top, validated_skip) tuple, with clamping applied.

    Raises:
        ToolException: If top < 0 or skip < 0.
    """
    if top is not None:
        if top < 0:
            raise ToolException(
                f"Invalid $top value: {top}. $top must be a non-negative integer."
            )
        top = max(1, min(top, 100))
    if skip is not None:
        if skip < 0:
            raise ToolException(
                f"Invalid $skip value: {skip}. $skip must be a non-negative integer."
            )
    return top, skip


# ---------------------------------------------------------------------------
# 1. Metadata
# ---------------------------------------------------------------------------

class _MetadataInput(BaseModel):
    """No parameters required for metadata request."""


async def _get_metadata(**_kwargs) -> str:
    return await call_odata(
        destination_name=_DEST,
        path="$metadata",
        user_token=_token(),
    )


# ---------------------------------------------------------------------------
# 2. Batch (unsupported — OData V2 multipart $batch not implemented)
# ---------------------------------------------------------------------------

class _BatchInput(BaseModel):
    body: Optional[str] = Field(
        default=None,
        description="Multipart batch request body (not used — batch is not supported).",
    )


async def _batch(body: Optional[str] = None, **_kwargs) -> str:
    # OData V2 multipart $batch requires constructing a multipart/mixed body with
    # per-part Content-Type, boundary handling, and response demultiplexing.
    # This is not implemented. Use the individual entity tools instead.
    raise ToolException(
        "OData V2 $batch is not supported by this agent. "
        "Use the individual entity tools (list_a_salesorder_for_api_sales_order_srv, "
        "get_a_salesorderitem_for_api_sales_order_srv, etc.) to retrieve data."
    )


# ---------------------------------------------------------------------------
# 3. list_a_salesorder
# ---------------------------------------------------------------------------

class _ListSalesOrderInput(BaseModel):
    filter: Optional[str] = Field(default=None, description="OData $filter expression (e.g. \"SoldToParty eq 'C1'\")")
    select: Optional[str] = Field(default=None, description="Comma-separated list of properties to return ($select)")
    orderby: Optional[str] = Field(default=None, description="OData $orderby expression")
    top: Optional[int] = Field(default=None, description="Maximum number of records to return ($top). Max 100.")
    skip: Optional[int] = Field(default=None, description="Number of records to skip ($skip)")
    expand: Optional[str] = Field(default=None, description="Comma-separated navigation properties to expand ($expand)")
    inlinecount: Optional[str] = Field(default=None, description="Set to 'allpages' to include total count in response")


async def _list_salesorder(
    filter: Optional[str] = None,
    select: Optional[str] = None,
    orderby: Optional[str] = None,
    top: Optional[int] = None,
    skip: Optional[int] = None,
    expand: Optional[str] = None,
    inlinecount: Optional[str] = None,
    **_kwargs,
) -> str:
    top, skip = _validate_pagination(top, skip)
    params: dict = {"$format": "json"}
    if filter:    params["$filter"] = filter
    if select:    params["$select"] = select
    if orderby:   params["$orderby"] = orderby
    if top is not None: params["$top"] = str(top)
    if skip is not None: params["$skip"] = str(skip)
    if expand:    params["$expand"] = expand
    if inlinecount: params["$inlinecount"] = inlinecount
    return await call_odata(destination_name=_DEST, path="A_SalesOrder", params=params, user_token=_token())


# ---------------------------------------------------------------------------
# 4. get_a_salesorder (by key)
# ---------------------------------------------------------------------------

class _GetSalesOrderInput(BaseModel):
    salesorder: str = Field(description="Sales order number key (e.g. '10')")
    select: Optional[str] = Field(default=None, description="Comma-separated list of properties to return ($select)")
    expand: Optional[str] = Field(default=None, description="Comma-separated navigation properties to expand ($expand)")


async def _get_salesorder(salesorder: str, select: Optional[str] = None, expand: Optional[str] = None, **_kwargs) -> str:
    params: dict = {"$format": "json"}
    if select: params["$select"] = select
    if expand: params["$expand"] = expand
    key = _escape_odata_string(salesorder)
    return await call_odata(destination_name=_DEST, path=f"A_SalesOrder('{key}')", params=params, user_token=_token())


# ---------------------------------------------------------------------------
# 5. count_a_salesorder
# ---------------------------------------------------------------------------

class _CountSalesOrderInput(BaseModel):
    filter: Optional[str] = Field(default=None, description="OData $filter expression to count matching records")


async def _count_salesorder(filter: Optional[str] = None, **_kwargs) -> str:
    params: dict = {}
    if filter: params["$filter"] = filter
    return await call_odata(destination_name=_DEST, path="A_SalesOrder/$count", params=params, user_token=_token())


# ---------------------------------------------------------------------------
# 6. get_a_salesorderbillingplan (by key)
# ---------------------------------------------------------------------------

class _GetBillingPlanInput(BaseModel):
    salesorder: str = Field(description="Sales order number key")
    billingplan: str = Field(description="Billing plan key")
    select: Optional[str] = Field(default=None, description="$select properties")
    expand: Optional[str] = Field(default=None, description="$expand navigation properties")


async def _get_billingplan(salesorder: str, billingplan: str, select: Optional[str] = None, expand: Optional[str] = None, **_kwargs) -> str:
    params: dict = {"$format": "json"}
    if select: params["$select"] = select
    if expand: params["$expand"] = expand
    so = _escape_odata_string(salesorder)
    bp = _escape_odata_string(billingplan)
    return await call_odata(
        destination_name=_DEST,
        path=f"A_SalesOrderBillingPlan(SalesOrder='{so}',BillingPlan='{bp}')",
        params=params,
        user_token=_token(),
    )


# ---------------------------------------------------------------------------
# 7. list_a_salesorderbillingplanitem
# ---------------------------------------------------------------------------

class _ListBillingPlanItemInput(BaseModel):
    filter: Optional[str] = Field(default=None, description="OData $filter expression")
    select: Optional[str] = Field(default=None, description="$select properties")
    orderby: Optional[str] = Field(default=None, description="$orderby expression")
    top: Optional[int] = Field(default=None, description="Max records to return ($top)")
    skip: Optional[int] = Field(default=None, description="Records to skip ($skip)")
    expand: Optional[str] = Field(default=None, description="$expand navigation properties")
    inlinecount: Optional[str] = Field(default=None, description="Set to 'allpages' for total count")


async def _list_billingplanitem(
    filter: Optional[str] = None,
    select: Optional[str] = None,
    orderby: Optional[str] = None,
    top: Optional[int] = None,
    skip: Optional[int] = None,
    expand: Optional[str] = None,
    inlinecount: Optional[str] = None,
    **_kwargs,
) -> str:
    top, skip = _validate_pagination(top, skip)
    params: dict = {"$format": "json"}
    if filter:    params["$filter"] = filter
    if select:    params["$select"] = select
    if orderby:   params["$orderby"] = orderby
    if top is not None: params["$top"] = str(top)
    if skip is not None: params["$skip"] = str(skip)
    if expand:    params["$expand"] = expand
    if inlinecount: params["$inlinecount"] = inlinecount
    return await call_odata(destination_name=_DEST, path="A_SalesOrderBillingPlanItem", params=params, user_token=_token())


# ---------------------------------------------------------------------------
# 8. get_a_salesorderbillingplanitem (by key)
# ---------------------------------------------------------------------------

class _GetBillingPlanItemInput(BaseModel):
    salesorder: str = Field(description="Sales order number key")
    billingplan: str = Field(description="Billing plan key")
    billingplanitem: str = Field(description="Billing plan item key")
    select: Optional[str] = Field(default=None, description="$select properties")
    expand: Optional[str] = Field(default=None, description="$expand navigation properties")


async def _get_billingplanitem(salesorder: str, billingplan: str, billingplanitem: str, select: Optional[str] = None, expand: Optional[str] = None, **_kwargs) -> str:
    params: dict = {"$format": "json"}
    if select: params["$select"] = select
    if expand: params["$expand"] = expand
    so = _escape_odata_string(salesorder)
    bp = _escape_odata_string(billingplan)
    bpi = _escape_odata_string(billingplanitem)
    return await call_odata(
        destination_name=_DEST,
        path=f"A_SalesOrderBillingPlanItem(SalesOrder='{so}',BillingPlan='{bp}',BillingPlanItem='{bpi}')",
        params=params,
        user_token=_token(),
    )


# ---------------------------------------------------------------------------
# 9. list_a_salesorderheaderpartner
# ---------------------------------------------------------------------------

class _ListHeaderPartnerInput(BaseModel):
    filter: Optional[str] = Field(default=None, description="OData $filter expression")
    select: Optional[str] = Field(default=None, description="$select properties")
    orderby: Optional[str] = Field(default=None, description="$orderby expression")
    top: Optional[int] = Field(default=None, description="Max records to return ($top)")
    skip: Optional[int] = Field(default=None, description="Records to skip ($skip)")
    expand: Optional[str] = Field(default=None, description="$expand navigation properties")
    inlinecount: Optional[str] = Field(default=None, description="Set to 'allpages' for total count")


async def _list_headerpartner(
    filter: Optional[str] = None,
    select: Optional[str] = None,
    orderby: Optional[str] = None,
    top: Optional[int] = None,
    skip: Optional[int] = None,
    expand: Optional[str] = None,
    inlinecount: Optional[str] = None,
    **_kwargs,
) -> str:
    top, skip = _validate_pagination(top, skip)
    params: dict = {"$format": "json"}
    if filter:    params["$filter"] = filter
    if select:    params["$select"] = select
    if orderby:   params["$orderby"] = orderby
    if top is not None: params["$top"] = str(top)
    if skip is not None: params["$skip"] = str(skip)
    if expand:    params["$expand"] = expand
    if inlinecount: params["$inlinecount"] = inlinecount
    return await call_odata(destination_name=_DEST, path="A_SalesOrderHeaderPartner", params=params, user_token=_token())


# ---------------------------------------------------------------------------
# 10. get_a_salesorderheaderpartner (by key)
# ---------------------------------------------------------------------------

class _GetHeaderPartnerInput(BaseModel):
    salesorder: str = Field(description="Sales order number key")
    partnerfunction: str = Field(description="Partner function key (e.g. 'AG' for sold-to)")
    select: Optional[str] = Field(default=None, description="$select properties")
    expand: Optional[str] = Field(default=None, description="$expand navigation properties")


async def _get_headerpartner(salesorder: str, partnerfunction: str, select: Optional[str] = None, expand: Optional[str] = None, **_kwargs) -> str:
    params: dict = {"$format": "json"}
    if select: params["$select"] = select
    if expand: params["$expand"] = expand
    so = _escape_odata_string(salesorder)
    pf = _escape_odata_string(partnerfunction)
    return await call_odata(
        destination_name=_DEST,
        path=f"A_SalesOrderHeaderPartner(SalesOrder='{so}',PartnerFunction='{pf}')",
        params=params,
        user_token=_token(),
    )


# ---------------------------------------------------------------------------
# 11. count_a_salesorderheaderpartner
# ---------------------------------------------------------------------------

class _CountHeaderPartnerInput(BaseModel):
    filter: Optional[str] = Field(default=None, description="OData $filter expression to count matching records")


async def _count_headerpartner(filter: Optional[str] = None, **_kwargs) -> str:
    params: dict = {}
    if filter: params["$filter"] = filter
    return await call_odata(destination_name=_DEST, path="A_SalesOrderHeaderPartner/$count", params=params, user_token=_token())


# ---------------------------------------------------------------------------
# 12. list_a_salesorderitem
# ---------------------------------------------------------------------------

class _ListSalesOrderItemInput(BaseModel):
    filter: Optional[str] = Field(default=None, description="OData $filter expression")
    select: Optional[str] = Field(default=None, description="$select properties")
    orderby: Optional[str] = Field(default=None, description="$orderby expression")
    top: Optional[int] = Field(default=None, description="Max records to return ($top)")
    skip: Optional[int] = Field(default=None, description="Records to skip ($skip)")
    expand: Optional[str] = Field(default=None, description="$expand navigation properties")
    inlinecount: Optional[str] = Field(default=None, description="Set to 'allpages' for total count")


async def _list_salesorderitem(
    filter: Optional[str] = None,
    select: Optional[str] = None,
    orderby: Optional[str] = None,
    top: Optional[int] = None,
    skip: Optional[int] = None,
    expand: Optional[str] = None,
    inlinecount: Optional[str] = None,
    **_kwargs,
) -> str:
    top, skip = _validate_pagination(top, skip)
    params: dict = {"$format": "json"}
    if filter:    params["$filter"] = filter
    if select:    params["$select"] = select
    if orderby:   params["$orderby"] = orderby
    if top is not None: params["$top"] = str(top)
    if skip is not None: params["$skip"] = str(skip)
    if expand:    params["$expand"] = expand
    if inlinecount: params["$inlinecount"] = inlinecount
    return await call_odata(destination_name=_DEST, path="A_SalesOrderItem", params=params, user_token=_token())


# ---------------------------------------------------------------------------
# 13. get_a_salesorderitem (by key)
# ---------------------------------------------------------------------------

class _GetSalesOrderItemInput(BaseModel):
    salesorder: str = Field(description="Sales order number key")
    salesorderitem: str = Field(description="Sales order item number key (e.g. '10')")
    select: Optional[str] = Field(default=None, description="$select properties")
    expand: Optional[str] = Field(default=None, description="$expand navigation properties")


async def _get_salesorderitem(salesorder: str, salesorderitem: str, select: Optional[str] = None, expand: Optional[str] = None, **_kwargs) -> str:
    params: dict = {"$format": "json"}
    if select: params["$select"] = select
    if expand: params["$expand"] = expand
    so = _escape_odata_string(salesorder)
    soi = _escape_odata_string(salesorderitem)
    return await call_odata(
        destination_name=_DEST,
        path=f"A_SalesOrderItem(SalesOrder='{so}',SalesOrderItem='{soi}')",
        params=params,
        user_token=_token(),
    )


# ---------------------------------------------------------------------------
# 14. count_a_salesorderitem
# ---------------------------------------------------------------------------

class _CountSalesOrderItemInput(BaseModel):
    filter: Optional[str] = Field(default=None, description="OData $filter expression to count matching records")


async def _count_salesorderitem(filter: Optional[str] = None, **_kwargs) -> str:
    params: dict = {}
    if filter: params["$filter"] = filter
    return await call_odata(destination_name=_DEST, path="A_SalesOrderItem/$count", params=params, user_token=_token())


# ---------------------------------------------------------------------------
# 15. list_a_salesorderscheduleline
# ---------------------------------------------------------------------------

class _ListScheduleLineInput(BaseModel):
    filter: Optional[str] = Field(default=None, description="OData $filter expression")
    select: Optional[str] = Field(default=None, description="$select properties")
    orderby: Optional[str] = Field(default=None, description="$orderby expression")
    top: Optional[int] = Field(default=None, description="Max records to return ($top)")
    skip: Optional[int] = Field(default=None, description="Records to skip ($skip)")
    expand: Optional[str] = Field(default=None, description="$expand navigation properties")
    inlinecount: Optional[str] = Field(default=None, description="Set to 'allpages' for total count")


async def _list_scheduleline(
    filter: Optional[str] = None,
    select: Optional[str] = None,
    orderby: Optional[str] = None,
    top: Optional[int] = None,
    skip: Optional[int] = None,
    expand: Optional[str] = None,
    inlinecount: Optional[str] = None,
    **_kwargs,
) -> str:
    top, skip = _validate_pagination(top, skip)
    params: dict = {"$format": "json"}
    if filter:    params["$filter"] = filter
    if select:    params["$select"] = select
    if orderby:   params["$orderby"] = orderby
    if top is not None: params["$top"] = str(top)
    if skip is not None: params["$skip"] = str(skip)
    if expand:    params["$expand"] = expand
    if inlinecount: params["$inlinecount"] = inlinecount
    return await call_odata(destination_name=_DEST, path="A_SalesOrderScheduleLine", params=params, user_token=_token())


# ---------------------------------------------------------------------------
# 16. get_a_salesorderscheduleline (by key)
# ---------------------------------------------------------------------------

class _GetScheduleLineInput(BaseModel):
    salesorder: str = Field(description="Sales order number key")
    salesorderitem: str = Field(description="Sales order item number key")
    scheduleline: str = Field(description="Schedule line counter key")
    select: Optional[str] = Field(default=None, description="$select properties")
    expand: Optional[str] = Field(default=None, description="$expand navigation properties")


async def _get_scheduleline(salesorder: str, salesorderitem: str, scheduleline: str, select: Optional[str] = None, expand: Optional[str] = None, **_kwargs) -> str:
    params: dict = {"$format": "json"}
    if select: params["$select"] = select
    if expand: params["$expand"] = expand
    so = _escape_odata_string(salesorder)
    soi = _escape_odata_string(salesorderitem)
    sl = _escape_odata_string(scheduleline)
    return await call_odata(
        destination_name=_DEST,
        path=f"A_SalesOrderScheduleLine(SalesOrder='{so}',SalesOrderItem='{soi}',ScheduleLine='{sl}')",
        params=params,
        user_token=_token(),
    )


# ---------------------------------------------------------------------------
# 17. count_a_salesorderscheduleline
# ---------------------------------------------------------------------------

class _CountScheduleLineInput(BaseModel):
    filter: Optional[str] = Field(default=None, description="OData $filter expression to count matching records")


async def _count_scheduleline(filter: Optional[str] = None, **_kwargs) -> str:
    params: dict = {}
    if filter: params["$filter"] = filter
    return await call_odata(destination_name=_DEST, path="A_SalesOrderScheduleLine/$count", params=params, user_token=_token())


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

def get_native_tools() -> list[StructuredTool]:
    """Return all 17 native S/4HANA Sales Order OData tools as StructuredTool instances.

    Tool names are identical to those in translation.json so that:
    - The LLM system prompt references remain valid
    - mcp-mock.json entries remain compatible for testing
    """
    return [
        # 1
        StructuredTool(
            name="get_metadata_api_sales_order_srv",
            description=(
                "Get metadata of the OData service. Returns the metadata in XML format, "
                "which can be used to discover available entities and their properties. "
                "Call this before other tools to understand the schema."
            ),
            args_schema=_MetadataInput,
            coroutine=_get_metadata,
            handle_tool_error=True,
        ),
        # 2
        StructuredTool(
            name="batch_for_api_sales_order_srv",
            description=(
                "NOT SUPPORTED: OData V2 multipart $batch is not implemented. "
                "Use the individual entity tools to retrieve data instead."
            ),
            args_schema=_BatchInput,
            coroutine=_batch,
            handle_tool_error=True,
        ),
        # 3
        StructuredTool(
            name="list_a_salesorder_for_api_sales_order_srv",
            description=(
                "Retrieve a list of sales orders from A_SalesOrder. "
                "Supports $filter, $select, $orderby, $top (max 100), $skip, $expand, $inlinecount."
            ),
            args_schema=_ListSalesOrderInput,
            coroutine=_list_salesorder,
            handle_tool_error=True,
        ),
        # 4
        StructuredTool(
            name="get_a_salesorder_for_api_sales_order_srv",
            description=(
                "Retrieve a single sales order by its key from A_SalesOrder. "
                "Provide the SalesOrder number. Supports $select and $expand."
            ),
            args_schema=_GetSalesOrderInput,
            coroutine=_get_salesorder,
            handle_tool_error=True,
        ),
        # 5
        StructuredTool(
            name="count_a_salesorder_for_api_sales_order_srv",
            description=(
                "Get the total count of sales orders in A_SalesOrder. "
                "Supports $filter to count only matching records."
            ),
            args_schema=_CountSalesOrderInput,
            coroutine=_count_salesorder,
            handle_tool_error=True,
        ),
        # 6
        StructuredTool(
            name="get_a_salesorderbillingplan_for_api_sales_order_srv",
            description=(
                "Retrieve a single billing plan by key from A_SalesOrderBillingPlan. "
                "Requires SalesOrder and BillingPlan keys. Supports $select and $expand."
            ),
            args_schema=_GetBillingPlanInput,
            coroutine=_get_billingplan,
            handle_tool_error=True,
        ),
        # 7
        StructuredTool(
            name="list_a_salesorderbillingplanitem_for_api_sales_order_srv",
            description=(
                "Retrieve a list of billing plan items from A_SalesOrderBillingPlanItem. "
                "Supports $filter, $select, $orderby, $top (max 100), $skip, $expand, $inlinecount."
            ),
            args_schema=_ListBillingPlanItemInput,
            coroutine=_list_billingplanitem,
            handle_tool_error=True,
        ),
        # 8
        StructuredTool(
            name="get_a_salesorderbillingplanitem_for_api_sales_order_srv",
            description=(
                "Retrieve a single billing plan item by key from A_SalesOrderBillingPlanItem. "
                "Requires SalesOrder, BillingPlan, and BillingPlanItem keys. Supports $select and $expand."
            ),
            args_schema=_GetBillingPlanItemInput,
            coroutine=_get_billingplanitem,
            handle_tool_error=True,
        ),
        # 9
        StructuredTool(
            name="list_a_salesorderheaderpartner_for_api_sales_order_srv",
            description=(
                "Retrieve a list of sales order header partners from A_SalesOrderHeaderPartner. "
                "Supports $filter, $select, $orderby, $top (max 100), $skip, $expand, $inlinecount."
            ),
            args_schema=_ListHeaderPartnerInput,
            coroutine=_list_headerpartner,
            handle_tool_error=True,
        ),
        # 10
        StructuredTool(
            name="get_a_salesorderheaderpartner_for_api_sales_order_srv",
            description=(
                "Retrieve a single header partner by key from A_SalesOrderHeaderPartner. "
                "Requires SalesOrder and PartnerFunction keys. Supports $select and $expand."
            ),
            args_schema=_GetHeaderPartnerInput,
            coroutine=_get_headerpartner,
            handle_tool_error=True,
        ),
        # 11
        StructuredTool(
            name="count_a_salesorderheaderpartner_for_api_sales_order_srv",
            description=(
                "Get the total count of header partners in A_SalesOrderHeaderPartner. "
                "Supports $filter to count only matching records."
            ),
            args_schema=_CountHeaderPartnerInput,
            coroutine=_count_headerpartner,
            handle_tool_error=True,
        ),
        # 12
        StructuredTool(
            name="list_a_salesorderitem_for_api_sales_order_srv",
            description=(
                "Retrieve a list of sales order items from A_SalesOrderItem. "
                "Supports $filter, $select, $orderby, $top (max 100), $skip, $expand, $inlinecount."
            ),
            args_schema=_ListSalesOrderItemInput,
            coroutine=_list_salesorderitem,
            handle_tool_error=True,
        ),
        # 13
        StructuredTool(
            name="get_a_salesorderitem_for_api_sales_order_srv",
            description=(
                "Retrieve a single sales order item by key from A_SalesOrderItem. "
                "Requires SalesOrder and SalesOrderItem keys. Supports $select and $expand."
            ),
            args_schema=_GetSalesOrderItemInput,
            coroutine=_get_salesorderitem,
            handle_tool_error=True,
        ),
        # 14
        StructuredTool(
            name="count_a_salesorderitem_for_api_sales_order_srv",
            description=(
                "Get the total count of sales order items in A_SalesOrderItem. "
                "Supports $filter to count only matching records."
            ),
            args_schema=_CountSalesOrderItemInput,
            coroutine=_count_salesorderitem,
            handle_tool_error=True,
        ),
        # 15
        StructuredTool(
            name="list_a_salesorderscheduleline_for_api_sales_order_srv",
            description=(
                "Retrieve a list of schedule lines from A_SalesOrderScheduleLine. "
                "Supports $filter, $select, $orderby, $top (max 100), $skip, $expand, $inlinecount."
            ),
            args_schema=_ListScheduleLineInput,
            coroutine=_list_scheduleline,
            handle_tool_error=True,
        ),
        # 16
        StructuredTool(
            name="get_a_salesorderscheduleline_for_api_sales_order_srv",
            description=(
                "Retrieve a single schedule line by key from A_SalesOrderScheduleLine. "
                "Requires SalesOrder, SalesOrderItem, and ScheduleLine keys. Supports $select and $expand."
            ),
            args_schema=_GetScheduleLineInput,
            coroutine=_get_scheduleline,
            handle_tool_error=True,
        ),
        # 17
        StructuredTool(
            name="count_a_salesorderscheduleline_for_api_sales_order_srv",
            description=(
                "Get the total count of schedule lines in A_SalesOrderScheduleLine. "
                "Supports $filter to count only matching records."
            ),
            args_schema=_CountScheduleLineInput,
            coroutine=_count_scheduleline,
            handle_tool_error=True,
        ),
    ]
