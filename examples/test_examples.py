#!/usr/bin/env python3
"""Local assertions for the two CLI demos; no model provider is contacted."""

import json
import unittest

from mini_agent import estimate_time, execute, run_agent
from research_assistant import build_graph, plan, publish
from langgraph.types import Command


def config(name):
    return {"configurable": {"thread_id": name}}


class ObservatoryTests(unittest.TestCase):
    def test_tool_pairing_and_budget(self):
        trace = run_agent("Halpha 曝光申请")
        calls = {c["id"] for c in trace[1]["tool_calls"]}
        results = {m["tool_call_id"] for m in trace if m["role"] == "tool"}
        self.assertEqual(calls, results)
        self.assertEqual(json.loads(estimate_time(6, 180))["total_s"], 1500)
        with self.assertRaises(ValueError):
            estimate_time(True, 180)
        with self.assertRaises(RuntimeError):
            run_agent("Halpha", max_steps=1)
        unknown = execute({"name": "submit_real_telescope", "arguments": {}})
        self.assertEqual(json.loads(unknown)["status"], "unknown_tool")
        bad = execute({"name": "estimate_time", "arguments": {"frames": -1, "exposure_s": 180}})
        self.assertEqual(json.loads(bad)["status"], "invalid_arguments")
        self.assertIn("停止", run_agent("未知档案")[-1]["content"])

    def test_duplicate_call_identity(self):
        def duplicate(messages, tools):
            call = {"id": "same", "name": "search_notes", "arguments": {"query": "Halpha"}}
            return {"role": "assistant", "tool_calls": [call, call]}
        with self.assertRaises(ValueError):
            run_agent("Halpha", model=duplicate)

    def test_pause_reject_approve_and_isolation(self):
        graph, cfg = build_graph(), config("proposal-a")
        state = graph.invoke({"question": "Halpha 申请", "notes": []}, cfg)
        self.assertEqual(state["total_s"], 1500)
        self.assertEqual(len(state["notes"]), 2)
        self.assertEqual(state["receipt"], "")
        self.assertTrue(state["__interrupt__"])
        self.assertEqual(graph.get_state(cfg).next, ("review",))
        state = graph.invoke(Command(resume={"approved": False, "revision": 1,
                                             "feedback": "写明未校验目标高度。"}), cfg)
        self.assertEqual(state["revision"], 2)
        self.assertEqual(state["receipt"], "")
        self.assertEqual(len(state["notes"]), 2)
        self.assertIn("未校验目标高度", state["draft"])
        other = graph.invoke({"question": "Halpha 第二份申请", "notes": []}, config("proposal-b"))
        self.assertEqual(other["revision"], 1)
        self.assertEqual(graph.get_state(cfg).values["revision"], 2)
        state = graph.invoke(Command(resume={"approved": True, "revision": 2}), cfg)
        self.assertEqual(state["receipt"], "local:SIM-OBS-17:v2")
        self.assertEqual(graph.get_state(cfg).next, ())

    def test_rejection_has_finite_end(self):
        graph, cfg = build_graph(), config("reject-all")
        graph.invoke({"question": "Halpha", "notes": []}, cfg)
        for revision in (1, 2, 3):
            state = graph.invoke(Command(resume={"approved": False, "revision": revision}), cfg)
        self.assertEqual(state["status"], "review_limit")
        self.assertEqual(state["receipt"], "")
        self.assertEqual(graph.get_state(cfg).next, ())

    def test_unknown_and_over_budget_do_not_reach_review(self):
        for name, question, window, status in (
            ("unknown", "不存在的星表", 1800, "needs_evidence"),
            ("short-window", "Halpha", 1000, "over_budget"),
        ):
            graph, cfg = build_graph(), config(name)
            state = graph.invoke({"question": question, "window_s": window, "notes": []}, cfg)
            self.assertEqual(state["status"], status)
            self.assertEqual(state["receipt"], "")
            self.assertEqual(graph.get_state(cfg).next, ())

    def test_bad_review_is_not_truthy_approval(self):
        for index, decision in enumerate((
            {"approved": "false", "revision": 1},
            {"approved": True, "revision": 99},
        )):
            graph, cfg = build_graph(), config(f"bad-review-{index}")
            graph.invoke({"question": "Halpha", "notes": []}, cfg)
            with self.assertRaises(ValueError):
                graph.invoke(Command(resume=decision), cfg)
            self.assertEqual(graph.get_state(cfg).values["receipt"], "")
        with self.assertRaises(ValueError):
            plan({"question": "Halpha", "frames": 0})
        with self.assertRaises(ValueError):
            publish({"approved": False})


if __name__ == "__main__":
    unittest.main()
