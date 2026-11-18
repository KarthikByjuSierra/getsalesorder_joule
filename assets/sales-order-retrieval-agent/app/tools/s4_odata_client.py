"""Async OData HTTP client for SAP S/4HANA via BTP Destination Service.

Wraps sap_cloud_sdk.destination to retrieve destination "s43" at runtime,
pre-baking all authentication headers (OAuth tokens, Basic auth, cert, etc.)
so callers never handle credentials directly.

In IBD_TESTING=1 mode the destination SDK switches to LocalDevDestinationClient
backed by mocks/destination.json — no network calls are made.

Usage:
    async with S4ODataClient("s43", user_token=token) as client:
        data = await client.get("A_SalesOrder", params={"$top": "5"})
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from langchain_core.tools import ToolException

from util import MCP_CALL_TIMEOUT_SECONDS, MCP_MAX_RESPONSE_CHARS, minify_json, truncate_response

logger = logging.getLogger(__name__)

_ODATA_SERVICE_PATH = "/sap/opu/odata/sap/API_SALES_ORDER_SRV"


def _build_destination_headers(destination_name: str, user_token: str | None) -> tuple[dict[str, str], str]:
    """Resolve destination and return (headers, base_url).

    Uses sap_cloud_sdk.destination.create_client() which auto-detects
    local dev mode (IBD_TESTING) vs cloud mode.

    Args:
        destination_name: BTP destination name (e.g. "s43")
        user_token: Optional JWT for user-token-exchange flows.

    Returns:
        Tuple of (headers dict, base_url string).

    Raises:
        ToolException: If destination cannot be resolved.
    """
    try:
        from sap_cloud_sdk.destination import create_client, ConsumptionOptions

        client = create_client()
        options = ConsumptionOptions(user_token=user_token) if user_token else None
        dest = client.get_destination(destination_name, options=options)

        if dest is None:
            raise ToolException(
                f"Destination '{destination_name}' not found in BTP Destination Service."
            )

        headers = dest.get_headers()
        base_url = (dest.url or "").rstrip("/")
        return headers, base_url

    except ToolException:
        raise
    except Exception as exc:
        raise ToolException(
            f"Failed to resolve BTP destination '{destination_name}': {exc}"
        ) from exc


async def call_odata(
    *,
    destination_name: str,
    path: str,
    params: dict[str, Any] | None = None,
    user_token: str | None = None,
) -> str:
    """Make an authenticated async GET request to the S/4HANA OData service.

    Args:
        destination_name: BTP destination name (e.g. "s43").
        path: OData resource path relative to the service root
              (e.g. "A_SalesOrder", "A_SalesOrder('10')", "A_SalesOrder/$count").
        params: Optional OData query parameters dict (filter, select, expand, top, skip, etc.)
        user_token: Optional JWT token for user-token-exchange auth flows.

    Returns:
        Response body as a (possibly truncated) string.

    Raises:
        ToolException: On auth failure, HTTP error, or timeout.
    """
    if os.environ.get("IBD_TESTING") == "1":
        return _mock_odata_response(path, params)

    headers, base_url = _build_destination_headers(destination_name, user_token)

    url = f"{base_url}{_ODATA_SERVICE_PATH}/{path.lstrip('/')}"
    headers.setdefault("Accept", "application/json")
    headers.setdefault("Content-Type", "application/json")

    logger.info(
        "OData GET %s params=%s destination=%s",
        path, list(params.keys()) if params else [], destination_name
    )

    try:
        async with httpx.AsyncClient(timeout=MCP_CALL_TIMEOUT_SECONDS) as http:
            resp = await http.get(url, headers=headers, params=params)
            resp.raise_for_status()
    except httpx.TimeoutException as exc:
        raise ToolException(
            f"OData request to '{path}' timed out after {MCP_CALL_TIMEOUT_SECONDS}s"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise ToolException(
            f"OData request to '{path}' failed: HTTP {exc.response.status_code} — {exc.response.text[:500]}"
        ) from exc
    except httpx.RequestError as exc:
        raise ToolException(
            f"OData request to '{path}' failed: {exc}"
        ) from exc

    raw = resp.text
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
