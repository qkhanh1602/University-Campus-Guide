from __future__ import annotations

import time
from typing import List, Tuple

from map_data import GridPos, Stage, movement_cost, neighbors

from .common import (
    NeighborInfo,
    SearchResult,
    TraceStep,
    action_name,
    finish_search as _finish,
    h as _h,
    stopped_search as _stopped,
)

def ida_star(stage: Stage) -> SearchResult:
    start_time = time.perf_counter()
    start, goal = stage.start, stage.goal
    threshold = float(_h(start, goal))
    trace: List[TraceStep] = []
    total = 0
    found_path: List[GridPos] = []
    best_path: List[GridPos] = [start]
    best_h = _h(start, goal)
    max_nodes = 30000

    def dfs_limit(path: List[GridPos], g: float, th: float, round_idx: int) -> float | str:
        nonlocal total, found_path, trace, best_path, best_h
        current = path[-1]
        h = _h(current, goal)
        f = g + h
        total += 1
        if total > max_nodes:
            return float("inf")
        if h < best_h:
            best_h = h
            best_path = path[:]
        if f > th:
            return f
        infos: List[NeighborInfo] = []
        if current == goal:
            found_path = path[:]
            trace.append(TraceStep(total, current, [], path[-30:], infos, "IDA*", g, h, f"IDA*: gặp Goal với threshold={th:.1f}."))
            return "FOUND"
        min_over = float("inf")
        allowed: List[Tuple[GridPos, float]] = []
        path_set = set(path)
        for nb in neighbors(current, stage):
            step_cost = float(movement_cost(nb, stage, "normal"))
            ng = g + step_cost
            hn = _h(nb, goal)
            nf = ng + hn
            info = f"g={ng:.1f}, h={hn}, f={nf:.1f}"
            if nb in path_set:
                infos.append(NeighborInfo(nb, action_name(current, nb), info, "SKIP", "Tranh cycle trong path hien tai."))
            elif nf > th:
                min_over = min(min_over, nf)
                infos.append(NeighborInfo(nb, action_name(current, nb), info, "CUT", f"f(child) > threshold={th:.1f}."))
            else:
                allowed.append((nb, ng))
                infos.append(NeighborInfo(nb, action_name(current, nb), info, "ADD", "f(child) <= threshold nen DFS tiep."))
        if len(trace) < 1500:
            trace.append(TraceStep(total, current, [x[0] for x in allowed], path[-30:], infos, "IDA*", g, h, f"Round {round_idx}, threshold={th:.1f}. IDA* dung g(n)=movement_cost; threshold moi la f nho nhat bi CUT."))
        allowed.sort(key=lambda item: item[1] + _h(item[0], goal))
        for nb, ng in allowed:
            res = dfs_limit(path+[nb], ng, th, round_idx)
            if res == "FOUND":
                return "FOUND"
            if isinstance(res, (int, float)):
                min_over = min(min_over, res)
        return min_over

    for r in range(1, 80):
        res = dfs_limit([start], 0.0, threshold, r)
        if res == "FOUND":
            return _finish("IDA*", start_time, found_path, stage, total, trace)
        if res == float("inf"):
            break
        threshold = float(res)
    return _stopped("IDA*", start_time, stage, best_path, total, trace, "IDA* dừng vì hết threshold hoặc vượt giới hạn mở rộng nhưng chưa đến Goal.")
