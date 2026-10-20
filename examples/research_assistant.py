#!/usr/bin/env python3
"""Offline proposal research with real LangGraph persistence and review routing."""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class Finding(TypedDict):
    source: str
    revision: str
    text: str


class ResearchState(TypedDict, total=False):
    question: str
    proposal_id: str
    frames: int
    exposure_s: int
    window_s: int
    plan: list[str]
    notes: Annotated[list[Finding], operator.add]
    total_s: int
    draft: str
    revision: int
    feedback: str
    approved: bool
    status: str
    receipt: str


# SIM identifiers deliberately distinguish fixtures from real telescope manuals.
LOCAL_CORPUS: dict[str, Finding] = {
    "filter": {"source": "SIM-FILTER-2", "revision": "r1",
               "text": "Halpha 窄带成像需核对滤镜配置，本示例不计算目标可见性。"},
    "timing": {"source": "SIM-TIME-4", "revision": "r1",
               "text": "每帧读出 20 秒，每份申请固定校准 300 秒。"},
}


def plan(state: ResearchState) -> dict:
    question = state["question"]
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be nonempty text")
    for field, default, upper in (("frames", 6, 30), ("exposure_s", 180, 600),
                                   ("window_s", 1800, 86400)):
        value = state.get(field, default)
        if type(value) is not int or not 1 <= value <= upper:
            raise ValueError(f"invalid {field}")
    proposal_id = state.get("proposal_id", "SIM-OBS-17")
    if not isinstance(proposal_id, str) or not proposal_id.startswith("SIM-"):
        raise ValueError("offline proposal ID must start with SIM-")
    return {"plan": ["filter", "timing"] if "halpha" in question.lower() else [],
            "proposal_id": proposal_id, "frames": state.get("frames", 6),
            "exposure_s": state.get("exposure_s", 180),
            "window_s": state.get("window_s", 1800), "revision": 1,
            "approved": False, "status": "researching", "receipt": ""}


def search(state: ResearchState) -> dict:
    return {"notes": [dict(LOCAL_CORPUS[key]) for key in state["plan"]]}


def draft(state: ResearchState) -> dict:
    total = state["frames"] * (state["exposure_s"] + 20) + 300
    if not state.get("notes"):
        return {"total_s": total, "draft": "资料未命中，不能形成申请建议。",
                "status": "needs_evidence"}
    refs = "、".join(f"{n['source']}@{n['revision']}" for n in state["notes"])
    text = (f"{state['proposal_id']} / v1\n"
            f"教学预算：{state['frames']} × ({state['exposure_s']} + 20) + 300 = {total} 秒。\n"
            f"申请窗口 {state['window_s']} 秒，余量 {state['window_s'] - total} 秒。\n"
            f"资料：{refs}。尚未核验真实天气、目标高度和排班。")
    return {"draft": text, "total_s": total,
            "status": "awaiting_review" if total <= state["window_s"] else "over_budget"}


def review(state: ResearchState) -> Command[Literal["publish", "revise", "cancel"]]:
    decision = interrupt({"kind": "observatory.review", "proposal_id": state["proposal_id"],
                          "revision": state["revision"], "draft": state["draft"],
                          "actions": ["approve", "reject"]})
    if not isinstance(decision, dict) or type(decision.get("approved")) is not bool:
        raise ValueError("approved must be a JSON boolean")
    if type(decision.get("revision")) is not int or decision["revision"] != state["revision"]:
        raise ValueError("review revision does not match draft")
    feedback = decision.get("feedback", "")
    if not isinstance(feedback, str) or len(feedback) > 500:
        raise ValueError("feedback must be text of at most 500 characters")
    accepted = decision["approved"]
    target = "publish" if accepted else ("revise" if state["revision"] < 3 else "cancel")
    return Command(update={"approved": accepted, "feedback": feedback,
                           "status": "approved" if accepted else "rejected"}, goto=target)


def revise(state: ResearchState) -> dict:
    revision = state["revision"] + 1
    feedback = state.get("feedback") or "请显式列出尚未完成的观测条件核验。"
    return {"revision": revision, "approved": False, "status": "awaiting_review",
            "draft": f"{state['draft']}\n修订 v{revision}：{feedback}\n提交前仍需值班员核验观测条件。"}


def publish(state: ResearchState) -> dict:
    if state.get("approved") is not True or state["total_s"] > state["window_s"]:
        raise ValueError("proposal is not eligible for local publication")
    # This is a stable local identifier, not a network write or a transaction claim.
    return {"receipt": f"local:{state['proposal_id']}:v{state['revision']}",
            "status": "published_locally"}


def cancel(state: ResearchState) -> dict:
    reason = state["status"] if state["status"] in ("needs_evidence", "over_budget") else "review_limit"
    return {"approved": False, "status": reason, "receipt": ""}


def build_graph():
    builder = StateGraph(ResearchState)
    for node in (plan, search, draft, review, revise, publish, cancel):
        builder.add_node(node.__name__, node)
    builder.add_edge(START, "plan")
    builder.add_edge("plan", "search")
    builder.add_edge("search", "draft")
    builder.add_conditional_edges("draft", lambda s: "review" if s["status"] == "awaiting_review" else "cancel",
                                  {"review": "review", "cancel": "cancel"})
    builder.add_edge("revise", "review")
    builder.add_edge("publish", END)
    builder.add_edge("cancel", END)
    return builder.compile(checkpointer=InMemorySaver())


def demo() -> None:
    graph = build_graph()
    config = {"configurable": {"thread_id": "observatory-demo"}}
    paused = graph.invoke({"question": "研究 Halpha 观测申请", "notes": []}, config)
    assert paused["total_s"] == 1500 and paused["receipt"] == ""
    assert graph.get_state(config).next == ("review",)
    revised = graph.invoke(Command(resume={"approved": False, "revision": 1,
                                           "feedback": "补充不含天气预测的说明。"}), config)
    assert revised["revision"] == 2 and revised["receipt"] == ""
    finished = graph.invoke(Command(resume={"approved": True, "revision": 2}), config)
    assert finished["receipt"] == "local:SIM-OBS-17:v2"
    assert graph.get_state(config).next == ()
    print(finished["draft"])
    print("本地回执：", finished["receipt"])


if __name__ == "__main__":
    demo()
