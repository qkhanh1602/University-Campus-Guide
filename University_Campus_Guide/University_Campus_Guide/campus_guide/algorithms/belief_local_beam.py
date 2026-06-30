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


def belief_local_beam(stage: Stage) -> SearchResult:
    start_time = time.perf_counter()
    goals = _belief_goal_set(stage, 2)
    aggregate = "AVG"
    k = 3
    start_b = _belief_initial(stage, 3)
    current_set: List[Dict[str, object]] = [{"belief": start_b, "rep_path": [stage.start], "h": _belief_h(start_b, goals, aggregate)}]
    trace: List[TraceStep] = []
    expanded = 0
    best = current_set[0]
    actions = ["UP", "DOWN", "LEFT", "RIGHT"]
    for round_idx in range(1, 35):
        candidates: List[Dict[str, object]] = []
        infos: List[NeighborInfo] = []
        for item in current_set:
            belief: Belief = item["belief"]  # type: ignore[assignment]
            rep_path: List[GridPos] = item["rep_path"]  # type: ignore[assignment]
            rep = rep_path[-1]
            expanded += 1
            if _is_goal_belief(belief, goals):
                return _finish("Belief Local Beam", start_time, rep_path, stage, expanded, trace)
            for a in actions:
                rep_nxt = _rep_next_for_action(rep, a, stage)
                if rep_nxt is None:
                    continue
                nb = _apply_belief_action(belief, a, stage, goals)
                hB = _belief_h(nb, goals, aggregate)
                cand = {"belief": nb, "rep_path": rep_path+[rep_nxt], "h": hB}
                candidates.append(cand)
                infos.append(NeighborInfo(rep_nxt, a, f"h(B)={hB:.1f}", "CANDIDATE", "Sinh belief neighbor từ một current belief."))
        if not candidates:
            return _stopped("Belief Local Beam", start_time, stage, best["rep_path"], expanded, trace, "Neighbor_States rỗng trong belief beam.")  # type: ignore[arg-type]
        for cand in candidates:
            if _is_goal_belief(cand["belief"], goals):  # type: ignore[arg-type]
                path: List[GridPos] = cand["rep_path"]  # type: ignore[assignment]
                trace.append(TraceStep(len(trace)+1, path[-1], [x["rep_path"][-1] for x in current_set], path[-30:], infos, "Belief Local Beam", path_cost(path, stage), 0, _belief_trace_note("Belief Local Beam", aggregate, 2) + " Gặp belief goal trong Neighbor_States."))
                return _finish("Belief Local Beam", start_time, path, stage, expanded, trace)
        candidates.sort(key=lambda x: x["h"])  # type: ignore[index]
        current_set = candidates[:k]
        if current_set[0]["h"] < best["h"]:  # type: ignore[index]
            best = current_set[0]
        chosen_reps = [x["rep_path"][-1] for x in current_set]  # type: ignore[index]
        for info in infos:
            if info.node in chosen_reps:
                info.status = "CHOSEN"
                info.reason = f"Giữ lại trong k={k} belief tốt nhất."
        trace.append(TraceStep(round_idx, current_set[0]["rep_path"][-1], chosen_reps, [x["rep_path"][-1] for x in current_set], infos, "Belief Local Beam", path_cost(current_set[0]["rep_path"], stage), current_set[0]["h"], _belief_trace_note("Belief Local Beam", aggregate, 2) + f" Lấy k={k} belief tốt nhất."))  # type: ignore[arg-type]
    return _stopped("Belief Local Beam", start_time, stage, best["rep_path"], expanded, trace, "Hết số vòng belief local beam.")
