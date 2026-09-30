"""图算法单元测试（仅依赖标准库，无需 PostgreSQL）。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.demo import DEMO_EDGES, DEMO_NODES  # noqa: E402
from app.graph import Edge, Graph, Node, analyze, validate_plan  # noqa: E402


def demo_graph(valve_closed: set[str] | None = None) -> Graph:
    valve_closed = valve_closed or set()
    g = Graph(
        nodes={n.code: Node(n.code, n.kind, n.name) for n in DEMO_NODES},
        edges={
            e.code: Edge(
                e.code, e.from_code, e.to_code, e.has_valve, e.code in valve_closed, e.name
            )
            for e in DEMO_EDGES
        },
    )
    return g


class RingDemoTests(unittest.TestCase):
    def test_isolate_fault_p3_with_p2_p4(self):
        g = demo_graph()
        issues = validate_plan(g, "P3", ["P2", "P4"])
        self.assertEqual(issues, [])
        r = analyze(g, "P3", ["P2", "P4"])
        self.assertTrue(r.can_isolate)
        # U2 经 J4-P5-J5-P6-J1 继续保供；U1、U3 失供，按编号排序
        self.assertEqual(r.lost_sinks, ("U1", "U3"))
        self.assertEqual(r.reachable_sinks_after, ("U2",))
        self.assertEqual(r.reachable_sinks_before, ("U1", "U2", "U3"))

    def test_single_valve_not_enough(self):
        g = demo_graph()
        r = analyze(g, "P3", ["P2"])
        # J3 仍可经 P4-J4-P5-J5-P6-J1 到达水源
        self.assertFalse(r.can_isolate)
        self.assertFalse(r.fault_u_reachable_after)  # J2 已随 P2 被切断
        self.assertTrue(r.fault_v_reachable_after)  # J3 经环的另一侧保供
        self.assertEqual(r.lost_sinks, ("U1",))

    def test_already_closed_valves_still_effective(self):
        # 场景二：P2、P4 已关闭并保持生效；故障 P5，再关 P6
        g = demo_graph(valve_closed={"P2", "P4"})
        self.assertEqual(validate_plan(g, "P5", ["P6"]), [])
        r = analyze(g, "P5", ["P6"])
        self.assertTrue(r.can_isolate)
        # U1/U3 提交前已不可达，只有 U2 是新失供点
        self.assertEqual(r.reachable_sinks_before, ("U2",))
        self.assertEqual(r.lost_sinks, ("U2",))


class PlanValidationTests(unittest.TestCase):
    def test_unknown_fault_and_edge(self):
        g = demo_graph()
        issues = validate_plan(g, "PX", ["P2", "PY"])
        codes = {i.code for i in issues}
        self.assertIn("fault_edge_not_found", codes)
        self.assertIn("edge_not_found", codes)

    def test_duplicate_in_request(self):
        g = demo_graph()
        issues = validate_plan(g, "P3", ["P2", "P2"])
        self.assertEqual([i.code for i in issues], ["duplicate_close"])

    def test_edge_without_valve(self):
        g = demo_graph()
        issues = validate_plan(g, "P5", ["P9"])
        self.assertEqual([i.code for i in issues], ["edge_without_valve"])

    def test_already_closed(self):
        g = demo_graph(valve_closed={"P2"})
        issues = validate_plan(g, "P3", ["P2"])
        self.assertEqual([i.code for i in issues], ["valve_already_closed"])

    def test_multiple_issues_collected(self):
        g = demo_graph(valve_closed={"P2"})
        issues = validate_plan(g, "P3", ["P2", "P9", "P2", "PY"])
        self.assertEqual(
            [i.code for i in issues],
            ["valve_already_closed", "edge_without_valve", "duplicate_close", "edge_not_found"],
        )


if __name__ == "__main__":
    unittest.main()
