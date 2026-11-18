"""Async OData HTTP client for SAP S/4HANA via BTP Connectivity Transparent Proxy.

Architecture
------------
For OnPremise destinations (ProxyType=OnPremise), SAP BTP uses the Transparent Proxy
pattern — the app does NOT connect directly to the Cloud Connector virtual host.
Instead it sends requests to the Connectivity Transparent Proxy pod running in the
Kubernetes cluster, with an `X-destination-name` header identifying the destination.

The SAP Cloud SDK models this via `TransparentProxyDestination`:

    client = create_client(use_default_proxy=True)
    proxy_dest = client.get_destination("S43", proxy_enabled=True, options=...)
    # proxy_dest.url     → "http://connectivity-proxy.<namespace>"
    # proxy_dest.headers → {"X-destination-name": "S43", ...}

The proxy is configured via `APPFND_CONHOS_TRANSP_PROXY` env var (auto-injected by
Joule Studio at deploy time). If the variable is missing we raise an explicit
diagnostic error rather than silently falling back to direct HTTP (which would fail
anyway for OnPremise destinations).

Authentication
--------------
`ConsumptionOptions(user_token=<jwt>)` is passed to `get_destination()` so the
Destination Service performs OAuth2UserTokenExchange / JWT Bearer token exchange
on behalf of the calling user. No credentials are hardcoded.

Local Testing
-------------
In IBD_TESTING=1 mode the destination SDK and all network calls are bypassed
entirely — a lightweight in-process mock is returned.

Usage
-----
    result = await call_odata(
        destination_name="S43",
        path="A_SalesOrder",
        params={"$top": "5", "$filter": "SalesOrderType eq 'OR'"},
        user_token=jwt_token,
    )
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import requests as _requests

from langchain_core.tools import ToolException
from sap_cloud_sdk.destination import create_client, ConsumptionOptions

from util import MCP_CALL_TIMEOUT_SECONDS, MCP_MAX_RESPONSE_CHARS, minify_json, truncate_response

logger = logging.getLogger(__name__)

_ODATA_SERVICE_PATH = "/sap/opu/odata/sap/API_SALES_ORDER_SRV"

# Environment variable set by Joule Studio / BTP runtime with the transparent proxy
# address in the format "{proxy_name}.{namespace}"
_TRANSP_PROXY_ENV = "APPFND_CONHOS_TRANSP_PROXY"


def _validate_proxy_configured() -> str:
    """Confirm that the Transparent Proxy environment variable is present.

    Raises:
        ToolException: With a clear diagnostic message if the variable is absent.

    Returns:
        The proxy address string (not used directly — the SDK reads it internally).
    """
    proxy_addr = os.environ.get(_TRANSP_PROXY_ENV, "").strip()
    if not proxy_addr:
        raise ToolException(
            f"BTP Connectivity Transparent Proxy is not configured. "
            f"The environment variable '{_TRANSP_PROXY_ENV}' is missing or empty. "
            f"Ensure the connectivity service binding is declared in asset.yaml "
            f"(kind: platform-service, service: connectivity) and that the solution "
            f"has been deployed via Joule Studio so the platform injects this variable."
        )
    return proxy_addr


def _resolve_proxy_destination(destination_name: str, user_token: str | None):
    """Resolve destination S43 via the Transparent Proxy.

    Uses create_client(use_default_proxy=True) so the SDK reads
    APPFND_CONHOS_TRANSP_PROXY and returns a TransparentProxyDestination
    instead of a plain Destination. The returned object carries:

        proxy_dest.url     → "http://connectivity-proxy.<namespace>"
        proxy_dest.headers → {"X-destination-name": "<destination_name>"}

    Args:
        destination_name: BTP destination name (case-sensitive, e.g. "S43").
        user_token: Optional JWT for OAuth2UserTokenExchange / JWT Bearer flows.

    Returns:
        TransparentProxyDestination from the SDK.

    Raises:
        ToolException: If proxy env var is missing, destination is not found,
                       or the SDK raises any error.
    """
    # Explicit pre-flight: fail fast with a diagnostic message if proxy is missing
    _validate_proxy_configured()

    try:
        # use_default_proxy=True tells the SDK to read APPFND_CONHOS_TRANSP_PROXY
        # and return TransparentProxyDestination for proxy-enabled lookups
        client = create_client(use_default_proxy=True)
        options = ConsumptionOptions(user_token=user_token) if user_token else None

        # proxy_enabled=True forces the SDK to return a TransparentProxyDestination
        # rather than a Destination with the virtual host URL
        proxy_dest = client.get_destination(
            destination_name,
            options=options,
            proxy_enabled=True,
        )

        if proxy_dest is None:
            raise ToolException(
                f"Destination '{destination_name}' not found in BTP Destination Service."
            )

        logger.info(
            "Resolved TransparentProxyDestination: name=%s proxy_url=%s headers_keys=%s",
            destination_name,
            getattr(proxy_dest, "url", "<unknown>"),
            list(getattr(proxy_dest, "headers", {}).keys()),
        )
        return proxy_dest

    except ToolException:
        raise
    except Exception as exc:
        raise ToolException(
            f"Failed to resolve BTP destination '{destination_name}' via "
            f"Transparent Proxy: {exc}"
        ) from exc


def _sync_odata_get(
    destination_name: str,
    path: str,
    params: dict[str, Any] | None,
    user_token: str | None,
) -> str:
    """Synchronous OData GET routed through the BTP Connectivity Transparent Proxy.

    Flow:
        1. Validate APPFND_CONHOS_TRANSP_PROXY is set (fail fast with diagnostic).
        2. Resolve destination via create_client(use_default_proxy=True) →
           returns TransparentProxyDestination with proxy URL + headers.
        3. Send GET request to proxy_dest.url + OData path with proxy_dest.headers
           merged into the request headers.

    The Transparent Proxy pod handles:
        - Cloud Connector tunnel selection
        - mTLS to the on-premise system
        - Principal propagation (if configured in the destination)

    This function is called via asyncio.to_thread() — it is intentionally
    synchronous to use requests.Session, which is not async-safe.

    Raises:
        ToolException: On proxy misconfiguration, auth failure, HTTP error,
                       timeout, or connection error.
    """
    proxy_dest = _resolve_proxy_destination(destination_name, user_token)

    full_path = f"{_ODATA_SERVICE_PATH}/{path.lstrip('/')}"
    proxy_url = getattr(proxy_dest, "url", "").rstrip("/")
    proxy_headers: dict[str, str] = dict(getattr(proxy_dest, "headers", {}))

    if not proxy_url:
        raise ToolException(
            f"TransparentProxyDestination for '{destination_name}' returned an empty URL. "
            f"Check that APPFND_CONHOS_TRANSP_PROXY is set correctly."
        )

    # Confirm X-destination-name header is present (SDK sets it automatically)
    if "X-destination-name" not in proxy_headers:
        raise ToolException(
            f"TransparentProxyDestination for '{destination_name}' is missing the "
            f"'X-destination-name' header. SDK may not have returned a valid proxy destination."
        )

    request_url = f"{proxy_url}/{full_path.lstrip('/')}"

    # Merge OData-specific headers on top of proxy headers
    # (proxy headers take precedence for X-destination-name etc.)
    merged_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        **proxy_headers,
    }

    all_params: dict[str, Any] = dict(params or {})

    logger.info(
        "OData GET via Transparent Proxy: path=%s params=%s destination=%s proxy=%s",
        path,
        list(all_params.keys()),
        destination_name,
        proxy_url,
    )

    try:
        resp = _requests.get(
            request_url,
            headers=merged_headers,
            params=all_params if all_params else None,
            timeout=MCP_CALL_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.text

    except _requests.exceptions.Timeout as exc:
        raise ToolException(
            f"OData request to '{path}' timed out after {MCP_CALL_TIMEOUT_SECONDS}s "
            f"(proxy: {proxy_url})"
        ) from exc
    except _requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        body = exc.response.text[:500] if exc.response is not None else ""
        raise ToolException(
            f"OData request to '{path}' failed: HTTP {status} — {body}"
        ) from exc
    except _requests.exceptions.ConnectionError as exc:
        raise ToolException(
            f"OData request to '{path}' failed: Cannot connect to Transparent Proxy "
            f"at '{proxy_url}'. Verify connectivity service binding and Cloud Connector "
            f"availability. Error: {exc}"
        ) from exc
    except _requests.exceptions.RequestException as exc:
        raise ToolException(
            f"OData request to '{path}' failed: {exc}"
        ) from exc


async def call_odata(
    *,
    destination_name: str,
    path: str,
    params: dict[str, Any] | None = None,
    user_token: str | None = None,
) -> str:
    """Make an authenticated async GET request to the S/4HANA OData service.

    Routes through the BTP Connectivity Transparent Proxy via
    create_client(use_default_proxy=True). The proxy handles Cloud Connector
    tunnel selection — no direct TCP connection to the on-premise virtual host
    is made.

    Args:
        destination_name: BTP destination name (case-sensitive, e.g. "S43").
        path: OData resource path relative to the service root
              (e.g. "A_SalesOrder", "A_SalesOrder('10')", "A_SalesOrder/$count").
        params: Optional OData query parameters dict
                ($filter, $select, $expand, $top, $skip, $orderby, $inlinecount, etc.)
        user_token: Optional JWT token for user-token-exchange auth flows.

    Returns:
        Response body as a (possibly truncated) string.

    Raises:
        ToolException: If proxy is not configured, destination not found,
                       auth fails, HTTP error, or timeout.
    """
    if os.environ.get("IBD_TESTING") == "1":
        return _mock_odata_response(path, params)

    raw = await asyncio.to_thread(
        _sync_odata_get, destination_name, path, params, user_token
    )

    result = minify_json(raw)

    if len(result) > MCP_MAX_RESPONSE_CHARS:
        logger.warning(
            "OData response from '%s' truncated from %d to ~%d chars",
            path, len(result), MCP_MAX_RESPONSE_CHARS,
        )
        result = truncate_response(result, MCP_MAX_RESPONSE_CHARS)

    logger.info("OData GET '%s' returned %d chars", path, len(result))
    return result


def _mock_odata_response(path: str, params: dict[str, Any] | None) -> str:
    """Return a lightweight mock response for IBD_TESTING=1 mode."""
    import json
    entity = path.split("/")[0].split("(")[0].split("$")[0]
    if path.endswith("/$count") or "$count" in path:
        return "0"
    if path.endswith("/$metadata"):
        return "<edmx:Edmx/>"
    return json.dumps({
        "d": {
            "results": [],
            "__mock": True,
            "entity": entity,
            "path": path,
            "params": params or {},
        }
    })
