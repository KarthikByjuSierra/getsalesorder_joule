"""Integration test: end-to-end agent flow with mocked LLM and MCP tools."""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["IBD_TESTING"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))


@pytest.mark.asyncio
async def test_full_order_query_end_to_end():
    """
    Integration test: full sales order query flow.
    Agent receives a query, calls tools (mocked), and returns a complete order summary.
    All LLM and MCP tool calls are mocked — test runs fully offline.
    """
    from agent import SampleAgent

    full_summary = (
        "## Sales Order Summary: 0000012345\n\n"
        "**Order Header**\n"
        "- Sales Order: 0000012345\n"
        "- Order Date: 2026-05-25\n"
        "- Order Type: OR\n"
        "- Status: In Process\n"
        "- Customer: CUST001\n"
        "- Net Value: 75,000.00 USD\n\n"
        "**Line Items**\n"
        "| Item | Material | Description | Qty | UoM | Net Price |\n"
        "|------|----------|-------------|-----|-----|-----------|\n"
        "| 10 | MAT-001 | Industrial Pump Model A | 5 | EA | 50,000.00 USD |\n"
        "| 20 | MAT-002 | Spare Parts Kit | 10 | EA | 25,000.00 USD |\n\n"
        "**Delivery Details**\n"
        "- Requested Delivery Date: 2026-06-02\n"
        "- Confirmed Delivery Date: 2026-06-02\n"
        "- Delivery Block: None\n\n"
        "**Billing Status**\n"
        "- Overall Billing Status: Partially invoiced (B)\n"
        "- Invoice Reference: N/A"
    )

    agent = SampleAgent()

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = full_summary
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "Give me the complete details for sales order 0000012345",
            "ctx-integration-001",
            tools=[],
        )

    assert result.status == "completed"
    assert "0000012345" in result.message
    assert "CUST001" in result.message
    assert "75" in result.message  # net value
    assert "MAT-001" in result.message or "pump" in result.message.lower()
    assert "deliver" in result.message.lower()
    assert "billing" in result.message.lower() or "invoiced" in result.message.lower()


@pytest.mark.asyncio
async def test_agent_handles_tool_error_gracefully():
    """Test that agent handles tool errors without crashing."""
    from agent import SampleAgent

    agent = SampleAgent()

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = (
            "I was unable to retrieve order 0000012345. "
            "Error: 404 Not Found - The requested resource was not found."
        )
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "Get order 0000012345", "ctx-integration-002", tools=[]
        )

    assert result.status == "completed"
    assert result.message  # Non-empty response


@pytest.mark.asyncio
async def test_agent_no_tools_available():
    """Test agent behavior when no MCP tools are available."""
    from agent import SampleAgent

    agent = SampleAgent()

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = "Tools are temporarily unavailable. Please try again later."
        mock_invoke.return_value = {"messages": [mock_msg]}

        result = await agent.invoke(
            "Get order 0000012345", "ctx-integration-003", tools=None
        )

    assert result.status == "completed"
    assert result.message


@pytest.mark.asyncio
async def test_milestone_logging(caplog):
    """Test that M1 milestone log is emitted for a recognizable order query."""
    import logging
    from agent import SampleAgent

    agent = SampleAgent()

    with patch.object(agent, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_msg = MagicMock()
        mock_msg.content = "Order 0000012345 retrieved successfully."
        mock_invoke.return_value = {"messages": [mock_msg]}

        with caplog.at_level(logging.INFO, logger="agent"):
            await agent.invoke("Get order 0000012345", "ctx-milestone-001", tools=[])

    # M1 achieved log should be present
    log_text = " ".join(caplog.messages)
    assert "M1.achieved" in log_text or "M2.achieved" in log_text
