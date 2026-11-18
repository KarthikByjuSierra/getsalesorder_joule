"""Tests for sales order header retrieval."""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["IBD_TESTING"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))


@pytest.mark.asyncio
async def test_get_sales_order_by_number():
    """Test retrieving a sales order by its number via the agent."""
    from agent import SampleAgent

    mock_tools = []
    mock_response_content = (
        "**Order Header**\n"
        "- Sales Order: 0000012345\n"
        "- Order Date: 2026-05-25\n"
        "- Status: In Process\n"
        "- Customer: CUST001\n"
        "- Net Value: 75000.00 USD\n\n"
        "**Line Items**\n"
        "- Item 10: Industrial Pump Model A, Qty 5 EA, 50000.00 USD\n\n"
        "**Delivery Details**\n"
        "- Requested Delivery: 2026-06-02\n\n"
        "**Billing Status**\n"
        "- Status: Partially invoiced"
    )

    agent = SampleAgent()

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = mock_response_content
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke("Get me sales order 0000012345", "ctx-001", tools=mock_tools)

    assert result.status == "completed"
    assert "0000012345" in result.message


@pytest.mark.asyncio
async def test_sales_order_not_found():
    """Test graceful handling when order number is not found."""
    from agent import SampleAgent

    agent = SampleAgent()

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = "Sales order 9999999 was not found."
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke("Get sales order 9999999", "ctx-002", tools=[])

    assert result.status == "completed"
    assert "not found" in result.message.lower() or "9999999" in result.message


@pytest.mark.asyncio
async def test_sales_order_header_fields_present():
    """Test that response includes expected header fields."""
    from agent import SampleAgent

    agent = SampleAgent()
    full_response = (
        "Sales Order: 0000012345\n"
        "Order Date: 2026-05-25\n"
        "Status: B\n"
        "Customer: CUST001\n"
        "Total Net Amount: 75000.00 USD\n"
        "Billing Status: Partially invoiced"
    )

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = full_response
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke("Show order 0000012345", "ctx-003", tools=[])

    assert result.status == "completed"
    assert "0000012345" in result.message
