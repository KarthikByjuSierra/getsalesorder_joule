"""Tests for sales order search by attributes."""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["IBD_TESTING"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))


@pytest.mark.asyncio
async def test_search_by_customer():
    """Test searching sales orders by customer number."""
    from agent import SampleAgent

    agent = SampleAgent()
    response_content = (
        "Found 2 orders for customer CUST001:\n"
        "1. Order 0000012345 - 2026-05-25 - In Process - 75000.00 USD\n"
        "2. Order 0000012346 - 2026-05-24 - Completed - 12500.00 USD"
    )

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = response_content
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "Show all orders for customer CUST001", "ctx-010", tools=[]
        )

    assert result.status == "completed"
    assert "CUST001" in result.message or "0000012345" in result.message


@pytest.mark.asyncio
async def test_search_by_date_range():
    """Test searching sales orders by date range."""
    from agent import SampleAgent

    agent = SampleAgent()

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = "Found 2 orders created between 2026-05-01 and 2026-05-31."
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "Show orders created in May 2026", "ctx-011", tools=[]
        )

    assert result.status == "completed"
    assert result.message


@pytest.mark.asyncio
async def test_search_by_status():
    """Test searching sales orders by status."""
    from agent import SampleAgent

    agent = SampleAgent()

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = "Found 1 open order: 0000012345."
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "Show all open sales orders", "ctx-012", tools=[]
        )

    assert result.status == "completed"
    assert "open" in result.message.lower() or "0000012345" in result.message


@pytest.mark.asyncio
async def test_search_no_results():
    """Test search with no matching orders."""
    from agent import SampleAgent

    agent = SampleAgent()

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = "No sales orders found matching the specified criteria."
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "Show orders for customer NONEXISTENT", "ctx-013", tools=[]
        )

    assert result.status == "completed"
    assert "no" in result.message.lower() or "not found" in result.message.lower() or "NONEXISTENT" in result.message
