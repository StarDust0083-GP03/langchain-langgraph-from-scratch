#!/usr/bin/env python3
"""Offline LangGraph example: route, persist, interrupt, resume, and inspect."""

from __future__ import annotations

import operator
from typing import Annotated, Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict


class ResearchState(TypedDict):
    question: str
    plan: list[str]
    notes: Annotated[list[str], operator.add]
    draft: str
    approved: bool


LOCAL_CORPUS = {
    "langchain": "LangChain 提供模型、消息、工具、Runnable 与 Agent 工厂。",
    "langgraph": "LangGraph 提供状态图、Pregel 运行时、检查点和中断。",
    "memory": "checkpointer 保存 thread 状态；store 保存跨 thread 数据。",
}


def plan(state: ResearchState) -> dict:
    terms = [term for term in LOCAL_CORPUS if term in state["question"].lower()]
    return {"plan": terms or ["langchain", "langgraph"]}


def search(state: ResearchState) -> dict:
    return {"notes": [LOCAL_CORPUS[term] for term in state["plan"]]}


def draft(state: ResearchState) -> dict:
    return {"draft": state["question"] + "\n\n" + "\n".join(state["notes"])}


def review(state: ResearchState) -> Command[Literal["publish", "revise"]]:
    decision = interrupt({"kind": "review", "draft": state["draft"]})
    approved = bool(decision.get("approved"))
    return Command(update={"approved": approved}, goto="publish" if approved else "revise")


def revise(state: ResearchState) -> dict:
    return {"draft": state["draft"] + "\n\n[已按审阅意见补充边界说明]"}


def publish(state: ResearchState) -> dict:
    return {}


def build_graph():
    builder = StateGraph(ResearchState)
    for node in (plan, search, draft, review, revise, publish):
        builder.add_node(node.__name__, node)
    builder.add_edge(START, "plan")
    builder.add_edge("plan", "search")
    builder.add_edge("search", "draft")
    builder.add_edge("draft", "review")
    builder.add_edge("revise", "review")
    builder.add_edge("publish", END)
    return builder.compile(checkpointer=InMemorySaver())


def demo() -> None:
    graph = build_graph()
    config = {"configurable": {"thread_id": "demo-thread"}}
    paused = graph.invoke(
        {"question": "LangChain 和 LangGraph 如何分工？", "notes": []}, config
    )
    assert paused["draft"]
    snapshot = graph.get_state(config)
    assert snapshot.next == ("review",)

    finished = graph.invoke(Command(resume={"approved": True}), config)
    assert finished["approved"] is True
    assert graph.get_state(config).next == ()
    print(finished["draft"])


if __name__ == "__main__":
    demo()
