"""Tests for app/tools/s4_odata_client.py — Transparent Proxy implementation.

Covers all 9 requirements:
  R1  Proxy configured and destination resolved successfully.
  R2  Proxy environment variable missing → explicit diagnostic ToolException.
  R3  X-destination-name header is present and correct.
  R4  User-token is passed via ConsumptionOptions to the SDK.
  R5  OData query parameters are forwarded unchanged to requests.get.
  R6  HTTP 4xx/5xx errors raise ToolException with status code.
  R7  Timeout raises ToolException with timeout duration.
  R8  create_client called with use_default_proxy=True.
  R9  get_destination called with proxy_enabled=True.

All tests run under IBD_TESTING=1 (set by conftest.py) for the tool layer.
The odata_client tests explicitly clear IBD_TESTING to exercise the real
production code paths, then restore it after each test.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest

# Ensure app/ is on sys.path
_APP = str(Path(__file__).parent.parent / "app")
if _APP not in sys.path:
    sys.path.insert(0, _APP)

from langchain_core.tools import ToolException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proxy_dest(destination_name: str = "S43", proxy_url: str = "http://connectivity-proxy.test-ns"):
    """Return a minimal mock TransparentProxyDestination."""
    dest = MagicMock()
    dest.url = proxy_url
    dest.headers = {"X-destination-name": destination_name}
    return dest


def _make_ok_response(body: str = '{"d":{"results":[]}}'):
    """Return a mock requests.Response with 200 OK."""
    resp = MagicMock()
    resp.status_code = 200
    resp.text = body
    resp.raise_for_status = MagicMock()   # no-op
    return resp


def _make_error_response(status_code: int, body: str = "Bad Request"):
    """Return a mock requests.Response that raises HTTPError on raise_for_status."""
    import requests
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = body
    http_err = requests.exceptions.HTTPError(response=resp)
    resp.raise_for_status = MagicMock(side_effect=http_err)
    return resp


# ---------------------------------------------------------------------------
# Fixture: disable IBD_TESTING for all tests in this file so the production
# code path (not the mock shortcut) is exercised.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _disable_ibd_testing(monkeypatch):
    """Remove IBD_TESTING=1 for each test so production code paths run."""
    monkeypatch.delenv("IBD_TESTING", raising=False)
    yield
    # conftest.py will have set it back via os.environ before this module runs,
    # but monkeypatch restores the original value automatically on teardown.


# ---------------------------------------------------------------------------
# R1 — Proxy configured: destination resolved and request sent
# ---------------------------------------------------------------------------

async def test_r1_proxy_configured_destination_resolved(monkeypatch):
    """R1: When proxy is configured and destination resolves, call_odata returns data."""
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "connectivity-proxy.test-ns")

    proxy_dest = _make_proxy_dest()
    mock_client = MagicMock()
    mock_client.get_destination.return_value = proxy_dest

    ok_response = _make_ok_response('{"d":{"results":[]}}')

    with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
         patch("requests.get", return_value=ok_response) as mock_get:

        from tools.s4_odata_client import call_odata
        result = await call_odata(destination_name="S43", path="A_SalesOrder")

    assert result is not None
    assert len(result) > 0
    mock_get.assert_called_once()


# ---------------------------------------------------------------------------
# R2 — Proxy env var missing → explicit diagnostic ToolException
# ---------------------------------------------------------------------------

async def test_r2_missing_proxy_env_var_raises_tool_exception(monkeypatch):
    """R2: If APPFND_CONHOS_TRANSP_PROXY is absent, raise ToolException with diagnostic message."""
    monkeypatch.delenv("APPFND_CONHOS_TRANSP_PROXY", raising=False)

    from tools.s4_odata_client import call_odata
    with pytest.raises(ToolException) as exc_info:
        await call_odata(destination_name="S43", path="A_SalesOrder")

    msg = str(exc_info.value)
    assert "APPFND_CONHOS_TRANSP_PROXY" in msg, f"Expected env var name in error, got: {msg}"
    assert "not configured" in msg.lower() or "missing" in msg.lower(), \
        f"Expected 'not configured' or 'missing' in error, got: {msg}"


async def test_r2_empty_proxy_env_var_raises_tool_exception(monkeypatch):
    """R2: If APPFND_CONHOS_TRANSP_PROXY is empty string, raise ToolException."""
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "")

    from tools.s4_odata_client import call_odata
    with pytest.raises(ToolException) as exc_info:
        await call_odata(destination_name="S43", path="A_SalesOrder")

    assert "APPFND_CONHOS_TRANSP_PROXY" in str(exc_info.value)


# ---------------------------------------------------------------------------
# R3 — X-destination-name header present and correct
# ---------------------------------------------------------------------------

async def test_r3_x_destination_name_header_sent(monkeypatch):
    """R3: The X-destination-name header is forwarded in the HTTP request."""
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "connectivity-proxy.test-ns")

    proxy_dest = _make_proxy_dest(destination_name="S43")
    mock_client = MagicMock()
    mock_client.get_destination.return_value = proxy_dest

    ok_response = _make_ok_response()
    captured_kwargs: dict = {}

    def capture_get(url, **kwargs):
        captured_kwargs.update(kwargs)
        return ok_response

    with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
         patch("requests.get", side_effect=capture_get):

        from tools.s4_odata_client import call_odata
        await call_odata(destination_name="S43", path="A_SalesOrder")

    headers_sent = captured_kwargs.get("headers", {})
    assert "X-destination-name" in headers_sent, \
        f"X-destination-name missing from request headers: {headers_sent}"
    assert headers_sent["X-destination-name"] == "S43", \
        f"Expected X-destination-name=S43, got: {headers_sent['X-destination-name']}"


async def test_r3_x_destination_name_matches_destination_name_arg(monkeypatch):
    """R3: X-destination-name matches the destination_name argument exactly (case-sensitive)."""
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "connectivity-proxy.test-ns")

    proxy_dest = _make_proxy_dest(destination_name="S43")
    mock_client = MagicMock()
    mock_client.get_destination.return_value = proxy_dest

    captured_headers: dict = {}

    def capture_get(url, **kwargs):
        captured_headers.update(kwargs.get("headers", {}))
        return _make_ok_response()

    with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
         patch("requests.get", side_effect=capture_get):

        from tools.s4_odata_client import call_odata
        await call_odata(destination_name="S43", path="A_SalesOrder")

    # Must be uppercase S43, not s43
    assert captured_headers.get("X-destination-name") == "S43"


# ---------------------------------------------------------------------------
# R4 — User-token propagated via ConsumptionOptions
# ---------------------------------------------------------------------------

async def test_r4_user_token_passed_to_consumption_options(monkeypatch):
    """R4: user_token is passed to ConsumptionOptions, not hardcoded in headers."""
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "connectivity-proxy.test-ns")

    proxy_dest = _make_proxy_dest()
    mock_client = MagicMock()
    mock_client.get_destination.return_value = proxy_dest

    captured_options = {}

    def capture_get_destination(name, options=None, proxy_enabled=False):
        captured_options["options"] = options
        captured_options["proxy_enabled"] = proxy_enabled
        return proxy_dest

    mock_client.get_destination.side_effect = capture_get_destination

    with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
         patch("requests.get", return_value=_make_ok_response()):

        from tools.s4_odata_client import call_odata
        await call_odata(
            destination_name="S43",
            path="A_SalesOrder",
            user_token="eyJhbGciOiJSUzI1NiJ9.test_jwt_token",
        )

    options = captured_options.get("options")
    assert options is not None, "ConsumptionOptions was not passed to get_destination"
    assert options.user_token == "eyJhbGciOiJSUzI1NiJ9.test_jwt_token", \
        f"Expected user_token in ConsumptionOptions, got: {options.user_token}"


async def test_r4_no_user_token_passes_none_options(monkeypatch):
    """R4: When user_token is None, ConsumptionOptions is not passed (options=None)."""
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "connectivity-proxy.test-ns")

    proxy_dest = _make_proxy_dest()
    mock_client = MagicMock()

    captured_options = {}

    def capture_get_destination(name, options=None, proxy_enabled=False):
        captured_options["options"] = options
        return proxy_dest

    mock_client.get_destination.side_effect = capture_get_destination

    with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
         patch("requests.get", return_value=_make_ok_response()):

        from tools.s4_odata_client import call_odata
        await call_odata(destination_name="S43", path="A_SalesOrder", user_token=None)

    assert captured_options.get("options") is None, \
        "ConsumptionOptions should be None when user_token is not provided"


# ---------------------------------------------------------------------------
# R5 — OData query parameters forwarded correctly
# ---------------------------------------------------------------------------

async def test_r5_odata_params_forwarded(monkeypatch):
    """R5: All OData query parameters are passed unchanged to requests.get."""
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "connectivity-proxy.test-ns")

    proxy_dest = _make_proxy_dest()
    mock_client = MagicMock()
    mock_client.get_destination.return_value = proxy_dest

    captured_kwargs: dict = {}

    def capture_get(url, **kwargs):
        captured_kwargs.update(kwargs)
        return _make_ok_response()

    test_params = {
        "$filter": "SalesOrderType eq 'OR'",
        "$select": "SalesOrder,SoldToParty",
        "$expand": "to_Item",
        "$top": "10",
        "$skip": "0",
        "$orderby": "SalesOrder desc",
        "$inlinecount": "allpages",
    }

    with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
         patch("requests.get", side_effect=capture_get):

        from tools.s4_odata_client import call_odata
        await call_odata(destination_name="S43", path="A_SalesOrder", params=test_params)

    actual_params = captured_kwargs.get("params", {})
    for key, value in test_params.items():
        assert actual_params.get(key) == value, \
            f"Expected {key}={value!r}, got {actual_params.get(key)!r}"


async def test_r5_no_params_passes_none(monkeypatch):
    """R5: When no params provided, requests.get receives params=None."""
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "connectivity-proxy.test-ns")

    proxy_dest = _make_proxy_dest()
    mock_client = MagicMock()
    mock_client.get_destination.return_value = proxy_dest

    captured_kwargs: dict = {}

    def capture_get(url, **kwargs):
        captured_kwargs.update(kwargs)
        return _make_ok_response()

    with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
         patch("requests.get", side_effect=capture_get):

        from tools.s4_odata_client import call_odata
        await call_odata(destination_name="S43", path="A_SalesOrder")

    assert captured_kwargs.get("params") is None, \
        f"Expected params=None for empty params, got: {captured_kwargs.get('params')}"


# ---------------------------------------------------------------------------
# R6 — HTTP errors raise ToolException with status code
# ---------------------------------------------------------------------------

async def test_r6_http_401_raises_tool_exception(monkeypatch):
    """R6: HTTP 401 raises ToolException containing the status code."""
    import requests as req_lib
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "connectivity-proxy.test-ns")

    proxy_dest = _make_proxy_dest()
    mock_client = MagicMock()
    mock_client.get_destination.return_value = proxy_dest

    err_resp = _make_error_response(401, "Unauthorized")

    with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
         patch("requests.get", return_value=err_resp):

        from tools.s4_odata_client import call_odata
        with pytest.raises(ToolException) as exc_info:
            await call_odata(destination_name="S43", path="A_SalesOrder")

    assert "401" in str(exc_info.value), f"Expected 401 in error, got: {exc_info.value}"


async def test_r6_http_404_raises_tool_exception(monkeypatch):
    """R6: HTTP 404 raises ToolException containing the status code."""
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "connectivity-proxy.test-ns")

    proxy_dest = _make_proxy_dest()
    mock_client = MagicMock()
    mock_client.get_destination.return_value = proxy_dest

    err_resp = _make_error_response(404, "Not Found")

    with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
         patch("requests.get", return_value=err_resp):

        from tools.s4_odata_client import call_odata
        with pytest.raises(ToolException) as exc_info:
            await call_odata(destination_name="S43", path="A_SalesOrder('99999')")

    assert "404" in str(exc_info.value)


async def test_r6_http_500_raises_tool_exception(monkeypatch):
    """R6: HTTP 500 raises ToolException containing the status code."""
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "connectivity-proxy.test-ns")

    proxy_dest = _make_proxy_dest()
    mock_client = MagicMock()
    mock_client.get_destination.return_value = proxy_dest

    err_resp = _make_error_response(500, "Internal Server Error")

    with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
         patch("requests.get", return_value=err_resp):

        from tools.s4_odata_client import call_odata
        with pytest.raises(ToolException) as exc_info:
            await call_odata(destination_name="S43", path="A_SalesOrder")

    assert "500" in str(exc_info.value)


# ---------------------------------------------------------------------------
# R7 — Timeout raises ToolException with timeout duration
# ---------------------------------------------------------------------------

async def test_r7_timeout_raises_tool_exception(monkeypatch):
    """R7: requests.Timeout raises ToolException mentioning the timeout duration."""
    import requests as req_lib
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "connectivity-proxy.test-ns")

    proxy_dest = _make_proxy_dest()
    mock_client = MagicMock()
    mock_client.get_destination.return_value = proxy_dest

    with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
         patch("requests.get", side_effect=req_lib.exceptions.Timeout("timed out")):

        from tools.s4_odata_client import call_odata
        with pytest.raises(ToolException) as exc_info:
            await call_odata(destination_name="S43", path="A_SalesOrder")

    msg = str(exc_info.value)
    assert "timed out" in msg.lower() or "timeout" in msg.lower(), \
        f"Expected timeout message, got: {msg}"
    # Should reference the configured timeout value
    from util import MCP_CALL_TIMEOUT_SECONDS
    assert str(int(MCP_CALL_TIMEOUT_SECONDS)) in msg or str(MCP_CALL_TIMEOUT_SECONDS) in msg, \
        f"Expected timeout duration ({MCP_CALL_TIMEOUT_SECONDS}s) in message: {msg}"


async def test_r7_connection_error_raises_tool_exception(monkeypatch):
    """R7: ConnectionError raises ToolException with diagnostic proxy info."""
    import requests as req_lib
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "connectivity-proxy.test-ns")

    proxy_dest = _make_proxy_dest(proxy_url="http://connectivity-proxy.test-ns")
    mock_client = MagicMock()
    mock_client.get_destination.return_value = proxy_dest

    with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
         patch("requests.get", side_effect=req_lib.exceptions.ConnectionError("connection refused")):

        from tools.s4_odata_client import call_odata
        with pytest.raises(ToolException) as exc_info:
            await call_odata(destination_name="S43", path="A_SalesOrder")

    msg = str(exc_info.value)
    assert "proxy" in msg.lower() or "connect" in msg.lower(), \
        f"Expected connection/proxy info in error: {msg}"


# ---------------------------------------------------------------------------
# R8 — create_client called with use_default_proxy=True
# ---------------------------------------------------------------------------

async def test_r8_create_client_called_with_use_default_proxy_true(monkeypatch):
    """R8: create_client is called with use_default_proxy=True."""
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "connectivity-proxy.test-ns")

    proxy_dest = _make_proxy_dest()
    mock_client = MagicMock()
    mock_client.get_destination.return_value = proxy_dest

    with patch("tools.s4_odata_client.create_client", return_value=mock_client) as mock_create, \
         patch("requests.get", return_value=_make_ok_response()):

        from tools.s4_odata_client import call_odata
        await call_odata(destination_name="S43", path="A_SalesOrder")

    mock_create.assert_called_once_with(use_default_proxy=True)


# ---------------------------------------------------------------------------
# R9 — get_destination called with proxy_enabled=True
# ---------------------------------------------------------------------------

async def test_r9_get_destination_called_with_proxy_enabled_true(monkeypatch):
    """R9: get_destination is called with proxy_enabled=True."""
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "connectivity-proxy.test-ns")

    proxy_dest = _make_proxy_dest()
    mock_client = MagicMock()

    captured_kwargs: dict = {}

    def capture_get_destination(name, options=None, proxy_enabled=False):
        captured_kwargs["name"] = name
        captured_kwargs["proxy_enabled"] = proxy_enabled
        return proxy_dest

    mock_client.get_destination.side_effect = capture_get_destination

    with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
         patch("requests.get", return_value=_make_ok_response()):

        from tools.s4_odata_client import call_odata
        await call_odata(destination_name="S43", path="A_SalesOrder")

    assert captured_kwargs.get("proxy_enabled") is True, \
        f"Expected proxy_enabled=True, got: {captured_kwargs.get('proxy_enabled')}"
    assert captured_kwargs.get("name") == "S43"


# ---------------------------------------------------------------------------
# Additional — OData path routing through proxy URL
# ---------------------------------------------------------------------------

async def test_request_url_contains_proxy_host_and_odata_path(monkeypatch):
    """The request URL must start with the proxy host, not the S/4HANA virtual host."""
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "connectivity-proxy.test-ns")

    proxy_dest = _make_proxy_dest(proxy_url="http://connectivity-proxy.test-ns")
    mock_client = MagicMock()
    mock_client.get_destination.return_value = proxy_dest

    captured_url: list = []

    def capture_get(url, **kwargs):
        captured_url.append(url)
        return _make_ok_response()

    with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
         patch("requests.get", side_effect=capture_get):

        from tools.s4_odata_client import call_odata
        await call_odata(destination_name="S43", path="A_SalesOrder")

    assert len(captured_url) == 1
    url = captured_url[0]
    assert url.startswith("http://connectivity-proxy.test-ns"), \
        f"URL should start with proxy host, got: {url}"
    assert "A_SalesOrder" in url, f"URL should contain OData path, got: {url}"
    assert "API_SALES_ORDER_SRV" in url, f"URL should contain OData service path, got: {url}"


async def test_missing_x_destination_name_header_raises_tool_exception(monkeypatch):
    """If SDK returns proxy dest without X-destination-name, raise ToolException."""
    monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "connectivity-proxy.test-ns")

    # Proxy dest missing the required header
    bad_dest = MagicMock()
    bad_dest.url = "http://connectivity-proxy.test-ns"
    bad_dest.headers = {}  # no X-destination-name

    mock_client = MagicMock()
    mock_client.get_destination.return_value = bad_dest

    with patch("tools.s4_odata_client.create_client", return_value=mock_client):
        from tools.s4_odata_client import call_odata
        with pytest.raises(ToolException) as exc_info:
            await call_odata(destination_name="S43", path="A_SalesOrder")

    assert "X-destination-name" in str(exc_info.value)
