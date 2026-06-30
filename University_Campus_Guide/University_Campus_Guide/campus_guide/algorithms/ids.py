from __future__ import annotations

import time
from typing import List, Set, Tuple

from map_data import GridPos, Stage, neighbors

from .common import NeighborInfo, SearchResult, TraceStep, action_name, finish_search as _finish


def _dls(stage: Stage, limit: int, base_iter: int = 0) -> Tuple[str, List[GridPos], List[TraceStep], int]:
    start, goal = stage.start, stage.goal
    frontier = [{"pos": start, "path": [start], "depth": 0, "path_set": {start}}]
    trace: List[TraceStep] = []
    expanded = 0
    result = "failure"
    while frontier:
        node = frontier.pop()
        current: GridPos = node["pos"]
        path: List[GridPos] = node["path"]
        depth: int = node["depth"]
        path_set: Set[GridPos] = node["path_set"]
        expanded += 1
        infos: List[NeighborInfo] = []
        if current == goal:
            trace.append(TraceStep(base_iter+expanded, current, [n["pos"] for n in reversed(frontier)][:16], path, infos, "IDS/DLS", depth, 0, f"DLS limit={limit}: gặp Goal."))
            return "found", path, trace, expanded
        if depth >= limit:
            result = "cutoff"
            infos.append(NeighborInfo(current, "CUT", f"depth={depth}", "CUTOFF", "depth = limit nên không sinh con trong vòng này."))
            if len(trace) < 1500:
                trace.append(TraceStep(base_iter+expanded, current, [n["pos"] for n in reversed(frontier)][:16], path, infos, "IDS/DLS", depth, 0, f"DLS limit={limit}: cutoff."))
            continue
        for nb in reversed(neighbors(current, stage)):
            if nb in path_set:
                infos.append(NeighborInfo(nb, action_name(current, nb), f"depth={depth+1}", "SKIP", "Tránh cycle trong path hiện tại."))
            else:
                frontier.append({"pos": nb, "path": path+[nb], "depth": depth+1, "path_set": set(path_set)|{nb}})
                infos.append(NeighborInfo(nb, action_name(current, nb), f"depth={depth+1}", "PUSH", "depth < limit nên push vào Stack."))
        if len(trace) < 1500:
            trace.append(TraceStep(base_iter+expanded, current, [n["pos"] for n in reversed(frontier)][:16], path, infos, "IDS/DLS", depth, 0, f"IDS chạy DLS với limit={limit}."))
    return result, [], trace, expanded


def ids(stage: Stage) -> SearchResult:
    start_time = time.perf_counter()
    all_trace: List[TraceStep] = []
    total = 0
    for limit in range(0, 160):
        status, path, trace, nodes = _dls(stage, limit, len(all_trace))
        total += nodes
        all_trace.extend(trace)
        if len(all_trace) > 1500:
            all_trace = all_trace[:1500]
        if status == "found":
            return _finish("IDS", start_time, path, stage, total, all_trace)
        if status == "failure":
            break
    return _finish("IDS", start_time, [], stage, total, all_trace)


# -----------------------------------------------------------------------------
# Nhóm 2: UCS / Greedy / A*
# -----------------------------------------------------------------------------
