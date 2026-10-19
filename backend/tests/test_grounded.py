import asyncio
from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException

from app.ai import tools
from app.ai.grounded import GroundedProvider, bounded_result
from app.ai.provider import AIMessage, AIStreamEvent, ToolCall, Usage
from app.core.config import Settings


@asynccontextmanager
async def session():
    yield object()


def test_real_tool_dispatch_contract_and_usage_accumulation(monkeypatch):
    executed = []

    async def execute(session, user, name, arguments, settings):
        executed.append(name)
        return {"revenue": "123.45"}

    monkeypatch.setattr(tools, "execute", execute)

    class Base:
        def ensure_available(self):
            pass

        async def stream(self, messages, *, system, tools=None):
            if tools:
                yield AIStreamEvent(
                    kind="tool_call", tool_call=ToolCall(name="get_sales_summary", arguments={})
                )
                yield AIStreamEvent(
                    kind="usage", usage=Usage(input_tokens=4, output_tokens=1, total_tokens=5)
                )
            else:
                assert "123.45" in messages[-1].content
                yield AIStreamEvent(kind="text", text="Revenue is 123.45 INR.")
                yield AIStreamEvent(
                    kind="usage", usage=Usage(input_tokens=8, output_tokens=2, total_tokens=10)
                )
            yield AIStreamEvent(kind="end", finish_reason="STOP")

    async def run():
        provider = GroundedProvider(Base(), session, Settings(_env_file=None), "actor")
        events = [
            event
            async for event in provider.stream(
                [AIMessage(role="user", content="Revenue?")], system="ignored"
            )
        ]
        assert executed == ["get_sales_summary"]
        assert provider.tool_trace == [{"name": "get_sales_summary", "status": "completed"}]
        assert [event.usage.total_tokens for event in events if event.kind == "usage"][-1] == 15

    asyncio.run(run())


def test_unknown_mutation_and_arbitrary_sql_tools_are_rejected():
    async def run():
        for name in ("execute_sql", "approve_purchase_order", "adjust_stock"):
            with pytest.raises(HTTPException):
                await tools.execute(
                    None, "actor", name, {"sql": "DROP TABLE users"}, Settings(_env_file=None)
                )

    asyncio.run(run())


def test_large_operational_results_remain_complete_json_with_explicit_omissions():
    import json

    result = bounded_result([{"date": str(i), "revenue": "x" * 100} for i in range(366)])
    assert result["omitted_items"] > 0
    assert len(json.dumps(result)) < 6000
    assert json.loads(json.dumps(result))["items"][0]["date"] == "0"
