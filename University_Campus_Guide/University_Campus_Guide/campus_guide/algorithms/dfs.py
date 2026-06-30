from __future__ import annotations

import time
from typing import Dict, List, Optional, Set

from map_data import GridPos, Stage, neighbors

from .common import NeighborInfo, SearchResult, TraceStep, action_name, finish_search, reconstruct


def dfs(stage: Stage) -> SearchResult:
    start_time = time.perf_counter()
    start, goal = stage.start, stage.goal
    frontier: List[GridPos] = [start]
    frontier_set: Set[GridPos] = {start}
    reached: Set[GridPos] = {start}
    parent: Dict[GridPos, Optional[GridPos]] = {start: None}
    trace: List[TraceStep] = []
    expanded = 0

    while frontier:
        current = frontier.pop()
        frontier_set.discard(current)
        expanded += 1
        infos: List[NeighborInfo] = []

        if current == goal:
            path = reconstruct(parent, goal)
            trace.append(TraceStep(
                expanded,
                current,
                list(reversed(frontier))[:16],
                list(reached),
                infos,
                "DFS",
                len(path) - 1,
                0,
                "DFS: Stack LIFO, pop node hiện tại rồi goal-test.",
            ))
            return finish_search("DFS", start_time, path, stage, expanded, trace)

        for nb in reversed(neighbors(current, stage)):
            if nb not in reached and nb not in frontier_set:
                reached.add(nb)
                frontier.append(nb)
                frontier_set.add(nb)
                parent[nb] = current
                infos.append(NeighborInfo(
                    nb,
                    action_name(current, nb),
                    "push",
                    "PUSH",
                    "Đưa vào Stack; node push sau sẽ được xét trước.",
                ))
            else:
                infos.append(NeighborInfo(
                    nb,
                    action_name(current, nb),
                    "",
                    "SKIP",
                    "Đã có trong reached/frontier.",
                ))

        if len(trace) < 1500:
            trace.append(TraceStep(
                expanded,
                current,
                list(reversed(frontier))[:16],
                list(reached),
                infos,
                "DFS",
                0,
                0,
                "DFS ưu tiên đi sâu một nhánh trước.",
            ))

    return finish_search("DFS", start_time, [], stage, expanded, trace)
