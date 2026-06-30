from __future__ import annotations

import time
from typing import Dict, List, Set, Tuple

from map_data import GridPos, Stage, movement_cost

from .belief_common import (
    Belief,
    _apply_belief_action,
    _belief_goal_set,
    _belief_h,
    _belief_initial,
    _belief_trace_note,
    _is_goal_belief,
    _rep_next_for_action,
)
from .common import NeighborInfo, SearchResult, TraceStep, finish_search as _finish, path_cost, stopped_search as _stopped


def belief_ida(stage: Stage) -> SearchResult:
    # Lightweight IDA* over belief states. Uses representative path for animation.
    start_time = time.perf_counter()
    start_b = _belief_initial(stage, 3)
    goals = _belief_goal_set(stage, 2)
    aggregate = "MAX"
    threshold = _belief_h(start_b, goals, aggregate)
    trace: List[TraceStep] = []
    total = 0
    found_path: List[GridPos] = []
    actions = ["UP", "DOWN", "LEFT", "RIGHT"]

    def dfs_belief(belief: Belief, rep_path: List[GridPos], g: float, th: float, seen: Set[Belief], round_idx: int) -> float | str:
        nonlocal total, found_path, trace
        total += 1
        rep = rep_path[-1]
        hB = _belief_h(belief, goals, aggregate)
        fB = g + hB
        if fB > th:
            return fB
        infos: List[NeighborInfo] = []
        if _is_goal_belief(belief, goals):
            found_path = rep_path[:]
            trace.append(TraceStep(total, rep, [], list(rep_path[-30:]), infos, "Belief IDA*", g, hB, _belief_trace_note("Belief IDA*", aggregate, 2) + f" Gặp belief goal với threshold={th:.1f}."))
            return "FOUND"
        min_over = float("inf")
        allowed: List[Tuple[str, Belief, GridPos, float]] = []
        for a in actions:
            rep_nxt = _rep_next_for_action(rep, a, stage)
            if rep_nxt is None:
                continue
            nb = _apply_belief_action(belief, a, stage, goals)
            ng = g + movement_cost(rep_nxt, stage)
            nf = ng + _belief_h(nb, goals, aggregate)
            if nb in seen:
                infos.append(NeighborInfo(rep_nxt, a, f"f(B)={nf:.1f}", "SKIP", "Belief đã có trong nhánh hiện tại."))
            elif nf > th:
                min_over = min(min_over, nf)
                infos.append(NeighborInfo(rep_nxt, a, f"f(B)={nf:.1f}", "CUT", f"f(B) > threshold={th:.1f}."))
            else:
                allowed.append((a, nb, rep_nxt, ng))
                infos.append(NeighborInfo(rep_nxt, a, f"f(B)={nf:.1f}", "ADD", "f(B) <= threshold nên mở rộng tiếp."))
        if len(trace) < 1500:
            trace.append(TraceStep(total, rep, [x[2] for x in allowed], list(rep_path[-30:]), infos, "Belief IDA*", g, hB, _belief_trace_note("Belief IDA*", aggregate, 2) + f" Round {round_idx}, threshold={th:.1f}."))
        for a, nb, rep_nxt, ng in allowed:
            res = dfs_belief(nb, rep_path+[rep_nxt], ng, th, seen|{nb}, round_idx)
            if res == "FOUND":
                return "FOUND"
            if isinstance(res, (int, float)):
                min_over = min(min_over, res)
        return min_over

    for r in range(1, 20):
        if total > 900:
            break
        res = dfs_belief(start_b, [stage.start], 0.0, threshold, {start_b}, r)
        if res == "FOUND":
            return _finish("Belief IDA*", start_time, found_path, stage, total, trace)
        if res == float("inf"):
            break
        threshold = float(res)
    return _stopped("Belief IDA*", start_time, stage, [stage.start], total, trace, "Belief IDA* hết vòng threshold nhưng chưa đưa toàn bộ belief về Goal.")
