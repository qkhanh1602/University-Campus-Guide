from __future__ import annotations

import math
import random
import time
from typing import Dict, List, Optional, Set, Tuple

from map_data import GridPos, Stage, manhattan, neighbors

from .common import (
    NeighborInfo,
    SearchResult,
    TraceStep,
    action_name,
    finish_search as _finish,
    h as _h,
    path_cost,
    stopped_search as _stopped,
)

def _local_value(pos: GridPos, stage: Stage) -> float:
    return float(_h(pos, stage.goal))

def random_restart_hill(stage: Stage) -> SearchResult:
    start_time = time.perf_counter()
    random.seed(11)
    all_trace: List[TraceStep] = []
    total_expanded = 0
    best_path: List[GridPos] = [stage.start]
    best_score = float("inf")
    # Restart bằng random walk từ START; path vẫn liên tục, không teleport.
    for restart in range(1, 8):
        prefix = [stage.start]
        cur = stage.start
        prev: Optional[GridPos] = None
        for _ in range(restart):
            opts = [p for p in neighbors(cur, stage) if p != prev]
            if not opts:
                opts = neighbors(cur, stage)
            if not opts:
                break
            nxt = random.choice(opts)
            prev, cur = cur, nxt
            prefix.append(cur)
        current = prefix[-1]
        path = prefix[:]
        reached = set(path)
        for _ in range(45):
            total_expanded += 1
            cur_val = _local_value(current, stage)
            if current == stage.goal:
                return _finish("Random Restart Hill Climbing", start_time, path, stage, total_expanded, all_trace)
            infos: List[NeighborInfo] = []
            better: List[Tuple[float, GridPos]] = []
            for nb in neighbors(current, stage):
                val = _local_value(nb, stage)
                if nb in reached:
                    infos.append(NeighborInfo(nb, action_name(current, nb), f"h={val:.1f}", "SKIP", "Đã đi qua trong restart này."))
                elif val < cur_val:
                    better.append((val, nb))
                    infos.append(NeighborInfo(nb, action_name(current, nb), f"h={val:.1f}", "CANDIDATE", "Better neighbor."))
                else:
                    infos.append(NeighborInfo(nb, action_name(current, nb), f"h={val:.1f}", "REJECT", "Không tốt hơn current."))
            chosen = random.choice(better)[1] if better else None
            if chosen is not None:
                for info in infos:
                    if info.node == chosen:
                        info.status = "CHOSEN"
                        info.reason = "Chọn ngẫu nhiên trong Better_Neighbors của restart hiện tại."
                current = chosen
                path.append(current)
                reached.add(current)
            score = path_cost(path, stage) + _local_value(current, stage)
            if score < best_score:
                best_score = score
                best_path = path[:]
            all_trace.append(TraceStep(len(all_trace)+1, current, [x[1] for x in better], list(reached), infos, "Random Restart Hill Climbing", path_cost(path, stage), cur_val, f"Restart {restart}: random-walk prefix rồi leo đồi."))
            if chosen is None:
                break
    return _stopped("Random Restart Hill Climbing", start_time, stage, best_path, total_expanded, all_trace, "Hết restart nhưng chưa tới Goal; trả về đường tốt nhất đã gặp.")
