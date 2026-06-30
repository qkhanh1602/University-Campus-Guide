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

def simple_hill(stage: Stage) -> SearchResult:
    start_time = time.perf_counter()
    current = stage.start
    path = [current]
    reached = {current}
    trace: List[TraceStep] = []
    expanded = 0
    while expanded < 160:
        expanded += 1
        cur_val = _local_value(current, stage)
        infos: List[NeighborInfo] = []
        if current == stage.goal:
            return _finish("Simple Hill Climbing", start_time, path, stage, expanded, trace)
        chosen: Optional[GridPos] = None
        for nb in neighbors(current, stage):
            val = _local_value(nb, stage)
            if nb in reached:
                infos.append(NeighborInfo(nb, action_name(current, nb), f"h={val:.1f}", "SKIP", "Đã đi qua, tránh vòng lặp."))
            elif val < cur_val:
                chosen = nb
                infos.append(NeighborInfo(nb, action_name(current, nb), f"h={val:.1f} < {cur_val:.1f}", "CHOSEN", "Chọn ngay neighbor đầu tiên tốt hơn current."))
                break
            else:
                infos.append(NeighborInfo(nb, action_name(current, nb), f"h={val:.1f}", "REJECT", "Không cải thiện so với current."))
        trace.append(TraceStep(expanded, current, [chosen] if chosen else [], list(reached), infos, "Simple Hill Climbing", path_cost(path, stage), cur_val, "Simple Hill Climbing: gặp neighbor đầu tiên có h nhỏ hơn thì đi ngay."))
        if chosen is None:
            return _stopped("Simple Hill Climbing", start_time, stage, path, expanded, trace, "Kẹt local optimum: không có neighbor tốt hơn.")
        current = chosen
        path.append(current)
        reached.add(current)
    return _stopped("Simple Hill Climbing", start_time, stage, path, expanded, trace, "Vượt quá số bước local search.")
