#!/usr/bin/env python3
"""Run a deterministic observatory tool loop without packages or network access."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    run: Callable[..., str]

    @property
    def schema(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description,
                "parameters": self.parameters}


# These records are teaching fixtures, not observatory operating instructions.
NOTES = {
    "SIM-FILTER-2": "教学仪器的 Halpha 滤镜用于窄带成像，曝光长度仍需另行评估。",
    "SIM-TIME-4": "教学时间预算包含逐帧读出和一次固定校准开销。",
}


def search_notes(query: str) -> str:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be nonempty text")
    matched = "halpha" in query.lower() or "曝光" in query
    records = [{"source": key, "text": text} for key, text in NOTES.items()] if matched else []
    return json.dumps({"status": "ok" if records else "no_match", "records": records},
                      ensure_ascii=False)


def estimate_time(frames: int, exposure_s: int) -> str:
    if type(frames) is not int or not 1 <= frames <= 30:
        raise ValueError("frames must be an integer in 1..30")
    if type(exposure_s) is not int or not 1 <= exposure_s <= 600:
        raise ValueError("exposure_s must be an integer in 1..600")
    total = frames * (exposure_s + 20) + 300
    return json.dumps({"total_s": total, "formula": "frames*(exposure_s+20)+300",
                       "scope": "simulation"})


TOOLS = {
    "search_notes": Tool("search_notes", "检索教学天文台规则，结果携带资料编号。", {
        "type": "object", "properties": {"query": {"type": "string"}},
        "required": ["query"], "additionalProperties": False,
    }, search_notes),
    "estimate_time": Tool("estimate_time", "估算教学申请时长，不查询真实排班。", {
        "type": "object", "properties": {
            "frames": {"type": "integer", "minimum": 1, "maximum": 30},
            "exposure_s": {"type": "integer", "minimum": 1, "maximum": 600},
        }, "required": ["frames", "exposure_s"], "additionalProperties": False,
    }, estimate_time),
}


def scripted_model(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
    """Request two fixed observations; this function does not interpret arbitrary prose."""
    if messages[-1]["role"] == "user":
        available = {tool["name"] for tool in tools}
        if not {"search_notes", "estimate_time"} <= available:
            raise ValueError("demo tools are missing")
        return {"role": "assistant", "content": "", "tool_calls": [
            {"id": "obs-rule", "name": "search_notes",
             "arguments": {"query": messages[0]["content"]}},
            {"id": "obs-time", "name": "estimate_time",
             "arguments": {"frames": 6, "exposure_s": 180}},
        ]}
    results = {m["tool_call_id"]: json.loads(m["content"])
               for m in messages if m["role"] == "tool"}
    rules, timing = results["obs-rule"], results["obs-time"]
    if rules["status"] != "ok":
        text = "没有匹配的教学资料，停止申请建议；时长计算不能补足证据。"
    else:
        refs = ", ".join(row["source"] for row in rules["records"])
        text = f"教学申请：6 帧，每帧 180 秒，总预算 {timing['total_s']} 秒。来源：{refs}。未提交真实申请。"
    return {"role": "assistant", "content": text}


def execute(call: dict[str, Any]) -> str:
    tool = TOOLS.get(call["name"])
    if tool is None:
        return json.dumps({"status": "unknown_tool", "name": call["name"]})
    try:
        return tool.run(**call["arguments"])
    except (TypeError, ValueError):
        # Only input mistakes become observations; dependency failures must propagate.
        return json.dumps({"status": "invalid_arguments", "name": call["name"]})


def run_agent(question: str, max_steps: int = 4, *, model=scripted_model) -> list[dict[str, Any]]:
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be nonempty text")
    if type(max_steps) is not int or max_steps < 1:
        raise ValueError("max_steps must be a positive integer")
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    schemas = [tool.schema for tool in TOOLS.values()]
    for _ in range(max_steps):
        reply = model(messages, schemas)
        calls = reply.get("tool_calls", [])
        ids = [call["id"] for call in calls]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate tool call IDs in one response")
        messages.append(reply)
        if not calls:
            return messages
        for call in calls:
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "name": call["name"], "content": execute(call)})
    raise RuntimeError(f"model turn budget exhausted: {max_steps}")


def _self_test() -> None:
    trace = run_agent("请研究 Halpha 观测申请：6 帧，每帧 180 秒")
    assert [m["role"] for m in trace] == ["user", "assistant", "tool", "tool", "assistant"]
    assert {m["tool_call_id"] for m in trace if m["role"] == "tool"} == {"obs-rule", "obs-time"}
    assert "1500" in trace[-1]["content"]
    assert json.loads(estimate_time(6, 180))["total_s"] == 1500
    assert "停止" in run_agent("查询不存在的彗星目录")[-1]["content"]


if __name__ == "__main__":
    _self_test()
    print(json.dumps(run_agent("请研究 Halpha 观测申请：6 帧，每帧 180 秒"),
                     ensure_ascii=False, indent=2))
