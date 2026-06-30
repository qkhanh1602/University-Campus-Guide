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

def stochastic_hill(stage: Stage, seed: int = 9) -> SearchResult:
    """Stochastic Hill Climbing: chọn ngẫu nhiên trong các neighbor tốt hơn.

    Bám theo style 8-puzzle: current chỉ đi sang neighbor có h nhỏ hơn.
    Nếu không có neighbor tốt hơn thì dừng tại local optimum, không dùng fallback.
    """
    random.seed(seed)
    start_time = time.perf_counter()
    current = stage.start
    path = [current]
    trace: List[TraceStep] = []
    reached = {current}
    expanded = 0
    best_path = path[:]
    best_h = manhattan(current, stage.goal)

    for step in range(1, 180):
        h_current = manhattan(current, stage.goal)
        if h_current < best_h:
            best_h = h_current
            best_path = path[:]
        infos: List[NeighborInfo] = []

        if current == stage.goal:
            trace.append(TraceStep(step, current, [], list(reached), infos, "Stochastic Hill Climbing", path_cost(path, stage), h_current, "Leo núi ngẫu nhiên: đã gặp Goal."))
            return _finish("Stochastic Hill Climbing", start_time, path, stage, expanded, trace)

        expanded += 1
        better: List[GridPos] = []
        for nb in neighbors(current, stage):
            h_nb = manhattan(nb, stage.goal)
            if nb in reached:
                infos.append(NeighborInfo(nb, action_name(current, nb), f"h={h_nb}", "SKIP", "Neighbor đã nằm trong reached."))
            elif h_nb < h_current:
                better.append(nb)
                infos.append(NeighborInfo(nb, action_name(current, nb), f"h={h_nb}", "BETTER", f"h(neighbor) < h(current) = {h_current}."))
            else:
                infos.append(NeighborInfo(nb, action_name(current, nb), f"h={h_nb}", "SKIP", f"Không tốt hơn vì h >= {h_current}."))

        if not better:
            trace.append(TraceStep(step, current, [], list(reached), infos, "Stochastic Hill Climbing", path_cost(path, stage), h_current, "Dừng tại local optimum: không còn neighbor tốt hơn."))
            return _stopped("Stochastic Hill Climbing", start_time, stage, best_path, expanded, trace, "Không có neighbor tốt hơn nên dừng tại local optimum.")

        chosen = random.choice(better)
        for info in infos:
            if info.node == chosen:
                info.status = "CHOSEN"
                info.reason = "Chọn ngẫu nhiên trong tập Better Neighbors."
                break
        trace.append(TraceStep(step, current, better[:12], list(reached), infos, "Stochastic Hill Climbing", path_cost(path, stage), h_current, "Lọc neighbor tốt hơn current rồi chọn ngẫu nhiên một neighbor."))
        current = chosen
        path.append(current)
        reached.add(current)

    return _stopped("Stochastic Hill Climbing", start_time, stage, best_path, expanded, trace, "Hết số bước stochastic hill climbing.")
