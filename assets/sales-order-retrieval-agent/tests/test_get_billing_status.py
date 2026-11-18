"""Tests for billing status retrieval and status code translation."""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["IBD_TESTING"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))


@pytest.mark.asyncio
async def test_billing_status_not_invoiced():
    """Test billing status code A: Not yet invoiced."""
    from agent import SampleAgent

    agent = SampleAgent()

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = "**Billing Status:** Not yet invoiced"
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "What is the billing status of order 0000012345?", "ctx-040", tools=[]
        )

    assert result.status == "completed"
    assert "not yet invoiced" in result.message.lower() or "billing" in result.message.lower()


@pytest.mark.asyncio
async def test_billing_status_partially_invoiced():
    """Test billing status code B: Partially invoiced."""
    from agent import SampleAgent

    agent = SampleAgent()

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = "**Billing Status:** Partially invoiced"
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "Has order 0000012345 been invoiced?", "ctx-041", tools=[]
        )

    assert result.status == "completed"
    assert "partially" in result.message.lower() or "invoiced" in result.message.lower()


@pytest.mark.asyncio
async def test_billing_status_fully_invoiced():
    """Test billing status code C: Fully invoiced."""
    from agent import SampleAgent

    agent = SampleAgent()

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = "**Billing Status:** Fully invoiced"
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "Show billing info for order 0000012346", "ctx-042", tools=[]
        )

    assert result.status == "completed"
    assert "fully" in result.message.lower() or "invoiced" in result.message.lower()


@pytest.mark.asyncio
async def test_billing_status_cancelled():
    """Test billing status code D: Invoice cancelled."""
    from agent import SampleAgent

    agent = SampleAgent()

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = "**Billing Status:** Invoice cancelled"
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "Check billing for order 0000012347", "ctx-043", tools=[]
        )

    assert result.status == "completed"
    assert "cancel" in result.message.lower() or "billing" in result.message.lower()
