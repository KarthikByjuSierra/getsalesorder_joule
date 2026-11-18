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
    assert captured["destination_name"] == "S43"


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
    assert captured["destination_name"] == "S43"


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


# ---------------------------------------------------------------------------
# 20. Transparent Proxy tests (s4_odata_client._sync_odata_get / call_odata)
# ---------------------------------------------------------------------------

class _FakeProxyDest:
    """Minimal stand-in for TransparentProxyDestination."""
    def __init__(self, url="http://conn-proxy.ns", dest_name="S43"):
        self.url = url
        self.headers = {"X-destination-name": dest_name}


def _make_mock_response(text: str = '{"d":{"results":[]}}', status: int = 200):
    """Create a mock requests.Response."""
    from unittest.mock import MagicMock
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.raise_for_status = MagicMock()
    if status >= 400:
        import requests as _r
        http_err = _r.exceptions.HTTPError(response=resp)
        resp.raise_for_status.side_effect = http_err
    return resp


def test_proxy_configured_and_destination_resolved(monkeypatch):
    """Happy path: proxy env var set, destination resolved, GET succeeds."""
    from unittest.mock import patch, MagicMock
    import tools.s4_odata_client as client_mod

    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "conn-proxy.namespace")

    mock_dest = _FakeProxyDest()
    mock_sdk_client = MagicMock()
    mock_sdk_client.get_destination.return_value = mock_dest

    with patch.object(client_mod, "create_client", return_value=mock_sdk_client), \
         patch.object(client_mod._requests, "get", return_value=_make_mock_response()) as mock_get:

        result = client_mod._sync_odata_get("S43", "A_SalesOrder", {}, None)

    assert result == '{"d":{"results":[]}}'
    mock_sdk_client.get_destination.assert_called_once()
    mock_get.assert_called_once()


def test_proxy_env_var_missing_raises_tool_exception(monkeypatch):
    """If APPFND_CONHOS_TRANSP_PROXY is absent, ToolException with diagnostic message."""
    from langchain_core.tools import ToolException
    import tools.s4_odata_client as client_mod

    monkeypatch.delenv("APPFND_CONHOS_TRANSP_PROXY", raising=False)

    with pytest.raises(ToolException) as exc_info:
        client_mod._sync_odata_get("S43", "A_SalesOrder", {}, None)

    msg = str(exc_info.value)
    assert "APPFND_CONHOS_TRANSP_PROXY" in msg
    assert "missing" in msg.lower() or "not configured" in msg.lower()


def test_x_destination_name_header_present(monkeypatch):
    """The X-destination-name header must be present in the outbound request."""
    from unittest.mock import patch, MagicMock, call
    import tools.s4_odata_client as client_mod

    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "conn-proxy.namespace")

    mock_dest = _FakeProxyDest(dest_name="S43")
    mock_sdk_client = MagicMock()
    mock_sdk_client.get_destination.return_value = mock_dest

    with patch.object(client_mod, "create_client", return_value=mock_sdk_client), \
         patch.object(client_mod._requests, "get", return_value=_make_mock_response()) as mock_get:

        client_mod._sync_odata_get("S43", "A_SalesOrder", {}, None)

    _, kwargs = mock_get.call_args
    sent_headers = kwargs.get("headers", {})
    assert "X-destination-name" in sent_headers
    assert sent_headers["X-destination-name"] == "S43"


def test_user_token_propagated_to_sdk(monkeypatch):
    """User JWT must be forwarded as Authorization: Bearer header on the proxy request.

    SDK 0.62.0 confirmed: ConsumptionOptions is silently discarded in proxy mode
    (client.py returns TransparentProxyDestination immediately when proxy_enabled=True).
    User identity is propagated via proxy_dest.set_header(AUTHORIZATION, "Bearer <jwt>").
    """
    from unittest.mock import patch, MagicMock
    import tools.s4_odata_client as client_mod
    from sap_cloud_sdk.destination import (
        TransparentProxyDestination, TransparentProxy
    )

    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "conn-proxy.namespace")

    # Use a real TransparentProxyDestination so set_header() actually works
    real_proxy_dest = TransparentProxyDestination.from_proxy(
        "S43", TransparentProxy("conn-proxy", "namespace")
    )
    mock_sdk_client = MagicMock()
    mock_sdk_client.get_destination.return_value = real_proxy_dest

    test_token = "eyJhbGciOiJSUzI1NiJ9.test.token"
    captured_headers: dict = {}

    def capture_get(url, **kwargs):
        captured_headers.update(kwargs.get("headers", {}))
        return _make_mock_response()

    with patch.object(client_mod, "create_client", return_value=mock_sdk_client), \
         patch.object(client_mod._requests, "get", side_effect=capture_get):

        client_mod._sync_odata_get("S43", "A_SalesOrder", {}, test_token)

    # Authorization: Bearer <jwt> must be present
    assert "Authorization" in captured_headers, \
        f"Authorization header missing from proxy request: {captured_headers}"
    assert captured_headers["Authorization"] == f"Bearer {test_token}", \
        f"Wrong Authorization value: {captured_headers['Authorization']}"
    # ConsumptionOptions must NOT be passed to get_destination in proxy mode
    _, kwargs = mock_sdk_client.get_destination.call_args
    assert kwargs.get("options") is None, \
        f"ConsumptionOptions must not be passed in proxy mode, got: {kwargs.get('options')}"


def test_odata_query_params_forwarded(monkeypatch):
    """OData query params must be forwarded as URL query string."""
    from unittest.mock import patch, MagicMock
    import tools.s4_odata_client as client_mod

    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "conn-proxy.namespace")

    mock_dest = _FakeProxyDest()
    mock_sdk_client = MagicMock()
    mock_sdk_client.get_destination.return_value = mock_dest

    params = {"$filter": "SalesOrderType eq 'OR'", "$top": "10", "$select": "SalesOrder"}

    with patch.object(client_mod, "create_client", return_value=mock_sdk_client), \
         patch.object(client_mod._requests, "get", return_value=_make_mock_response()) as mock_get:

        client_mod._sync_odata_get("S43", "A_SalesOrder", params, None)

    _, kwargs = mock_get.call_args
    sent_params = kwargs.get("params", {})
    assert sent_params["$filter"] == "SalesOrderType eq 'OR'"
    assert sent_params["$top"] == "10"
    assert sent_params["$select"] == "SalesOrder"


def test_http_error_raises_tool_exception(monkeypatch):
    """HTTP 404 from proxy must raise ToolException with status info."""
    from unittest.mock import patch, MagicMock
    from langchain_core.tools import ToolException
    import tools.s4_odata_client as client_mod

    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "conn-proxy.namespace")

    mock_dest = _FakeProxyDest()
    mock_sdk_client = MagicMock()
    mock_sdk_client.get_destination.return_value = mock_dest

    with patch.object(client_mod, "create_client", return_value=mock_sdk_client), \
         patch.object(client_mod._requests, "get", return_value=_make_mock_response(status=404)):

        with pytest.raises(ToolException) as exc_info:
            client_mod._sync_odata_get("S43", "A_SalesOrder", {}, None)

    assert "404" in str(exc_info.value) or "HTTP" in str(exc_info.value)


def test_timeout_raises_tool_exception(monkeypatch):
    """Timeout must raise ToolException with timeout info."""
    from unittest.mock import patch, MagicMock
    from langchain_core.tools import ToolException
    import tools.s4_odata_client as client_mod
    import requests as _r

    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "conn-proxy.namespace")

    mock_dest = _FakeProxyDest()
    mock_sdk_client = MagicMock()
    mock_sdk_client.get_destination.return_value = mock_dest

    with patch.object(client_mod, "create_client", return_value=mock_sdk_client), \
         patch.object(client_mod._requests, "get", side_effect=_r.exceptions.Timeout()):

        with pytest.raises(ToolException) as exc_info:
            client_mod._sync_odata_get("S43", "A_SalesOrder", {}, None)

    assert "timed out" in str(exc_info.value).lower()


def test_connection_error_raises_tool_exception(monkeypatch):
    """ConnectionError must raise ToolException with proxy address info."""
    from unittest.mock import patch, MagicMock
    from langchain_core.tools import ToolException
    import tools.s4_odata_client as client_mod
    import requests as _r

    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "conn-proxy.namespace")

    mock_dest = _FakeProxyDest(url="http://conn-proxy.namespace")
    mock_sdk_client = MagicMock()
    mock_sdk_client.get_destination.return_value = mock_dest

    with patch.object(client_mod, "create_client", return_value=mock_sdk_client), \
         patch.object(client_mod._requests, "get", side_effect=_r.exceptions.ConnectionError("refused")):

        with pytest.raises(ToolException) as exc_info:
            client_mod._sync_odata_get("S43", "A_SalesOrder", {}, None)

    msg = str(exc_info.value)
    assert "conn-proxy" in msg or "Transparent Proxy" in msg or "connect" in msg.lower()
