"""Tests for delivery details retrieval."""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["IBD_TESTING"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))


@pytest.mark.asyncio
async def test_get_delivery_details():
    """Test retrieving delivery schedule line details for a sales order."""
    from agent import SampleAgent

    agent = SampleAgent()
    response_content = (
        "**Delivery Details for Order 0000012345:**\n"
        "- Item 10: Requested Delivery: 2026-06-02 | Confirmed: 2026-06-02 | Qty: 5\n"
        "- Item 20: Requested Delivery: 2026-06-02 | Confirmed: 2026-06-09 | Qty: 10\n"
        "- Delivery Block: None"
    )

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = response_content
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "When will order 0000012345 be delivered?", "ctx-030", tools=[]
        )

    assert result.status == "completed"
    assert "deliver" in result.message.lower() or "2026" in result.message


@pytest.mark.asyncio
async def test_delivery_details_no_schedule_lines():
    """Test graceful handling when no schedule lines exist."""
    from agent import SampleAgent

    agent = SampleAgent()

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = "Delivery details are unavailable for order 0000012345. No schedule lines found."
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "Show delivery info for order 0000012345", "ctx-031", tools=[]
        )

    assert result.status == "completed"
    assert result.message


@pytest.mark.asyncio
async def test_delivery_block_present():
    """Test that delivery block reason is surfaced when present."""
    from agent import SampleAgent

    agent = SampleAgent()
    response = "Order 0000012345 has a delivery block: Credit Check (01). Please contact finance."

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = response
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "Check delivery status for 0000012345", "ctx-032", tools=[]
        )

    assert result.status == "completed"
    assert "block" in result.message.lower() or "credit" in result.message.lower() or "0000012345" in result.message
