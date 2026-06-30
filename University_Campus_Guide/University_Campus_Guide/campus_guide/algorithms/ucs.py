from __future__ import annotations

import heapq
import time
from typing import Dict, List, Optional, Set, Tuple

from map_data import GridPos, Stage, movement_cost, neighbors

from .common import (
    NeighborInfo,
    SearchResult,
    TraceStep,
    action_name,
    finish_search as _finish,
    frontier_from_heap as _frontier_from_heap,
    h as _h,
    reconstruct,
)


def ucs(stage: Stage) -> SearchResult:
    name = "UCS"
    start_time = time.perf_counter()
    start, goal = stage.start, stage.goal
    frontier: List[Tuple[float, int, GridPos]] = [(0.0, 0, start)]
    parent: Dict[GridPos, Optional[GridPos]] = {start: None}
    best_g: Dict[GridPos, float] = {start: 0.0}
    reached: Set[GridPos] = set()
    trace: List[TraceStep] = []
    expanded = 0
    order = 1
    while frontier:
        g, _, current = heapq.heappop(frontier)
        if current in reached:
            continue
        reached.add(current)
        expanded += 1
        infos: List[NeighborInfo] = []
        if current == goal:
            path = reconstruct(parent, goal)
            trace.append(TraceStep(expanded, current, _frontier_from_heap(frontier), list(reached), infos, name, g, _h(current, goal), f"{name}: pop node có g(n) nhỏ nhất."))
            return _finish(name, start_time, path, stage, expanded, trace)
        for nb in neighbors(current, stage):
            step = movement_cost(nb, stage)
            new_g = g + step
            if nb in reached and new_g >= best_g.get(nb, float("inf")):
                infos.append(NeighborInfo(nb, action_name(current, nb), f"g={new_g:.1f}", "SKIP", "Reached đã có g tốt hơn hoặc bằng."))
                continue
            if new_g < best_g.get(nb, float("inf")):
                best_g[nb] = new_g
                parent[nb] = current
                heapq.heappush(frontier, (new_g, order, nb))
                order += 1
                infos.append(NeighborInfo(nb, action_name(current, nb), f"g={new_g:.1f}", "ADD/UPDATE", "Cập nhật g(child)=g(parent)+step_cost vào Priority Queue."))
            else:
                infos.append(NeighborInfo(nb, action_name(current, nb), f"g={new_g:.1f}", "SKIP", "Frontier đã có đường tốt hơn."))
        if len(trace) < 1500:
            trace.append(TraceStep(expanded, current, _frontier_from_heap(frontier), list(reached), infos, name, g, _h(current, goal), f"{name}: Priority Queue theo g(n)."))
    return _finish(name, start_time, [], stage, expanded, trace)
