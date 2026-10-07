#!/usr/bin/env python3
"""A dependency-free model/tool loop used by chapter 2."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    run: Callable[..., str]

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"query": {"type": "string"}},
        }


def search_notes(query: str) -> str:
    notes = {
        "langchain": "LangChain supplies model, message, tool and agent abstractions.",
        "langgraph": "LangGraph supplies stateful graph orchestration and persistence.",
    }
    hits = [text for key, text in notes.items() if key in query.lower()]
    return "\n".join(hits) or "No local note matched."


TOOLS = {"search_notes": Tool("search_notes", "Search the local notes", search_notes)}


def scripted_model(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
    """Stand in for a chat model so the control loop can be tested offline."""
    last = messages[-1]
    if last["role"] == "user":
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call-1",
                    "name": tools[0]["name"],
                    "arguments": {"query": last["content"]},
                }
            ],
        }
    if last["role"] == "tool":
        return {"role": "assistant", "content": f"根据本地资料：{last['content']}"}
    raise ValueError(f"unexpected message: {last}")


def run_agent(question: str, max_steps: int = 4) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    schemas = [tool.schema for tool in TOOLS.values()]

    for _ in range(max_steps):
        reply = scripted_model(messages, schemas)
        messages.append(reply)
        calls = reply.get("tool_calls", [])
        if not calls:
            return messages

        for call in calls:
            tool = TOOLS.get(call["name"])
            if tool is None:
                result = f"Unknown tool: {call['name']}"
            else:
                try:
                    result = tool.run(**call["arguments"])
                except Exception as exc:  # A tool error is data for the next model turn.
                    result = f"Tool failed: {type(exc).__name__}: {exc}"
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "name": call["name"],
                    "content": result,
                }
            )

    raise RuntimeError(f"agent exceeded max_steps={max_steps}")


def _self_test() -> None:
    trace = run_agent("LangChain 与 LangGraph 分别做什么？")
    assert [m["role"] for m in trace] == ["user", "assistant", "tool", "assistant"]
    assert "stateful graph" in trace[-1]["content"]


if __name__ == "__main__":
    _self_test()
    print(json.dumps(run_agent("LangGraph 是什么？"), ensure_ascii=False, indent=2))
