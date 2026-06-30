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


def astar(stage: Stage) -> SearchResult:
    name = "A*"
    weight = 1.0
    mode = "normal"
    start_time = time.perf_counter()
    start, goal = stage.start, stage.goal
    frontier: List[Tuple[float, int, GridPos]] = [(float(weight*_h(start, goal)), 0, start)]
    parent: Dict[GridPos, Optional[GridPos]] = {start: None}
    g_score: Dict[GridPos, float] = {start: 0.0}
    best_f: Dict[GridPos, float] = {start: float(weight*_h(start, goal))}
    reached: Set[GridPos] = set()
    trace: List[TraceStep] = []
    expanded = 0
    order = 1
    while frontier:
        f, _, current = heapq.heappop(frontier)
        if f != best_f.get(current):
            continue
        best_f.pop(current, None)
        if current in reached:
            continue
        expanded += 1
        infos: List[NeighborInfo] = []
        gcur = g_score[current]
        if current == goal:
            path = reconstruct(parent, goal)
            trace.append(TraceStep(expanded, current, _frontier_from_heap(frontier), list(reached), infos, name, gcur, _h(current, goal), f"{name}: pop node có f(n)=g(n)+h(n) nhỏ nhất."))
            return _finish(name, start_time, path, stage, expanded, trace, mode)
        reached.add(current)
        for nb in neighbors(current, stage):
            step = movement_cost(nb, stage, mode)
            new_g = gcur + step
            h = _h(nb, goal)
            new_f = new_g + weight * h
            if nb in reached and new_g >= g_score.get(nb, float("inf")):
                infos.append(NeighborInfo(nb, action_name(current, nb), f"g={new_g:.1f}, h={h}, f={new_f:.1f}", "SKIP", "Reached đã có g tốt hơn."))
                continue
            if new_g < g_score.get(nb, float("inf")):
                g_score[nb] = new_g
                parent[nb] = current
                best_f[nb] = new_f
                heapq.heappush(frontier, (new_f, order, nb))
                order += 1
                infos.append(NeighborInfo(nb, action_name(current, nb), f"g={new_g:.1f}, h={h}, f={new_f:.1f}", "ADD/UPDATE", "Cập nhật frontier theo f(n)=g(n)+h(n)."))
            else:
                infos.append(NeighborInfo(nb, action_name(current, nb), f"g={new_g:.1f}, h={h}, f={new_f:.1f}", "SKIP", "Frontier đã có f/g tốt hơn."))
        if len(trace) < 1500:
            trace.append(TraceStep(expanded, current, _frontier_from_heap(frontier), list(reached), infos, name, gcur, _h(current, goal), f"{name}: giống 8-puzzle, frontier là Priority Queue theo f(n)."))
    return _finish(name, start_time, [], stage, expanded, trace, mode)
