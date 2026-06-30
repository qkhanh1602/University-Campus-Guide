from __future__ import annotations

from dataclasses import replace
from html import escape
import re
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QBrush, QFont, QKeyEvent, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from algorithms.search_algorithms import SearchResult, TraceStep, run_algorithm, path_cost
from algorithms.csp_common import csp_color_assignments_from_note, csp_color_for_value_text, _shortest_segment
from map_data import STAGES, Stage, GridPos, is_walkable, landmark_name_at, building_label_at, collision_reason, validate_path_detail, audit_stage, movement_cost, terrain_at, TERRAIN_LABELS, manhattan
from map_scene import CampusMapView
from trace_dialog import (
    TraceDialog,
    csp_assignment_from_step,
    csp_representation_from_note,
    csp_solving_steps_from_note,
    game_representation_from_step,
    game_selected_action_text,
    is_and_or_trace,
    is_csp_trace,
    is_game_trace,
    trace_metric_labels,
    trace_ui_profile,
)


def belief_cells_from_note(note: str) -> List[GridPos]:
    marker = "CURRENT_BELIEF="
    if marker not in str(note):
        return []
    tail = str(note).split(marker, 1)[1]
    cells: List[GridPos] = []
    for r, c in re.findall(r"\((\d+),\s*(\d+)\)", tail):
        cell = (int(r), int(c))
        if cell not in cells:
            cells.append(cell)
    return cells


class InfoCard(QFrame):
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("InfoCard")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 14, 14, 14)
        self.layout.setSpacing(8)
        if title:
            label = QLabel(title)
            label.setObjectName("CardTitle")
            label.setFont(QFont("Segoe UI", 12, QFont.Bold))
            self.layout.addWidget(label)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("University Campus Guide")
        self.resize(1460, 900)

        self.stage: Stage = STAGES[1]
        self.goal_select_mode = False
        self.algorithm = self.stage.algorithms[0]

        self.result: Optional[SearchResult] = None
        self.trace_index = 0

        self.manual_mode = False
        self.manual_pos: GridPos = self.stage.start
        self.manual_steps = 0
        self.manual_path: List[GridPos] = []

        self.speed_ms = 800
        self.trace_by_cell: Dict[GridPos, int] = {}
        self.path_trace_indices: List[int] = []
        self.follow_agent_trace = True
        self.benchmark_results: Dict[int, List[dict]] = {}
        self.benchmark_fastest: Dict[int, dict] = {}

        self.search_timer = QTimer(self)
        self.search_timer.timeout.connect(self.next_trace_step)
        self.route_timer = QTimer(self)
        self.route_timer.timeout.connect(self.next_stage6_route_cell)
        self.route_index = 0
        self.route_animation_kind = ""
        self.and_or_route_branches: List[List[GridPos]] = []
        self.and_or_route_branch_index = 0
        self.stage6_agent_pos: GridPos = self.stage.start
        self.stage6_step_path: List[GridPos] = []
        self.stage6_step_index = 0
        self.stage6_step_target_index = 0
        self.stage6_auto_running = False

        self.trace_dialog = TraceDialog(self)
        for btn in (
            self.trace_dialog.first_btn,
            self.trace_dialog.prev_btn,
            self.trace_dialog.next_btn,
            self.trace_dialog.last_btn,
        ):
            btn.clicked.connect(lambda _checked=False: QTimer.singleShot(0, self.sync_map_to_trace_dialog))

        self.build_ui()
        self.apply_style()
        self.update_stage(1)
        self.setup_shortcuts()

    def build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("Header")

        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 12, 20, 12)

        title = QLabel("University Campus Guide")
        title.setObjectName("HeaderTitle")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))

        subtitle = QLabel("University Campus Guide | SPACE mô phỏng | N từng bước | T trace chi tiết | P WASD | Chọn GOAL bất kỳ")
        subtitle.setObjectName("HeaderSub")

        h_layout.addWidget(title)
        h_layout.addWidget(subtitle, 1)

        outer.addWidget(header)

        splitter = QSplitter(Qt.Horizontal)
        outer.addWidget(splitter, 1)

        left_frame = QFrame()
        left_frame.setObjectName("MapPanel")

        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(16, 16, 10, 16)
        left_layout.setSpacing(10)

        top_map = QHBoxLayout()
        top_map.addStretch(1)

        self.zoom_in_btn = QPushButton("+")
        self.zoom_out_btn = QPushButton("−")
        self.fit_btn = QPushButton("Fit")

        for b in (
            self.zoom_in_btn,
            self.zoom_out_btn,
            self.fit_btn,
        ):
            b.setObjectName("SmallButton")
            top_map.addWidget(b)

        left_layout.addLayout(top_map)

        self.map_view = CampusMapView()
        self.map_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout.addWidget(self.map_view, 1)

        self.legend = QLabel(
            "Chú thích: Đang xét xanh dương | Frontier vàng | Đã xét tím"
        )
        self.legend.setObjectName("Legend")
        self.legend.setWordWrap(True)
        left_layout.addWidget(self.legend)

        splitter.addWidget(left_frame)

        self.right_scroll = QScrollArea()
        self.right_scroll.setWidgetResizable(True)
        self.right_scroll.setObjectName("RightScroll")

        right_content = QWidget()
        self.right_scroll.setWidget(right_content)

        self.right_layout = QVBoxLayout(right_content)
        self.right_layout.setContentsMargins(18, 18, 18, 18)
        self.right_layout.setSpacing(14)

        splitter.addWidget(self.right_scroll)
        splitter.setSizes([940, 420])

        self.build_control_panel()

        self.zoom_in_btn.clicked.connect(self.map_view.zoom_in)
        self.zoom_out_btn.clicked.connect(self.map_view.zoom_out)
        self.fit_btn.clicked.connect(self.fit_map)
        self.map_view.cell_clicked.connect(self.on_map_cell_clicked)

    def build_control_panel(self) -> None:
        app_title = QLabel("University Campus Guide")
        app_title.setObjectName("AppTitle")
        app_title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        self.right_layout.addWidget(app_title)

        desc = QLabel("Ứng dụng mô phỏng thuật toán AI tìm đường trong khuôn viên Trường Đại học.")
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        self.right_layout.addWidget(desc)

        guide_card = InfoCard("Cách xem thuật toán")
        self.guide_label = QLabel(
            "1) Chọn chặng và thuật toán.\n"
            "2) Muốn test Goal khác thì bấm 'Chọn GOAL bất kỳ', sau đó click một ô đi được trên bản đồ.\n"
            "3) SPACE để chạy mô phỏng, N để xem từng bước.\n"
            "4) T mở trace chi tiết; P bật WASD để tự đi thử."
        )
        self.guide_label.setObjectName("Muted")
        self.guide_label.setWordWrap(True)
        guide_card.layout.addWidget(self.guide_label)
        self.right_layout.addWidget(guide_card)

        stage_card = InfoCard("Chọn chặng")

        grid = QGridLayout()
        self.stage_buttons: Dict[int, QPushButton] = {}

        for i in range(1, 7):
            btn = QPushButton(str(i))
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, idx=i: self.update_stage(idx))
            self.stage_buttons[i] = btn
            grid.addWidget(btn, 0, i - 1)

        stage_card.layout.addLayout(grid)

        self.stage_title = QLabel("")
        self.stage_title.setObjectName("StageTitle")
        self.stage_title.setWordWrap(True)

        self.stage_env = QLabel("")
        self.stage_env.setWordWrap(True)
        self.stage_env.setObjectName("Muted")
        self.stage_env.setVisible(False)

        stage_card.layout.addWidget(self.stage_title)
        stage_card.layout.addWidget(self.stage_env)

        goal_row = QHBoxLayout()

        self.goal_pick_btn = QPushButton("Chọn GOAL bất kỳ")
        self.goal_pick_btn.setCheckable(True)

        self.reset_goal_btn = QPushButton("Reset GOAL gốc")

        goal_row.addWidget(self.goal_pick_btn)
        goal_row.addWidget(self.reset_goal_btn)

        stage_card.layout.addLayout(goal_row)
        self.right_layout.addWidget(stage_card)

        algo_card = InfoCard("3 thuật toán của nhóm")

        self.algo_group = QButtonGroup(self)
        self.algo_buttons: List[QRadioButton] = []

        for i in range(3):
            rb = QRadioButton("")
            rb.setObjectName("AlgoRadio")
            rb.clicked.connect(lambda checked=False, idx=i: self.select_algorithm(idx))
            self.algo_group.addButton(rb, i)
            self.algo_buttons.append(rb)
            algo_card.layout.addWidget(rb)

        self.algo_nature = QLabel("")
        self.algo_nature.setObjectName("Muted")
        self.algo_nature.setWordWrap(True)

        algo_card.layout.addWidget(self.algo_nature)
        self.right_layout.addWidget(algo_card)

        control_card = InfoCard("Điều khiển")

        cgrid = QGridLayout()

        self.search_btn = QPushButton("SPACE - Chạy AI")
        self.step_btn = QPushButton("N - Xem 1 bước")
        self.trace_btn = QPushButton("T - Search Trace chi tiết")
        self.manual_btn = QPushButton("P - Tự chơi")

        for idx, btn in enumerate([self.search_btn, self.step_btn, self.trace_btn, self.manual_btn]):
            cgrid.addWidget(btn, idx // 2, idx % 2)

        control_card.layout.addLayout(cgrid)
        self.right_layout.addWidget(control_card)

        result_card = InfoCard("Kết quả")

        rgrid = QGridLayout()

        self.cost_value = self.metric_box("Cost", "-")
        self.expanded_value = self.metric_box("Node đã xét", "-")
        self.step_value = self.metric_box("Số bước", "-")
        self.time_value = self.metric_box("Thời gian", "-")

        rgrid.addWidget(self.cost_value, 0, 0)
        rgrid.addWidget(self.expanded_value, 0, 1)
        rgrid.addWidget(self.step_value, 1, 0)
        rgrid.addWidget(self.time_value, 1, 1)

        result_card.layout.addLayout(rgrid)

        self.status_label = QLabel("Chưa chạy thuật toán")
        self.status_label.setObjectName("Muted")
        self.status_label.setWordWrap(True)

        result_card.layout.addWidget(self.status_label)
        self.right_layout.addWidget(result_card)

        benchmark_card = InfoCard("Benchmark thời gian")

        benchmark_actions = QHBoxLayout()
        self.benchmark_btn = QPushButton("Tổng hợp runtime 6 chặng")
        self.export_benchmark_btn = QPushButton("Xem biểu đồ")
        self.export_benchmark_btn.setEnabled(False)

        benchmark_actions.addWidget(self.benchmark_btn)
        benchmark_actions.addWidget(self.export_benchmark_btn)
        benchmark_card.layout.addLayout(benchmark_actions)

        self.benchmark_summary = QTextEdit()
        self.benchmark_summary.setReadOnly(True)
        self.benchmark_summary.setMinimumHeight(210)
        self.benchmark_summary.setText(
            "Bấm 'Tổng hợp runtime 6 chặng' để chạy 3 thuật toán của mỗi chặng, "
            "tự động highlight thuật toán nhanh nhất và xem biểu đồ so sánh."
        )
        benchmark_card.layout.addWidget(self.benchmark_summary)

        self.right_layout.addWidget(benchmark_card)

        cell_card = InfoCard("Thông tin ô đang chọn")

        self.cell_info = QLabel("Click một ô trên bản đồ để xem thông tin ô")
        self.cell_info.setObjectName("Muted")
        self.cell_info.setWordWrap(True)

        cell_card.layout.addWidget(self.cell_info)
        self.right_layout.addWidget(cell_card)

        self.trace_counter = QLabel("0/0")
        self.trace_counter.setObjectName("Muted")

        self.trace_preview = QTextEdit()
        self.trace_preview.setReadOnly(True)
        self.trace_preview.setMinimumHeight(190)
        self.trace_preview.setFont(QFont("Consolas", 9))

        manual_card = InfoCard("Tự chơi ")

        self.manual_info = QLabel("Tắt. Bấm P để bật. Khi bật, dùng W/A/S/D để di chuyển từ START đến GOAL. Không thể đi xuyên chướng ngại vật.")
        self.manual_info.setObjectName("Muted")
        self.manual_info.setWordWrap(True)

        manual_card.layout.addWidget(self.manual_info)
        self.right_layout.addWidget(manual_card)

        self.right_layout.addStretch(1)

        self.search_btn.clicked.connect(self.toggle_search_timer)
        self.step_btn.clicked.connect(self.next_trace_step)
        self.trace_btn.clicked.connect(self.open_trace_dialog)
        self.manual_btn.clicked.connect(self.toggle_manual_mode)
        self.goal_pick_btn.clicked.connect(self.toggle_goal_select_mode)
        self.reset_goal_btn.clicked.connect(self.reset_goal_to_default)
        self.benchmark_btn.clicked.connect(self.run_runtime_benchmark)
        self.export_benchmark_btn.clicked.connect(self.export_runtime_chart)

    def metric_box(self, label: str, value: str) -> QFrame:
        box = QFrame()
        box.setObjectName("MetricBox")

        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 8)

        v = QLabel(value)
        v.setObjectName("MetricValue")
        v.setAlignment(Qt.AlignCenter)
        v.setFont(QFont("Segoe UI", 18, QFont.Bold))

        l = QLabel(label)
        l.setObjectName("MetricLabel")
        l.setAlignment(Qt.AlignCenter)

        box.value_label = v  # type: ignore[attr-defined]

        lay.addWidget(v)
        lay.addWidget(l)

        return box

    def apply_style(self) -> None:
        self.setStyleSheet("""
            QMainWindow { background: #0f172a; font-family: 'Segoe UI', Arial, Tahoma; }
            QFrame#Header { background: #111827; border-bottom: 3px solid #2563eb; }
            QLabel#HeaderTitle { color: #ffffff; }
            QLabel#HeaderSub { color: #9ca3af; padding-left: 12px; }
            QFrame#MapPanel { background: #111827; }
            QLabel#SectionTitle { color: #e5e7eb; font-size: 17px; font-weight: 700; }
            QLabel#Legend { color: #d1d5db; background: #1f2937; border: 1px solid #374151; border-radius: 10px; padding: 8px; }
            QScrollArea#RightScroll { background: #f4f7fb; border-left: 1px solid #dbe3ef; }
            QWidget { font-size: 14px; }
            QLabel#AppTitle { color: #2563eb; }
            QLabel#CardTitle, QLabel#StageTitle { color: #1f2937; font-weight: 700; }
            QLabel#Muted { color: #6b7280; line-height: 130%; }
            QFrame#InfoCard { background: #ffffff; border: 1px solid #d9e2ef; border-radius: 16px; }
            QPushButton { background: #eef5ff; color: #0f172a; border: 1px solid #bfd0e8; border-radius: 10px; padding: 9px 11px; font-weight: 600; }
            QPushButton:hover { background: #dbeafe; color: #0f172a; border-color: #60a5fa; }
            QPushButton:checked { background: #2563eb; color: #ffffff; border-color: #1d4ed8; font-weight: 800; }
            QPushButton#SmallButton { min-width: 44px; max-width: 70px; padding: 6px; background: #1f2937; color: #f8fafc; border: 1px solid #475569; }
            QRadioButton#AlgoRadio { background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 10px; padding: 10px 12px; font-weight: 650; }
            QRadioButton#AlgoRadio:hover { background: #eff6ff; color: #0f172a; border: 1px solid #60a5fa; }
            QRadioButton#AlgoRadio::indicator { width: 0px; height: 0px; }
            QRadioButton#AlgoRadio[benchmarkWinner="true"] { background: #dcfce7; color: #14532d; border: 2px solid #22c55e; font-weight: 800; }
            QRadioButton#AlgoRadio:checked { background: #1d4ed8; color: #ffffff; border: 2px solid #1e40af; font-weight: 800; }
            QRadioButton#AlgoRadio[benchmarkWinner="true"]:checked { background: #16a34a; color: #ffffff; border: 2px solid #15803d; font-weight: 900; }
            QRadioButton#AlgoRadio:disabled { background: #f8fafc; color: #64748b; border: 1px solid #e2e8f0; }
            QFrame#MetricBox { background: #f8fafc; border: 1px solid #edf2f7; border-radius: 14px; }
            QLabel#MetricValue { color: #2563eb; }
            QLabel#MetricLabel { color: #94a3b8; font-size: 12px; }
            QTextEdit { background: #ffffff; border: 1px solid #d9e2ef; border-radius: 10px; padding: 8px; color: #1f2937; }
            QScrollBar:vertical { background: #e5e7eb; width: 11px; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #94a3b8; border-radius: 5px; min-height: 24px; }
        """)

    def setup_shortcuts(self) -> None:
        def shortcut(seq: str, fn):
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(fn)
            return sc

        self._shortcuts = []

        for i in range(1, 7):
            self._shortcuts.append(shortcut(str(i), lambda idx=i: self.update_stage(idx)))

        self._shortcuts.append(shortcut("Q", lambda: (self.algo_buttons[0].setChecked(True), self.select_algorithm(0))))
        self._shortcuts.append(shortcut("W", lambda: self.manual_move(-1, 0) if self.manual_mode else (self.algo_buttons[1].setChecked(True), self.select_algorithm(1))))
        self._shortcuts.append(shortcut("E", lambda: (self.algo_buttons[2].setChecked(True), self.select_algorithm(2))))

        self._shortcuts.append(shortcut("A", lambda: self.manual_move(0, -1) if self.manual_mode else None))
        self._shortcuts.append(shortcut("S", lambda: self.manual_move(1, 0) if self.manual_mode else None))
        self._shortcuts.append(shortcut("D", lambda: self.manual_move(0, 1) if self.manual_mode else None))

        self._shortcuts.append(shortcut("Space", self.toggle_search_timer))
        self._shortcuts.append(shortcut("N", self.next_trace_step))
        self._shortcuts.append(shortcut("Right", self.next_trace_step))
        self._shortcuts.append(shortcut("Left", self.prev_trace_step))
        self._shortcuts.append(shortcut("P", self.toggle_manual_mode))
        self._shortcuts.append(shortcut("T", self.open_trace_dialog))
        self._shortcuts.append(shortcut("L", self.map_view.toggle_labels))
        self._shortcuts.append(shortcut("V", self.map_view.toggle_collision))

        self._shortcuts.append(shortcut("Y", self.toggle_goal_select_mode))
        self._shortcuts.append(shortcut("R", self.reset_goal_to_default))

        self._shortcuts.append(shortcut("+", lambda: self.set_speed(max(60, self.speed_ms - 40))))
        self._shortcuts.append(shortcut("-", lambda: self.set_speed(min(1000, self.speed_ms + 40))))

    def set_speed(self, value: int) -> None:
        self.speed_ms = value

        if self.search_timer.isActive():
            self.search_timer.setInterval(self.speed_ms)
        if self.route_timer.isActive():
            self.route_timer.setInterval(self.speed_ms)

        self.status_label.setText(f"Tốc độ mô phỏng: {self.speed_ms} ms/bước")

    def current_result_reaches_goal(self) -> bool:
        if not self.result:
            return False

        ok, _ = validate_path_detail(self.result.path, self.stage)
        return ok

    def stage_summary_text(self) -> str:
        summaries = {
            1: "Tìm đường cơ bản từ START tới GOAL; so sánh BFS / DFS / IDS.",
            2: "Tìm đường có heuristic và chi phí; so sánh Greedy / A* / IDA*.",
            3: "Local Search cải thiện từng bước; nhanh nhưng có thể kẹt cực trị cục bộ.",
            4: "Môi trường không chắc chắn: Có thể sinh ra các hành động không chắc chắc hoặc không biết Start ",
            5: "Game Search: Agent tới GOAL trong khi đối thủ và môi trường làm điểm bất lợi hơn.",
            6: "CSP tô màu các tòa nhà: hai tòa kề nhau không được trùng màu.",
        }
        return summaries.get(self.stage.idx, self.stage.detail)

    def algorithm_summary_text(self) -> str:
        summaries = {
            "BFS": "Duyệt theo lớp, đảm bảo ít bước nhất khi mọi bước cùng chi phí.",
            "DFS": "Đi sâu trước, dễ minh họa thử nhánh nhưng không đảm bảo tối ưu.",
            "IDS": "Lặp DFS theo độ sâu tăng dần, tiết kiệm bộ nhớ.",
            "Greedy Best First": "Chọn ô gần GOAL theo heuristic, nhanh nhưng có thể không tối ưu.",
            "A*": "Kết hợp chi phí đã đi và heuristic để tìm đường tốt.",
            "IDA*": "A* theo ngưỡng lặp, tiết kiệm bộ nhớ hơn.",
            "Hill Climbing": "Luôn chọn bước cải thiện gần nhất, có thể kẹt cực trị cục bộ.",
            "Local Beam Search": "Giữ nhiều ứng viên tốt cùng lúc để giảm nguy cơ kẹt.",
            "Simulated Annealing": "Đôi khi nhận bước xấu để thoát kẹt, xác suất giảm dần.",
            "AND-OR Graph Search": "Một action sinh R1/R2; mỗi branch đều phải có plan tới GOAL.",
            "Belief State A*": "Tìm trên tập vị trí có thể, dùng A* để giảm bất định.",
            "Belief State BFS": "Duyệt belief state bằng hàng đợi FIFO.",
            "Minimax": "Agent chọn nước tốt nhất khi đối thủ gây bất lợi nhất.",
            "Alpha-Beta Pruning": "Minimax có cắt nhánh để giảm số node phải xét.",
            "Expectimax": "Tính điểm kỳ vọng khi có yếu tố ngẫu nhiên.",
            "Backtracking": "Thử màu từng tòa nhà; sai ràng buộc thì quay lui.",
            "Forward Checking": "Sau mỗi lần tô, loại màu đó khỏi domain của các tòa kề.",
            "Min-Conflicts": "Bắt đầu với assignment màu đầy đủ, chọn biến xung đột rồi đổi sang màu ít xung đột nhất.",
        }
        return summaries.get(self.algorithm, "Mô phỏng thuật toán theo từng bước trên bản đồ.")

    def update_stage_text(self) -> None:
        default_goal = STAGES[self.stage.idx].goal
        goal_label = landmark_name_at(self.stage.goal) or ""

        goal_note = ""
        if self.stage.goal != default_goal:
            goal_note = f"\nGOAL tùy chọn: {self.stage.goal} {goal_label}"

        self.stage_title.setText(f"{self.stage.title}\nNhóm: {self.stage.group}{goal_note}")

        audit = audit_stage(self.stage)
        audit_msg = "" if not audit else "\nCảnh báo thiết lập: " + "; ".join(audit)

        self.stage_env.setText(
            f"Môi trường: {self.stage.environment} | Độ khó: {self.stage.difficulty}/6\n"
            f"{self.stage_summary_text()}{audit_msg}"
        )

    def reset_after_stage_or_goal_change(self, message: str) -> None:
        self.search_timer.stop()
        self.route_timer.stop()
        self.route_index = 0
        self.route_animation_kind = ""
        self.and_or_route_branches = []
        self.and_or_route_branch_index = 0
        self.stage6_agent_pos = self.stage.start
        self.stage6_step_path = []
        self.stage6_step_index = 0
        self.stage6_step_target_index = 0
        self.stage6_auto_running = False

        self.manual_mode = False
        self.manual_pos = self.stage.start
        self.manual_steps = 0
        self.manual_path = [self.manual_pos]

        self.result = None
        self.trace_index = 0
        self.trace_by_cell = {}
        self.path_trace_indices = []

        self.refresh_map_for_algorithm()
        self.reset_result_labels()
        self.update_stage_text()
        self.update_algorithm_nature()
        self.refresh_benchmark_highlights(select_fastest=False)

        self.trace_preview.setText(message)
        self.trace_counter.setText("0/0")
        self.manual_info.setText("Tắt. Bấm P để bật tự chơi WASD.")

    def refresh_map_for_algorithm(self) -> None:
        """Redraw stage 4 visuals according to selected algorithm.

        AND-OR uses one START/GOAL. Belief algorithms keep uncertain START?
        markers and fog-of-war. This affects UI only, not algorithm input.
        """
        if hasattr(self.map_view, "set_algorithm_visual_mode"):
            self.map_view.set_algorithm_visual_mode(self.algorithm)
        self.map_view.set_stage(self.stage)

    def toggle_goal_select_mode(self) -> None:
        self.goal_select_mode = not self.goal_select_mode
        self.goal_pick_btn.setChecked(self.goal_select_mode)

        if self.goal_select_mode:
            self.search_timer.stop()
            self.status_label.setText("Đang bật chế độ chọn GOAL. Hãy click một ô đi được trên bản đồ.")
            self.cell_info.setText("Chế độ chọn GOAL: click vào ô đi được. Không chọn tòa nhà, cỏ, hồ nước, ô chặn hoặc đối thủ.")
        else:
            self.status_label.setText("Đã tắt chế độ chọn GOAL.")

    def set_custom_goal(self, pos: GridPos) -> None:
        label = landmark_name_at(pos) or ""

        if pos == self.stage.start:
            QMessageBox.warning(self, "Không thể chọn GOAL", "GOAL không nên trùng với START.")
            self.status_label.setText("Không thể chọn GOAL trùng START.")
            return

        if not is_walkable(pos, self.stage):
            reason = collision_reason(pos, self.stage)
            QMessageBox.warning(self, "Không thể chọn GOAL", f"Ô {pos} không đi được: {reason}")
            self.status_label.setText(f"Không thể chọn GOAL tại {pos}: {reason}")
            return

        self.stage = replace(self.stage, goal=pos)

        self.goal_select_mode = False
        self.goal_pick_btn.setChecked(False)

        self.reset_after_stage_or_goal_change(
            f"Đã đổi GOAL sang {pos} {label}. Bấm SPACE hoặc N để chạy lại {self.algorithm}."
        )

        self.status_label.setText(f"Đã chọn GOAL mới: {pos} {label}. Thuật toán sẽ chạy lại với Goal này.")

    def reset_goal_to_default(self) -> None:
        idx = self.stage.idx
        current_algorithm = self.algorithm

        self.stage = STAGES[idx]

        self.goal_select_mode = False
        self.goal_pick_btn.setChecked(False)

        if current_algorithm in self.stage.algorithms:
            self.algorithm = current_algorithm
        else:
            self.algorithm = self.stage.algorithms[0]

        for i, rb in enumerate(self.algo_buttons):
            rb.setChecked(self.stage.algorithms[i] == self.algorithm)

        self.reset_after_stage_or_goal_change(
            f"Đã reset GOAL về mặc định của chặng {idx}. Bấm SPACE hoặc N để chạy lại {self.algorithm}."
        )

        self.status_label.setText(f"Đã reset GOAL gốc: {self.stage.goal} {landmark_name_at(self.stage.goal) or ''}")

    def update_stage(self, idx: int) -> None:
        self.search_timer.stop()

        self.stage = STAGES[idx]
        self.goal_select_mode = False

        if hasattr(self, "goal_pick_btn"):
            self.goal_pick_btn.setChecked(False)

        self.manual_mode = False
        self.manual_pos = self.stage.start
        self.manual_steps = 0
        self.manual_path = [self.manual_pos]
        self.stage6_agent_pos = self.stage.start
        self.stage6_step_path = []
        self.stage6_step_index = 0
        self.stage6_step_target_index = 0
        self.stage6_auto_running = False

        self.result = None
        self.trace_index = 0
        self.trace_by_cell = {}
        self.path_trace_indices = []

        self.algorithm = self.stage.algorithms[0]

        for i, btn in self.stage_buttons.items():
            btn.setChecked(i == idx)

        self.update_stage_text()

        for i, rb in enumerate(self.algo_buttons):
            rb.setText(f"{['Q','W','E'][i]}. {self.stage.algorithms[i]}")
            rb.setChecked(i == 0)

        self.update_algorithm_nature()
        self.refresh_benchmark_highlights(select_fastest=True)

        self.refresh_map_for_algorithm()
        self.reset_result_labels()

        self.trace_preview.setText("Hãy bấm SPACE để chạy mô phỏng tìm kiếm từng bước, hoặc N để xem từng bước thủ công.")
        self.trace_counter.setText("0/0")
        self.manual_info.setText("Tắt. Bấm P để bật tự chơi WASD.")
        self.cell_info.setText("Click một ô trên bản đồ để xem terrain, collision, cost và trace liên quan.")

    def select_algorithm(self, idx: int) -> None:
        self.search_timer.stop()
        self.route_timer.stop()
        self.route_index = 0
        self.route_animation_kind = ""
        self.and_or_route_branches = []
        self.and_or_route_branch_index = 0
        self.stage6_agent_pos = self.stage.start
        self.stage6_step_path = []
        self.stage6_step_index = 0
        self.stage6_step_target_index = 0
        self.stage6_auto_running = False

        self.algorithm = self.stage.algorithms[idx]

        self.result = None
        self.trace_index = 0
        self.trace_by_cell = {}
        self.path_trace_indices = []

        self.refresh_map_for_algorithm()
        self.reset_result_labels()
        self.update_algorithm_nature()
        self.refresh_benchmark_highlights(select_fastest=False)

        self.trace_preview.setText(f"Đã chọn {self.algorithm}. Bấm SPACE để chạy tìm kiếm.")

    def update_algorithm_nature(self) -> None:
        desc = {
            "BFS": "Queue FIFO, duyệt theo chiều rộng ",
            "DFS": "Stack LIFO, đi sâu trước, ít bộ nhớ nhưng không đảm bảo tối ưu.",
            "IDS": "DFS lặp với depth limit tăng dần, thấy rõ CUTOFF ở từng vòng.",
            "UCS": "Priority Queue theo g(n), chọn đường có chi phí đã đi nhỏ nhất.",
            "Greedy Best First": "Priority Queue theo h(n), chọn node nhìn gần Goal nhất.",
            "A*": "Priority Queue theo f(n)=g(n)+h(n), cân bằng cost thật và heuristic.",
            "IDA*": "DFS lặp với threshold theo f(n), tiết kiệm bộ nhớ hơn A*.",
            "Local Beam Search": "Giữ k trạng thái hiện tại, sinh neighbor của tất cả rồi lấy k trạng thái tốt nhất.",
            "Simulated Annealing": "Random 1 neighbor; tốt hơn thì nhận, xấu hơn thì nhận theo xác suất nhiệt độ T.",
            "Hill Climbing": "Local Search: chọn neighbor đầu tiên tốt hơn current; nếu kẹt local optimum thì dừng.",
            "Simple Hill Climbing": "Local Search: chọn neighbor đầu tiên tốt hơn current.",
            "Steepest Hill Climbing": "Local Search: xét hết neighbor rồi chọn neighbor tốt nhất.",
            "Stochastic Hill Climbing": "Local Search: chọn ngẫu nhiên trong nhóm neighbor tốt hơn current.",
            "Random Restart Hill Climbing": "Local Search: chạy nhiều start để giảm nguy cơ kẹt local optimum.",
            "Belief BFS": "Môi trường không chắc chắn: BFS trên belief state, node là tập vị trí có thể.",
            "Belief State BFS": "Môi trường không chắc chắn: BFS trên belief state bằng Queue FIFO; giữ các START? và mở sương mù theo trace.",
            "Belief UCS": "Môi trường không chắc chắn: UCS trên belief state theo g(B).",
            "Belief A*": "Môi trường không chắc chắn: A* trên belief state theo f(B)=g(B)+h(B).",
            "Belief State A*": "Môi trường không chắc chắn: A* trên belief state theo f(B)=g(B)+h(B); bản đồ có sương mù mở dần khi khám phá.",
            "Belief Greedy": "Môi trường không chắc chắn: Greedy chọn belief có h(B) nhỏ nhất.",
            "Belief IDA*": "Môi trường không chắc chắn: IDA* dùng threshold theo f(B).",
            "Belief Local Beam": "Môi trường không chắc chắn: giữ k belief state tốt nhất mỗi vòng.",
            "Minimax": "Game Search: agent chọn nước tốt nhất khi giả định đối thủ chọn nước gây bất lợi.",
            "Alpha-Beta Pruning": "Game Search: giống Minimax nhưng cắt bớt nhánh kém hứa hẹn để giảm số node xét.",
            "Expectimax": "Game Search có yếu tố ngẫu nhiên: tính kỳ vọng khi đối thủ/môi trường có xác suất rủi ro.",
            "Backtracking": "CSP: thử tô màu từng tòa nhà; sai constraint kề nhau thì quay lui.",
            "Forward Checking": "CSP: sau khi tô một tòa, loại màu đó khỏi domain của các tòa kề.",
            "Min-Conflicts": "CSP: bắt đầu với assignment màu bất kỳ rồi sửa dần các cặp xung đột.",
        }

        suffix = ""

        if self.stage.idx == 6:
            suffix = " Chặng 6 là graph coloring CSP: biến là tòa nhà, domain là màu, constraint là tòa kề nhau không cùng màu."

        if self.stage.idx == 4 and self.algorithm == "AND-OR Graph Search":
            suffix += " AND-OR trên bản đồ chỉ có 1 START và 1 GOAL; nhiều result state là do action không xác định, không phải nhiều Start."
        elif self.stage.idx == 4 and "Belief" in self.algorithm:
            suffix += " Belief State giữ nguyên các START? không chắc chắn; sương mù chỉ là hiệu ứng minh họa vùng đã khám phá."

        self.algo_nature.setText("Tóm tắt: " + self.algorithm_summary_text())
        self.update_map_legend()

    def update_map_legend(self) -> None:
        if self.stage.idx == 4 and self.algorithm == "AND-OR Graph Search":
            self.legend.setText(
                "Chú thích AND-OR: đường xanh = result branch R1 | đường tím = result branch R2 | "
                "mỗi branch đều phải có plan tới GOAL"
            )
        elif self.stage.idx == 6:
            self.legend.setText(
                "CSP tô màu: tòa trắng = chưa tô | vàng = đang thử | màu thật = đã gán | "
                "xám = màu bị loại | đỏ = vi phạm constraint"
            )
        else:
            self.legend.setText("Chú thích: Đang xét xanh dương | Frontier vàng | Đã xét tím")

    def reset_result_labels(self) -> None:
        for box, value in [
            (self.cost_value, "-"),
            (self.expanded_value, "-"),
            (self.step_value, "-"),
            (self.time_value, "-"),
        ]:
            box.value_label.setText(value)  # type: ignore[attr-defined]

        self.status_label.setText("Chưa chạy thuật toán")
        self.cell_info.setText("Click một ô trên bản đồ để xem terrain, collision, cost và trace liên quan.")

    def refresh_benchmark_highlights(self, select_fastest: bool = False) -> None:
        best = self.benchmark_fastest.get(self.stage.idx)
        best_algorithm = best["algorithm"] if best else None

        if select_fastest and best_algorithm in self.stage.algorithms and self.algorithm != best_algorithm:
            self.algorithm = best_algorithm
            self.result = None
            self.trace_index = 0
            self.trace_by_cell = {}
            self.path_trace_indices = []
            self.refresh_map_for_algorithm()
            self.reset_result_labels()
            self.update_algorithm_nature()
            self.trace_preview.setText(
                f"Benchmark đã chọn thuật toán nhanh nhất của chặng {self.stage.idx}: {best_algorithm}."
            )

        for i, rb in enumerate(self.algo_buttons):
            algorithm = self.stage.algorithms[i]
            label = f"{['Q','W','E'][i]}. {algorithm}"

            if algorithm == best_algorithm:
                label += f"  [FASTEST {best['runtime_ms']:.3f} ms]"

            rb.setText(label)
            rb.setChecked(algorithm == self.algorithm)
            rb.setProperty("benchmarkWinner", algorithm == best_algorithm)
            rb.style().unpolish(rb)
            rb.style().polish(rb)
            rb.update()

    def run_runtime_benchmark(self) -> None:
        self.search_timer.stop()
        self.benchmark_btn.setEnabled(False)
        self.export_benchmark_btn.setEnabled(False)
        self.benchmark_summary.setText("Đang chạy benchmark 18 thuật toán...")
        self.status_label.setText("Đang tổng hợp runtime các thuật toán...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()

        results: Dict[int, List[dict]] = {}
        fastest: Dict[int, dict] = {}

        try:
            for stage_idx, stage in STAGES.items():
                stage_rows: List[dict] = []

                for algorithm in stage.algorithms:
                    result = run_algorithm(stage, algorithm)
                    row = {
                        "stage": stage_idx,
                        "algorithm": algorithm,
                        "runtime_ms": float(result.runtime_ms),
                        "cost": int(result.cost),
                        "expanded": int(result.expanded),
                        "steps": max(0, len(result.path) - 1),
                        "status": result.status,
                    }
                    stage_rows.append(row)
                    self.status_label.setText(
                        f"Benchmark chặng {stage_idx}: {algorithm} = {row['runtime_ms']:.3f} ms"
                    )
                    QApplication.processEvents()

                best = min(stage_rows, key=lambda row: row["runtime_ms"])
                results[stage_idx] = stage_rows
                fastest[stage_idx] = best

            self.benchmark_results = results
            self.benchmark_fastest = fastest
            self.benchmark_summary.setHtml(self.build_benchmark_html())
            self.export_benchmark_btn.setEnabled(True)
            self.refresh_benchmark_highlights(select_fastest=True)
            self.status_label.setText("Đã tổng hợp runtime và highlight thuật toán nhanh nhất mỗi chặng.")
        finally:
            QApplication.restoreOverrideCursor()
            self.benchmark_btn.setEnabled(True)

    def build_benchmark_html(self) -> str:
        if not self.benchmark_results:
            return "<p>Chưa có dữ liệu benchmark.</p>"

        parts = [
            "<div style='font-family: Segoe UI, Arial; color:#111827;'>",
            "<h3 style='margin:0 0 8px 0;color:#166534;'>Tổng hợp runtime theo chặng</h3>",
            "<p style='margin:0 0 8px 0;color:#475569;'>Dòng màu xanh lá là thuật toán nhanh nhất trong chặng.</p>",
        ]

        for stage_idx in sorted(self.benchmark_results):
            rows = self.benchmark_results[stage_idx]
            best_algorithm = self.benchmark_fastest[stage_idx]["algorithm"]
            parts.append(f"<h4 style='margin:10px 0 4px 0;color:#1d4ed8;'>Chặng {stage_idx}</h4>")
            parts.append(
                "<table cellspacing='0' cellpadding='5' width='100%' "
                "style='border-collapse:collapse;background:#ffffff;'>"
                "<tr style='background:#dbeafe;color:#1e3a8a;'>"
                "<th style='border:1px solid #bfdbfe;'>Thuật toán</th>"
                "<th style='border:1px solid #bfdbfe;'>Runtime</th>"
                "<th style='border:1px solid #bfdbfe;'>Cost</th>"
                "<th style='border:1px solid #bfdbfe;'>Node</th>"
                "<th style='border:1px solid #bfdbfe;'>Kết quả</th>"
                "</tr>"
            )

            for row in rows:
                is_best = row["algorithm"] == best_algorithm
                bg = "#dcfce7" if is_best else "#ffffff"
                badge = "FASTEST" if is_best else ""
                parts.append(
                    f"<tr style='background:{bg};'>"
                    f"<td style='border:1px solid #e5e7eb;'><b>{escape(row['algorithm'])}</b> {badge}</td>"
                    f"<td style='border:1px solid #e5e7eb;text-align:right;'>{row['runtime_ms']:.3f} ms</td>"
                    f"<td style='border:1px solid #e5e7eb;text-align:right;'>{row['cost']}</td>"
                    f"<td style='border:1px solid #e5e7eb;text-align:right;'>{row['expanded']}</td>"
                    f"<td style='border:1px solid #e5e7eb;'>{escape(row['status'])}</td>"
                    "</tr>"
                )

            parts.append("</table>")

        parts.append("</div>")
        return "".join(parts)

    def export_runtime_chart(self) -> None:
        if not self.benchmark_fastest:
            self.run_runtime_benchmark()

        if not self.benchmark_fastest:
            return

        pixmap = self.build_runtime_chart_pixmap()

        if pixmap.isNull():
            QMessageBox.warning(self, "Không thể xem", "Chưa tạo được biểu đồ runtime.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Biểu đồ runtime nhanh nhất theo chặng")
        dialog.resize(1280, 760)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        image_label = QLabel()
        image_label.setPixmap(pixmap)
        image_label.setAlignment(Qt.AlignCenter)

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setWidget(image_label)
        layout.addWidget(scroll, 1)

        action_row = QHBoxLayout()
        action_row.addStretch(1)

        fullscreen_btn = QPushButton("Toàn màn hình")

        def toggle_fullscreen() -> None:
            if dialog.isFullScreen():
                dialog.showMaximized()
                fullscreen_btn.setText("Toàn màn hình")
            else:
                dialog.showFullScreen()
                fullscreen_btn.setText("Thu nhỏ")

        fullscreen_btn.clicked.connect(toggle_fullscreen)
        action_row.addWidget(fullscreen_btn)

        close_btn = QPushButton("Đóng")
        close_btn.clicked.connect(dialog.accept)
        action_row.addWidget(close_btn)
        layout.addLayout(action_row)

        self.status_label.setText("Đã mở biểu đồ runtime trong app.")
        dialog.setWindowState(dialog.windowState() | Qt.WindowMaximized)
        dialog.exec()

    def build_runtime_chart_pixmap(self) -> QPixmap:
        rows = [self.benchmark_fastest[idx] for idx in sorted(self.benchmark_fastest)]
        if not rows:
            return QPixmap()

        width, height = 1280, 760
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#ffffff"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        try:
            margin_left, margin_right = 92, 60
            margin_top, margin_bottom = 108, 150
            chart_w = width - margin_left - margin_right
            chart_h = height - margin_top - margin_bottom
            max_runtime = max(row["runtime_ms"] for row in rows) or 1.0

            painter.setPen(QColor("#0f172a"))
            painter.setFont(QFont("Segoe UI", 22, QFont.Bold))
            painter.drawText(QRectF(0, 26, width, 34), Qt.AlignCenter, "Runtime thuật toán nhanh nhất theo chặng")

            painter.setFont(QFont("Segoe UI", 10))
            painter.setPen(QColor("#475569"))
            painter.drawText(
                QRectF(0, 62, width, 24),
                Qt.AlignCenter,
                "Mỗi cột là thuật toán nhanh nhất trong một chặng sau khi benchmark trong app",
            )

            axis_pen = QPen(QColor("#334155"), 2)
            painter.setPen(axis_pen)
            painter.drawLine(margin_left, margin_top, margin_left, margin_top + chart_h)
            painter.drawLine(margin_left, margin_top + chart_h, margin_left + chart_w, margin_top + chart_h)

            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QColor("#64748b"))
            for i in range(5):
                ratio = i / 4
                value = max_runtime * (1 - ratio)
                y = margin_top + int(chart_h * ratio)
                painter.drawLine(margin_left - 6, y, margin_left + chart_w, y)
                painter.drawText(QRectF(8, y - 10, margin_left - 18, 20), Qt.AlignRight | Qt.AlignVCenter, f"{value:.2f} ms")

            bar_gap = 24
            slot_w = chart_w / len(rows)
            bar_w = max(56, min(118, slot_w - bar_gap))
            colors = ["#2563eb", "#16a34a", "#f59e0b", "#db2777", "#7c3aed", "#0891b2"]

            for i, row in enumerate(rows):
                stage_idx = row["stage"]
                runtime = row["runtime_ms"]
                bar_h = int((runtime / max_runtime) * (chart_h - 16))
                x = margin_left + i * slot_w + (slot_w - bar_w) / 2
                y = margin_top + chart_h - bar_h
                color = QColor(colors[i % len(colors)])

                painter.setBrush(QBrush(color))
                painter.setPen(QPen(color.darker(130), 1.5))
                painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 6, 6)

                painter.setPen(QColor("#0f172a"))
                painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
                painter.drawText(QRectF(x - 12, y - 26, bar_w + 24, 20), Qt.AlignCenter, f"{runtime:.3f} ms")

                painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
                painter.drawText(QRectF(x - 18, margin_top + chart_h + 12, bar_w + 36, 20), Qt.AlignCenter, f"Chặng {stage_idx}")

                painter.setFont(QFont("Segoe UI", 8))
                painter.setPen(QColor("#334155"))
                painter.drawText(
                    QRectF(x - 42, margin_top + chart_h + 36, bar_w + 84, 52),
                    Qt.AlignHCenter | Qt.TextWordWrap,
                    row["algorithm"],
                )

            painter.setPen(QColor("#475569"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(
                QRectF(margin_left, height - 40, chart_w, 22),
                Qt.AlignCenter,
                "Kết quả runtime có thể dao động nhẹ tùy máy và tải hệ thống.",
            )
        finally:
            painter.end()

        return pixmap

    def save_runtime_chart(self, path: str) -> bool:
        pixmap = self.build_runtime_chart_pixmap()
        return False if pixmap.isNull() else pixmap.save(path, "PNG")

    def ensure_result(self) -> None:
        if self.result is None:
            self.status_label.setText(f"Đang chạy {self.algorithm}...")
            QApplication.processEvents()

            if self.stage.idx == 5 and hasattr(self.map_view, "reset_stage5_opponents"):
                self.map_view.reset_stage5_opponents()
            self.result = run_algorithm(self.stage, self.algorithm)

            self.trace_index = 0
            self.build_trace_lookup()

            self.cost_value.value_label.setText(str(int(self.result.cost)))  # type: ignore[attr-defined]
            self.expanded_value.value_label.setText(str(self.result.expanded))  # type: ignore[attr-defined]
            self.step_value.value_label.setText(str(max(0, len(self.result.path) - 1)))  # type: ignore[attr-defined]
            self.time_value.value_label.setText(f"{self.result.runtime_ms:.2f} ms")  # type: ignore[attr-defined]

            ok, detail = validate_path_detail(self.result.path, self.stage)

            if ok:
                self.status_label.setText(self.result.status + " | " + detail)
            else:
                self.status_label.setText(self.result.status + " | " + detail + " | Thuật toán đã dừng, không dùng A* hỗ trợ.")

            if self.stage.idx == 6 and is_csp_trace(self.result.algorithm):
                self.stage6_agent_pos = self.stage.start
                self.render_trace(0, move_character=False)
                self.map_view.set_character_cell(self.stage6_agent_pos)
            else:
                self.render_trace(0)
        self.trace_dialog.set_result(self.result)

    def sync_map_to_trace_dialog(self) -> None:
        if not self.result or self.trace_dialog.result is not self.result:
            return
        self.render_trace(self.trace_dialog.index)

    def build_trace_lookup(self) -> None:
        self.trace_by_cell = {}
        self.path_trace_indices = []

        if not self.result:
            return

        for i, step in enumerate(self.result.trace):
            self.trace_by_cell.setdefault(step.current, i)

        for cell in self.result.path:
            self.path_trace_indices.append(self.trace_by_cell.get(cell, self.find_nearest_trace_index(cell)))

    def find_nearest_trace_index(self, cell: GridPos) -> int:
        if not self.result or not self.result.trace:
            return 0

        if cell in self.trace_by_cell:
            return self.trace_by_cell[cell]

        for i, step in enumerate(self.result.trace):
            if cell in step.frontier or cell in step.reached or any(nb.node == cell for nb in step.neighbors):
                return i

        return max(0, min(self.trace_index, len(self.result.trace) - 1))

    def sync_trace_to_cell(self, cell: GridPos, source: str = "Nhân vật") -> None:
        if not self.follow_agent_trace or not self.result or not self.result.trace:
            return

        idx = self.trace_by_cell.get(cell, self.find_nearest_trace_index(cell))
        opponent_route = self.manual_path if self.manual_mode and self.stage.idx == 5 else None
        self.render_trace(idx, follow_cell=cell, source=source, keep_final_path=True, opponent_route=opponent_route)

        if self.trace_dialog.isVisible():
            self.trace_dialog.show_step(idx)

    def _html_block(self, title: str, body: str, color: str = "#1e3a8a") -> str:
        safe = escape(str(body)).replace("\n", "<br>")
        return (
            f"<div style='background:#ffffff;border:1px solid #dbeafe;border-radius:10px;"
            f"padding:8px;margin:8px 0;'>"
            f"<b style='color:{color};'>{escape(title)}</b><br>"
            f"<span style='color:#111827;'>{safe}</span>"
            f"</div>"
        )

    def _and_or_branch_paths_from_step(self, step: TraceStep) -> List[List[GridPos]]:
        if not self.result or not step.frontier:
            return []

        base = list(step.reached or [step.current])
        branch_paths: List[List[GridPos]] = []
        for result_state in step.frontier:
            prefix = base[:] if base else [step.current]
            if not prefix or prefix[-1] != result_state:
                prefix = prefix + [result_state]

            best = prefix[:]
            for later in self.result.trace:
                reached = list(later.reached)
                if len(reached) < len(prefix):
                    continue
                if reached[: len(prefix)] != prefix:
                    continue
                if len(reached) > len(best):
                    best = reached
                if reached and reached[-1] == self.stage.goal:
                    best = reached
                    break
            branch_paths.append(best)
        return branch_paths

    def and_or_branch_paths_for_step(self, step: TraceStep) -> List[List[GridPos]]:
        local_paths = self._and_or_branch_paths_from_step(step)
        if len(local_paths) >= 2:
            return local_paths

        # Later AND-OR steps are OR_SEARCH calls inside one result branch, so
        # their local frontier often has only one state. Keep the root R1/R2
        # conditional-plan context visible on the map so the trace never looks
        # like ordinary one-path search.
        if not self.result:
            return local_paths
        for root_step in self.result.trace:
            if root_step.frontier and len(root_step.frontier) >= 2:
                root_paths = self._and_or_branch_paths_from_step(root_step)
                if len(root_paths) >= 2:
                    return root_paths
        return local_paths

    def and_or_root_step(self) -> Optional[TraceStep]:
        if not self.result:
            return None
        for step in self.result.trace:
            if step.frontier and len(step.frontier) >= 2:
                return step
        return None

    def and_or_root_action(self) -> str:
        root_step = self.and_or_root_step()
        if not root_step:
            return ""
        for n in root_step.neighbors:
            if str(n.status).upper() in {"OK", "SELECTED", "CHOSEN"}:
                return str(n.action)
        return ""

    def and_or_route_branches_from_trace(self) -> List[List[GridPos]]:
        root_step = self.and_or_root_step()
        if root_step:
            branches = self._and_or_branch_paths_from_step(root_step)
            if len(branches) >= 2:
                return branches
        return [self.result.path] if self.result and self.result.path else []

    def and_or_branch_is_contiguous(self, path: List[GridPos]) -> bool:
        if not path:
            return False
        for a, b in zip(path, path[1:]):
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
                return False
        return True

    def render_trace(
        self,
        index: int,
        follow_cell: Optional[GridPos] = None,
        source: str = "AI",
        keep_final_path: bool = False,
        opponent_route: Optional[List[GridPos]] = None,
        move_character: bool = True,
    ) -> None:
        if not self.result or not self.result.trace:
            return

        index = max(0, min(index, len(self.result.trace) - 1))
        if self.stage.idx == 5 and index == 0 and hasattr(self.map_view, "reset_stage5_opponents"):
            self.map_view.reset_stage5_opponents()
        self.trace_index = index

        step: TraceStep = self.result.trace[index]

        is_stage6_csp = self.stage.idx == 6 and is_csp_trace(self.result.algorithm, step.mode)
        is_and_or_map = self.stage.idx == 4 and is_and_or_trace(self.result.algorithm, step.mode)
        is_belief_map = self.stage.idx == 4 and "belief" in f"{self.result.algorithm} {step.mode}".lower()
        belief_cells = belief_cells_from_note(step.note) if is_belief_map else []
        if is_belief_map and not belief_cells:
            belief_cells = sorted(self.stage.uncertain_starts) or [self.stage.start]
        final_path = [] if (is_stage6_csp or is_and_or_map or is_belief_map) else (self.result.path if (keep_final_path or index >= len(self.result.trace) - 1) else [])
        belief_branch_paths: List[List[GridPos]] = []
        belief_has_solution = is_belief_map and self.result.status == "Hoàn thành" and index >= len(self.result.trace) - 1
        if belief_has_solution:
            for path in getattr(self.result, "belief_paths", []):
                if path:
                    belief_branch_paths.append(list(path[: min(index + 1, len(path))]))
        route_for_opponent = opponent_route
        if route_for_opponent is None and self.stage.idx == 5 and self.result.path:
            step_route = list(step.reached)
            if (
                step_route
                and step_route[0] == self.stage.start
                and step_route[-1] == step.current
                and all(manhattan(a, b) == 1 for a, b in zip(step_route, step_route[1:]))
            ):
                route_for_opponent = step_route
            elif step.current in self.result.path:
                last_index = len(self.result.path) - 1 - list(reversed(self.result.path)).index(step.current)
                route_for_opponent = self.result.path[: last_index + 1]
            else:
                route_for_opponent = [self.stage.start]
        csp_try_cells: List[GridPos] = []
        csp_removed_cells: List[GridPos] = []
        csp_failed_cells: List[GridPos] = []
        if is_stage6_csp:
            for n in step.neighbors:
                status = str(n.status).upper()
                if status in {"ADD", "ADD/UPDATE", "ENQUEUE", "PUSH", "CANDIDATE", "CHOSEN", "MEET", "SELECTED", "TRY", "KEEP"}:
                    csp_try_cells.append(n.node)
                elif status in {"REMOVE"}:
                    csp_removed_cells.append(n.node)
                elif status in {"FAIL", "PRUNE"}:
                    csp_failed_cells.append(n.node)
        csp_color_cells = csp_color_assignments_from_note(step.note) if is_stage6_csp else None
        if is_stage6_csp and csp_color_cells is not None:
            for n in step.neighbors:
                status = str(n.status).upper()
                if status in {"ADD", "TRY", "SELECTED", "KEEP", "OK", "FAIL", "PRUNE", "REMOVE"}:
                    color_hex = csp_color_for_value_text(str(n.value))
                    if color_hex:
                        csp_color_cells[n.node] = color_hex
        and_or_action = ""
        if is_and_or_map:
            for n in step.neighbors:
                if str(n.status).upper() in {"OK", "SELECTED", "CHOSEN"}:
                    and_or_action = str(n.action)
                    break
        and_or_branch_paths = self.and_or_branch_paths_for_step(step) if is_and_or_map else []

        self.map_view.set_trace_overlay(
            None if is_belief_map else step.current,
            step.frontier,
            step.reached,
            [] if is_belief_map else csp_try_cells if is_stage6_csp else [
                n.node
                for n in step.neighbors
                if n.status in {"ADD", "ADD/UPDATE", "ENQUEUE", "PUSH", "CANDIDATE", "CHOSEN", "MEET", "SELECTED"}
            ],
            final_path,
            route_for_opponent,
            move_character and not is_belief_map,
            is_stage6_csp,
            csp_removed_cells,
            csp_failed_cells,
            None,
            is_and_or_map,
            and_or_action,
            and_or_branch_paths,
            csp_color_cells,
            belief_branch_paths,
        )
        if move_character and (is_and_or_map or is_stage6_csp) and not self.manual_mode:
            self.map_view.set_character_cell(step.current)
            if is_stage6_csp:
                self.stage6_agent_pos = step.current
        elif move_character and is_belief_map and not self.manual_mode:
            self.map_view.set_belief_character_cells(belief_cells)

        profile = trace_ui_profile(self.result.algorithm, step.mode)

        headers = list(profile["headers"])
        header_html = "".join(
            f"<th style='border:1px solid #bfdbfe;'>{header}</th>"
            for header in headers
        )

        status_rows = []

        for nb in step.neighbors[:12]:
            badge = nb.status

            color = (
                "#16a34a"
                if nb.status in {"ADD", "ADD/UPDATE", "ENQUEUE", "PUSH", "CHOSEN", "CANDIDATE", "MEET", "OK", "SELECTED"}
                else "#ca8a04"
                if nb.status in {"SKIP", "REJECT", "CUTOFF", "PRUNE", "TRY", "INFO"}
                else "#dc2626"
                if nb.status in {"FAIL", "BLOCKED"}
                else "#2563eb"
            )

            status_rows.append(
                f"<tr>"
                f"<td style='border:1px solid #e5e7eb;color:#111827;'>{nb.node}</td>"
                f"<td style='border:1px solid #e5e7eb;color:#111827;'>{nb.action}</td>"
                f"<td style='border:1px solid #e5e7eb;color:#111827;'>{nb.value}</td>"
                f"<td style='border:1px solid #e5e7eb;'><b style='color:{color}'>{badge}</b></td>"
                f"<td style='border:1px solid #e5e7eb;color:#111827;'>{nb.reason}</td>"
                f"</tr>"
            )

        more = f"<p><i>... còn {len(step.neighbors) - 12} dòng cập nhật</i></p>" if len(step.neighbors) > 12 else ""

        label1, value1, label2, value2 = trace_metric_labels(step, self.result.algorithm)

        extra_sections = ""
        if is_csp_trace(self.result.algorithm, step.mode):
            extra_sections = (
                self._html_block("Ô 1: BIỂU DIỄN CSP", csp_representation_from_note(step.note), "#2563eb")
                + self._html_block("Ô 2: ASSIGNMENT HIỆN TẠI", csp_assignment_from_step(step, self.result.algorithm), "#d97706")
            )
        elif is_game_trace(self.result.algorithm, step.mode):
            extra_sections = (
                self._html_block("MÔ TẢ MAX / MIN / CHANCE / UTILITY", game_representation_from_step(step, self.result.algorithm), "#2563eb")
                + self._html_block("HÀNH ĐỘNG ĐƯỢC CHỌN", game_selected_action_text(step), "#d97706")
            )

        focus_label = f"{source} dang dung tai"
        focus_pos = f"{follow_cell if follow_cell else step.current} {landmark_name_at(follow_cell) if follow_cell else landmark_name_at(step.current) or ''}"
        if is_csp_trace(self.result.algorithm, step.mode) and self.stage.idx == 6:
            focus_label = "Toa nha CSP dang xet"
            focus_pos = f"{step.current} {landmark_name_at(step.current) or ''}"

        html = f"""
        <div style='font-family: Segoe UI, Arial; color:#1f2937;'>
          <h3 style='margin:0;color:#2563eb;'>Bước {index + 1}/{len(self.result.trace)} - {self.result.algorithm}</h3>
          <p style='margin:4px 0 8px 0; color:#64748b;'>Node hiện tại: <b>{step.current} {landmark_name_at(step.current) or ''}</b> | Mode: {step.mode}</p>
          <p style='margin:0 0 8px 0;'>{label1}: <b>{value1}</b> &nbsp;&nbsp; {label2}: <b>{value2}</b></p>
          <p style='margin:0 0 10px 0;background:#ecfeff;border:1px solid #67e8f9;border-radius:8px;padding:7px;color:#155e75;'>
            <b>{source} đang đứng tại:</b> {follow_cell if follow_cell else step.current} {landmark_name_at(follow_cell) if follow_cell else landmark_name_at(step.current) or ''}.
            Trace này giải thích bước thuật toán liên quan đến vị trí đó.
          </p>
          {extra_sections}
          <h4 style='margin:4px 0 6px 0;color:#1e3a8a;'>{profile["detail"]}</h4>
          <table cellspacing='0' cellpadding='6' width='100%' style='border-collapse:collapse;color:#111827;background:#ffffff;'>
            <tr style='background:#dbeafe;color:#1e3a8a;'>{header_html}</tr>
            {''.join(status_rows)}
          </table>
          {more}
          <p style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:8px;'>{escape('' if is_csp_trace(self.result.algorithm, step.mode) else str(step.note)).replace(chr(10), '<br>')}</p>
        </div>
        """

        self.trace_preview.setHtml(html)
        self.trace_counter.setText(f"{index + 1}/{len(self.result.trace)}")

        if self.trace_dialog.isVisible():
            self.trace_dialog.show_step(index)

        if index >= len(self.result.trace) - 1:
            if self.current_result_reaches_goal():
                self.status_label.setText(self.result.status + " | Đã hiện đường đi cuối cùng trên bản đồ.")
            else:
                self.status_label.setText(self.result.status + " | Thuật toán dừng tại trạng thái hiện tại, không có path đến Goal.")

            self.search_timer.stop()

    def stage6_path_is_contiguous(self) -> bool:
        if not self.result or not self.result.path:
            return False
        if self.result.path[0] != self.stage.start or self.result.path[-1] != self.stage.goal:
            return False
        for a, b in zip(self.result.path, self.result.path[1:]):
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
                return False
        return True

    def result_path_is_contiguous(self) -> bool:
        if not self.result or not self.result.path:
            return False
        if self.result.path[0] != self.stage.start or self.result.path[-1] != self.stage.goal:
            return False
        for a, b in zip(self.result.path, self.result.path[1:]):
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
                return False
        return True

    def stage6_selected_visit_cells(self) -> List[GridPos]:
        if not self.result:
            return []
        for step in reversed(self.result.trace):
            cells: List[GridPos] = []
            for pos in step.reached:
                if pos in {self.stage.start, self.stage.goal}:
                    continue
                if self.result.path and pos not in self.result.path:
                    continue
                if pos not in cells:
                    cells.append(pos)
            if cells:
                return cells
        return []

    def start_stage6_step_animation(self, target_index: int) -> None:
        if not self.result or not self.result.trace:
            return
        target_index = max(0, min(target_index, len(self.result.trace) - 1))
        target = self.result.trace[target_index].current
        self.render_trace(target_index, move_character=False)

        start = self.stage6_agent_pos
        path = _shortest_segment(self.stage, start, target) or [start, target]
        self.stage6_step_path = path[1:] if len(path) > 1 else [target]
        self.stage6_step_index = 0
        self.stage6_step_target_index = target_index
        self.route_animation_kind = "stage6_step"
        self.search_timer.stop()
        self.route_timer.start(max(45, min(130, self.speed_ms // 6)))

    def start_stage6_exit_animation(self) -> None:
        target = self.stage.goal
        path = _shortest_segment(self.stage, self.stage6_agent_pos, target) or [self.stage6_agent_pos, target]
        self.stage6_step_path = path[1:] if len(path) > 1 else [target]
        self.stage6_step_index = 0
        self.stage6_step_target_index = self.trace_index
        self.route_animation_kind = "stage6_exit"
        self.search_timer.stop()
        self.route_timer.start(max(45, min(130, self.speed_ms // 6)))
        self.status_label.setText("CSP đã tô màu hợp lệ, nhân vật đang quay ra cổng.")

    def next_stage6_step_cell(self) -> None:
        if not self.stage6_step_path:
            self.route_timer.stop()
            self.route_animation_kind = ""
            return
        if self.stage6_step_index >= len(self.stage6_step_path):
            self.route_timer.stop()
            finished_kind = self.route_animation_kind
            self.route_animation_kind = ""
            if finished_kind == "stage6_exit":
                self.stage6_auto_running = False
                self.status_label.setText("Hoàn thành CSP: tất cả tòa được tô màu hợp lệ và nhân vật đã ra cổng.")
                return
            if self.result and self.stage6_step_target_index >= len(self.result.trace) - 1:
                self.start_stage6_exit_animation()
                return
            if self.stage6_auto_running:
                self.search_timer.start(self.speed_ms)
            return

        current = self.stage6_step_path[self.stage6_step_index]
        self.stage6_agent_pos = current
        self.map_view.set_character_cell(current)
        self.trace_counter.setText(f"Đi tới tòa: {self.stage6_step_index + 1}/{len(self.stage6_step_path)}")
        self.stage6_step_index += 1

    def start_stage6_route_animation(self) -> None:
        if not self.result or not self.result.path:
            self.status_label.setText("Chặng 6 chưa có route CSP để animate.")
            return
        if not self.stage6_path_is_contiguous():
            self.route_timer.stop()
            self.status_label.setText("Route CSP không liên tục từng ô, không thể animate.")
            return
        self.search_timer.stop()
        self.route_index = 0
        self.route_animation_kind = "stage6"
        self.route_timer.start(self.speed_ms)
        self.status_label.setText("Đang animate route CSP từng ô theo result.path...")

    def start_and_or_route_animation(self) -> None:
        if not self.result or not self.result.path:
            self.status_label.setText("AND-OR chưa có route để animate.")
            return
        if not self.result_path_is_contiguous():
            self.route_timer.stop()
            self.status_label.setText("Route AND-OR không liên tục từng ô, không thể animate.")
            return
        self.search_timer.stop()
        self.and_or_route_branches = self.and_or_route_branches_from_trace()
        self.and_or_route_branch_index = 0
        self.route_index = 0
        self.route_animation_kind = "and_or"
        self.route_timer.start(self.speed_ms)
        self.status_label.setText("Đang animate route AND-OR từng ô theo plan đã tìm được...")

    def next_stage6_route_cell(self) -> None:
        if self.route_animation_kind in {"stage6_step", "stage6_exit"}:
            self.next_stage6_step_cell()
            return
        if self.route_animation_kind == "and_or":
            self.next_and_or_route_cell()
            return
        if not self.result or not self.result.path:
            self.route_timer.stop()
            return
        if self.route_index >= len(self.result.path):
            self.route_timer.stop()
            self.route_animation_kind = ""
            self.status_label.setText("Hoan thanh route animation chang 6.")
            return

        current = self.result.path[self.route_index]
        color_cells = csp_color_assignments_from_note(self.result.trace[-1].note) if self.result.trace else None
        self.map_view.set_trace_overlay(
            current,
            [],
            [],
            [],
            [],
            None,
            True,
            True,
            [],
            [],
            [],
            False,
            "",
            None,
            color_cells,
        )
        self.map_view.set_character_cell(current)
        self.trace_counter.setText(f"Route {self.route_index + 1}/{len(self.result.path)}")
        self.route_index += 1

    def next_and_or_route_cell(self) -> None:
        if not self.result:
            self.route_timer.stop()
            self.route_animation_kind = ""
            return
        if not self.and_or_route_branches:
            self.and_or_route_branches = self.and_or_route_branches_from_trace()
            self.and_or_route_branch_index = 0
            self.route_index = 0
        if not self.and_or_route_branches:
            self.route_timer.stop()
            self.route_animation_kind = ""
            return

        if self.and_or_route_branch_index >= len(self.and_or_route_branches):
            self.route_timer.stop()
            self.route_animation_kind = ""
            self.status_label.setText("Hoan thanh route animation AND-OR.")
            return

        branch = self.and_or_route_branches[self.and_or_route_branch_index]
        if self.route_index >= len(branch):
            self.and_or_route_branch_index += 1
            self.route_index = 0
            if self.and_or_route_branch_index >= len(self.and_or_route_branches):
                self.route_timer.stop()
                self.route_animation_kind = ""
                self.status_label.setText("Hoan thanh AND-OR: tat ca result branches deu den GOAL.")
                return
            branch = self.and_or_route_branches[self.and_or_route_branch_index]

        current = branch[self.route_index]
        path_prefix = branch[: self.route_index + 1]
        result_states: List[GridPos] = []
        for candidate in self.and_or_route_branches:
            if len(candidate) > 1:
                result_states.append(candidate[1] if candidate[0] == self.stage.start else candidate[0])
        self.map_view.set_trace_overlay(
            current,
            result_states,
            [],
            [],
            path_prefix,
            None,
            True,
            False,
            [],
            [],
            None,
            True,
            self.and_or_root_action(),
            self.and_or_route_branches,
        )
        self.map_view.set_character_cell(current)
        self.trace_counter.setText(f"Route AND-OR R{self.and_or_route_branch_index + 1}: {self.route_index + 1}/{len(branch)}")
        self.route_index += 1
    def toggle_search_timer(self) -> None:
        self.ensure_result()

        if not self.result:
            return

        if self.stage.idx == 6 and is_csp_trace(self.result.algorithm):
            if self.search_timer.isActive() or self.route_timer.isActive():
                self.search_timer.stop()
                self.route_timer.stop()
                self.route_animation_kind = ""
                self.stage6_auto_running = False
                self.status_label.setText("Tạm dừng mô phỏng tô màu CSP.")
            else:
                self.stage6_auto_running = True
                self.next_trace_step()
            return

        if self.stage.idx == 4 and self.algorithm == "AND-OR Graph Search":
            if self.route_timer.isActive():
                self.route_timer.stop()
                self.route_animation_kind = ""
                self.status_label.setText("Tạm dừng route animation AND-OR.")
            else:
                self.start_and_or_route_animation()
            return

        if self.search_timer.isActive():
            self.search_timer.stop()
            self.status_label.setText("Tạm dừng mô phỏng tìm kiếm")
        else:
            self.search_timer.start(self.speed_ms)
            self.status_label.setText("Đang mô phỏng tìm kiếm từng bước...")

    def next_trace_step(self) -> None:
        if self.route_timer.isActive():
            self.route_timer.stop()
            self.route_animation_kind = ""
        self.ensure_result()

        if not self.result:
            return

        if self.stage.idx == 6 and is_csp_trace(self.result.algorithm):
            if self.trace_index < len(self.result.trace) - 1:
                self.start_stage6_step_animation(self.trace_index + 1)
            else:
                self.render_trace(self.trace_index, move_character=False)
                self.start_stage6_exit_animation()
            return

        if self.trace_index < len(self.result.trace) - 1:
            self.render_trace(self.trace_index + 1)
        else:
            self.render_trace(self.trace_index)
            self.search_timer.stop()

    def prev_trace_step(self) -> None:
        if self.route_timer.isActive():
            self.route_timer.stop()
            self.route_animation_kind = ""
        if self.result and self.result.trace:
            self.render_trace(self.trace_index - 1)

    def toggle_manual_mode(self) -> None:
        self.manual_mode = not self.manual_mode

        if self.manual_mode:
            self.search_timer.stop()
            self.manual_pos = self.stage.start
            self.manual_steps = 0
            self.manual_path = [self.manual_pos]
            if self.stage.idx == 5 and hasattr(self.map_view, "reset_stage5_opponents"):
                self.map_view.reset_stage5_opponents()
            self.map_view.set_manual_cell(self.manual_pos)
            if self.stage.idx == 5:
                self.map_view.set_trace_overlay(self.manual_pos, [], [], [], [], self.manual_path)
            self.status_label.setText("Manual Mode đang bật. Dùng W/A/S/D để di chuyển.")
            self.manual_info.setText(f"Đang bật. Vị trí: {self.manual_pos}. Số bước: {self.manual_steps}. Cost: 0.")
        else:
            if self.map_view.manual_group:
                self.map_view.scene_obj.removeItem(self.map_view.manual_group)
                self.map_view.manual_group = None

            self.status_label.setText("Đã tắt Manual Mode.")
            self.manual_info.setText("Tắt. Bấm P để bật tự chơi WASD.")

    def manual_move(self, dr: int, dc: int) -> None:
        if not self.manual_mode:
            return

        nxt = (self.manual_pos[0] + dr, self.manual_pos[1] + dc)

        if self.map_view.is_valid_manual_move(nxt):
            self.manual_pos = nxt
            self.manual_steps += 1
            self.manual_path.append(self.manual_pos)
            self.map_view.set_manual_cell(self.manual_pos)
            if self.stage.idx == 5:
                self.map_view.set_trace_overlay(self.manual_pos, [], [], [], [], self.manual_path)

            label = landmark_name_at(self.manual_pos) or ""
            manual_cost = path_cost(self.manual_path, self.stage, "normal")

            self.manual_info.setText(
                f"Đang bật. Vị trí: {self.manual_pos} {label}. "
                f"Số bước: {self.manual_steps}. Cost: {int(manual_cost)}."
            )

            self.sync_trace_to_cell(self.manual_pos, source="Người chơi WASD")

            if self.manual_pos == self.stage.goal:
                comparison = self.build_manual_ai_comparison(manual_cost)
                QMessageBox.information(self, "Hoàn thành", comparison)
                self.toggle_manual_mode()
        else:
            self.status_label.setText(f"Không thể đi vào ô {nxt}: {collision_reason(nxt, self.stage)}.")

    def build_manual_ai_comparison(self, manual_cost: float) -> str:
        lines = [
            "Bạn đã đến Goal!",
            "",
            "Người chơi WASD:",
            f"- Số bước: {self.manual_steps}",
            f"- Cost: {int(manual_cost)}",
        ]

        if self.result and self.result.path:
            ok, detail = validate_path_detail(self.result.path, self.stage)
            lines.extend(["", f"Thuật toán đang chọn: {self.result.algorithm}"])

            if ok:
                ai_steps = max(0, len(self.result.path) - 1)

                lines.extend([
                    f"- Số bước: {ai_steps}",
                    f"- Cost: {int(self.result.cost)}",
                    f"- Node đã xét: {self.result.expanded}",
                ])

                diff = self.manual_steps - ai_steps

                if diff > 0:
                    lines.append(f"Kết luận: thuật toán đi ít hơn người chơi {diff} bước.")
                elif diff < 0:
                    lines.append(f"Kết luận: người chơi đi ít hơn thuật toán {-diff} bước.")
                else:
                    lines.append("Kết luận: số bước của người chơi bằng thuật toán.")
            else:
                lines.append(f"- Thuật toán chưa có path hoàn chỉnh tới Goal: {detail}")
                lines.append("Kết luận: có thể dùng WASD để minh họa khi thuật toán dừng đúng bản chất.")
        else:
            lines.extend(["", "Chưa chạy thuật toán để so sánh. Bạn có thể chạy AI rồi chơi lại chặng này."])

        return "\n".join(lines)

    def open_trace_dialog(self) -> None:
        self.ensure_result()

        if not self.result:
            QMessageBox.warning(
                self,
                "Trace",
                "Chưa có kết quả thuật toán. Hãy chạy thuật toán trước."
            )
            return

        if not self.result.trace:
            QMessageBox.warning(
                self,
                "Trace",
                f"{self.result.algorithm} không có dữ liệu trace để hiển thị."
            )
            return

        self.trace_dialog.setWindowModality(Qt.NonModal)
        self.trace_dialog.set_result(self.result, self.trace_index)
        self.trace_dialog.show()
        self.trace_dialog.raise_()
        self.trace_dialog.activateWindow()
        self.trace_dialog.setFocus()

        self.status_label.setText(
            f"Đã mở trace chi tiết cho {self.result.algorithm} - bước {self.trace_index + 1}/{len(self.result.trace)}."
        )

    def fit_map(self) -> None:
        self.map_view.fitInView(self.map_view.sceneRect(), Qt.KeepAspectRatio)

    def on_map_cell_clicked(self, pos: GridPos) -> None:
        if self.goal_select_mode:
            self.set_custom_goal(pos)
            return

        label = landmark_name_at(pos) or ""
        reason = collision_reason(pos, self.stage)

        self.update_cell_info(pos)

        if self.result and self.result.trace:
            idx = self.find_nearest_trace_index(pos)
            self.render_trace(idx, follow_cell=pos, source="Ô được chọn", keep_final_path=True)
            self.status_label.setText(
                f"Ô được chọn: {pos} {label} | {reason} | Trace liên quan: bước {idx + 1}/{len(self.result.trace)}"
            )
        else:
            self.status_label.setText(
                f"Ô được chọn: {pos} {label} | {reason}. Chạy thuật toán để xem trace của ô này."
            )

    def update_cell_info(self, pos: GridPos) -> None:
        terrain = terrain_at(pos)
        terrain_label = TERRAIN_LABELS.get(terrain, terrain)
        landmark = landmark_name_at(pos)
        building = building_label_at(pos)
        walkable = is_walkable(pos, self.stage)
        reason = collision_reason(pos, self.stage)
        cost = movement_cost(pos, self.stage, "normal") if walkable else None

        trace_text = "Trace: chưa chạy thuật toán."

        if self.result and self.result.trace:
            idx = self.find_nearest_trace_index(pos)
            step = self.result.trace[idx]
            relation = "current" if step.current == pos else "frontier/reached/neighbor"
            trace_text = f"Trace: bước {idx + 1}/{len(self.result.trace)} ({relation})."

        roles = []

        if pos == self.stage.start:
            roles.append("START")
        if pos in self.stage.uncertain_starts:
            roles.append("START?")
        if pos in self.stage.uncertain_goals:
            roles.append("GOAL?")
        if pos == self.stage.goal:
            roles.append("GOAL")
        if pos in self.stage.high_cost:
            roles.append("cost cao")
        if pos in self.stage.risk:
            roles.append("rủi ro")
        if pos in self.stage.covered:
            roles.append("mái che")
        if pos in self.stage.blocked:
            roles.append("bị chặn")
        if pos in self.stage.opponent:
            roles.append("đối thủ")

        role_text = ", ".join(roles) if roles else "ô thường"

        lines = [
            f"Tọa độ: {pos}",
            f"Khu/tòa: {landmark or building or 'Không có nhãn'}",
            f"Vai trò: {role_text}",
            f"Terrain: {terrain_label}",
            f"Collision: {'Đi được' if walkable else 'Không đi được'} - {reason}",
            f"Cost: {int(cost)}" if cost is not None else "Cost: không áp dụng",
            trace_text,
        ]

        self.cell_info.setText("\n".join(lines))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()

        if key in (Qt.Key_1, Qt.Key_2, Qt.Key_3, Qt.Key_4, Qt.Key_5, Qt.Key_6):
            self.update_stage(int(event.text()))
        elif key == Qt.Key_Q:
            self.algo_buttons[0].setChecked(True)
            self.select_algorithm(0)
        elif key == Qt.Key_W and not self.manual_mode:
            self.algo_buttons[1].setChecked(True)
            self.select_algorithm(1)
        elif key == Qt.Key_E:
            self.algo_buttons[2].setChecked(True)
            self.select_algorithm(2)
        elif key == Qt.Key_Space:
            self.toggle_search_timer()
        elif key in (Qt.Key_N, Qt.Key_Right):
            self.next_trace_step()
        elif key == Qt.Key_Left:
            self.prev_trace_step()
        elif key == Qt.Key_P:
            self.toggle_manual_mode()
        elif key == Qt.Key_T:
            self.open_trace_dialog()
        elif key == Qt.Key_L:
            self.map_view.toggle_labels()
        elif key == Qt.Key_Y:
            self.toggle_goal_select_mode()
        elif key == Qt.Key_R:
            self.reset_goal_to_default()
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self.speed_ms = max(60, self.speed_ms - 40)
            self.status_label.setText(f"Tốc độ nhanh hơn: {self.speed_ms} ms/bước")
        elif key == Qt.Key_Minus:
            self.speed_ms = min(1000, self.speed_ms + 40)
            self.status_label.setText(f"Tốc độ chậm hơn: {self.speed_ms} ms/bước")
        elif self.manual_mode and key == Qt.Key_W:
            self.manual_move(-1, 0)
        elif self.manual_mode and key == Qt.Key_A:
            self.manual_move(0, -1)
        elif self.manual_mode and key == Qt.Key_S:
            self.manual_move(1, 0)
        elif self.manual_mode and key == Qt.Key_D:
            self.manual_move(0, 1)
        elif key == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
