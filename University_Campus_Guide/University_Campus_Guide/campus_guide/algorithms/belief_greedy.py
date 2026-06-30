from __future__ import annotations

import heapq
import time
from typing import Dict, List, Set, Tuple

from map_data import GridPos, Stage, movement_cost

from .belief_common import (
    Belief,
    _apply_belief_action,
    _belief_frontier_view,
    _belief_goal_set,
    _belief_h,
    _belief_initial,
    _belief_trace_note,
    _is_goal_belief,
    _rep_next_for_action,
)
from .common import NeighborInfo, SearchResult, TraceStep, finish_search as _finish, path_cost, stopped_search as _stopped


def belief_greedy(stage: Stage) -> SearchResult:
    name = "Belief Greedy"
    priority = "h"
    aggregate = "AVG"
    goal_size = 2
    start_time = time.perf_counter()
    start_b = _belief_initial(stage, 3)
    goals = _belief_goal_set(stage, goal_size)
    h0 = _belief_h(start_b, goals, aggregate)
    start_node = {"belief": start_b, "rep_path": [stage.start], "g": 0.0, "h": h0}
    def pr(g: float, h: float) -> float:
        if priority == "g": return g
        if priority == "h": return h
        return g + h
    frontier: List[Tuple[float, int, Dict[str, object]]] = [(pr(0.0, h0), 0, start_node)]
    best_score: Dict[Belief, float] = {start_b: pr(0.0, h0)}
    reached: Set[Belief] = set()
    trace: List[TraceStep] = []
    expanded = 0
    best_path: List[GridPos] = [stage.start]
    best_h = h0
    order = 1
    actions = ["UP", "DOWN", "LEFT", "RIGHT"]
    while frontier and expanded < 500:
        _, _, node = heapq.heappop(frontier)
        belief: Belief = node["belief"]  # type: ignore[assignment]
        rep_path: List[GridPos] = node["rep_path"]  # type: ignore[assignment]
        g = float(node["g"])
        hB = float(node["h"])
        rep = rep_path[-1]
        if hB < best_h:
            best_h = hB
            best_path = rep_path[:]
        if belief in reached:
            continue
        reached.add(belief)
        expanded += 1
        infos: List[NeighborInfo] = []
        if _is_goal_belief(belief, goals):
            trace.append(TraceStep(expanded, rep, _belief_frontier_view([x[2]["belief"] for x in frontier]), [b[0] for b in reached], infos, name, g, hB, _belief_trace_note(name, aggregate, goal_size)))
            return _finish(name, start_time, rep_path, stage, expanded, trace)
        for a in actions:
            rep_nxt = _rep_next_for_action(rep, a, stage)
            if rep_nxt is None:
                continue
            nb = _apply_belief_action(belief, a, stage, goals)
            ng = g + movement_cost(rep_nxt, stage)
            nh = _belief_h(nb, goals, aggregate)
            score = pr(ng, nh)
            if nb in reached and score >= best_score.get(nb, float("inf")):
                infos.append(NeighborInfo(rep_nxt, a, f"g={ng:.1f}, h(B)={nh:.1f}", "SKIP", "Reached có score tốt hơn."))
                continue
            if score < best_score.get(nb, float("inf")):
                best_score[nb] = score
                heapq.heappush(frontier, (score, order, {"belief": nb, "rep_path": rep_path+[rep_nxt], "g": ng, "h": nh}))
                order += 1
                infos.append(NeighborInfo(rep_nxt, a, f"g={ng:.1f}, h(B)={nh:.1f}, score={score:.1f}", "ADD/UPDATE", f"Thêm/cập nhật Priority Queue theo {priority}."))
            else:
                infos.append(NeighborInfo(rep_nxt, a, f"g={ng:.1f}, h(B)={nh:.1f}, score={score:.1f}", "SKIP", "Frontier đã có score tốt hơn."))
        trace.append(TraceStep(expanded, rep, _belief_frontier_view([x[2]["belief"] for x in frontier]), [b[0] for b in reached], infos, name, g, hB, _belief_trace_note(name, aggregate, goal_size)))
    return _stopped(name, start_time, stage, best_path, expanded, trace, "Belief Priority Queue rỗng hoặc vượt giới hạn nhưng chưa đạt belief goal.")
