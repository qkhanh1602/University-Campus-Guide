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
    stopped_search as _stopped,
)

def local_beam(stage: Stage, k: int = 3) -> SearchResult:
    start_time = time.perf_counter()
    start, goal = stage.start, stage.goal
    # k trạng thái khởi đầu được tạo bằng các random-walk ngắn từ Start để không teleport.
    current_set: List[Dict[str, object]] = [{"pos": start, "path": [start], "h": _h(start, goal)}]
    for i, nb in enumerate(neighbors(start, stage)[:max(0, k-1)]):
        current_set.append({"pos": nb, "path": [start, nb], "h": _h(nb, goal)})
    trace: List[TraceStep] = []
    expanded = 0
    best = min(current_set, key=lambda x: x["h"])  # type: ignore[index]
    for round_idx in range(1, 90):
        all_candidates: List[Dict[str, object]] = []
        infos: List[NeighborInfo] = []
        for item in current_set:
            pos: GridPos = item["pos"]  # type: ignore[index]
            path: List[GridPos] = item["path"]  # type: ignore[index]
            expanded += 1
            if pos == goal:
                return _finish("Local Beam Search", start_time, path, stage, expanded, trace)
            for nb in neighbors(pos, stage):
                h = _h(nb, goal)
                if nb in path:
                    infos.append(NeighborInfo(nb, f"{pos}->{action_name(pos, nb)}", f"h={h}", "SKIP", "Tránh lặp trong nhánh beam."))
                    continue
                cand = {"pos": nb, "path": path+[nb], "h": h}
                all_candidates.append(cand)
                infos.append(NeighborInfo(nb, f"{pos}->{action_name(pos, nb)}", f"h={h}", "CANDIDATE", "Neighbor sinh ra từ một state trong Current_State_set."))
        if not all_candidates:
            return _stopped("Local Beam Search", start_time, stage, best["path"], expanded, trace, "Neighbor_States rỗng, trả về trạng thái tốt nhất đã gặp.")  # type: ignore[arg-type]
        for cand in all_candidates:
            if cand["pos"] == goal:
                path = cand["path"]  # type: ignore[assignment]
                trace.append(TraceStep(len(trace)+1, goal, [x["pos"] for x in current_set], [], infos, "Local Beam Search", 0.0, 0, "Local Beam: gặp Goal trong Neighbor_States nên dừng ngay. Thuật toán chỉ dùng h(n), không dùng g(n) để chọn beam."))
                return _finish("Local Beam Search", start_time, path, stage, expanded, trace)
        all_candidates.sort(key=lambda x: x["h"])  # type: ignore[index]
        current_set = all_candidates[:k]
        if current_set[0]["h"] < best["h"]:  # type: ignore[index]
            best = current_set[0]
        chosen_positions = [x["pos"] for x in current_set]  # type: ignore[index]
        for info in infos:
            if info.node in chosen_positions:
                info.status = "CHOSEN"
                info.reason = f"Giữ lại trong k={k} trạng thái tốt nhất theo h(n)."
        trace.append(TraceStep(round_idx, current_set[0]["pos"], chosen_positions, [x["pos"] for x in current_set], infos, "Local Beam Search", 0.0, current_set[0]["h"], f"Local Beam: sinh neighbor của tất cả current states, sắp xếp theo h(n) tăng dần, lấy k={k}. g(n) không được dùng trong bước chọn beam."))  # type: ignore[arg-type]
    return _stopped("Local Beam Search", start_time, stage, best["path"], expanded, trace, "Hết số vòng Local Beam.")
