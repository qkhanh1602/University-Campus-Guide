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

def simulated_annealing(stage: Stage, seed: int = 7) -> SearchResult:
    start_time = time.perf_counter()
    random.seed(seed)
    current = stage.start
    path = [current]
    trace: List[TraceStep] = []
    expanded = 0
    T = 10.0
    alpha = 0.86
    Tmin = 0.05
    while T > Tmin and expanded < 220:
        expanded += 1
        cur_h = _h(current, stage.goal)
        if current == stage.goal:
            return _finish("Simulated Annealing", start_time, path, stage, expanded, trace)
        nbs = neighbors(current, stage)
        if not nbs:
            break
        nb = random.choice(nbs)
        nh = _h(nb, stage.goal)
        delta = nh - cur_h
        prob = 1.0 if delta < 0 else math.exp(-delta / max(T, 1e-9))
        rv = random.random()
        accept = delta < 0 or rv < prob
        status = "ACCEPT" if accept else "REJECT"
        reason = "Tốt hơn nên nhận chắc chắn." if delta < 0 else f"Bước xấu/ngang: p=exp(-Δ/T)={prob:.3f}, random={rv:.3f}."
        infos = [NeighborInfo(nb, action_name(current, nb), f"h_next={nh}, Δ={delta}, T={T:.2f}", status, reason)]
        trace.append(TraceStep(expanded, current, [nb], path[-30:], infos, "Simulated Annealing", path_cost(path, stage), cur_h, "SA: mỗi vòng chỉ random một neighbor; tốt hơn thì nhận, xấu hơn thì nhận theo xác suất."))
        if accept:
            # Tránh path nhảy; accepted neighbor luôn kề current.
            current = nb
            path.append(current)
        T *= alpha
    return _stopped("Simulated Annealing", start_time, stage, path, expanded, trace, "T giảm dưới Tmin hoặc hết bước nhưng chưa gặp Goal.")
