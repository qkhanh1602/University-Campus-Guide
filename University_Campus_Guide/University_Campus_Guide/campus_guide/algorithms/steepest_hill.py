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

def steepest_hill(stage: Stage) -> SearchResult:
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
        candidates: List[Tuple[float, GridPos]] = []
        if current == stage.goal:
            return _finish("Steepest Hill Climbing", start_time, path, stage, expanded, trace)
        for nb in neighbors(current, stage):
            val = _local_value(nb, stage)
            if nb in reached:
                infos.append(NeighborInfo(nb, action_name(current, nb), f"h={val:.1f}", "SKIP", "Đã đi qua, tránh vòng lặp."))
            elif val < cur_val:
                candidates.append((val, nb))
                infos.append(NeighborInfo(nb, action_name(current, nb), f"h={val:.1f}", "CANDIDATE", "Neighbor tốt hơn current."))
            else:
                infos.append(NeighborInfo(nb, action_name(current, nb), f"h={val:.1f}", "REJECT", "Không tốt hơn current."))
        chosen = min(candidates, key=lambda x: x[0])[1] if candidates else None
        if chosen is not None:
            for info in infos:
                if info.node == chosen:
                    info.status = "CHOSEN"
                    info.reason = "Steepest xét hết neighbor rồi chọn h nhỏ nhất."
        trace.append(TraceStep(expanded, current, [x[1] for x in sorted(candidates)[:8]], list(reached), infos, "Steepest Hill Climbing", path_cost(path, stage), cur_val, "Steepest Hill Climbing: xét toàn bộ neighbor rồi chọn tốt nhất."))
        if chosen is None:
            return _stopped("Steepest Hill Climbing", start_time, stage, path, expanded, trace, "Kẹt local optimum: không có candidate tốt hơn.")
        current = chosen
        path.append(current)
        reached.add(current)
    return _stopped("Steepest Hill Climbing", start_time, stage, path, expanded, trace, "Vượt quá số bước local search.")
