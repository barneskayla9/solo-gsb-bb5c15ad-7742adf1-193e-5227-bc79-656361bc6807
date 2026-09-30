"""管网图算法与方案校验（纯 Python，不依赖数据库/框架）。

图按无向图处理：水可沿管段双向流动。
方案图 = 现状管网移除故障管段、拟关闭管段、以及所有此前已关闭阀门所在管段。
隔离成立条件：故障管段两个端点在方案图中都无法从任一水源到达。
失供用水点：提交前可达、方案后不可达的用水点之差集。
"""

from dataclasses import dataclass, field
from typing import Iterable

from .errors import APIError


@dataclass(frozen=True)
class Node:
    code: str
    kind: str  # source / junction / sink
    name: str | None = None


@dataclass(frozen=True)
class Edge:
    code: str
    from_code: str
    to_code: str
    has_valve: bool = False
    valve_closed: bool = False
    name: str | None = None


@dataclass(frozen=True)
class AnalysisResult:
    can_isolate: bool
    lost_sinks: tuple[str, ...]
    reachable_sinks_before: tuple[str, ...]
    reachable_sinks_after: tuple[str, ...]
    fault_u_reachable_after: bool
    fault_v_reachable_after: bool


@dataclass(frozen=True)
class PlanIssue:
    code: str
    message: str
    edge: str | None = None


@dataclass
class Graph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: dict[str, Edge] = field(default_factory=dict)

    def _adjacency(self, blocked: Iterable[str]) -> dict[str, set[str]]:
        blocked_set = set(blocked)
        adj: dict[str, set[str]] = {code: set() for code in self.nodes}
        for code, e in self.edges.items():
            if code in blocked_set:
                continue
            adj.setdefault(e.from_code, set()).add(e.to_code)
            adj.setdefault(e.to_code, set()).add(e.from_code)
        return adj

    def reachable(self, sources: Iterable[str], blocked: Iterable[str]) -> set[str]:
        """从任一水源出发、不经过 blocked 管段可达的节点集合（无向 BFS）。"""
        adj = self._adjacency(blocked)
        seen: set[str] = set()
        stack: list[str] = []
        for s in sources:
            if s in adj and s not in seen:
                seen.add(s)
                stack.append(s)
        while stack:
            cur = stack.pop()
            for nxt in adj.get(cur, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen


def validate_plan(graph: Graph, fault_edge: str, proposed_closed: list[str]) -> list[PlanIssue]:
    """校验拟关闭方案的合法性（与版本无关的部分）。

    检查项（顺序固定，全部收集后返回）：
    1. 故障管段不存在 / 拟关闭管段不存在；
    2. 拟关闭列表中编号重复；
    3. 拟关闭管段上没有阀门（无阀管段）；
    4. 阀门已经处于关闭状态（重复关闭）。
    """
    issues: list[PlanIssue] = []

    if fault_edge not in graph.edges:
        issues.append(PlanIssue("fault_edge_not_found", f"故障管段 {fault_edge} 不存在", fault_edge))

    seen: set[str] = set()
    for code in proposed_closed:
        e = graph.edges.get(code)
        if e is None:
            issues.append(PlanIssue("edge_not_found", f"拟关闭管段 {code} 不存在", code))
            continue
        if code in seen:
            # 重复出现只报重复本身；阀门状态已在首次出现时检查
            issues.append(PlanIssue("duplicate_close", f"拟关闭管段 {code} 在请求中重复出现", code))
            continue
        seen.add(code)
        if not e.has_valve:
            issues.append(PlanIssue("edge_without_valve", f"管段 {code} 上没有阀门，无法关闭", code))
        elif e.valve_closed:
            issues.append(PlanIssue("valve_already_closed", f"管段 {code} 的阀门已经关闭，不得重复关闭", code))

    return issues


def issues_to_api_error(issues: list[PlanIssue]) -> APIError:
    return APIError(
        status_code=422,
        code="invalid_plan",
        message="关阀方案校验失败：" + "；".join(i.message for i in issues),
        details={"issues": [{"code": i.code, "message": i.message, "edge": i.edge} for i in issues]},
    )


def analyze(graph: Graph, fault_edge: str, proposed_closed: Iterable[str]) -> AnalysisResult:
    """计算能否隔离与失供用水点。

    调用方需先通过 validate_plan 且故障管段存在。
    """
    sources = [c for c, n in graph.nodes.items() if n.kind == "source"]
    sinks = sorted(c for c, n in graph.nodes.items() if n.kind == "sink")

    currently_closed = [c for c, e in graph.edges.items() if e.has_valve and e.valve_closed]
    blocked_after = set(currently_closed) | set(proposed_closed) | {fault_edge}

    reach_before = graph.reachable(sources, currently_closed)
    reach_after = graph.reachable(sources, blocked_after)

    before_sinks = tuple(c for c in sinks if c in reach_before)
    after_sinks = tuple(c for c in sinks if c in reach_after)
    lost = tuple(c for c in before_sinks if c not in reach_after)

    fault = graph.edges[fault_edge]
    u_ok = fault.from_code in reach_after
    v_ok = fault.to_code in reach_after

    return AnalysisResult(
        can_isolate=not u_ok and not v_ok,
        lost_sinks=lost,
        reachable_sinks_before=before_sinks,
        reachable_sinks_after=after_sinks,
        fault_u_reachable_after=u_ok,
        fault_v_reachable_after=v_ok,
    )
