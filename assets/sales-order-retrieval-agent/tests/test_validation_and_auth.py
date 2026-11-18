"""Comprehensive tests for authentication flow, input validation, batch, and concurrency.

Covers:
  AUTH-1   JWT flows from JWTContextMiddleware → ContextVar → _token() → call_odata().
  AUTH-2   Concurrent requests carry independent JWTs — no cross-request leakage.
  AUTH-3   Missing JWT (unauthenticated request) is handled without error at tool layer.
  AUTH-4   Malformed Authorization header (not "Bearer <token>") results in token=None.
  AUTH-5   JWT is never logged (checked across all log records).
  AUTH-6   ContextVar is correctly reset after each request via reset_user_token().

  BATCH-1  batch_for_api_sales_order_srv raises ToolException with "not supported" message.
  BATCH-2  Batch tool description explicitly states it is NOT SUPPORTED.

  PAGINATION-1  Negative $top raises ToolException.
  PAGINATION-2  Negative $skip raises ToolException.
  PAGINATION-3  $top > 100 is clamped to 100.
  PAGINATION-4  $top = 0 is clamped to 1.
  PAGINATION-5  $top = None passes through without error.
  PAGINATION-6  $skip = 0 is valid.
  PAGINATION-7  $skip = None passes through without error.

  ESCAPE-1  Apostrophe in salesorder key is doubled (OData V2 escaping).
  ESCAPE-2  Apostrophe in composite key parts is doubled.
  ESCAPE-3  Normal alphanumeric values are unchanged.
  ESCAPE-4  Multiple apostrophes are all escaped.

  PROXY-1   X-destination-name header is "S43" (uppercase).
  PROXY-2   proxy_dest.url is not the S/4HANA virtual host.
  PROXY-3   Authorization header present when user_token is provided.
  PROXY-4   Authorization header absent when user_token is None.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from contextvars import copy_context
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_APP = str(Path(__file__).parent.parent / "app")
if _APP not in sys.path:
    sys.path.insert(0, _APP)

from langchain_core.tools import ToolException, StructuredTool


# ---------------------------------------------------------------------------
# Helpers shared across auth and proxy tests
# ---------------------------------------------------------------------------

def _make_proxy_dest(dest_name: str = "S43", proxy_url: str = "http://conn-proxy.ns"):
    """Return a minimal mock TransparentProxyDestination."""
    dest = MagicMock()
    dest.url = proxy_url
    dest.headers = {"X-destination-name": dest_name}
    return dest


def _make_ok_response(body: str = '{"d":{"results":[]}}'):
    resp = MagicMock()
    resp.status_code = 200
    resp.text = body
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# AUTH — JWT flow through middleware → ContextVar → tools
# ---------------------------------------------------------------------------

class TestJWTContextFlow:
    """AUTH-1: JWT set by middleware is accessible to tool layer via ContextVar."""

    def test_set_and_get_user_token_roundtrip(self):
        """set_user_token() / get_user_token() must return the same value."""
        from mcp_providers.agw import set_user_token, get_user_token, reset_user_token
        token_ctx = set_user_token("eyJhbGciOiJSUzI1NiJ9.test")
        try:
            assert get_user_token() == "eyJhbGciOiJSUzI1NiJ9.test"
        finally:
            reset_user_token(token_ctx)

    def test_reset_restores_previous_value(self):
        """reset_user_token() must restore the previous ContextVar value."""
        from mcp_providers.agw import set_user_token, get_user_token, reset_user_token
        token_ctx = set_user_token("first_token")
        inner_ctx = set_user_token("second_token")
        assert get_user_token() == "second_token"
        reset_user_token(inner_ctx)
        assert get_user_token() == "first_token"
        reset_user_token(token_ctx)
        assert get_user_token() is None

    def test_token_is_none_before_set(self):
        """Before any set_user_token() call, get_user_token() must return None."""
        from mcp_providers.agw import get_user_token
        # In IBD_TESTING mode and no token set → None
        assert get_user_token() is None

    async def test_token_propagates_to_call_odata(self, monkeypatch):
        """AUTH-1: JWT set via set_user_token() must reach call_odata(user_token=...)."""
        from mcp_providers.agw import set_user_token, reset_user_token

        monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "conn-proxy.ns")
        captured: dict = {}

        async def mock_call_odata(**kwargs):
            captured["user_token"] = kwargs.get("user_token")
            return '{"d":{"results":[]}}'

        secret_jwt = "eyJhbGciOiJSUzI1NiJ9.user_specific_jwt"
        token_ctx = set_user_token(secret_jwt)
        try:
            with patch("tools.sales_order_tools.call_odata", side_effect=mock_call_odata):
                from tools.sales_order_tools import _token, _list_salesorder
                # Verify _token() reads from ContextVar
                assert _token() == secret_jwt
                # Verify tool passes it to call_odata
                await _list_salesorder()
        finally:
            reset_user_token(token_ctx)

        assert captured["user_token"] == secret_jwt, \
            f"JWT not propagated: {captured.get('user_token')}"


class TestConcurrentJWTIsolation:
    """AUTH-2: Concurrent requests must not leak JWTs between async tasks."""

    async def test_concurrent_requests_independent_tokens(self):
        """Two concurrent tasks must each see only their own JWT."""
        from mcp_providers.agw import set_user_token, get_user_token, reset_user_token

        results: dict[str, str | None] = {}

        async def task(name: str, jwt: str):
            tok_ctx = set_user_token(jwt)
            try:
                await asyncio.sleep(0)  # yield — allow other task to run
                results[name] = get_user_token()
            finally:
                reset_user_token(tok_ctx)

        # Run both tasks concurrently in the same event loop
        await asyncio.gather(
            task("user_a", "jwt_for_user_A"),
            task("user_b", "jwt_for_user_B"),
        )

        assert results["user_a"] == "jwt_for_user_A", \
            f"User A got wrong token: {results['user_a']}"
        assert results["user_b"] == "jwt_for_user_B", \
            f"User B got wrong token: {results['user_b']}"

    async def test_concurrent_different_jwts_no_cross_contamination(self):
        """10 concurrent tasks must each receive only their own JWT."""
        from mcp_providers.agw import set_user_token, get_user_token, reset_user_token

        N = 10
        seen: list[tuple[str, str | None]] = []
        lock = asyncio.Lock()

        async def worker(user_id: int):
            jwt = f"jwt_user_{user_id}"
            tok_ctx = set_user_token(jwt)
            try:
                await asyncio.sleep(0)
                observed = get_user_token()
                async with lock:
                    seen.append((jwt, observed))
            finally:
                reset_user_token(tok_ctx)

        await asyncio.gather(*[worker(i) for i in range(N)])

        for expected, observed in seen:
            assert expected == observed, \
                f"Token leakage: expected {expected!r}, got {observed!r}"


class TestMissingAndMalformedJWT:
    """AUTH-3/4: Missing and malformed tokens must be handled gracefully."""

    def test_missing_auth_header_gives_none_token(self, monkeypatch):
        """AUTH-3: No Authorization header → token is None, not an error."""
        from mcp_providers.agw import set_user_token, get_user_token, reset_user_token
        # Simulate middleware receiving no auth header
        tok_ctx = set_user_token(None)
        try:
            assert get_user_token() is None
        finally:
            reset_user_token(tok_ctx)

    def test_malformed_non_bearer_header_gives_none(self):
        """AUTH-4: 'Basic dXNlcjpwYXNz' is not a Bearer token → middleware sets None."""
        # Simulate the middleware logic from main.py
        auth_header = "Basic dXNlcjpwYXNz"
        token = auth_header[7:] if auth_header.lower().startswith("bearer ") else None
        assert token is None

    def test_bearer_prefix_stripped_correctly(self):
        """AUTH-4: 'Bearer eyJ...' → 'eyJ...' after middleware extraction."""
        auth_header = "Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig"
        token = auth_header[7:] if auth_header.lower().startswith("bearer ") else None
        assert token == "eyJhbGciOiJSUzI1NiJ9.payload.sig"

    def test_empty_auth_header_gives_none(self):
        """AUTH-4: Empty Authorization header → None."""
        auth_header = ""
        token = auth_header[7:] if auth_header.lower().startswith("bearer ") else None
        assert token is None


class TestJWTNotLogged:
    """AUTH-5: JWT values must never appear in log records."""

    async def test_jwt_not_in_logs_during_tool_call(self, monkeypatch, caplog):
        """AUTH-5: No log record may contain the JWT value."""
        monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "conn-proxy.ns")

        from sap_cloud_sdk.destination import (
            TransparentProxyDestination, TransparentProxy
        )
        real_proxy_dest = TransparentProxyDestination.from_proxy(
            "S43", TransparentProxy("conn-proxy", "ns")
        )
        mock_client = MagicMock()
        mock_client.get_destination.return_value = real_proxy_dest

        secret_jwt = "eyJhbGciOiJSUzI1NiJ9.SECRET_PAYLOAD_DO_NOT_LOG"

        with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
             patch("tools.s4_odata_client._requests.get", return_value=_make_ok_response()), \
             caplog.at_level(logging.DEBUG):

            from tools.s4_odata_client import call_odata
            import os; os.environ.pop("IBD_TESTING", None)
            try:
                await call_odata(
                    destination_name="S43",
                    path="A_SalesOrder",
                    user_token=secret_jwt,
                )
            finally:
                os.environ["IBD_TESTING"] = "1"

        for record in caplog.records:
            msg = record.getMessage()
            assert secret_jwt not in msg, f"JWT leaked in log: {msg}"
            assert "SECRET_PAYLOAD_DO_NOT_LOG" not in msg, f"JWT segment leaked: {msg}"


# ---------------------------------------------------------------------------
# BATCH — explicit unsupported error
# ---------------------------------------------------------------------------

class TestBatchToolUnsupported:
    """BATCH-1/2: Batch tool must explicitly raise ToolException and say "not supported"."""

    @pytest.fixture(scope="class")
    @classmethod
    def native_tools(cls, add_agent_to_path):
        from tools.sales_order_tools import get_native_tools
        return {t.name: t for t in get_native_tools()}

    async def test_batch_raises_tool_exception(self, native_tools):
        """BATCH-1: Calling batch tool raises ToolException."""
        batch_tool = native_tools["batch_for_api_sales_order_srv"]
        with pytest.raises(ToolException) as exc_info:
            await batch_tool.coroutine()
        assert "not supported" in str(exc_info.value).lower(), \
            f"Expected 'not supported' in error, got: {exc_info.value}"

    async def test_batch_raises_even_with_body(self, native_tools):
        """BATCH-1: Batch tool raises ToolException even when body is provided."""
        batch_tool = native_tools["batch_for_api_sales_order_srv"]
        with pytest.raises(ToolException):
            await batch_tool.coroutine(body="--batch\r\nGET A_SalesOrder HTTP/1.1\r\n--batch--")

    def test_batch_description_says_not_supported(self, native_tools):
        """BATCH-2: Description must state NOT SUPPORTED so LLM knows not to use it."""
        desc = native_tools["batch_for_api_sales_order_srv"].description
        assert "NOT SUPPORTED" in desc or "not supported" in desc.lower(), \
            f"Batch tool description does not state NOT SUPPORTED: {desc}"

    async def test_batch_does_not_call_call_odata(self, native_tools):
        """BATCH-1: batch coroutine must not invoke call_odata."""
        with patch("tools.sales_order_tools.call_odata") as mock_call:
            with pytest.raises(ToolException):
                await native_tools["batch_for_api_sales_order_srv"].coroutine()
        mock_call.assert_not_called()


# ---------------------------------------------------------------------------
# PAGINATION — input validation
# ---------------------------------------------------------------------------

class TestPaginationValidation:
    """PAGINATION-1 to -7: _validate_pagination() and downstream clamping."""

    def test_negative_top_raises_tool_exception(self):
        """PAGINATION-1: $top < 0 must raise ToolException."""
        from tools.sales_order_tools import _validate_pagination
        with pytest.raises(ToolException) as exc_info:
            _validate_pagination(-1, None)
        assert "$top" in str(exc_info.value)
        assert "-1" in str(exc_info.value)

    def test_negative_skip_raises_tool_exception(self):
        """PAGINATION-2: $skip < 0 must raise ToolException."""
        from tools.sales_order_tools import _validate_pagination
        with pytest.raises(ToolException) as exc_info:
            _validate_pagination(None, -5)
        assert "$skip" in str(exc_info.value)
        assert "-5" in str(exc_info.value)

    def test_top_greater_than_100_clamped_to_100(self):
        """PAGINATION-3: $top > 100 must be clamped to 100."""
        from tools.sales_order_tools import _validate_pagination
        top, skip = _validate_pagination(500, None)
        assert top == 100

    def test_top_exactly_100_unchanged(self):
        """PAGINATION-3: $top = 100 must remain 100."""
        from tools.sales_order_tools import _validate_pagination
        top, _ = _validate_pagination(100, None)
        assert top == 100

    def test_top_0_clamped_to_1(self):
        """PAGINATION-4: $top = 0 must be clamped to 1."""
        from tools.sales_order_tools import _validate_pagination
        top, _ = _validate_pagination(0, None)
        assert top == 1

    def test_top_none_passes_through(self):
        """PAGINATION-5: $top = None must pass through unchanged."""
        from tools.sales_order_tools import _validate_pagination
        top, _ = _validate_pagination(None, None)
        assert top is None

    def test_skip_0_is_valid(self):
        """PAGINATION-6: $skip = 0 is valid, must pass through."""
        from tools.sales_order_tools import _validate_pagination
        _, skip = _validate_pagination(None, 0)
        assert skip == 0

    def test_skip_none_passes_through(self):
        """PAGINATION-7: $skip = None must pass through unchanged."""
        from tools.sales_order_tools import _validate_pagination
        _, skip = _validate_pagination(None, None)
        assert skip is None

    async def test_negative_top_in_list_salesorder_raises(self, add_agent_to_path):
        """PAGINATION-1: Negative $top propagates from list tool to ToolException."""
        from tools.sales_order_tools import _list_salesorder
        with pytest.raises(ToolException) as exc_info:
            await _list_salesorder(top=-10)
        assert "$top" in str(exc_info.value)

    async def test_negative_skip_in_list_salesorderitem_raises(self, add_agent_to_path):
        """PAGINATION-2: Negative $skip propagates from list tool to ToolException."""
        from tools.sales_order_tools import _list_salesorderitem
        with pytest.raises(ToolException) as exc_info:
            await _list_salesorderitem(skip=-1)
        assert "$skip" in str(exc_info.value)

    async def test_top_500_clamped_in_list_tool(self, add_agent_to_path):
        """PAGINATION-3: $top=500 is clamped to 100 by list tool, not rejected."""
        captured: dict = {}

        async def mock_call_odata(**kwargs):
            captured.update(kwargs.get("params", {}))
            return '{"d":{"results":[]}}'

        with patch("tools.sales_order_tools.call_odata", side_effect=mock_call_odata):
            from tools.sales_order_tools import _list_salesorder
            await _list_salesorder(top=500)

        assert captured.get("$top") == "100", \
            f"Expected $top=100, got {captured.get('$top')}"

    async def test_negative_top_in_list_scheduleline_raises(self, add_agent_to_path):
        """PAGINATION-1: Negative $top also works for schedule line list."""
        from tools.sales_order_tools import _list_scheduleline
        with pytest.raises(ToolException):
            await _list_scheduleline(top=-3)


# ---------------------------------------------------------------------------
# ESCAPE — OData V2 string key escaping
# ---------------------------------------------------------------------------

class TestODataKeyEscaping:
    """ESCAPE-1 to -4: _escape_odata_string() and integration with key paths."""

    def test_apostrophe_is_doubled(self):
        """ESCAPE-1: Single apostrophe in a key value must be doubled."""
        from tools.sales_order_tools import _escape_odata_string
        assert _escape_odata_string("O'Reilly") == "O''Reilly"

    def test_no_apostrophe_unchanged(self):
        """ESCAPE-3: Alphanumeric values must pass through unchanged."""
        from tools.sales_order_tools import _escape_odata_string
        assert _escape_odata_string("1234567890") == "1234567890"
        assert _escape_odata_string("ABC-123") == "ABC-123"

    def test_multiple_apostrophes_all_doubled(self):
        """ESCAPE-4: Multiple apostrophes in one value must all be doubled."""
        from tools.sales_order_tools import _escape_odata_string
        result = _escape_odata_string("it's O'Brien's order")
        assert result == "it''s O''Brien''s order"

    def test_empty_string_unchanged(self):
        """ESCAPE-3: Empty string must remain empty."""
        from tools.sales_order_tools import _escape_odata_string
        assert _escape_odata_string("") == ""

    async def test_apostrophe_in_salesorder_key_is_escaped(self, add_agent_to_path):
        """ESCAPE-1: Apostrophe in salesorder key is escaped in OData path."""
        captured: dict = {}

        async def mock_call_odata(**kwargs):
            captured["path"] = kwargs.get("path", "")
            return '{"d":{}}'

        with patch("tools.sales_order_tools.call_odata", side_effect=mock_call_odata):
            from tools.sales_order_tools import _get_salesorder
            await _get_salesorder(salesorder="O'Brien")

        assert "O''Brien" in captured["path"], \
            f"Apostrophe not escaped in path: {captured['path']}"
        assert "O'Brien" not in captured["path"].replace("O''Brien", ""), \
            f"Unescaped apostrophe still present: {captured['path']}"

    async def test_apostrophe_in_composite_key_all_parts_escaped(self, add_agent_to_path):
        """ESCAPE-2: All parts of composite key have apostrophes escaped."""
        captured: dict = {}

        async def mock_call_odata(**kwargs):
            captured["path"] = kwargs.get("path", "")
            return '{"d":{}}'

        with patch("tools.sales_order_tools.call_odata", side_effect=mock_call_odata):
            from tools.sales_order_tools import _get_billingplan
            await _get_billingplan(salesorder="A'1", billingplan="B'2")

        path = captured["path"]
        assert "A''1" in path, f"salesorder key not escaped: {path}"
        assert "B''2" in path, f"billingplan key not escaped: {path}"

    async def test_normal_salesorder_key_path_unchanged(self, add_agent_to_path):
        """ESCAPE-3: Normal alphanumeric key is not modified."""
        captured: dict = {}

        async def mock_call_odata(**kwargs):
            captured["path"] = kwargs.get("path", "")
            return '{"d":{}}'

        with patch("tools.sales_order_tools.call_odata", side_effect=mock_call_odata):
            from tools.sales_order_tools import _get_salesorder
            await _get_salesorder(salesorder="1234567")

        assert captured["path"] == "A_SalesOrder('1234567')", \
            f"Unexpected path: {captured['path']}"


# ---------------------------------------------------------------------------
# PROXY — destination name and proxy URL in outbound request
# ---------------------------------------------------------------------------

class TestProxyHeaders:
    """PROXY-1 to -4: Correct proxy headers on outbound OData requests."""

    async def test_destination_name_is_uppercase_S43(self, monkeypatch):
        """PROXY-1: X-destination-name must be 'S43' (uppercase, case-sensitive)."""
        monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "conn-proxy.ns")
        monkeypatch.delenv("IBD_TESTING", raising=False)

        from sap_cloud_sdk.destination import (
            TransparentProxyDestination, TransparentProxy
        )
        real_proxy_dest = TransparentProxyDestination.from_proxy(
            "S43", TransparentProxy("conn-proxy", "ns")
        )
        mock_client = MagicMock()
        mock_client.get_destination.return_value = real_proxy_dest

        captured_headers: dict = {}

        def capture(url, **kwargs):
            captured_headers.update(kwargs.get("headers", {}))
            return _make_ok_response()

        with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
             patch("tools.s4_odata_client._requests.get", side_effect=capture):
            from tools.s4_odata_client import call_odata
            await call_odata(destination_name="S43", path="A_SalesOrder")

        monkeypatch.setenv("IBD_TESTING", "1")
        assert captured_headers.get("X-destination-name") == "S43", \
            f"Expected S43, got: {captured_headers.get('X-destination-name')}"

    async def test_proxy_url_not_s4hana_virtual_host(self, monkeypatch):
        """PROXY-2: Request URL must start with the proxy host, not an S/4HANA hostname."""
        monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "conn-proxy.ns")
        monkeypatch.delenv("IBD_TESTING", raising=False)

        from sap_cloud_sdk.destination import (
            TransparentProxyDestination, TransparentProxy
        )
        real_proxy_dest = TransparentProxyDestination.from_proxy(
            "S43", TransparentProxy("conn-proxy", "ns")
        )
        mock_client = MagicMock()
        mock_client.get_destination.return_value = real_proxy_dest

        captured_urls: list = []

        def capture(url, **kwargs):
            captured_urls.append(url)
            return _make_ok_response()

        with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
             patch("tools.s4_odata_client._requests.get", side_effect=capture):
            from tools.s4_odata_client import call_odata
            await call_odata(destination_name="S43", path="A_SalesOrder")

        monkeypatch.setenv("IBD_TESTING", "1")
        assert len(captured_urls) == 1
        url = captured_urls[0]
        assert url.startswith("http://conn-proxy.ns"), \
            f"URL should start with proxy host, not virtual host: {url}"
        # Must not start with a SAP on-premise typical hostname pattern
        assert not url.startswith("http://virtualhost"), \
            f"URL must not be a direct on-premise address: {url}"

    async def test_authorization_header_present_with_token(self, monkeypatch):
        """PROXY-3: Authorization: Bearer <jwt> must appear when user_token is set."""
        monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "conn-proxy.ns")
        monkeypatch.delenv("IBD_TESTING", raising=False)

        from sap_cloud_sdk.destination import (
            TransparentProxyDestination, TransparentProxy
        )
        real_proxy_dest = TransparentProxyDestination.from_proxy(
            "S43", TransparentProxy("conn-proxy", "ns")
        )
        mock_client = MagicMock()
        mock_client.get_destination.return_value = real_proxy_dest

        captured_headers: dict = {}

        def capture(url, **kwargs):
            captured_headers.update(kwargs.get("headers", {}))
            return _make_ok_response()

        test_jwt = "eyJhbGciOiJSUzI1NiJ9.test_payload"
        with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
             patch("tools.s4_odata_client._requests.get", side_effect=capture):
            from tools.s4_odata_client import call_odata
            await call_odata(
                destination_name="S43", path="A_SalesOrder", user_token=test_jwt
            )

        monkeypatch.setenv("IBD_TESTING", "1")
        assert captured_headers.get("Authorization") == f"Bearer {test_jwt}", \
            f"Authorization header wrong: {captured_headers.get('Authorization')}"

    async def test_authorization_header_absent_without_token(self, monkeypatch):
        """PROXY-4: Authorization header must be absent when user_token is None."""
        monkeypatch.setenv("APPFND_CONHOS_TRANSP_PROXY", "conn-proxy.ns")
        monkeypatch.delenv("IBD_TESTING", raising=False)

        from sap_cloud_sdk.destination import (
            TransparentProxyDestination, TransparentProxy
        )
        real_proxy_dest = TransparentProxyDestination.from_proxy(
            "S43", TransparentProxy("conn-proxy", "ns")
        )
        mock_client = MagicMock()
        mock_client.get_destination.return_value = real_proxy_dest

        captured_headers: dict = {}

        def capture(url, **kwargs):
            captured_headers.update(kwargs.get("headers", {}))
            return _make_ok_response()

        with patch("tools.s4_odata_client.create_client", return_value=mock_client), \
             patch("tools.s4_odata_client._requests.get", side_effect=capture):
            from tools.s4_odata_client import call_odata
            await call_odata(destination_name="S43", path="A_SalesOrder", user_token=None)

        monkeypatch.setenv("IBD_TESTING", "1")
        assert "Authorization" not in captured_headers, \
            f"Authorization must be absent when user_token=None, got: {captured_headers}"
