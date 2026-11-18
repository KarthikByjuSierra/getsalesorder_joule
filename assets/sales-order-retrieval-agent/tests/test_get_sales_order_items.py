"""Tests for sales order line item retrieval."""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["IBD_TESTING"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))


@pytest.mark.asyncio
async def test_get_line_items():
    """Test retrieving line items for a sales order."""
    from agent import SampleAgent

    agent = SampleAgent()
    response_content = (
        "**Line Items for Order 0000012345:**\n"
        "- Item 10: Industrial Pump Model A | Qty: 5 EA | Price: 50000.00 USD\n"
        "- Item 20: Spare Parts Kit | Qty: 10 EA | Price: 25000.00 USD"
    )

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = response_content
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "Show me the line items for order 0000012345", "ctx-020", tools=[]
        )

    assert result.status == "completed"
    assert "item" in result.message.lower() or "0000012345" in result.message


@pytest.mark.asyncio
async def test_get_line_items_empty():
    """Test handling of a sales order with no line items."""
    from agent import SampleAgent

    agent = SampleAgent()

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = "No line items found for order 0000099999."
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "Get items for sales order 0000099999", "ctx-021", tools=[]
        )

    assert result.status == "completed"
    assert result.message


@pytest.mark.asyncio
async def test_line_items_include_material_and_quantity():
    """Test that line item response includes material and quantity information."""
    from agent import SampleAgent

    agent = SampleAgent()
    response = "MAT-001 | Industrial Pump | Qty: 5 EA | 50000.00 USD"

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = response
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "What items are on order 0000012345?", "ctx-022", tools=[]
        )

    assert result.status == "completed"
    assert "MAT-001" in result.message or "pump" in result.message.lower() or "5" in result.message
