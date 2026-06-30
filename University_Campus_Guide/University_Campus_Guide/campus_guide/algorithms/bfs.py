from __future__ import annotations

from collections import deque
import time
from typing import List, Set

from map_data import GridPos, Stage, neighbors

from .common import NeighborInfo, SearchResult, TraceStep, action_name


def bfs(stage: Stage) -> SearchResult:
    start_time = time.perf_counter()
    start, goal = stage.start, stage.goal

    frontier = deque([{"pos": start, "path": [start]}])
    reached: Set[GridPos] = {start}
    trace: List[TraceStep] = []
    expanded = 0

    while frontier:
        node = frontier.popleft()
        current: GridPos = node["pos"]
        path: List[GridPos] = node["path"]
        expanded += 1

        infos: List[NeighborInfo] = []
        current_steps = len(path) - 1

        if current == goal:
            trace.append(TraceStep(
                expanded,
                current,
                [n["pos"] for n in list(frontier)[:16]],
                list(reached),
                infos,
                "BFS",
                current_steps,
                0,
                "BFS: Queue FIFO, duyệt theo chiều rộng. Cost = số bước di chuyển.",
            ))

            runtime_ms = (time.perf_counter() - start_time) * 1000

            return SearchResult(
                "BFS",
                path,
                int(current_steps),
                expanded,
                trace,
                round(runtime_ms, 3),
                "Hoàn thành",
                False,
            )

        for nb in neighbors(current, stage):
            depth_child = len(path)

            if nb not in reached:
                reached.add(nb)
                frontier.append({"pos": nb, "path": path + [nb]})

                infos.append(NeighborInfo(
                    nb,
                    action_name(current, nb),
                    f"step={depth_child}",
                    "ADD",
                    "Chưa có trong reached nên thêm vào cuối Queue FIFO. Cost child = cost parent + 1.",
                ))
            else:
                infos.append(NeighborInfo(
                    nb,
                    action_name(current, nb),
                    "",
                    "SKIP",
                    "Đã có trong reached nên bỏ qua.",
                ))

        if len(trace) < 1500:
            trace.append(TraceStep(
                expanded,
                current,
                [n["pos"] for n in list(frontier)[:16]],
                list(reached),
                infos,
                "BFS",
                current_steps,
                0,
                "BFS không dùng cost địa hình và không dùng h(n). Cost trong mô phỏng = số bước di chuyển.",
            ))

    runtime_ms = (time.perf_counter() - start_time) * 1000

    return SearchResult(
        "BFS",
        [],
        0,
        expanded,
        trace,
        round(runtime_ms, 3),
        "Dừng - không tìm thấy Goal",
        False,
    )