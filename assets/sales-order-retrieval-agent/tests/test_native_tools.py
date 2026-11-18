"""Tests for all 17 native Python OData tools (tools/sales_order_tools.py).

Runs under IBD_TESTING=1 (set by conftest.py) so:
- call_odata() returns mock JSON responses (no network calls)
- Destination SDK switches to LocalDevDestinationClient (mocks/destination.json)

Each test verifies:
1. The tool is registered in get_native_tools() with the correct name
2. The tool coroutine can be called without error
3. The response is a non-empty string
4. OData parameters are passed correctly (filter, select, top etc.)
"""
from __future__ import annotations

import json
import pytest
from langchain_core.tools import StructuredTool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _path(add_agent_to_path):
    """Ensure app/ is on sys.path (via conftest add_agent_to_path fixture)."""
    return _path


@pytest.fixture(scope="module")
def native_tools(add_agent_to_path) -> dict[str, StructuredTool]:
    """Return a dict of tool_name -> StructuredTool for all 17 tools."""
    from tools.sales_order_tools import get_native_tools
    return {t.name: t for t in get_native_tools()}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _invoke(tool: StructuredTool, **kwargs) -> str:
    """Call a tool's coroutine directly."""
    return await tool.coroutine(**kwargs)


def _parse(result: str) -> dict:
    """Parse JSON result, return empty dict on failure."""
    try:
        return json.loads(result)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# 1. Registry completeness — all 17 tools present
# ---------------------------------------------------------------------------

EXPECTED_TOOL_NAMES = [
    "get_metadata_api_sales_order_srv",
    "batch_for_api_sales_order_srv",
    "list_a_salesorder_for_api_sales_order_srv",
    "get_a_salesorder_for_api_sales_order_srv",
    "count_a_salesorder_for_api_sales_order_srv",
    "get_a_salesorderbillingplan_for_api_sales_order_srv",
    "list_a_salesorderbillingplanitem_for_api_sales_order_srv",
    "get_a_salesorderbillingplanitem_for_api_sales_order_srv",
    "list_a_salesorderheaderpartner_for_api_sales_order_srv",
    "get_a_salesorderheaderpartner_for_api_sales_order_srv",
    "count_a_salesorderheaderpartner_for_api_sales_order_srv",
    "list_a_salesorderitem_for_api_sales_order_srv",
    "get_a_salesorderitem_for_api_sales_order_srv",
    "count_a_salesorderitem_for_api_sales_order_srv",
    "list_a_salesorderscheduleline_for_api_sales_order_srv",
    "get_a_salesorderscheduleline_for_api_sales_order_srv",
    "count_a_salesorderscheduleline_for_api_sales_order_srv",
]


def test_all_17_tools_registered(native_tools):
    """All 17 tools must be present in get_native_tools()."""
    assert len(native_tools) == 17, f"Expected 17 tools, got {len(native_tools)}: {list(native_tools.keys())}"
    for name in EXPECTED_TOOL_NAMES:
        assert name in native_tools, f"Tool '{name}' missing from get_native_tools()"


def test_all_tools_are_structured_tools(native_tools):
    """Every tool must be a StructuredTool with handle_tool_error=True."""
    for name, tool in native_tools.items():
        assert isinstance(tool, StructuredTool), f"'{name}' is not a StructuredTool"
        assert tool.handle_tool_error is True, f"'{name}' missing handle_tool_error=True"


def test_all_tools_have_descriptions(native_tools):
    """Every tool must have a non-empty description."""
    for name, tool in native_tools.items():
        assert tool.description and len(tool.description) > 10, f"'{name}' has empty/short description"


def test_all_tools_have_coroutines(native_tools):
    """Every tool must be async (have a coroutine)."""
    for name, tool in native_tools.items():
        assert tool.coroutine is not None, f"'{name}' has no coroutine (not async)"


# ---------------------------------------------------------------------------
# 2. Tool 1 — get_metadata_api_sales_order_srv
# ---------------------------------------------------------------------------

async def test_get_metadata(native_tools):
    result = await _invoke(native_tools["get_metadata_api_sales_order_srv"])
    assert result is not None and len(result) > 0


# ---------------------------------------------------------------------------
# 3. Tool 2 — batch_for_api_sales_order_srv
# ---------------------------------------------------------------------------

async def test_batch(native_tools):
    result = await _invoke(native_tools["batch_for_api_sales_order_srv"])
    assert result is not None and len(result) > 0


# ---------------------------------------------------------------------------
# 4. Tool 3 — list_a_salesorder
# ---------------------------------------------------------------------------

async def test_list_salesorder_no_params(native_tools):
    result = await _invoke(native_tools["list_a_salesorder_for_api_sales_order_srv"])
    assert isinstance(result, str) and len(result) > 0


async def test_list_salesorder_with_filter(native_tools):
    result = await _invoke(
        native_tools["list_a_salesorder_for_api_sales_order_srv"],
        filter="SoldToParty eq 'C1'",
        top=10,
    )
    assert isinstance(result, str)


async def test_list_salesorder_with_select_expand(native_tools):
    result = await _invoke(
        native_tools["list_a_salesorder_for_api_sales_order_srv"],
        select="SalesOrder,SalesOrderType",
        expand="to_Item",
        top=5,
        skip=0,
    )
    assert isinstance(result, str)


async def test_list_salesorder_top_capped_at_100(native_tools):
    """$top values > 100 must be capped to 100."""
    from unittest.mock import patch, AsyncMock
    captured_params = {}

    async def mock_call_odata(**kwargs):
        captured_params.update(kwargs.get("params", {}))
        return '{"d":{"results":[]}}'

    with patch("tools.sales_order_tools.call_odata", side_effect=mock_call_odata):
        await _invoke(
            native_tools["list_a_salesorder_for_api_sales_order_srv"],
            top=500,
        )
    assert captured_params.get("$top") == "100", f"Expected $top=100, got {captured_params.get('$top')}"


# ---------------------------------------------------------------------------
# 5. Tool 4 — get_a_salesorder (by key)
# ---------------------------------------------------------------------------

async def test_get_salesorder_by_key(native_tools):
    result = await _invoke(
        native_tools["get_a_salesorder_for_api_sales_order_srv"],
        salesorder="10",
    )
    assert isinstance(result, str) and len(result) > 0


async def test_get_salesorder_with_expand(native_tools):
    result = await _invoke(
        native_tools["get_a_salesorder_for_api_sales_order_srv"],
        salesorder="10",
        expand="to_Item,to_Partner",
        select="SalesOrder,SalesOrderType,SoldToParty",
    )
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 6. Tool 5 — count_a_salesorder
# ---------------------------------------------------------------------------

async def test_count_salesorder_no_filter(native_tools):
    result = await _invoke(native_tools["count_a_salesorder_for_api_sales_order_srv"])
    assert isinstance(result, str)


async def test_count_salesorder_with_filter(native_tools):
    result = await _invoke(
        native_tools["count_a_salesorder_for_api_sales_order_srv"],
        filter="SalesOrderType eq 'OR'",
    )
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 7. Tool 6 — get_a_salesorderbillingplan (by key)
# ---------------------------------------------------------------------------

async def test_get_billingplan_by_key(native_tools):
    result = await _invoke(
        native_tools["get_a_salesorderbillingplan_for_api_sales_order_srv"],
        salesorder="10",
        billingplan="1",
    )
    assert isinstance(result, str) and len(result) > 0


# ---------------------------------------------------------------------------
# 8. Tool 7 — list_a_salesorderbillingplanitem
# ---------------------------------------------------------------------------

async def test_list_billingplanitem(native_tools):
    result = await _invoke(
        native_tools["list_a_salesorderbillingplanitem_for_api_sales_order_srv"],
        filter="SalesOrder eq '10'",
        top=10,
    )
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 9. Tool 8 — get_a_salesorderbillingplanitem (by key)
# ---------------------------------------------------------------------------

async def test_get_billingplanitem_by_key(native_tools):
    result = await _invoke(
        native_tools["get_a_salesorderbillingplanitem_for_api_sales_order_srv"],
        salesorder="10",
        billingplan="1",
        billingplanitem="1",
    )
    assert isinstance(result, str) and len(result) > 0


# ---------------------------------------------------------------------------
# 10. Tool 9 — list_a_salesorderheaderpartner
# ---------------------------------------------------------------------------

async def test_list_headerpartner(native_tools):
    result = await _invoke(
        native_tools["list_a_salesorderheaderpartner_for_api_sales_order_srv"],
        filter="SalesOrder eq '10'",
        top=10,
    )
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 11. Tool 10 — get_a_salesorderheaderpartner (by key)
# ---------------------------------------------------------------------------

async def test_get_headerpartner_by_key(native_tools):
    result = await _invoke(
        native_tools["get_a_salesorderheaderpartner_for_api_sales_order_srv"],
        salesorder="10",
        partnerfunction="AG",
    )
    assert isinstance(result, str) and len(result) > 0


# ---------------------------------------------------------------------------
# 12. Tool 11 — count_a_salesorderheaderpartner
# ---------------------------------------------------------------------------

async def test_count_headerpartner(native_tools):
    result = await _invoke(
        native_tools["count_a_salesorderheaderpartner_for_api_sales_order_srv"],
        filter="SalesOrder eq '10'",
    )
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 13. Tool 12 — list_a_salesorderitem
# ---------------------------------------------------------------------------

async def test_list_salesorderitem(native_tools):
    result = await _invoke(
        native_tools["list_a_salesorderitem_for_api_sales_order_srv"],
        filter="SalesOrder eq '10'",
        top=10,
    )
    assert isinstance(result, str)


async def test_list_salesorderitem_all_params(native_tools):
    result = await _invoke(
        native_tools["list_a_salesorderitem_for_api_sales_order_srv"],
        filter="SalesOrder eq '10'",
        select="SalesOrder,SalesOrderItem,Material",
        orderby="SalesOrderItem asc",
        top=50,
        skip=0,
        expand="to_ScheduleLine",
        inlinecount="allpages",
    )
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 14. Tool 13 — get_a_salesorderitem (by key)
# ---------------------------------------------------------------------------

async def test_get_salesorderitem_by_key(native_tools):
    result = await _invoke(
        native_tools["get_a_salesorderitem_for_api_sales_order_srv"],
        salesorder="10",
        salesorderitem="10",
    )
    assert isinstance(result, str) and len(result) > 0


# ---------------------------------------------------------------------------
# 15. Tool 14 — count_a_salesorderitem
# ---------------------------------------------------------------------------

async def test_count_salesorderitem(native_tools):
    result = await _invoke(
        native_tools["count_a_salesorderitem_for_api_sales_order_srv"],
        filter="SalesOrder eq '10'",
    )
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 16. Tool 15 — list_a_salesorderscheduleline
# ---------------------------------------------------------------------------

async def test_list_scheduleline(native_tools):
    result = await _invoke(
        native_tools["list_a_salesorderscheduleline_for_api_sales_order_srv"],
        filter="SalesOrder eq '10'",
        top=10,
    )
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 17. Tool 16 — get_a_salesorderscheduleline (by key)
# ---------------------------------------------------------------------------

async def test_get_scheduleline_by_key(native_tools):
    result = await _invoke(
        native_tools["get_a_salesorderscheduleline_for_api_sales_order_srv"],
        salesorder="10",
        salesorderitem="10",
        scheduleline="1",
    )
    assert isinstance(result, str) and len(result) > 0


# ---------------------------------------------------------------------------
# 18. Tool 17 — count_a_salesorderscheduleline
# ---------------------------------------------------------------------------

async def test_count_scheduleline(native_tools):
    result = await _invoke(
        native_tools["count_a_salesorderscheduleline_for_api_sales_order_srv"],
        filter="SalesOrder eq '10'",
    )
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 19. OData client parameter passing tests
# ---------------------------------------------------------------------------

async def test_odata_params_filter_passed_correctly(native_tools):
    """Verify $filter is passed to call_odata correctly."""
    from unittest.mock import patch

    captured = {}

    async def mock_call_odata(**kwargs):
        captured.update(kwargs)
        return '{"d":{"results":[]}}'

    with patch("tools.sales_order_tools.call_odata", side_effect=mock_call_odata):
        await _invoke(
            native_tools["list_a_salesorder_for_api_sales_order_srv"],
            filter="SalesOrderType eq 'OR'",
        )

    assert captured["path"] == "A_SalesOrder"
    assert captured["params"]["$filter"] == "SalesOrderType eq 'OR'"
    assert captured["destination_name"] == "s43"


async def test_odata_key_path_built_correctly(native_tools):
    """Verify key-based path is built correctly for get_a_salesorder."""
    from unittest.mock import patch

    captured = {}

    async def mock_call_odata(**kwargs):
        captured.update(kwargs)
        return '{"d":{}}'

    with patch("tools.sales_order_tools.call_odata", side_effect=mock_call_odata):
        await _invoke(
            native_tools["get_a_salesorder_for_api_sales_order_srv"],
            salesorder="1234567",
        )

    assert captured["path"] == "A_SalesOrder('1234567')"
    assert captured["destination_name"] == "s43"


async def test_odata_count_path_correct(native_tools):
    """Verify $count path is built correctly."""
    from unittest.mock import patch

    captured = {}

    async def mock_call_odata(**kwargs):
        captured.update(kwargs)
        return "42"

    with patch("tools.sales_order_tools.call_odata", side_effect=mock_call_odata):
        await _invoke(native_tools["count_a_salesorder_for_api_sales_order_srv"])

    assert captured["path"] == "A_SalesOrder/$count"


async def test_schedule_line_composite_key_path(native_tools):
    """Verify composite key path for schedule line is correct."""
    from unittest.mock import patch

    captured = {}

    async def mock_call_odata(**kwargs):
        captured.update(kwargs)
        return '{"d":{}}'

    with patch("tools.sales_order_tools.call_odata", side_effect=mock_call_odata):
        await _invoke(
            native_tools["get_a_salesorderscheduleline_for_api_sales_order_srv"],
            salesorder="10",
            salesorderitem="20",
            scheduleline="1",
        )

    assert captured["path"] == "A_SalesOrderScheduleLine(SalesOrder='10',SalesOrderItem='20',ScheduleLine='1')"
