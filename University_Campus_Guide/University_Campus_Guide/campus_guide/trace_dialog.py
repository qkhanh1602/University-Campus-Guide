from __future__ import annotations

from typing import Dict, List, Optional
import math
import re

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QBrush, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from algorithms.search_algorithms import SearchResult, TraceStep
from algorithms.common import action_name
from algorithms.game_common import (
    EXPECTIMAX_DEPTH,
    LOOKAHEAD_DEPTH,
    MAX_AGENT_BRANCH,
    MAX_CHANCE_BRANCH,
    _expectimax_value,
    _game_value,
    _game_static_value,
    _score_breakdown,
    _environment_penalty,
)
from map_data import landmark_name_at, manhattan, neighbors


def _is_grid_pos(value) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], int)
        and isinstance(value[1], int)
    )


def fmt_pos(pos) -> str:
    if _is_grid_pos(pos):
        name = landmark_name_at(pos)
        return f"({pos[0]}, {pos[1]})" + (f" - {name}" if name else "")

    if isinstance(pos, float):
        if pos.is_integer():
            return str(int(pos))
        return f"{pos:.2f}"

    if isinstance(pos, int):
        return str(pos)

    if isinstance(pos, (list, tuple, set, frozenset)):
        values = list(pos)

        if not values:
            return "Rỗng"

        if all(_is_grid_pos(v) for v in values):
            shown = [fmt_pos(v) for v in values[:8]]
            if len(values) > 8:
                shown.append(f"... còn {len(values) - 8} ô")
            return "{ " + "; ".join(shown) + " }"

        shown = [fmt_pos(v) for v in values[:8]]
        if len(values) > 8:
            shown.append(f"... còn {len(values) - 8} giá trị")
        return "{ " + "; ".join(shown) + " }"

    return str(pos)


def trace_metric_labels(step: TraceStep, algorithm: str):
    mode = (step.mode or algorithm or "").lower()
    alg = (algorithm or "").lower()
    text = mode + " " + alg
    if "minimax" in text or "alpha-beta" in text or "expectimax" in text:
        return ("Cay doi khang", "MAX/MIN/CHANCE", "Diem danh gia", "xem bang")

    if "minimax" in text or "alpha-beta" in text or "expectimax" in text:
        return ("Giới hạn độ sâu", "3", "Điểm đánh giá", "xem bảng")

    if "and-or" in text or "and_or" in text or "and or" in text:
        return ("Cost tuyến", f"{step.cost:.0f}", "h(n)", f"{step.heuristic:.0f}")

    if "backtracking" in text or "forward checking" in text or "min-conflicts" in text:
        return ("Cost tuyến", f"{step.cost:.0f}", "Số vi phạm", f"{step.heuristic:.0f}")

    if "local beam" in text and "belief" not in text:
        return ("g(n)", "Không dùng", "h(n) / Manhattan", f"{step.heuristic:.0f}")

    if "belief" in text:
        return ("Cost g(B)", f"{step.cost:.0f}", "Heuristic h(B)", f"{step.heuristic:.0f}")

    if "bfs" in text or "dfs" in text or "ids" in text or "dls" in text:
        return ("Độ sâu", f"{step.cost:.0f}", "Heuristic", "Không dùng")

    if "greedy" in text and "a*" not in text:
        return ("Cost đường đi", f"{step.cost:.0f}", "h(n)", f"{step.heuristic:.0f}")

    if "hill" in text or "leo" in text or "annealing" in text:
        return ("Cost đường đi", f"{step.cost:.0f}", "value/h", f"{step.heuristic:.0f}")

    return ("Cost g(n)", f"{step.cost:.0f}", "Heuristic h(n)", f"{step.heuristic:.0f}")




def is_csp_trace(algorithm: str, mode: str = "") -> bool:
    text = f"{algorithm} {mode}".lower()
    return any(key in text for key in ("backtracking", "forward checking", "min-conflicts"))




def is_game_trace(algorithm: str, mode: str = "") -> bool:
    text = f"{algorithm} {mode}".lower()
    return any(key in text for key in ("minimax", "alpha-beta", "expectimax"))


def is_and_or_trace(algorithm: str, mode: str = "") -> bool:
    text = f"{algorithm} {mode}".lower()
    return "and-or" in text or "and_or" in text or "and or" in text


def _selected_action_from_note(note: str) -> str:
    text = str(note)
    for marker in ("Hành động được chọn=", "Hanh dong duoc chon=", "Selected Action="):
        if marker in text:
            value = text.split(marker, 1)[1].split(".", 1)[0].split(",", 1)[0].strip()
            return value or "chưa chọn"
    return "xem bảng bên dưới"


def _selected_game_neighbor(step: TraceStep) -> Optional[object]:
    selected = _selected_action_from_note(step.note).upper()
    for nb in step.neighbors:
        status = str(nb.status).upper()
        action_upper = str(nb.action).upper()
        if status == "SELECTED" or (selected and selected != "XEM BẢNG BÊN DƯỚI" and selected in action_upper):
            return nb
    return None


def game_choice_reason(step: TraceStep, algorithm: str = "") -> str:
    """Short Vietnamese explanation for why the highlighted game-tree move is chosen."""
    selected = _selected_action_from_note(step.note)
    chosen_nb = _selected_game_neighbor(step)

    raw_value = str(chosen_nb.value) if chosen_nb is not None else ""
    score_value = _extract_game_value(raw_value) if raw_value else None
    value = f"{score_value:.1f}" if score_value is not None else "xem trên cây"
    reason = str(chosen_nb.reason) if chosen_nb is not None else ""
    if len(reason) > 110:
        reason = reason[:107].rstrip() + "..."

    text = f"Chọn {selected} vì nhánh này có điểm đánh giá tốt nhất ở nút MAX"
    alg_text = f"{algorithm} {step.mode}".lower()
    if "expectimax" in alg_text:
        text += f" sau khi tính điểm kỳ vọng EV = {value}."
    elif "alpha" in alg_text or "beta" in alg_text:
        text += f" sau khi áp dụng Minimax và cắt tỉa Alpha-Beta, điểm = {value}."
    else:
        text += f" sau khi MIN chọn tình huống bất lợi nhất, điểm = {value}."
    if reason:
        text += f" Lý do ngắn: {reason}"
    return text


def game_representation_from_step(step: TraceStep, algorithm: str) -> str:
    if "goal" in str(step.note).lower():
        return (
            "ĐÃ TỚI GOAL\n"
            f"Root state: {fmt_pos(step.current)}\n"
            f"Thuật toán: {algorithm}\n"
            "Kết quả: agent đã tới ô Goal, trace kết thúc tại đây."
        )

    selected = _selected_action_from_note(step.note)
    chosen_nb = _selected_game_neighbor(step)
    next_state = chosen_nb.node if chosen_nb is not None else (step.frontier[0] if step.frontier else step.current)
    selected_text = _action_vi(selected)
    return (
        "DECISION SNAPSHOT\n"
        f"Root state: {fmt_pos(step.current)}\n"
        f"Thuật toán: {algorithm}\n"
        f"Action được chọn: {selected_text}\n"
        f"Next state: {fmt_pos(next_state)}\n"
        f"Lý do chọn: {game_choice_reason(step, algorithm)}"
    )


def game_selected_action_text(step: TraceStep, algorithm: str = "") -> str:
    selected = _selected_action_from_note(step.note)
    return (
        "HÀNH ĐỘNG ĐƯỢC CHỌN\n"
        f"{selected}\n\n"
        f"{game_choice_reason(step, algorithm)}"
    )



def _extract_game_value(text: str) -> Optional[float]:
    """Extract the first numeric điểm/expected value from a trace cell."""
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(text))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _action_vi(action: str) -> str:
    text = str(action or "").upper()
    for eng, vi in (
        ("UP", "ĐI LÊN"),
        ("DOWN", "ĐI XUỐNG"),
        ("LEFT", "ĐI TRÁI"),
        ("RIGHT", "ĐI PHẢI"),
        ("STAY", "ĐỨNG YÊN"),
    ):
        if eng in text:
            return vi
    cleaned = str(action).replace("MAX chọn", "").replace("MAX", "").strip()
    return cleaned or "HÀNH ĐỘNG"




def _action_key(text: str) -> str:
    upper = str(text or "").upper()
    for key in ("UP", "DOWN", "LEFT", "RIGHT", "STAY"):
        if key in upper:
            return key
    return upper.strip()


def _game_phase_from_note(note: str) -> str:
    upper = str(note or "").upper()
    for phase in ("LEAF", "MIN", "CHANCE", "ALPHA_BETA", "PRUNE", "MAX"):
        if f"PHASE={phase}" in upper:
            return phase
    return "MAX"

def _short_pos(pos) -> str:
    if _is_grid_pos(pos):
        name = landmark_name_at(pos)
        if name:
            return f"({pos[0]}, {pos[1]})\n{name}"
        return f"({pos[0]}, {pos[1]})"
    return fmt_pos(pos)


def _parse_grid_positions_from_text(text: str) -> List[tuple]:
    """Extract grid positions like (22, 34) from a trace string."""
    positions = []
    for a, b in re.findall(r"\((\d+)\s*,\s*(\d+)\)", str(text)):
        positions.append((int(a), int(b)))
    return positions


class GameTreeWidget(QWidget):
    """Zoomable + pannable full-tree view for Stage 5.

    The tree is always drawn from the whole trace, so it looks like a classroom
    adversarial tree. Navigation buttons only change the highlighted node/row
    and table detail; they do not hide earlier or later parts of the tree.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.step: Optional[TraceStep] = None
        self.result: Optional[SearchResult] = None
        self.algorithm = ""
        self.scale = 0.58
        self.offset = QPointF(36, 32)
        self._dragging = False
        self._last_mouse = QPointF(0, 0)
        self._tree_cache = None
        self._score_cache = {}
        self._canvas_size = (1400, 720)
        self.current_index = 0
        self._current_state = None
        self._last_result_object = None
        self.setMinimumHeight(500)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)
        self.setAutoFillBackground(False)

    # ---------- public controls ----------
    def set_step(self, step: TraceStep, algorithm: str) -> None:
        # Backward compatible entry point. Used only when a SearchResult is not available.
        self.step = step
        self.result = None
        self.algorithm = algorithm or ""
        self._tree_cache = None
        self._score_cache = {}
        self.update()

    def set_result(self, result: SearchResult, current_index: int = 0) -> None:
        new_result = result is not self._last_result_object
        self.result = result
        if result and result.trace:
            self.current_index = max(0, min(current_index, len(result.trace) - 1))
            self.step = result.trace[self.current_index]
            self._current_state = self.step.current
        else:
            self.current_index = 0
            self.step = None
            self._current_state = None
        self.algorithm = result.algorithm if result else ""
        self._tree_cache = None
        self._score_cache = {}
        if new_result:
            self._last_result_object = result
            self.reset_view()
        else:
            self.update()

    def zoom_in(self) -> None:
        self._zoom_at(1.18, QPointF(self.width() / 2, self.height() / 2))

    def zoom_out(self) -> None:
        self._zoom_at(1 / 1.18, QPointF(self.width() / 2, self.height() / 2))

    def reset_view(self) -> None:
        """Đưa cây về khung xem dễ đọc, không ép fit theo toàn bộ số trạng thái.

        Với cây đối kháng dài, nếu fit toàn bộ cây vào viewport thì node bị quá nhỏ
        và các tầng đè lên vùng bảng. Vì vậy nút “Vừa khung” chỉ đưa gốc cây lên
        đầu khung với tỉ lệ đọc được; người dùng kéo/lăn chuột trong khung cây để
        xem các tầng dưới.
        """
        tree = self._make_tree()
        if not tree:
            self.scale = 0.82
            self.offset = QPointF(36, 42)
            self.update()
            return

        self.scale = 0.82
        root_x = float(tree.get("x", self._canvas_size[0] / 2))
        self.offset = QPointF((self.width() / 2) - root_x * self.scale, 72)
        self.update()

    # ---------- interaction: drag + zoom ----------
    def _zoom_at(self, factor: float, anchor: QPointF) -> None:
        new_scale = max(0.28, min(2.8, self.scale * factor))
        if abs(new_scale - self.scale) < 0.001:
            return
        before = QPointF(
            (anchor.x() - self.offset.x()) / self.scale,
            (anchor.y() - self.offset.y()) / self.scale,
        )
        self.scale = new_scale
        self.offset = QPointF(
            anchor.x() - before.x() * self.scale,
            anchor.y() - before.y() * self.scale,
        )
        self.update()

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt naming
        delta = event.angleDelta().y()
        if delta == 0:
            return

        # Ctrl + lăn chuột = zoom. Lăn chuột thường = cuộn cây lên/xuống.
        # Cách này giúp xem được các phần bị khuất mà không làm chữ nhỏ đi.
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.14 if delta > 0 else 1 / 1.14
            self._zoom_at(factor, event.position())
        else:
            # Wheel up moves the canvas down visually, like scrolling lên trên nội dung.
            self.offset = QPointF(self.offset.x(), self.offset.y() + delta * 0.42)
            self.update()
        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._last_mouse = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self._dragging:
            pos = event.position()
            delta = pos - self._last_mouse
            self._last_mouse = pos
            self.offset = QPointF(self.offset.x() + delta.x(), self.offset.y() + delta.y())
            self.update()
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self.setCursor(Qt.OpenHandCursor)
            event.accept()

    # ---------- tree construction ----------
    def _is_expectimax(self) -> bool:
        return "expectimax" in (self.algorithm or "").lower()

    def _is_alpha_beta(self) -> bool:
        alg = (self.algorithm or "").lower()
        return "alpha" in alg or "beta" in alg

    def _lookahead_depth(self) -> int:
        return EXPECTIMAX_DEPTH if self._is_expectimax() else LOOKAHEAD_DEPTH

    def _selected_action(self, step: TraceStep) -> str:
        selected = _selected_action_from_note(step.note).upper()
        if selected and selected != "XEM BẢNG BÊN DƯỚI":
            return selected
        for nb in step.neighbors:
            if str(nb.status).upper() == "SELECTED":
                return str(nb.action).upper()
        return selected

    def _visible_trace(self) -> List[TraceStep]:
        """Return the full trace for the game tree.

        Minimax, Alpha-Beta and Expectimax conceptually evaluate a complete
        depth-limited decision tree and then propagate values from leaves back
        to the root. Therefore the UI always shows the full tree from the first
        state to the final state. The current trace index is used only to
        highlight the node/branch currently being explained in the table below.
        """
        if not self.result or not self.result.trace:
            return [self.step] if self.step else []
        return list(self.result.trace)

    def _trace_map(self) -> Dict[object, TraceStep]:
        out: Dict[object, TraceStep] = {}
        for step in self._visible_trace():
            # Stage 5 now has several explanation phases for the same state
            # (LEAF -> MIN/CHANCE/ALPHA_BETA -> MAX).  Use the MAX/SELECTED
            # phase to build the full decision tree, otherwise the first LEAF
            # phase would have no selected continuation to expand.
            has_selected = any(str(nb.status).upper() == "SELECTED" for nb in step.neighbors)
            is_decision_phase = _game_phase_from_note(step.note) == "MAX" or has_selected
            if step.current not in out or is_decision_phase:
                out[step.current] = step
        return out

    def _make_tree(self):
        """Build a readable depth-limited look-ahead tree for the current game step.

        Stage 5 algorithms do not draw one long route like BFS/A*.  At each
        current state they look ahead a limited number of plies, evaluate leaf
        scores, and propagate values back to the root.  The visual tree therefore
        shows a local look-ahead tree with a selected spine expanded deeply and
        sibling choices kept as compact score nodes.
        """
        if self._tree_cache is not None:
            return self._tree_cache
        if not self.step:
            self._tree_cache = None
            return None

        stage = getattr(self.result, "stage", None)
        if stage is None:
            self._tree_cache = self._make_tree_from_step_only()
            return self._tree_cache

        phase = _game_phase_from_note(self.step.note)
        current = self.step.current
        lookahead_depth = self._lookahead_depth()
        reached_goal = current == stage.goal or "goal" in str(self.step.note).lower()
        root = {
            "kind": "GOAL" if reached_goal else "MAX",
            "title": "GOAL" if reached_goal else "MAX",
            "body": (
                f"State {self._pos_one_line(current)}\nĐã tới GOAL\nHoàn thành"
                if reached_goal
                else f"State {self._pos_one_line(current)}\n{self._landmark_short(current)}\nNhìn trước {lookahead_depth} bước"
            ),
            "value": "DONE" if reached_goal else "",
            "status": "CURRENT",
            "active": phase == "MAX" or reached_goal,
            "selected": reached_goal,
            "pruned": False,
            "depth": 0,
            "children": [],
            "x": 0,
            "y": 0,
        }
        if reached_goal:
            self._layout_tree(root)
            self._tree_cache = root
            return root
        self._expand_lookahead(root, current, "MAX", lookahead_depth, {current}, selected_spine=True)
        self._layout_tree(root)
        self._tree_cache = root
        return root

    def _pos_one_line(self, pos) -> str:
        if _is_grid_pos(pos):
            return f"({pos[0]}, {pos[1]})"
        return fmt_pos(pos)

    def _landmark_short(self, pos) -> str:
        if not _is_grid_pos(pos):
            return ""
        name = landmark_name_at(pos) or ""
        if len(name) > 22:
            return name[:19].rstrip() + "..."
        return name

    def _phase(self) -> str:
        return _game_phase_from_note(self.step.note if self.step else "")

    def _score_for(self, pos, remaining: int, next_maximizing: bool) -> float:
        stage = getattr(self.result, "stage", None)
        if stage is None:
            return 0.0
        if self._is_expectimax():
            return _expectimax_value(
                pos,
                stage,
                min(max(0, remaining), EXPECTIMAX_DEPTH),
                next_maximizing,
                cache=self._score_cache,
            )
        return _game_value(
            pos,
            stage,
            max(0, remaining),
            next_maximizing,
            use_ab=self._is_alpha_beta(),
            expectimax_mode=self._is_expectimax(),
            cache=self._score_cache,
        )

    def _score_label(self, value: float) -> str:
        return f"{value:+.1f}"

    def _phase_active(self, kind: str, depth: int, is_leaf: bool = False, pruned: bool = False) -> bool:
        phase = self._phase()
        if phase == "LEAF":
            return is_leaf or depth >= self._lookahead_depth()
        if phase in {"MIN", "ALPHA_BETA"}:
            return kind in {"MIN", "PRUNE"} or pruned
        if phase == "CHANCE":
            return kind == "CHANCE"
        if phase == "PRUNE":
            return pruned or kind == "PRUNE"
        if phase == "MAX":
            return kind == "MAX" and depth == 0
        return False

    def _make_child_node(self, *, kind: str, title: str, pos, value: float, depth: int,
                         selected: bool = False, pruned: bool = False, body_extra: str = ""):
        body_lines = [f"State {self._pos_one_line(pos)}"]
        lm = self._landmark_short(pos)
        if lm:
            body_lines.append(lm)
        body_lines.append(f"Điểm {self._score_label(value)}")
        if body_extra:
            body_lines.append(body_extra)
        is_leaf = depth >= self._lookahead_depth() or kind == "LÁ"
        return {
            "kind": kind,
            "title": title,
            "body": "\n".join(body_lines[:4]),
            "value": self._score_label(value),
            "status": "SELECTED" if selected else ("PRUNE" if pruned else "TRY"),
            "selected": selected,
            "active": self._phase_active(kind, depth, is_leaf=is_leaf, pruned=pruned),
            "pruned": pruned,
            "depth": depth,
            "children": [],
            "x": 0,
            "y": 0,
        }

    def _ordered_neighbors(self, pos, stage, role: str, remaining: int, path_seen: set):
        nbs = list(neighbors(pos, stage))
        filtered = [p for p in nbs if p not in path_seen]
        if filtered:
            nbs = filtered
        if role == "MAX":
            nbs.sort(key=lambda p: self._score_for(p, remaining - 1, False), reverse=True)
        elif role == "MIN":
            nbs.sort(key=lambda p: self._score_for(p, remaining - 1, True))
        else:
            nbs.sort(key=lambda p: (manhattan(p, stage.goal), _environment_penalty(p, stage)))
        limit = MAX_AGENT_BRANCH if self._is_expectimax() else 4
        return nbs[:limit]

    def _expand_lookahead(self, node, pos, role: str, remaining: int, path_seen: set, selected_spine: bool) -> None:
        stage = getattr(self.result, "stage", None)
        if stage is None or remaining <= 0 or pos == stage.goal:
            return

        is_expectimax = self._is_expectimax()
        is_alpha_beta = self._is_alpha_beta()
        nbs = self._ordered_neighbors(pos, stage, role, remaining, path_seen)
        if not nbs:
            return

        if role == "MAX":
            # MAX chooses the child with the highest backed-up score.
            scored = [(self._score_for(nb, remaining - 1, False), nb) for nb in nbs]
            scored.sort(reverse=True, key=lambda x: x[0])
            selected_pos = scored[0][1]
            for idx, (value, nb) in enumerate(scored):
                raw = action_name(pos, nb)
                action = _action_vi(raw)
                pruned = is_alpha_beta and idx >= 3 and remaining <= self._lookahead_depth() - 1
                next_kind = "CHANCE" if is_expectimax else ("PRUNE" if pruned else "MIN")
                title = f"{action}\n{next_kind if next_kind != 'PRUNE' else 'CẮT'}"
                extra = "MAX thử action" if nb == selected_pos else "So sánh"
                if pruned:
                    extra = "β ≤ α"
                child = self._make_child_node(
                    kind=next_kind,
                    title=title,
                    pos=nb,
                    value=value,
                    depth=self._lookahead_depth() - remaining + 1,
                    selected=(nb == selected_pos),
                    pruned=pruned,
                    body_extra=extra,
                )
                node["children"].append(child)
                if nb == selected_pos and not pruned and selected_spine:
                    next_role = "CHANCE" if is_expectimax else "MIN"
                    self._expand_lookahead(child, nb, next_role, remaining - 1, path_seen | {nb}, True)

        elif role == "MIN":
            # MIN/environment chooses the worst outcome for MAX.
            scored = [(self._score_for(nb, remaining - 1, True), nb) for nb in nbs]
            scored.sort(key=lambda x: x[0])
            selected_pos = scored[0][1]
            for value, nb in scored:
                raw = action_name(pos, nb)
                title = f"{_action_vi(raw)}\nMAX"
                child = self._make_child_node(
                    kind="MAX",
                    title=title,
                    pos=nb,
                    value=value,
                    depth=self._lookahead_depth() - remaining + 1,
                    selected=(nb == selected_pos),
                    body_extra="MIN chọn thấp nhất" if nb == selected_pos else "Kết quả khác",
                )
                node["children"].append(child)
                if nb == selected_pos and selected_spine:
                    self._expand_lookahead(child, nb, "MAX", remaining - 1, path_seen | {nb}, True)

        else:  # CHANCE node for Expectimax
            # Show two clear outcomes instead of a noisy full branching factor.
            normal = min(nbs, key=lambda p: manhattan(p, stage.goal))
            risky = max(nbs, key=lambda p: (_environment_penalty(p, stage), manhattan(p, stage.goal)))
            outcomes = [("70% thường", normal, 0.7), ("30% rủi ro", risky, 0.3)]
            used = set()
            for label, nb, prob in outcomes:
                if nb in used:
                    continue
                used.add(nb)
                value = self._score_for(nb, remaining - 1, True)
                child = self._make_child_node(
                    kind="MAX",
                    title=f"{label}\nMAX",
                    pos=nb,
                    value=value,
                    depth=self._lookahead_depth() - remaining + 1,
                    selected=True,
                    body_extra=f"p={prob:.1f}",
                )
                node["children"].append(child)
                # Expand the normal/closer outcome only; both outcomes are still visible
                # and contribute to the expected score shown in the table.
                if label.startswith("70") and selected_spine:
                    self._expand_lookahead(child, nb, "MAX", remaining - 1, path_seen | {nb}, True)

    def _make_tree_from_step_only(self):
        step = self.step
        if not step:
            return None
        phase = _game_phase_from_note(step.note)
        root = {
            "kind": "MAX",
            "title": "MAX",
            "body": f"State {self._pos_one_line(step.current)}\nNhìn trước {self._lookahead_depth()} bước",
            "value": "",
            "status": "CURRENT",
            "active": phase == "MAX",
            "selected": False,
            "pruned": False,
            "depth": 0,
            "children": [],
            "x": 0,
            "y": 0,
        }
        for nb in step.neighbors[:4]:
            key = _action_key(str(nb.action))
            pruned = str(nb.status).upper() == "PRUNE"
            v = _extract_game_value(str(nb.value))
            value = v if v is not None else 0.0
            selected = str(nb.status).upper() == "SELECTED"
            kind = "PRUNE" if pruned else ("CHANCE" if self._is_expectimax() else "MIN")
            root["children"].append(self._make_child_node(
                kind=kind,
                title=f"{_action_vi(str(nb.action))}\n{kind if kind != 'PRUNE' else 'CẮT'}",
                pos=nb.node,
                value=value,
                depth=1,
                selected=selected,
                pruned=pruned,
                body_extra="từ bảng trace",
            ))
        self._layout_tree(root)
        return root

    def _layout_tree(self, tree) -> None:
        """Layout with bounded spacing: not overlapping, not stretched too far."""
        top_margin = 115
        side_margin = 110
        vertical_spacing = 150
        min_gap = 34
        max_gap = 72

        def node_visual_width(node) -> float:
            return 224.0

        def measure(node) -> float:
            children = node.get("children", [])
            own = node_visual_width(node) + 20
            if not children:
                node["_width"] = own
                node["_children_width"] = 0.0
                return own
            child_widths = [measure(child) for child in children]
            gap = min(max_gap, max(min_gap, 46 + 8 * max(0, 3 - len(children))))
            children_w = sum(child_widths) + gap * (len(child_widths) - 1)
            node["_gap"] = gap
            node["_children_width"] = children_w
            node["_width"] = max(own, children_w)
            return node["_width"]

        bounds = {"min_x": 10**9, "max_x": -10**9, "min_y": 10**9, "max_y": -10**9}

        def update_bounds(node) -> None:
            rect_w = 224
            rect_h = 106
            bounds["min_x"] = min(bounds["min_x"], node["x"] - rect_w / 2)
            bounds["max_x"] = max(bounds["max_x"], node["x"] + rect_w / 2)
            bounds["min_y"] = min(bounds["min_y"], node["y"] - rect_h / 2)
            bounds["max_y"] = max(bounds["max_y"], node["y"] + rect_h / 2)

        def assign(node, left: float, depth: int) -> None:
            width = float(node.get("_width", node_visual_width(node)))
            node["x"] = left + width / 2
            node["y"] = top_margin + depth * vertical_spacing
            update_bounds(node)
            children = node.get("children", [])
            if not children:
                return
            children_w = float(node.get("_children_width", 0.0))
            gap = float(node.get("_gap", 48.0))
            child_left = left + (width - children_w) / 2
            for child in children:
                assign(child, child_left, depth + 1)
                child_left += float(child.get("_width", node_visual_width(child))) + gap

        measure(tree)
        assign(tree, side_margin, 0)

        dx = max(0.0, side_margin - bounds["min_x"])
        if dx:
            def shift(node):
                node["x"] += dx
                for child in node.get("children", []):
                    shift(child)
            shift(tree)
            bounds["max_x"] += dx
            bounds["min_x"] += dx

        canvas_w = max(1250, int(bounds["max_x"] + side_margin))
        canvas_h = max(900, int(bounds["max_y"] + 175))
        self._canvas_size = (canvas_w, canvas_h)

    # ---------- drawing ----------
    def _draw_box(self, painter: QPainter, rect: QRectF, title: str, body: str, fill: str, border: str, title_color: str = "#0f172a") -> None:
        painter.setPen(QPen(QColor(border), 2.6))
        painter.setBrush(QBrush(QColor(fill)))
        painter.drawRoundedRect(rect, 12, 12)
        painter.setPen(QColor(title_color))
        painter.setFont(QFont("Segoe UI", 9.6, QFont.Bold))
        title_rect = QRectF(rect.left() + 8, rect.top() + 7, rect.width() - 16, 34)
        painter.drawText(title_rect, Qt.AlignCenter | Qt.TextWordWrap, title)
        painter.setPen(QColor("#1f2937"))
        painter.setFont(QFont("Segoe UI", 8.2))
        body_rect = QRectF(rect.left() + 8, rect.top() + 43, rect.width() - 16, rect.height() - 50)
        painter.drawText(body_rect, Qt.AlignCenter | Qt.TextWordWrap, body)

    def _draw_arrow(self, painter: QPainter, start: QPointF, end: QPointF, color: str, dashed: bool = False, thick: bool = False) -> None:
        pen = QPen(QColor(color), 3.2 if thick else 2.0)
        if dashed:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(color)))
        painter.drawLine(start, end)
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        size = 8.5
        p1 = QPointF(end.x() - size * math.cos(angle - math.pi / 6), end.y() - size * math.sin(angle - math.pi / 6))
        p2 = QPointF(end.x() - size * math.cos(angle + math.pi / 6), end.y() - size * math.sin(angle + math.pi / 6))
        painter.drawPolygon(QPolygonF([end, p1, p2]))

    def _node_rect(self, node) -> QRectF:
        # One consistent size keeps row spacing predictable and prevents text clipping.
        return QRectF(node["x"] - 112, node["y"] - 53, 224, 106)

    def _style_for_node(self, node):
        if node.get("active"):
            return "#fef9c3", "#ca8a04", "#854d0e"
        if node.get("pruned") or node.get("kind") == "PRUNE":
            return "#fee2e2", "#dc2626", "#991b1b"
        if node.get("selected"):
            return "#dcfce7", "#16a34a", "#166534"
        if node.get("kind") == "GOAL":
            return "#dcfce7", "#16a34a", "#166534"
        if node.get("kind") == "MAX":
            return "#eff6ff", "#2563eb", "#1d4ed8"
        if node.get("kind") == "CHANCE":
            return "#faf5ff", "#9333ea", "#6b21a8"
        return "#fff7ed", "#ef4444", "#991b1b"

    def _draw_tree_recursive(self, painter: QPainter, node) -> None:
        parent_rect = self._node_rect(node)
        for child in node.get("children", []):
            child_rect = self._node_rect(child)
            if child.get("pruned"):
                color = "#dc2626"
            elif child.get("selected"):
                color = "#16a34a"
            elif child.get("kind") == "CHANCE":
                color = "#9333ea"
            else:
                color = "#ef4444" if node.get("kind") != "MAX" else "#0ea5e9"
            self._draw_arrow(
                painter,
                QPointF(parent_rect.center().x(), parent_rect.bottom()),
                QPointF(child_rect.center().x(), child_rect.top()),
                color,
                dashed=child.get("pruned", False),
                thick=child.get("selected", False),
            )
            self._draw_tree_recursive(painter, child)

        fill, border, title_color = self._style_for_node(node)
        title = node["title"]
        self._draw_box(painter, parent_rect, title, node["body"], fill, border, title_color)
        if node.get("active"):
            badge = QRectF(parent_rect.right() - 78, parent_rect.top() - 14, 74, 24)
            painter.setPen(QPen(QColor("#ca8a04"), 1.6))
            painter.setBrush(QBrush(QColor("#fde68a")))
            painter.drawRoundedRect(badge, 8, 8)
            painter.setFont(QFont("Segoe UI", 7.8, QFont.Bold))
            painter.setPen(QColor("#713f12"))
            painter.drawText(badge, Qt.AlignCenter, "ĐANG XÉT")
        if node.get("value"):
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.setPen(QColor("#16a34a") if node.get("selected") else QColor("#475569"))
            painter.drawText(QRectF(parent_rect.left(), parent_rect.bottom() + 4, parent_rect.width(), 22), Qt.AlignCenter, node["value"])

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#ffffff"))

        # Fixed overlay: title and usage hint are not transformed.
        painter.setPen(QColor("#0f172a"))
        painter.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_text = "TRACE CÂY ĐỐI KHÁNG"
        painter.drawText(QRectF(0, 6, self.width(), 28), Qt.AlignCenter, title_text)
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor("#475569"))

        tree = self._make_tree()
        if not tree:
            painter.drawText(QRectF(0, 120, self.width(), 50), Qt.AlignCenter, "Chưa có dữ liệu cây đối kháng.")
            painter.end()
            return

        painter.save()
        painter.translate(self.offset)
        painter.scale(self.scale, self.scale)

        # Canvas background.
        canvas_w, canvas_h = self._canvas_size
        painter.setPen(QPen(QColor("#e5e7eb"), 1))
        painter.setBrush(QBrush(QColor("#fbfdff")))
        painter.drawRoundedRect(QRectF(0, 0, canvas_w, canvas_h), 18, 18)

        # Row labels, similar to the reference image.
        labels = ["Lượt 1: MAX", "Lượt 2: MIN/CHANCE", "Lượt 3: MAX", "Lượt 4: MIN/CHANCE", "Lượt 5: MAX", "Lượt 6: LÁ"]
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.setPen(QColor("#334155"))
        for i, label in enumerate(labels):
            painter.drawText(QRectF(18, 100 + i * 150, 185, 30), Qt.AlignLeft | Qt.AlignVCenter, label)

        self._draw_tree_recursive(painter, tree)

        # Legend / result box.
        result = game_selected_action_text(self.step or (self.result.trace[0] if self.result and self.result.trace else None)) if (self.step or (self.result and self.result.trace)) else ""
        legend_rect = QRectF(24, canvas_h - 95, 520, 68)
        painter.setPen(QPen(QColor("#16a34a"), 2))
        painter.setBrush(QBrush(QColor("#f0fdf4")))
        painter.drawRoundedRect(legend_rect, 12, 12)
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.setPen(QColor("#166534"))
        painter.drawText(legend_rect.adjusted(10, 8, -10, -8), Qt.AlignLeft | Qt.TextWordWrap, "Cách đọc: thuật toán nhìn trước 5 bước từ state hiện tại, đọc điểm lá rồi truyền lên gốc. MAX chọn điểm lớn nhất, MIN chọn điểm nhỏ nhất, CHANCE tính điểm kỳ vọng. Node vàng = bước đang giải thích, xanh = nhánh được chọn, đỏ = nhánh bị cắt.")

        painter.restore()
        painter.end()


class AndOrTreeWidget(QWidget):
    """Zoomable + pannable tree view for AND-OR Graph Search.

    Unlike Stage 5, this tree grows progressively: at step k the widget shows
    only the OR/AND nodes that the algorithm has actually reached up to that
    step. This matches the classroom idea OR_SEARCH -> AND_SEARCH -> OR_SEARCH.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result: Optional[SearchResult] = None
        self.step: Optional[TraceStep] = None
        self.current_index = 0
        self.scale = 0.92
        self.offset = QPointF(34, 42)
        self._dragging = False
        self._last_mouse = QPointF(0, 0)
        self._tree_cache = None
        self._canvas_size = (1100, 620)
        self._last_result_object = None
        self.setMinimumHeight(500)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)

    def set_result(self, result: SearchResult, current_index: int = 0) -> None:
        new_result = result is not self._last_result_object
        self.result = result
        if result and result.trace:
            self.current_index = max(0, min(current_index, len(result.trace) - 1))
            self.step = result.trace[self.current_index]
        else:
            self.current_index = 0
            self.step = None
        self._tree_cache = None
        if new_result:
            self._last_result_object = result
            self.reset_view()
        else:
            self.update()

    def zoom_in(self) -> None:
        self._zoom_at(1.18, QPointF(self.width() / 2, self.height() / 2))

    def zoom_out(self) -> None:
        self._zoom_at(1 / 1.18, QPointF(self.width() / 2, self.height() / 2))

    def reset_view(self) -> None:
        tree = self._make_tree()
        if not tree:
            self.scale = 0.86
            self.offset = QPointF(34, 52)
            self.update()
            return

        self.scale = 0.86
        root_x = float(tree.get("x", self._canvas_size[0] / 2))
        self.offset = QPointF((self.width() / 2) - root_x * self.scale, 74)
        self.update()

    def _zoom_at(self, factor: float, anchor: QPointF) -> None:
        new_scale = max(0.28, min(3.0, self.scale * factor))
        if abs(new_scale - self.scale) < 0.001:
            return
        before = QPointF((anchor.x() - self.offset.x()) / self.scale, (anchor.y() - self.offset.y()) / self.scale)
        self.scale = new_scale
        self.offset = QPointF(anchor.x() - before.x() * self.scale, anchor.y() - before.y() * self.scale)
        self.update()

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta == 0:
            return

        # Ctrl + lăn chuột = zoom. Lăn chuột thường = cuộn lên/xuống cây AND-OR.
        if event.modifiers() & Qt.ControlModifier:
            self._zoom_at(1.14 if delta > 0 else 1 / 1.14, event.position())
        else:
            self.offset = QPointF(self.offset.x(), self.offset.y() + delta * 0.42)
            self.update()
        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._last_mouse = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._dragging:
            pos = event.position()
            delta = pos - self._last_mouse
            self._last_mouse = pos
            self.offset = QPointF(self.offset.x() + delta.x(), self.offset.y() + delta.y())
            self.update()
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self.setCursor(Qt.OpenHandCursor)
            event.accept()

    def _make_or_node(self, pos, active: bool = False, label: str = "OR_SEARCH", path_key=None):
        if path_key is None:
            path_key = (pos,) if pos is not None else tuple()
        return {
            "kind": "OR",
            "title": label,
            "body": f"State\n{_short_pos(pos)}\nOR: agent chọn action",
            "pos": pos,
            "path_key": tuple(path_key),
            "active": active,
            "status": "",
            "expanded": False,
            "children": [],
            "x": 0,
            "y": 0,
        }

    def _find_or_node(self, node, pos, path_key=None):
        # Repeated coordinates may appear in different conditional-plan branches.
        # Prefer an exact reached/path prefix match so OR_SEARCH((5,30)) under
        # the START action is not confused with OR_SEARCH((5,30)) deeper in the
        # first result branch.
        if path_key is not None and node.get("kind") == "OR" and node.get("pos") == pos and tuple(node.get("path_key", ())) == tuple(path_key) and not node.get("expanded"):
            return node
        for child in node.get("children", []):
            found = self._find_or_node(child, pos, path_key)
            if found is not None:
                return found
        if path_key is not None:
            return None
        if node.get("kind") == "OR" and node.get("pos") == pos and not node.get("expanded"):
            return node
        for child in node.get("children", []):
            found = self._find_or_node(child, pos, None)
            if found is not None:
                return found
        return None

    def _terminal_node(self, title: str, body: str, status: str):
        kind = "GOAL" if status == "OK" else ("INFO" if status == "INFO" else "FAIL")
        return {
            "kind": kind,
            "title": title,
            "body": body,
            "pos": None,
            "active": False,
            "status": status,
            "expanded": True,
            "children": [],
            "x": 0,
            "y": 0,
        }

    def _make_tree(self):
        if self._tree_cache is not None:
            return self._tree_cache
        if not self.result or not self.result.trace:
            self._tree_cache = None
            return None

        visible = list(self.result.trace[: self.current_index + 1])
        if not visible:
            self._tree_cache = None
            return None

        root_pos = self.result.path[0] if self.result and self.result.path else visible[0].current
        root = self._make_or_node(root_pos, active=(self.current_index == 0), label="START DUY NHẤT\nOR_SEARCH", path_key=(root_pos,))
        goal_pos = self.result.path[-1] if self.result and self.result.path else None
        root["body"] = (
            f"1 START\n{_short_pos(root_pos)}"
            + (f"\n1 GOAL: {_short_pos(goal_pos)}" if goal_pos else "")
        )

        def is_chosen_neighbor(nb, order: int) -> bool:
            status = str(nb.status).upper()
            reason = str(nb.reason).lower()
            return (
                status in {"OK", "SELECTED", "CHOSEN", "ADD", "ADD/UPDATE"}
                or "chọn action này" in reason
                or (order == 0 and status not in {"SKIP", "FAIL", "X", "BLOCKED", "REJECT"})
            )

        def add_action_node(current_node, nb):
            status = str(nb.status).upper()
            action_raw = str(nb.action)
            action_vi = _action_vi(action_raw)
            reason = str(nb.reason)
            pruned_fail = status in {"FAIL", "X", "BLOCKED", "REJECT"}

            if "GOAL" in action_raw.upper():
                current_node["children"].append(self._terminal_node("GOAL", "Đã đạt mục tiêu\nreturn []", "OK"))
                return
            if "CYCLE" in action_raw.upper():
                current_node["children"].append(self._terminal_node("FAIL", "Phát hiện cycle\nreturn failure", "FAIL"))
                return

            results = _parse_grid_positions_from_text(nb.value)
            if not results and _is_grid_pos(nb.node):
                results = [nb.node]

            title = f"{action_vi}\nAND_SEARCH"
            if len(results) > 1:
                body = "Action không xác định\nsinh nhiều result state\nphải giải TẤT CẢ"
            else:
                body = "Action sinh 1 result state\nAND_SEARCH gọi OR_SEARCH\ncho result này"
            if pruned_fail:
                body = (reason[:58] + "...") if len(reason) > 60 else reason

            action_node = {
                "kind": "FAIL" if pruned_fail else "AND",
                "title": title,
                "body": body,
                "pos": None,
                "active": False,
                "status": status,
                "expanded": True,
                "children": [],
                "x": 0,
                "y": 0,
            }
            # Show result states of the chosen action.  Keep at most 3 to avoid
            # an unreadably wide tree; the table tab still contains full detail.
            parent_path = tuple(current_node.get("path_key", (current_node.get("pos"),)))
            for pos in results[:3]:
                action_node["children"].append(self._make_or_node(pos, active=False, label="RESULT STATE\nOR_SEARCH", path_key=parent_path + (pos,)))
            if len(results) > 3:
                action_node["children"].append(self._terminal_node("...", f"còn {len(results) - 3} result", "INFO"))
            current_node["children"].append(action_node)

        for i, step in enumerate(visible):
            step_path_key = tuple(step.reached or [step.current])
            current_node = self._find_or_node(root, step.current, step_path_key) or self._find_or_node(root, step.current)
            if current_node is None:
                # Recursive traces may mention a child before the UI has expanded
                # its parent.  Keep it as a compact note instead of creating a
                # second disconnected wide subtree.
                if i != 0:
                    root["children"].append(self._terminal_node(
                        "OR_SEARCH đang giải",
                        f"State {_short_pos(step.current)}\nđược sinh trong nhánh con",
                        "INFO",
                    ))
                continue

            current_node["active"] = (i == self.current_index)
            if current_node.get("expanded") and current_node is not root:
                continue
            current_node["expanded"] = True

            chosen = []
            skipped = []
            terminals = []
            for order, nb in enumerate(step.neighbors):
                action_raw = str(nb.action)
                if "GOAL" in action_raw.upper() or "CYCLE" in action_raw.upper():
                    terminals.append(nb)
                elif is_chosen_neighbor(nb, order):
                    chosen.append(nb)
                else:
                    skipped.append(nb)

            # Draw the selected/OK action(s) first; normally there is one.
            for nb in chosen[:2]:
                add_action_node(current_node, nb)
            for nb in terminals[:2]:
                add_action_node(current_node, nb)

            # Do not draw unchosen OR actions in the visual tree.  The user
            # requested a cleaner AND-OR trace: show the selected action and the
            # AND result states that must all be solved.  OR_SEARCH may try other
            # actions internally only when the selected action fails, but those
            # actions are not part of the final conditional plan and would make
            # the classroom tree look like a noisy BFS tree.
            _ = skipped

        self._layout_tree(root)
        self._tree_cache = root
        return root

    def _measure(self, node) -> float:
        children = node.get("children", [])
        if not children:
            node["_width"] = 205
            return node["_width"]
        spacing = 42
        width = sum(self._measure(ch) for ch in children) + spacing * (len(children) - 1)
        node["_width"] = max(205, width)
        return node["_width"]

    def _layout_tree(self, root) -> None:
        """Compact AND-OR layout following the selected plan spine.

        A normal tidy-tree layout reserves horizontal space for every side
        branch at every level.  AND-OR traces may have many skipped actions, so
        that makes the tree extremely wide and hard to read.  Here the selected
        OR→AND→OR plan is drawn as a vertical spine, while skipped/extra actions
        are placed as short side notes near the state where they were considered.
        This keeps the tree compact but still shows the AND-OR idea clearly.
        """
        root_x = 560.0
        top = 96.0
        level_gap = 168.0
        side_gap = 290.0

        bounds = {
            "min_x": 10**9,
            "max_x": -10**9,
            "min_y": 10**9,
            "max_y": -10**9,
        }

        def update_bounds(node) -> None:
            rect_w = 246 if node.get("kind") != "OR" else 236
            rect_h = 118
            bounds["min_x"] = min(bounds["min_x"], node["x"] - rect_w / 2)
            bounds["max_x"] = max(bounds["max_x"], node["x"] + rect_w / 2)
            bounds["min_y"] = min(bounds["min_y"], node["y"] - rect_h / 2)
            bounds["max_y"] = max(bounds["max_y"], node["y"] + rect_h / 2)

        def set_pos(node, x: float, y: float) -> None:
            node["x"] = x
            node["y"] = y
            update_bounds(node)

        def assign(node, x: float, y: float, depth: int) -> None:
            set_pos(node, x, y)
            children = list(node.get("children", []))
            if not children:
                return

            main_children = [c for c in children if c.get("kind") != "INFO"]
            info_children = [c for c in children if c.get("kind") == "INFO"]

            next_y = y + level_gap

            if node.get("kind") == "OR":
                # Usually one selected AND_SEARCH plus one compact “other branches” note.
                if len(main_children) == 1:
                    assign(main_children[0], x, next_y, depth + 1)
                elif main_children:
                    spacing = 292.0
                    start_x = x - (len(main_children) - 1) * spacing / 2
                    for i, child in enumerate(main_children):
                        assign(child, start_x + i * spacing, next_y, depth + 1)

                # Place summaries to the side at the same level; do not let them
                # consume width recursively.
                for i, child in enumerate(info_children[:3]):
                    direction = 1 if i % 2 == 0 else -1
                    distance = side_gap * (1 + i // 2)
                    assign(child, x + direction * distance, next_y, depth + 1)

            elif node.get("kind") == "AND":
                # Result states of one action.  One result goes straight down;
                # multiple uncertain results are spread just enough to read.
                if len(main_children) == 1:
                    assign(main_children[0], x, next_y, depth + 1)
                else:
                    spacing = 292.0
                    start_x = x - (len(main_children) - 1) * spacing / 2
                    for i, child in enumerate(main_children):
                        assign(child, start_x + i * spacing, next_y, depth + 1)
                for i, child in enumerate(info_children[:2]):
                    assign(child, x + side_gap * (i + 1), next_y, depth + 1)

            else:
                # Terminal/info nodes rarely have children, but handle them safely.
                spacing = 278.0
                start_x = x - (len(children) - 1) * spacing / 2
                for i, child in enumerate(children):
                    assign(child, start_x + i * spacing, next_y, depth + 1)

        assign(root, root_x, top, 0)

        # Shift into positive coordinates if needed.
        dx = max(0.0, 110.0 - bounds["min_x"])
        if dx:
            def shift(node):
                node["x"] += dx
                for child in node.get("children", []):
                    shift(child)
            shift(root)
            bounds["min_x"] += dx
            bounds["max_x"] += dx

        self._canvas_size = (
            max(1080, int(bounds["max_x"] + 120)),
            max(720, int(bounds["max_y"] + 150)),
        )

    def _node_rect(self, node) -> QRectF:
        if node.get("kind") == "OR":
            return QRectF(node["x"] - 118, node["y"] - 59, 236, 118)
        return QRectF(node["x"] - 123, node["y"] - 59, 246, 118)

    def _style_for_node(self, node):
        if node.get("active"):
            return "#fef9c3", "#ca8a04", "#854d0e"
        kind = node.get("kind")
        status = str(node.get("status", "")).upper()
        if kind == "GOAL" or status == "OK":
            return "#dcfce7", "#16a34a", "#166534"
        if kind == "FAIL" or status == "FAIL":
            return "#fee2e2", "#dc2626", "#991b1b"
        if kind == "AND":
            return "#fff7ed", "#f97316", "#9a3412"
        if kind == "INFO":
            return "#f8fafc", "#64748b", "#334155"
        if kind == "ACTION":
            return "#f0f9ff", "#0ea5e9", "#075985"
        return "#eff6ff", "#2563eb", "#1d4ed8"

    def _draw_box(self, painter: QPainter, rect: QRectF, title: str, body: str, fill: str, border: str, title_color: str = "#0f172a") -> None:
        painter.setPen(QPen(QColor(border), 2.0))
        painter.setBrush(QBrush(QColor(fill)))
        painter.drawRoundedRect(rect, 12, 12)
        painter.setPen(QColor(title_color))
        painter.setFont(QFont("Segoe UI", 8.8, QFont.Bold))
        painter.drawText(QRectF(rect.left() + 9, rect.top() + 7, rect.width() - 18, 42), Qt.AlignCenter | Qt.TextWordWrap, title)
        painter.setPen(QColor("#1f2937"))
        painter.setFont(QFont("Segoe UI", 8.0))
        painter.drawText(QRectF(rect.left() + 9, rect.top() + 52, rect.width() - 18, rect.height() - 59), Qt.AlignCenter | Qt.TextWordWrap, body)

    def _draw_arrow(self, painter: QPainter, start: QPointF, end: QPointF, color: str, dashed: bool = False) -> None:
        pen = QPen(QColor(color), 2.2)
        if dashed:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(color)))
        painter.drawLine(start, end)
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        size = 8.0
        p1 = QPointF(end.x() - size * math.cos(angle - math.pi / 6), end.y() - size * math.sin(angle - math.pi / 6))
        p2 = QPointF(end.x() - size * math.cos(angle + math.pi / 6), end.y() - size * math.sin(angle + math.pi / 6))
        painter.drawPolygon(QPolygonF([end, p1, p2]))

    def _draw_tree_recursive(self, painter: QPainter, node) -> None:
        parent_rect = self._node_rect(node)
        for child in node.get("children", []):
            child_rect = self._node_rect(child)
            color = "#f97316" if child.get("kind") == "AND" else "#0ea5e9"
            if child.get("kind") == "FAIL" or str(child.get("status", "")).upper() == "FAIL":
                color = "#dc2626"
            if child.get("kind") == "GOAL" or str(child.get("status", "")).upper() == "OK":
                color = "#16a34a"
            self._draw_arrow(
                painter,
                QPointF(parent_rect.center().x(), parent_rect.bottom()),
                QPointF(child_rect.center().x(), child_rect.top()),
                color,
                dashed=(child.get("kind") == "FAIL"),
            )
            self._draw_tree_recursive(painter, child)
        fill, border, title_color = self._style_for_node(node)
        title = node["title"]
        self._draw_box(painter, parent_rect, title, node["body"], fill, border, title_color)
        if node.get("active"):
            badge = QRectF(parent_rect.right() - 76, parent_rect.top() - 10, 70, 22)
            painter.setPen(QPen(QColor("#ca8a04"), 1.5))
            painter.setBrush(QBrush(QColor("#fde68a")))
            painter.drawRoundedRect(badge, 8, 8)
            painter.setFont(QFont("Segoe UI", 7.4, QFont.Bold))
            painter.setPen(QColor("#713f12"))
            painter.drawText(badge, Qt.AlignCenter, "ĐANG XÉT")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.setPen(QColor("#0f172a"))
        painter.setFont(QFont("Segoe UI", 14, QFont.Bold))
        painter.drawText(QRectF(0, 6, self.width(), 28), Qt.AlignCenter, "TRACE CÂY AND-OR SEARCH - 1 START, 1 GOAL")
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor("#475569"))
        total = len(self.result.trace) if self.result and self.result.trace else 1
        painter.drawText(
            QRectF(12, 34, self.width() - 24, 24),
            Qt.AlignCenter,
            f"Bước {self.current_index + 1}/{total}: OR chọn action → AND_SEARCH(result_states) → OR_SEARCH từng result • Lăn chuột để cuộn, Ctrl+lăn để zoom",
        )
        tree = self._make_tree()
        if not tree:
            painter.drawText(QRectF(0, 120, self.width(), 50), Qt.AlignCenter, "Chưa có dữ liệu AND-OR.")
            painter.end()
            return
        painter.save()
        painter.translate(self.offset)
        painter.scale(self.scale, self.scale)
        canvas_w, canvas_h = self._canvas_size
        painter.setPen(QPen(QColor("#e5e7eb"), 1))
        painter.setBrush(QBrush(QColor("#fbfdff")))
        painter.drawRoundedRect(QRectF(0, 0, canvas_w, canvas_h), 18, 18)
        self._draw_tree_recursive(painter, tree)
        legend_rect = QRectF(24, canvas_h - 86, 620, 60)
        painter.setPen(QPen(QColor("#2563eb"), 2))
        painter.setBrush(QBrush(QColor("#eff6ff")))
        painter.drawRoundedRect(legend_rect, 12, 12)
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.setPen(QColor("#1e3a8a"))
        painter.drawText(legend_rect.adjusted(10, 8, -10, -8), Qt.AlignLeft | Qt.TextWordWrap, "Cách đọc đúng mã giả: AND_OR_GRAPH_SEARCH gọi OR_SEARCH(Start). OR_SEARCH thử từng action rồi gọi AND_SEARCH(result_states). AND_SEARCH gọi OR_SEARCH cho từng result state. Chỉ có 1 Start và 1 Goal; nhiều result state là do action không xác định.")
        painter.restore()
        painter.end()

def _count_csp_variables(note: str) -> int:
    for line in str(note).splitlines():
        if line.strip().lower().startswith("- variables:"):
            rhs = line.split(":", 1)[1].strip()
            if not rhs or rhs == "route checkpoints":
                return 0
            return len([part for part in rhs.split(",") if part.strip()])
    return 0


def csp_representation_from_note(note: str) -> str:
    """Return a compact static CSP model for the Stage 6 trace."""
    return "\n".join([
        "- Variables: Khối D, Khối B, Khối C, Khối Thư viện, Phòng y tế, Hội trường lớn, Khối A.1-A.5, Xưởng động cơ, Xưởng thực tập gỗ, Xưởng điện ô tô, Khối F.1, Ký túc xá D, Căn tin, Khối E.1, Khoa CNTT, Xưởng thực tập hàn, Khối G, Dịch vụ ô tô Toyota",
        "- DOMAIN = { Cam, Hồng, Xanh, Tím }",
        "- CONSTRAINTS:",
        "- Hai tòa nhà kề nhau không được cùng màu.",
    ])

def csp_solving_steps_from_note(note: str) -> str:
    """Return the dynamic solving log, similar to the classroom CSP trace."""
    lines = str(note).splitlines()
    steps: List[str] = []
    in_rep = False
    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("CSP REPRESENTATION") or upper.startswith("BIỂU DIỄN CSP"):
            in_rep = True
            continue
        if in_rep:
            if stripped.startswith("- Assignment"):
                continue
            if stripped.startswith("-") and not (
                stripped.startswith("- Chọn")
                or stripped.startswith("- Thử")
                or stripped.startswith("- Kiểm tra")
                or stripped.startswith("- Forward")
                or stripped.startswith("- Nếu")
            ):
                continue
            if (
                stripped.startswith("Bước")
                or stripped.startswith("Forward Checking")
                or stripped.startswith("Min-Conflicts")
                or stripped.startswith("Đã gán")
                or stripped.startswith("Sau đó")
            ):
                in_rep = False
            else:
                continue
        if stripped:
            steps.append(line)
    return "\n".join(steps).strip() or "Bước 1: Bắt đầu với assignment rỗng\nAssignment = {}"


def csp_assignment_from_step(step: TraceStep, algorithm: str = "") -> str:
    """Return a compact assignment box for the current CSP step."""
    alg = f"{algorithm} {step.mode}".lower()
    note = str(step.note)
    if "CURRENT ASSIGNMENT / DOMAINS" in note:
        section = note.split("CURRENT ASSIGNMENT / DOMAINS", 1)[1]
        section = section.split("SOLVING STEPS", 1)[0]
        if "Mien gia tri con lai" in section:
            section = section.split("Mien gia tri con lai", 1)[0]
        return "ASSIGNMENT HIEN TAI\n" + section.strip()
    var_count = _count_csp_variables(note)

    values = list(step.reached or [])
    if var_count > 0:
        values = values[:var_count]

    if not values:
        return "ASSIGNMENT HIỆN TẠI\n{}"

    parts = []
    for i, value in enumerate(values, start=1):
        parts.append(f"X{i} = {fmt_pos(value)}")
    return "ASSIGNMENT HIỆN TẠI\n{" + ",\n ".join(parts) + "}"

def trace_ui_profile(algorithm: str, mode: str = "") -> Dict[str, object]:
    text = f"{algorithm} {mode}".lower()

    if is_csp_trace(algorithm, mode):
        return {
            "subtitle": "",
            "current": "Ô 1: BIẾN / DOMAIN / CONSTRAINTS",
            "frontier": "Ô 2: ASSIGNMENT HIỆN TẠI",
            "reached": "",
            "detail": "Bảng kiểm tra domain và ràng buộc",
            "headers": ["Giá trị", "Thao tác", "Thông số", "Trạng thái", "Ràng buộc / lý do"],
            "show_reached": False,
        }

    if "minimax" in text or "alpha-beta" in text or "expectimax" in text:
        return {
            "subtitle": "TRACE CAY DOI KHANG: MAX chon diem cao, MIN lam diem thap, CHANCE tinh diem ky vong.",
            "current": "CAY DOI KHANG",
            "frontier": "HANH DONG DUOC CHON",
            "reached": "TRANG THAI DA XET",
            "detail": "Bang chi tiet: hanh dong, diem danh gia, alpha/beta hoac xac suat",
            "headers": ["Nut", "Vai tro / Hanh dong", "Diem danh gia / Thong so", "Trang thai", "Hanh dong duoc chon / Giai thich"],
            "show_reached": False,
        }

    if "minimax" in text or "alpha-beta" in text or "expectimax" in text:
        return {
            "subtitle": "TRACE CÂY ĐỐI KHÁNG: điểm ban đầu = 0; MAX chọn điểm cao nhất, MIN làm điểm thấp nhất, CHANCE tính điểm kỳ vọng.",
            "current": "CÂY ĐỐI KHÁNG",
            "frontier": "HÀNH ĐỘNG ĐƯỢC CHỌN",
            "reached": "TRẠNG THÁI ĐÃ XÉT",
            "detail": "Bảng chi tiết dưới cây: Hành động, điểm đánh giá, độ sâu, alpha/beta hoặc xác suất",
            "headers": ["Nút", "Vai trò / Hành động", "Điểm đánh giá / Độ sâu", "Trạng thái", "Hành động được chọn / Giải thích"],
            "show_reached": True,
        }

    if is_and_or_trace(algorithm, mode):
        return {
            "subtitle": "Trace AND-OR: chỉ có 1 Start và 1 Goal. OR_SEARCH là agent chọn action; AND_SEARCH xử lý nhiều result state do action không xác định sinh ra, không phải nhiều Start.",
            "current": "CÂY AND-OR",
            "frontier": "ACTION / RESULT STATES",
            "reached": "PATH ĐANG XÉT",
            "detail": "Bảng chi tiết AND-OR: action, result states, trạng thái OK/FAIL và giải thích",
            "headers": ["State / Result", "Action", "Result states", "Trạng thái", "Giải thích OR/AND"],
            "show_reached": True,
        }

    if "belief" in text:
        return {
            "subtitle": "Trace belief search: mỗi node là một tập trạng thái có thể, không phải một ô duy nhất.",
            "current": "BELIEF ĐẠI DIỆN",
            "frontier": "BELIEF FRONTIER",
            "reached": "BELIEF ĐÃ XÉT",
            "detail": "Hành động áp dụng lên belief state",
            "headers": ["Ô đại diện", "Hành động", "g/h/điểm belief", "Trạng thái", "Giải thích"],
            "show_reached": True,
        }

    if "bfs" in text:
        return {
            "subtitle": "Trace BFS: pop từ Queue FIFO, sau đó cập nhật Frontier/Reached. Không dùng heuristic.",
            "current": "NODE HIỆN TẠI",
            "frontier": "FRONTIER - HÀNG ĐỢI FIFO",
            "reached": "ĐÃ XÉT",
            "detail": "Cập nhật Queue sau khi xét ô kề",
            "headers": ["Ô", "Cập nhật Queue", "Depth", "Kết quả", "Lý do"],
            "show_reached": True,
        }

    if "dfs" in text or "ids" in text or "dls" in text:
        return {
            "subtitle": "Trace DFS/IDS: pop từ Stack LIFO; IDS lặp DFS giới hạn độ sâu. Không dùng heuristic.",
            "current": "NODE HIỆN TẠI",
            "frontier": "FRONTIER - NGĂN XẾP LIFO",
            "reached": "ĐÃ XÉT",
            "detail": "Cập nhật Stack hoặc cutoff theo depth",
            "headers": ["Ô", "Cập nhật Stack", "Depth", "Kết quả", "Lý do"],
            "show_reached": True,
        }

    if "ucs" in text or "greedy" in text or "a*" in text:
        return {
            "subtitle": "Trace tìm kiếm có thông tin/chi phí: chọn node từ Priority Queue theo g, h hoặc f.",
            "current": "NODE HIỆN TẠI",
            "frontier": "FRONTIER - HÀNG ĐỢI ƯU TIÊN",
            "reached": "ĐÃ XÉT",
            "detail": "Cập nhật priority của candidate",
            "headers": ["Node", "Hành động", "g/h/f", "Trạng thái", "Giải thích"],
            "show_reached": True,
        }

    if "local beam" in text and "belief" not in text:
        return {
            "subtitle": "Trace Local Beam Search: chỉ dùng h(n) để sắp xếp neighbor và giữ k trạng thái tốt nhất; không dùng g(n) để chọn beam.",
            "current": "BEAM TỐT NHẤT HIỆN TẠI",
            "frontier": "BEAM ĐƯỢC GIỮ THEO h(n)",
            "reached": "",
            "detail": "Neighbor_States được đánh giá bằng h(n)",
            "headers": ["Hàng xóm", "Hành động", "h(n)", "Trạng thái", "Lý do chọn / bỏ"],
            "show_reached": False,
        }

    if "hill" in text or "beam" in text or "annealing" in text:
        return {
            "subtitle": "Trace chặng 3: so sánh Current Node với Next Node được chọn theo hàm đánh giá.",
            "current": "NODE HIỆN TẠI",
            "frontier": "NODE TIẾP THEO",
            "reached": "",
            "detail": "Đánh giá và chọn Next Node",
            "headers": ["Node tiếp theo", "Hành động", "Giá trị", "Trạng thái", "Lý do chọn / bỏ"],
            "show_reached": False,
        }

    return {
        "subtitle": "Trace tổng quát: Current, Frontier, Reached và các cập nhật ở bước hiện tại.",
        "current": "NODE HIỆN TẠI",
        "frontier": "FRONTIER / OPEN LIST",
        "reached": "ĐÃ XÉT / CLOSED LIST",
        "detail": "Cập nhật ở bước hiện tại",
        "headers": ["Node", "Hành động", "Giá trị", "Trạng thái", "Lý do"],
        "show_reached": True,
    }


class TraceCard(QFrame):
    def __init__(self, title: str, color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("TraceCard")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 10, 12, 10)
        self.layout.setSpacing(6)

        self.title = QLabel(title)
        self.title.setObjectName("TraceCardTitle")
        self.title.setStyleSheet(f"color: {color};")
        self.title.setFont(QFont("Segoe UI", 11, QFont.Bold))

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(QFont("Consolas", 9))
        self.text.setMinimumHeight(125)

        self.layout.addWidget(self.title)
        self.layout.addWidget(self.text, 1)

    def setText(self, value: str) -> None:
        self.text.setText(str(value))


class TraceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Search Trace chi tiết - University Campus Guide")
        self.resize(1540, 980)
        self.setMinimumSize(1180, 780)
        self.result: Optional[SearchResult] = None
        self.index = 0
        self.build_ui()

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        header = QFrame()
        header.setObjectName("TraceHeader")

        h = QHBoxLayout(header)
        h.setContentsMargins(16, 14, 16, 14)
        h.setSpacing(12)

        title_box = QVBoxLayout()

        self.title_label = QLabel("Search Trace chi tiết")
        self.title_label.setObjectName("DialogTitle")
        self.title_label.setFont(QFont("Segoe UI", 20, QFont.Bold))

        self.subtitle_label = QLabel("Theo dõi từng bước thuật toán.")
        self.subtitle_label.setObjectName("DialogSub")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(False)

        title_box.addWidget(self.title_label)
        title_box.addWidget(self.subtitle_label)

        h.addLayout(title_box, 1)

        self.progress = QProgressBar()
        self.progress.setMinimumWidth(260)
        self.progress.setTextVisible(True)

        h.addWidget(self.progress)
        root.addWidget(header)

        self.meta = QLabel("Chưa có dữ liệu")
        self.meta.setObjectName("MetaLabel")
        self.meta.setWordWrap(True)

        root.addWidget(self.meta)

        nav = QHBoxLayout()

        self.first_btn = QPushButton("Về đầu")
        self.prev_btn = QPushButton("← Bước trước")
        self.next_btn = QPushButton("Bước sau →")
        self.last_btn = QPushButton("Đến cuối")

        for btn in (self.first_btn, self.prev_btn, self.next_btn, self.last_btn):
            btn.setCursor(Qt.PointingHandCursor)
            nav.addWidget(btn)

        nav.addStretch(1)

        self.zoom_hint = QLabel("Cây: kéo chuột | lăn chuột cuộn | Ctrl+lăn zoom | +/-")
        self.zoom_hint.setObjectName("ZoomHint")
        self.zoom_out_btn = QPushButton("− Thu nhỏ")
        self.zoom_reset_btn = QPushButton("Vừa khung")
        self.zoom_in_btn = QPushButton("+ Phóng to")
        self.tree_full_btn = QPushButton("Toàn màn hình trace")
        for btn in (self.zoom_out_btn, self.zoom_reset_btn, self.zoom_in_btn, self.tree_full_btn):
            btn.setCursor(Qt.PointingHandCursor)
            nav.addWidget(btn)
        nav.addWidget(self.zoom_hint)

        root.addLayout(nav)

        # Tree traces (Stage 4 AND-OR and Stage 5 adversarial search) are shown
        # in separate tabs instead of sharing one vertical splitter.  This avoids
        # the old bug where a large tree covered the detail table/note area.
        self.tree_tabs = QTabWidget()
        self.tree_tabs.setObjectName("TreeTraceTabs")
        self.tree_tabs.setVisible(False)

        tree_page = QWidget()
        tree_page_layout = QVBoxLayout(tree_page)
        tree_page_layout.setContentsMargins(0, 0, 0, 0)
        tree_page_layout.setSpacing(8)

        self.tree_tab_hint = QLabel("Cây hiển thị trong khung riêng. Kéo chuột để di chuyển cây, Ctrl + lăn chuột để zoom.")
        self.tree_tab_hint.setObjectName("TreeTabHint")
        self.tree_tab_hint.setWordWrap(True)
        self.tree_tab_hint.setVisible(False)
        tree_page_layout.addWidget(self.tree_tab_hint)

        self.game_tree_widget = GameTreeWidget()
        self.game_tree_widget.setVisible(False)
        self.and_or_tree_widget = AndOrTreeWidget()
        self.and_or_tree_widget.setVisible(False)
        tree_page_layout.addWidget(self.game_tree_widget, 1)
        tree_page_layout.addWidget(self.and_or_tree_widget, 1)

        detail_page = QWidget()
        detail_page_layout = QVBoxLayout(detail_page)
        detail_page_layout.setContentsMargins(0, 0, 0, 0)
        detail_page_layout.setSpacing(10)

        self.tree_detail_title = QLabel("Bảng chi tiết và giải thích")
        self.tree_detail_title.setObjectName("SectionTitle")
        self.tree_detail_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        detail_page_layout.addWidget(self.tree_detail_title)

        self.tree_detail_table = QTableWidget(0, 5)
        self.tree_detail_table.setMinimumHeight(360)
        self.tree_detail_table.setWordWrap(True)
        self.tree_detail_table.verticalHeader().setDefaultSectionSize(48)
        self.tree_detail_table.setHorizontalHeaderLabels(["Node", "Hành động", "Giá trị", "Trạng thái", "Lý do"])
        self.tree_detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tree_detail_table.horizontalHeader().setStretchLastSection(False)
        self.tree_detail_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tree_detail_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tree_detail_table.verticalHeader().setVisible(False)
        self.tree_detail_table.setAlternatingRowColors(True)
        self.tree_detail_table.setSelectionBehavior(QTableWidget.SelectRows)
        detail_page_layout.addWidget(self.tree_detail_table, 3)

        self.tree_detail_note = QTextEdit()
        self.tree_detail_note.setReadOnly(True)
        self.tree_detail_note.setMinimumHeight(190)
        self.tree_detail_note.setFont(QFont("Segoe UI", 12))
        detail_page_layout.addWidget(self.tree_detail_note, 1)

        self.tree_tabs.addTab(tree_page, "Cây trực quan")
        self.tree_tabs.addTab(detail_page, "Bảng chi tiết / Giải thích")
        root.addWidget(self.tree_tabs, 1)

        self.first_btn.clicked.connect(lambda: self.show_step(0))
        self.last_btn.clicked.connect(lambda: self.show_step(len(self.result.trace) - 1 if self.result else 0))
        self.prev_btn.clicked.connect(lambda: self.show_step(self.index - 1))
        self.next_btn.clicked.connect(lambda: self.show_step(self.index + 1))
        self.zoom_out_btn.clicked.connect(lambda: self._active_tree_widget().zoom_out() if self._active_tree_widget() else None)
        self.zoom_reset_btn.clicked.connect(lambda: self._active_tree_widget().reset_view() if self._active_tree_widget() else None)
        self.zoom_in_btn.clicked.connect(lambda: self._active_tree_widget().zoom_in() if self._active_tree_widget() else None)
        self.tree_full_btn.clicked.connect(self.toggle_tree_fullscreen)

        self._tree_fullscreen = False
        splitter = QSplitter(Qt.Vertical)
        self.splitter = splitter
        root.addWidget(splitter, 1)

        upper = QFrame()
        upper.setObjectName("TreeViewportPanel")
        self.upper_panel = upper
        upper.setMinimumHeight(320)
        upper_layout = QGridLayout(upper)
        self.upper_layout = upper_layout
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setSpacing(10)
        upper_layout.setRowStretch(0, 1)
        upper_layout.setColumnStretch(0, 1)
        upper_layout.setColumnStretch(1, 1)
        upper_layout.setColumnStretch(2, 1)

        self.current_box = TraceCard("NODE HIỆN TẠI", "#2563eb")
        self.frontier_box = TraceCard("FRONTIER / OPEN LIST", "#d97706")
        self.reached_box = TraceCard("ĐÃ XÉT / CLOSED LIST", "#7c3aed")
        upper_layout.addWidget(self.current_box, 0, 0)
        upper_layout.addWidget(self.frontier_box, 0, 1)
        upper_layout.addWidget(self.reached_box, 0, 2)

        splitter.addWidget(upper)

        lower = QWidget()
        self.lower_panel = lower
        lower.setMinimumHeight(300)
        lower_layout = QVBoxLayout(lower)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        lower_layout.setSpacing(10)

        self.detail_title = QLabel("Cập nhật ở bước hiện tại")
        self.detail_title.setObjectName("SectionTitle")
        self.detail_title.setFont(QFont("Segoe UI", 12, QFont.Bold))

        lower_layout.addWidget(self.detail_title)

        self.table = QTableWidget(0, 5)
        self.table.setMinimumHeight(190)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setHorizontalHeaderLabels(["Node", "Hành động", "Giá trị", "Trạng thái", "Lý do"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        lower_layout.addWidget(self.table, 1)

        note_row = QHBoxLayout()
        self.note_row = note_row

        self.note_box = QTextEdit()
        self.note_box.setReadOnly(True)
        self.note_box.setMinimumHeight(105)
        self.note_box.setMaximumHeight(180)
        self.note_box.setFont(QFont("Segoe UI", 12))
        self.note_box.setVisible(False)

        note_row.addWidget(self.note_box, 1)
        lower_layout.addLayout(note_row)

        splitter.addWidget(lower)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(5)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([430, 470])

        self.setStyleSheet("""
            QDialog { background: #eef3fb; color: #172033; font-family: 'Segoe UI', Arial, Tahoma; }
            QFrame#TraceHeader { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0f172a, stop:1 #1e3a8a); border-radius: 18px; }
            QLabel#DialogTitle { color: white; }
            QLabel#DialogSub { color: #bfdbfe; }
            QLabel#MetaLabel { color: #475569; background: #ffffff; border: 1px solid #d7e1ef; border-radius: 12px; padding: 10px 12px; }
            QLabel#SectionTitle { color: #1f2937; }
            QLabel#ZoomHint { color: #475569; font-weight: 600; padding-left: 8px; }
            QLabel#TreeTabHint { color: #334155; background: #ffffff; border: 1px solid #d7e1ef; border-radius: 10px; padding: 8px 10px; font-weight: 600; }
            QTabWidget#TreeTraceTabs::pane { border: 1px solid #d8e2f0; border-radius: 12px; background: #ffffff; padding: 8px; }
            QTabBar::tab { background: #eaf2ff; color: #1e3a8a; border: 1px solid #bfdbfe; border-bottom: none; border-top-left-radius: 9px; border-top-right-radius: 9px; padding: 9px 16px; font-weight: 800; }
            QTabBar::tab:selected { background: #2563eb; color: white; }
            QFrame#TraceCard { background: #ffffff; border: 1px solid #d8e2f0; border-radius: 16px; }
            QFrame#TreeViewportPanel { background: #ffffff; border: 1px solid #d8e2f0; border-radius: 14px; }
            QLabel#TraceCardTitle { padding-bottom: 4px; }
            QTextEdit { background: #f8fafc; border: 1px solid #e3e9f3; border-radius: 10px; padding: 8px; color: #1f2937; }
            QTableWidget { background: white; color: #111827; border: 1px solid #d7e1ef; border-radius: 12px; gridline-color: #e5eaf2; alternate-background-color: #f8fafc; selection-background-color: #bfdbfe; selection-color: #0f172a; }
            QTableWidget::item { color: #111827; padding: 4px; }
            QHeaderView::section { background: #dbeafe; color: #1e3a8a; border: none; border-right: 1px solid #bfdbfe; padding: 8px; font-weight: 800; }
            QPushButton { background: #ffffff; color: #1f2937; border: 1px solid #cbd8ea; border-radius: 10px; padding: 9px 14px; font-weight: 600; }
            QPushButton:hover { background: #dbeafe; border-color: #60a5fa; }
            QProgressBar { border: 1px solid #93c5fd; border-radius: 9px; text-align: center; color: white; background: #1e293b; height: 22px; }
            QProgressBar::chunk { background: #22c55e; border-radius: 8px; }
            QSplitter::handle { background: #cbd8ea; border-radius: 2px; }
            QSplitter::handle:hover { background: #93c5fd; }
        """)

    def _active_tree_widget(self):
        if getattr(self, "game_tree_widget", None) and self.game_tree_widget.isVisible():
            return self.game_tree_widget
        if getattr(self, "and_or_tree_widget", None) and self.and_or_tree_widget.isVisible():
            return self.and_or_tree_widget
        return None

    def toggle_tree_fullscreen(self) -> None:
        """Toggle a larger trace view.

        For tree traces this focuses the tree tab. For regular traces it maximizes
        the whole Search Trace window so the upper cards, table and explanation
        can be read without being squeezed.
        """
        tree_mode = bool(self.tree_tabs.isVisible())
        if not tree_mode:
            if self.isMaximized():
                self.showNormal()
                self.tree_full_btn.setText("Toàn màn hình trace")
            else:
                self.showMaximized()
                self.tree_full_btn.setText("Thoát toàn màn hình")
            return

        self._tree_fullscreen = not getattr(self, "_tree_fullscreen", False)
        self.tree_full_btn.setText("Thoát toàn màn hình" if self._tree_fullscreen else "Toàn màn hình trace")
        self._apply_tree_fullscreen_layout(reset=True)

    def _apply_tree_fullscreen_layout(self, reset: bool = False) -> None:
        tree_mode = (self._active_tree_widget() is not None)
        if not tree_mode:
            self._tree_fullscreen = False
            self.tree_full_btn.setText("Thoat toan man hinh" if self.isMaximized() else "Toan man hinh trace")
            if self.result and self.result.trace and is_csp_trace(self.result.algorithm, self.result.trace[self.index].mode):
                self.lower_panel.setVisible(True)
                self.splitter.setSizes([520, 360])
                return
            self.lower_panel.setVisible(True)
            self.splitter.setSizes([430, 450])
            return

        # Tree traces now use separate tabs for tree and detail.  The old
        # fullscreen implementation hid the lower splitter panel, which caused
        # overlapping/hidden detail rows.  In tab mode, fullscreen simply focuses
        # the tree tab and resets the view; the detail table remains available
        # in the second tab.
        if hasattr(self, "tree_tabs") and self.tree_tabs.isVisible():
            self.tree_tabs.setCurrentIndex(0)
            widget = self._active_tree_widget()
            if reset and widget:
                widget.reset_view()
            return

        if getattr(self, "_tree_fullscreen", False):
            self.lower_panel.setVisible(False)
            self.upper_panel.setMinimumHeight(760)
            self.splitter.setSizes([1, 0])
        else:
            self.lower_panel.setVisible(True)
            self.upper_panel.setMinimumHeight(520)
            self.splitter.setSizes([560, 390])

        widget = self._active_tree_widget()
        if reset and widget:
            widget.reset_view()

    def set_result(self, result: SearchResult, index: int = 0) -> None:
        self.result = result
        self.index = max(0, min(index, len(result.trace) - 1)) if result.trace else 0
        # Search Trace needs wide tables and multi-panel cards, so open maximized
        # by default. The user can restore the window with the fullscreen button.
        if result and result.trace:
            self.setWindowState(self.windowState() | Qt.WindowMaximized)
            self.tree_full_btn.setText("Thoát toàn màn hình")
        self.show_step(self.index)

    def _list_text(self, nodes: List, limit: int = 90) -> str:
        if not nodes:
            return "Rỗng"

        data = [fmt_pos(p) for p in nodes[:limit]]

        if len(nodes) > limit:
            data.append(f"... còn {len(nodes) - limit} node")

        return "\n".join(data)

    def _apply_table_column_widths(self, headers: List[str], table: Optional[QTableWidget] = None) -> None:
        """Keep the detail table readable without letting long explanations hide columns."""
        table = table or self.table
        w = max(900, table.viewport().width())
        if len(headers) >= 5:
            widths = [120, 170, 300, 110, max(360, w - 720)]
        elif len(headers) == 4:
            widths = [160, 180, 160, max(420, w - 500)]
        else:
            widths = [max(140, int(w / max(1, len(headers)))) for _ in headers]
        for col, width in enumerate(widths[:len(headers)]):
            table.setColumnWidth(col, int(width))

    def _status_color(self, status: str) -> QColor:
        if status in {
            "CHOSEN",
            "ADD",
            "ADD/UPDATE",
            "ENQUEUE",
            "PUSH",
            "MEET",
            "CANDIDATE",
            "OK",
            "KEEP",
            "SELECTED",
        }:
            return QColor("#dcfce7")

        if status in {
            "SKIP",
            "REJECT",
            "CUTOFF",
            "PRUNE",
            "TRY",
            "INFO",
            "REMOVE",
        }:
            return QColor("#fef3c7")

        if status in {
            "X",
            "BLOCKED",
            "FAIL",
        }:
            return QColor("#fee2e2")

        return QColor("#eef2ff")

    def show_step(self, index: int) -> None:
        if not self.result or not self.result.trace:
            self.meta.setText("Chưa có trace. Hãy chạy thuật toán trước.")
            self.progress.setValue(0)
            return

        index = max(0, min(index, len(self.result.trace) - 1))
        self.index = index

        step: TraceStep = self.result.trace[index]

        total = max(1, len(self.result.trace))
        self.progress.setMaximum(total)
        self.progress.setValue(index + 1)
        self.progress.setFormat(f"Bước {index + 1}/{total}")

        profile = trace_ui_profile(self.result.algorithm, step.mode)
        headers = list(profile["headers"])

        self.title_label.setText(f"{self.result.algorithm} Trace")
        self.subtitle_label.setText(str(profile["subtitle"]))
        self.subtitle_label.setVisible(False)
        self.current_box.title.setText(str(profile["current"]))
        self.frontier_box.title.setText(str(profile["frontier"]))
        self.reached_box.title.setText(str(profile["reached"]))
        self.reached_box.setVisible(bool(profile.get("show_reached", True)))
        self.detail_title.setText(str(profile["detail"]))

        game_mode = is_game_trace(self.result.algorithm, step.mode)
        and_or_mode = is_and_or_trace(self.result.algorithm, step.mode)
        tree_mode = game_mode or and_or_mode
        self.tree_tabs.setVisible(tree_mode)
        self.splitter.setVisible(not tree_mode)
        if tree_mode and self.tree_tabs.currentIndex() < 0:
            self.tree_tabs.setCurrentIndex(0)
        for widget in (self.zoom_hint, self.zoom_out_btn, self.zoom_reset_btn, self.zoom_in_btn):
            widget.setVisible(tree_mode)
        self.tree_full_btn.setVisible(True)
        if not tree_mode and not self.isMaximized():
            self.tree_full_btn.setText("Toàn màn hình trace")

        label1, value1, label2, value2 = trace_metric_labels(step, self.result.algorithm)

        self.meta.setText(
            f"<b>Thuật toán:</b> {self.result.algorithm} &nbsp; | &nbsp; "
            f"<b>Mode:</b> {step.mode} &nbsp; | &nbsp; "
            f"<b>{label1}:</b> {value1} &nbsp; | &nbsp; "
            f"<b>{label2}:</b> {value2}"
        )

        if is_csp_trace(self.result.algorithm, step.mode):
            self.game_tree_widget.setVisible(False)
            self.and_or_tree_widget.setVisible(False)
            self.current_box.setVisible(True)
            self.frontier_box.setVisible(True)
            self.reached_box.setVisible(False)
            self.lower_panel.setVisible(True)
            self.note_box.setVisible(False)
            self.upper_layout.setColumnStretch(0, 1)
            self.upper_layout.setColumnStretch(1, 1)
            self.upper_layout.setColumnStretch(2, 0)
            self.current_box.setText(csp_representation_from_note(step.note))
            self.frontier_box.setText(csp_assignment_from_step(step, self.result.algorithm))
        elif is_game_trace(self.result.algorithm, step.mode):
            self.lower_panel.setVisible(True)
            self.tree_detail_note.setVisible(False)
            self.upper_layout.setColumnStretch(0, 1)
            self.upper_layout.setColumnStretch(1, 1)
            self.upper_layout.setColumnStretch(2, 1)
            self.current_box.setVisible(False)
            self.frontier_box.setVisible(False)
            self.reached_box.setVisible(False)
            self.and_or_tree_widget.setVisible(False)
            self.game_tree_widget.setVisible(True)
            self.game_tree_widget.set_result(self.result, index)
            self.tree_tabs.setTabText(0, "Cây đối kháng")
            self.tree_tabs.setTabText(1, "Bảng điểm / Giải thích")
            self.tree_tab_hint.setText("Cây đối kháng nằm trong tab riêng, không đè bảng bên dưới. Kéo chuột để xem các nhánh, Ctrl + lăn chuột để zoom. Sang tab Bảng điểm / Giải thích để xem chi tiết từng trạng thái.")
            self.tree_tab_hint.setVisible(False)
            game_note = (
                f"Bước quyết định {index + 1}/{total}\n"
                + game_representation_from_step(step, self.result.algorithm)
                + "\n\n"
                + "Cách xem: bấm Bước sau để chuyển sang decision snapshot kế tiếp. Map chỉ đi theo action được chọn; cây chỉ minh họa look-ahead của root hiện tại."
            )
            self.note_box.setText(game_note)
            self.tree_detail_note.clear()
        elif is_and_or_trace(self.result.algorithm, step.mode):
            self.lower_panel.setVisible(True)
            self.tree_detail_note.setVisible(True)
            self.upper_layout.setColumnStretch(0, 1)
            self.upper_layout.setColumnStretch(1, 1)
            self.upper_layout.setColumnStretch(2, 1)
            self.current_box.setVisible(False)
            self.frontier_box.setVisible(False)
            self.reached_box.setVisible(False)
            self.game_tree_widget.setVisible(False)
            self.and_or_tree_widget.setVisible(True)
            self.and_or_tree_widget.set_result(self.result, index)
            self.tree_tabs.setTabText(0, "Cây AND-OR")
            self.tree_tabs.setTabText(1, "Bảng AND-OR / Giải thích")
            self.tree_tab_hint.setText("Cây AND-OR nằm trong tab riêng. Cây chỉ hiện action được chọn và các result states cần giải; OR_SEARCH chọn action, AND_SEARCH xử lý tất cả result_states. Sang tab Bảng AND-OR / Giải thích để xem chi tiết.")
            self.tree_tab_hint.setVisible(False)
            andor_note = (
                "TRACE CÂY AND-OR SEARCH\n"
                f"Bước hiện tại: {index + 1}/{total}\n"
                f"OR_SEARCH đang xét state: {fmt_pos(step.current)}\n"
                "Đúng theo mã giả: AND_OR_GRAPH_SEARCH gọi OR_SEARCH(Start). OR_SEARCH thử action rồi gọi AND_SEARCH(result_states). AND_SEARCH gọi OR_SEARCH cho từng result state.\n"
                "Chỉ có 1 Start và 1 Goal; nhiều result state là do action không xác định, không phải nhiều Start như Belief State.\n"
                "Cách xem: cây ở tab riêng; bảng và giải thích ở tab riêng nên không bị che nhau."
            )
            self.note_box.setText(andor_note)
            self.tree_detail_note.setText(andor_note)
        else:
            self.lower_panel.setVisible(True)
            self.upper_layout.setColumnStretch(0, 1)
            self.upper_layout.setColumnStretch(1, 1)
            self.upper_layout.setColumnStretch(2, 1)
            self.game_tree_widget.setVisible(False)
            self.and_or_tree_widget.setVisible(False)
            self.current_box.setVisible(True)
            self.frontier_box.setVisible(True)
            self.reached_box.setVisible(bool(profile.get("show_reached", True)))
            self.current_box.setText(
                f"Vòng lặp: {step.iteration}\n"
                f"Node hiện tại: {fmt_pos(step.current)}\n"
                f"{label1}: {value1}\n"
                f"{label2}: {value2}\n"
                f"Ghi chú: {step.note}"
            )

            self.frontier_box.setText(self._list_text(step.frontier))
            self.reached_box.setText(self._list_text(step.reached))
            self.note_box.setText(str(step.note))

        self._apply_tree_fullscreen_layout(reset=False)

        active_table = self.tree_detail_table if tree_mode else self.table
        self.tree_detail_title.setText(str(profile["detail"]))
        active_table.setColumnCount(len(headers))
        active_table.setHorizontalHeaderLabels(headers)
        active_table.setRowCount(len(step.neighbors))
        self._apply_table_column_widths(headers, active_table)

        for row, nb in enumerate(step.neighbors):
            values = [
                fmt_pos(nb.node),
                str(nb.action),
                str(nb.value),
                str(nb.status),
                str(nb.reason),
            ]

            bg = self._status_color(str(nb.status))
            if tree_mode and game_mode:
                phase = _game_phase_from_note(step.note)
                status_upper = str(nb.status).upper()
                row_active = False
                if phase in {"LEAF", "MIN", "CHANCE", "ALPHA_BETA"}:
                    row_active = True
                elif phase == "PRUNE":
                    row_active = status_upper == "PRUNE"
                elif phase == "MAX":
                    row_active = status_upper == "SELECTED"
                if row_active:
                    bg = QColor("#fef9c3")

            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setBackground(QBrush(bg))
                item.setForeground(QBrush(QColor("#111827")))

                if col == 3:
                    item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                    item.setTextAlignment(Qt.AlignCenter)

                active_table.setItem(row, col, item)

        active_table.resizeRowsToContents()
