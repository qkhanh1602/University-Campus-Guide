from __future__ import annotations

import heapq
import time
from typing import Dict, List, Set, Tuple

from map_data import GridPos, Stage, neighbors

from .common import (
    NeighborInfo,
    SearchResult,
    TraceStep,
    action_name,
    finish_search as _finish,
    h as _h,
    path_cost,
)


def greedy_best_first(stage: Stage) -> SearchResult:
    start_time = time.perf_counter()
    start, goal = stage.start, stage.goal
    frontier: List[Tuple[float, int, Dict[str, object]]] = [(float(_h(start, goal)), 0, {"pos": start, "path": [start]})]
    frontier_keys: Set[GridPos] = {start}
    reached: Set[GridPos] = set()
    trace: List[TraceStep] = []
    expanded = 0
    order = 1
    while frontier:
        h, _, node = heapq.heappop(frontier)
        current: GridPos = node["pos"]  # type: ignore[index]
        path: List[GridPos] = node["path"]  # type: ignore[index]
        if current not in frontier_keys:
            continue
        frontier_keys.remove(current)
        if current in reached:
            continue
        expanded += 1
        infos: List[NeighborInfo] = []
        if current == goal:
            trace.append(TraceStep(expanded, current, [x[2]["pos"] for x in sorted(frontier)[:16]], list(reached), infos, "Greedy Best First", path_cost(path, stage), h, "Greedy: chọn node có h(n) nhỏ nhất."))
            return _finish("Greedy Best First", start_time, path, stage, expanded, trace)
        reached.add(current)
        for nb in neighbors(current, stage):
            hn = _h(nb, goal)
            if nb not in reached and nb not in frontier_keys:
                heapq.heappush(frontier, (hn, order, {"pos": nb, "path": path+[nb]}))
                frontier_keys.add(nb)
                order += 1
                infos.append(NeighborInfo(nb, action_name(current, nb), f"h={hn}", "ADD", "Thêm vào Priority Queue theo h(n)."))
            else:
                infos.append(NeighborInfo(nb, action_name(current, nb), f"h={hn}", "SKIP", "Đã có trong reached/frontier."))
        if len(trace) < 1500:
            trace.append(TraceStep(expanded, current, [x[2]["pos"] for x in sorted(frontier)[:16]], list(reached), infos, "Greedy Best First", path_cost(path, stage), h, "Greedy dùng h(n), không quan tâm g(n) khi chọn node."))
    return _finish("Greedy Best First", start_time, [], stage, expanded, trace)
