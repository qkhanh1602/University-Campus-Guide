from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPen, QPainter
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItemGroup,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from map_data import (
    BUILDINGS,
    COLS,
    FIELD,
    GRASS,
    GRID,
    LANDMARKS,
    PARKING,
    PATH,
    PLAZA,
    ROAD,
    ROWS,
    STAGES,
    TILE,
    WATER,
    GridPos,
    Stage,
    in_bounds,
    is_walkable,
    collision_reason,
)
from algorithms.game_common import advance_opponents, fixed_opponent_starts, opponent_positions_for_route


def qcolor(hex_value: str, alpha: int = 255) -> QColor:
    color = QColor(hex_value)
    color.setAlpha(alpha)
    return color


TERRAIN = {
    GRASS: ("#74bf65", "#4d9a43"),
    ROAD: ("#9fa7ad", "#6e777f"),
    PATH: ("#d9c48f", "#a9874d"),
    PLAZA: ("#ecd79f", "#b99355"),
    FIELD: ("#45ad51", "#2f853d"),
    WATER: ("#4fc3df", "#117c9b"),
    PARKING: ("#aeb8c6", "#6f7c8d"),
}

BUILDING_STYLE = {
    "academic": ("#f37b2f", "#a6421a", "#ffd0aa"),
    "center": ("#ef6d99", "#9d3157", "#ffd1e0"),
    "workshop": ("#328ec7", "#1c587b", "#c9edff"),
    "service": ("#9d65ca", "#5c3482", "#ead7ff"),
}

BUILDING_BADGE = {
    "academic": ("HOC", "#fff7ed", "#9a3412"),
    "center": ("TT", "#fff1f2", "#9f1239"),
    "workshop": ("XUONG", "#eff6ff", "#075985"),
    "service": ("DV", "#faf5ff", "#6b21a8"),
}

# Extra scene margin for row/column labels like a chess board.
# The campus cells still keep their original (row, col) coordinates.
COORD_MARGIN = 30



ENVIRONMENT_ICON = {
    "rain": ("RAIN", "#bfdbfe", "#1d4ed8", "Mua: -10 diem"),
    "crowd": ("CROWD", "#fed7aa", "#9a3412", "Dam dong: -8 diem"),
    "mud": ("MUD", "#d6b089", "#7c2d12", "Bun/ngap: -15 diem"),
    "risk": ("RISK", "#fecaca", "#991b1b", "Rui ro: -20 diem"),
    "covered": ("COVER", "#bbf7d0", "#166534", "Mai che: an toan/giam rui ro"),
    "crowd_block": ("BLOCK", "#fecaca", "#7f1d1d", "Dam dong/chot chan: khong duoc di vao"),
    "blocked": ("BARRIER", "#fecaca", "#7f1d1d", "Vat can: khong duoc di vao"),
}

def stage_environment_kind(pos: GridPos, stage: Stage) -> str | None:
    """Return a simple visual environment type for map icons.

    The Stage model stores generic high_cost/risk/covered/opponent sets. For a
    clearer presentation, especially in Stage 5, the renderer maps them to
    intuitive icons: rain, mud/flood, crowd, risk and covered/safe.
    """
    if pos in stage.covered:
        return "covered"
    if pos in stage.opponent:
        return "crowd_block"
    if pos in stage.blocked:
        return "blocked"
    if pos in stage.high_cost:
        return "crowd"
    if pos in stage.risk:
        selector = (pos[0] * 7 + pos[1] * 11) % 3
        return "rain" if selector == 0 else "mud" if selector == 1 else "risk"
    return None

COMPACT_LABELS = {
    "Cổng chính Võ Văn Ngân": "Cổng chính",
    "Cổng phụ Võ Văn Ngân": "Cổng phụ",
    "Khối A.1-A.5": "Khối A",
    "Khối Thư viện": "Thư viện",
    "Hội trường lớn": "Hội trường",
    "Xưởng thực tập hàn": "Xưởng hàn",
    "Xưởng thực tập gỗ": "Xưởng gỗ",
    "Xưởng điện ô tô": "Xưởng ô tô",
    "Sân bóng đá ngoài trời": "Sân bóng",
    "Dịch vụ ô tô Toyota": "Toyota",
    "Khoa Công nghệ Thông tin": "Khoa CNTT",
}


def compact_label(text: str) -> str:
    return COMPACT_LABELS.get(text, text)


class CampusMapView(QGraphicsView):
    cell_clicked = Signal(tuple)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene_obj = QGraphicsScene(self)
        self.setScene(self.scene_obj)
        self.setRenderHint(QPainter.Antialiasing, False)
        self.setRenderHint(QPainter.TextAntialiasing, True)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setBackgroundBrush(QBrush(qcolor("#0f172a")))
        self.setFocusPolicy(Qt.StrongFocus)

        self.stage: Stage = STAGES[1]
        self.labels_visible = True
        self.zoom_level = 1.0
        self.base_items: List[object] = []
        self.label_items: List[object] = []
        self.effect_items: List[object] = []
        self.fog_items: List[object] = []
        self.overlay_items: List[object] = []
        self.collision_items: List[object] = []
        self.coordinate_highlight_items: List[object] = []
        self.collision_visible = False
        self.belief_fog_enabled = False
        self.hidden_belief_start: Optional[GridPos] = None
        self.show_uncertain_start_markers = False
        self.algorithm_name = ""
        self.fog_revealed_cells: set[GridPos] = set()
        self.character_group: Optional[QGraphicsItemGroup] = None
        self.belief_character_groups: List[QGraphicsItemGroup] = []
        self.manual_group: Optional[QGraphicsItemGroup] = None
        self._stage5_visible_opponents: List[GridPos] = []
        self.current_path: List[GridPos] = []

        self.draw_static_map()
        self.set_stage(self.stage)
        self.setSceneRect(-COORD_MARGIN, -COORD_MARGIN, COLS * TILE + COORD_MARGIN * 2, ROWS * TILE + COORD_MARGIN * 2)

    def cell_to_rect(self, pos: GridPos) -> QRectF:
        r, c = pos
        return QRectF(c * TILE, r * TILE, TILE, TILE)

    def cell_center(self, pos: GridPos) -> QPointF:
        rect = self.cell_to_rect(pos)
        return rect.center()

    def add_rect(self, pos: GridPos, color: QColor | str, z: float, pen: Optional[QPen] = None, inset: float = 0) -> QGraphicsRectItem:
        rect = self.cell_to_rect(pos).adjusted(inset, inset, -inset, -inset)
        item = QGraphicsRectItem(rect)
        item.setBrush(QBrush(qcolor(color) if isinstance(color, str) else color))
        item.setPen(pen or QPen(Qt.NoPen))
        item.setZValue(z)
        self.scene_obj.addItem(item)
        return item

    def add_label(self, text: str, pos: GridPos, z: float = 8.0, bg: str = "#fff5db", tooltip: Optional[str] = None) -> QGraphicsItemGroup:
        group = QGraphicsItemGroup()
        p = self.cell_center(pos)
        font = QFont("Segoe UI", 8)
        font.setBold(False)
        label = QGraphicsSimpleTextItem(compact_label(text))
        label.setFont(font)
        label.setBrush(QBrush(qcolor("#3a2a15")))
        br = label.boundingRect()
        w, h = br.width() + 10, br.height() + 6
        back = QGraphicsRectItem(QRectF(p.x() - w / 2, p.y() - TILE * 0.95, w, h))
        back.setBrush(QBrush(qcolor(bg, 230)))
        back.setPen(QPen(qcolor("#a88449"), 1))
        label.setPos(p.x() - br.width() / 2, p.y() - TILE * 0.95 + 3)
        group.addToGroup(back)
        group.addToGroup(label)
        group.setToolTip(tooltip or text)
        group.setZValue(z)
        self.scene_obj.addItem(group)
        return group

    def draw_static_map(self) -> None:
        self.scene_obj.clear()
        self.base_items.clear()
        self.label_items.clear()
        self.coordinate_highlight_items.clear()

        for r in range(ROWS):
            for c in range(COLS):
                terrain = GRID[r][c]
                base, border = TERRAIN.get(terrain, TERRAIN[GRASS])
                item = self.add_rect((r, c), base, 0, QPen(qcolor(border), 0.7), 0)
                self.base_items.append(item)

                if terrain == GRASS:
                    if (r * 7 + c * 11) % 13 == 0:
                        dot = QGraphicsEllipseItem(c * TILE + 9, r * TILE + 8, 4, 4)
                        dot.setBrush(QBrush(qcolor("#a7f38a", 150)))
                        dot.setPen(QPen(Qt.NoPen))
                        dot.setZValue(0.2)
                        self.scene_obj.addItem(dot)
                        self.base_items.append(dot)
                    if (r * 3 + c * 5) % 29 == 0:
                        flower = QGraphicsEllipseItem(c * TILE + 14, r * TILE + 14, 3, 3)
                        flower.setBrush(QBrush(qcolor("#fde68a", 180)))
                        flower.setPen(QPen(Qt.NoPen))
                        flower.setZValue(0.25)
                        self.scene_obj.addItem(flower)
                        self.base_items.append(flower)

                elif terrain in {ROAD, PATH, PLAZA}:
                    if (r + c) % 2 == 0:
                        pebble = QGraphicsRectItem(QRectF(c * TILE + 3, r * TILE + 3, 5, 2))
                        pebble.setBrush(QBrush(qcolor("#fff0ca", 95)))
                        pebble.setPen(QPen(Qt.NoPen))
                        pebble.setZValue(0.2)
                        self.scene_obj.addItem(pebble)
                        self.base_items.append(pebble)

                    if terrain == ROAD and c % 4 == 0:
                        seam = QGraphicsLineItem(c * TILE + 2, r * TILE + TILE - 2, c * TILE + TILE - 2, r * TILE + TILE - 2)
                        seam.setPen(QPen(qcolor("#6b6257", 60), 0.8))
                        seam.setZValue(0.21)
                        self.scene_obj.addItem(seam)
                        self.base_items.append(seam)

                elif terrain == WATER:
                    for off in (8, 15):
                        wave = QGraphicsLineItem(c * TILE + 4, r * TILE + off, c * TILE + 20, r * TILE + off)
                        wave.setPen(QPen(qcolor("#d8fbff", 150), 1.2))
                        wave.setZValue(0.4)
                        self.scene_obj.addItem(wave)
                        self.base_items.append(wave)

        for r in range(ROWS):
            for c in range(COLS):
                edge = r in (0, ROWS - 1) or c in (0, COLS - 1)
                if GRID[r][c] == GRASS and (edge or ((r * 5 + c * 3) % 41 == 0 and ((r < 8 and c < 12) or c > 40))):
                    self.draw_tree((r, c))

        self.draw_sports_field((24, 30), 7, 6)
        self.draw_water((29, 19), 3, 3)
        self.draw_parking((25, 37), 7, 7)
        self.draw_campus_decoration()

        for b in BUILDINGS:
            self.draw_building(b)

        important_labels = {
            "Sân bóng đá ngoài trời",
        }

        for _, (label, pos) in LANDMARKS.items():
            if label in important_labels:
                self.label_items.append(self.add_label(label, pos, 7.5, tooltip=label))

        self.draw_coordinate_axes()

    def draw_coordinate_axes(self) -> None:
        """Draw subtle X/Y coordinate labels around the map.

        The labels make it easier to compare trace states like (row, col) with
        the visual map, similar to reading a chess board.
        """
        # Light strips outside the map to keep labels readable.
        top_strip = QGraphicsRectItem(QRectF(0, -COORD_MARGIN, COLS * TILE, COORD_MARGIN))
        top_strip.setBrush(QBrush(qcolor("#f8fafc", 218)))
        top_strip.setPen(QPen(qcolor("#cbd5e1", 120), 0.7))
        top_strip.setZValue(6.4)
        self.scene_obj.addItem(top_strip)
        self.base_items.append(top_strip)

        left_strip = QGraphicsRectItem(QRectF(-COORD_MARGIN, 0, COORD_MARGIN, ROWS * TILE))
        left_strip.setBrush(QBrush(qcolor("#f8fafc", 218)))
        left_strip.setPen(QPen(qcolor("#cbd5e1", 120), 0.7))
        left_strip.setZValue(6.4)
        self.scene_obj.addItem(left_strip)
        self.base_items.append(left_strip)

        # Axis corner labels.
        corner = QGraphicsSimpleTextItem("Y/X")
        corner.setFont(QFont("Segoe UI", 7, QFont.Bold))
        corner.setBrush(QBrush(qcolor("#334155")))
        corner.setPos(-COORD_MARGIN + 4, -COORD_MARGIN + 8)
        corner.setZValue(7.2)
        self.scene_obj.addItem(corner)
        self.base_items.append(corner)

        font = QFont("Segoe UI", 6.6, QFont.Bold)
        # X axis = columns. Show every column, but emphasize multiples of 5.
        for c in range(COLS):
            label = QGraphicsSimpleTextItem(str(c))
            label.setFont(font)
            label.setBrush(QBrush(qcolor("#1e3a8a" if c % 5 == 0 else "#475569")))
            br = label.boundingRect()
            label.setPos(c * TILE + (TILE - br.width()) / 2, -COORD_MARGIN + 8)
            label.setZValue(7.0)
            self.scene_obj.addItem(label)
            self.base_items.append(label)

        # Y axis = rows. Show every row, but emphasize multiples of 5.
        for r in range(ROWS):
            label = QGraphicsSimpleTextItem(str(r))
            label.setFont(font)
            label.setBrush(QBrush(qcolor("#1e3a8a" if r % 5 == 0 else "#475569")))
            br = label.boundingRect()
            label.setPos(-COORD_MARGIN + (COORD_MARGIN - br.width()) / 2, r * TILE + (TILE - br.height()) / 2)
            label.setZValue(7.0)
            self.scene_obj.addItem(label)
            self.base_items.append(label)

        # Thin guide lines at multiples of 5 help orientation without clutter.
        guide_pen = QPen(qcolor("#1e3a8a", 75), 0.8, Qt.DashLine)
        for c in range(0, COLS + 1, 5):
            line = QGraphicsLineItem(c * TILE, 0, c * TILE, ROWS * TILE)
            line.setPen(guide_pen)
            line.setZValue(6.35)
            self.scene_obj.addItem(line)
            self.base_items.append(line)
        for r in range(0, ROWS + 1, 5):
            line = QGraphicsLineItem(0, r * TILE, COLS * TILE, r * TILE)
            line.setPen(guide_pen)
            line.setZValue(6.35)
            self.scene_obj.addItem(line)
            self.base_items.append(line)

    def draw_tree(self, pos: GridPos) -> None:
        r, c = pos
        x, y = c * TILE, r * TILE

        trunk = QGraphicsRectItem(QRectF(x + 10, y + 13, 4, 8))
        trunk.setBrush(QBrush(qcolor("#7c4a23")))
        trunk.setPen(QPen(Qt.NoPen))
        trunk.setZValue(1.1)

        leaf1 = QGraphicsEllipseItem(x + 4, y + 3, 16, 14)
        leaf1.setBrush(QBrush(qcolor("#2f9e44")))
        leaf1.setPen(QPen(Qt.NoPen))
        leaf1.setZValue(1.15)

        leaf2 = QGraphicsEllipseItem(x + 0, y + 8, 15, 13)
        leaf2.setBrush(QBrush(qcolor("#37b24d")))
        leaf2.setPen(QPen(Qt.NoPen))
        leaf2.setZValue(1.16)

        leaf3 = QGraphicsEllipseItem(x + 10, y + 8, 15, 13)
        leaf3.setBrush(QBrush(qcolor("#51cf66")))
        leaf3.setPen(QPen(Qt.NoPen))
        leaf3.setZValue(1.17)

        for it in (trunk, leaf1, leaf2, leaf3):
            self.scene_obj.addItem(it)
            self.base_items.append(it)

    def draw_building(self, b) -> None:
        fill, border, window = BUILDING_STYLE.get(b.kind, BUILDING_STYLE["academic"])
        x, y = b.col * TILE, b.row * TILE
        w, h = b.w * TILE, b.h * TILE

        shadow = QGraphicsRectItem(QRectF(x + 5, y + 6, w, h))
        shadow.setBrush(QBrush(qcolor("#000000", 52)))
        shadow.setPen(QPen(Qt.NoPen))
        shadow.setZValue(2.0)

        foundation = QGraphicsRectItem(QRectF(x - 1, y - 1, w + 2, h + 2))
        foundation.setBrush(QBrush(qcolor("#f8fafc", 110)))
        foundation.setPen(QPen(qcolor("#0f172a", 70), 1))
        foundation.setZValue(2.05)

        body = QGraphicsRectItem(QRectF(x + 3, y + 3, w - 6, h - 6))
        body.setBrush(QBrush(qcolor(fill)))
        body.setPen(QPen(qcolor(border), 2))
        body.setZValue(2.2)

        roof_color = "#ffad58" if b.kind == "academic" else "#b18be4" if b.kind == "service" else "#62b4e6" if b.kind == "workshop" else "#ff9fbd"

        roof = QGraphicsRectItem(QRectF(x + 5, y + 5, w - 10, max(10, h * 0.22)))
        roof.setBrush(QBrush(qcolor(roof_color)))
        roof.setPen(QPen(qcolor(border, 170), 1))
        roof.setZValue(2.4)

        highlight = QGraphicsLineItem(x + 8, y + 9, x + w - 8, y + 9)
        highlight.setPen(QPen(qcolor("#fff3cf", 150), 1.2))
        highlight.setZValue(2.7)

        self.scene_obj.addItem(shadow)
        self.scene_obj.addItem(foundation)
        self.scene_obj.addItem(body)
        self.scene_obj.addItem(roof)
        self.scene_obj.addItem(highlight)

        self.base_items += [shadow, foundation, body, roof, highlight]

        badge_text, badge_fill, badge_text_color = BUILDING_BADGE.get(b.kind, ("", "#ffffff", "#111827"))

        if badge_text:
            badge = QGraphicsRectItem(QRectF(x + 7, y + 7, min(42, max(20, len(badge_text) * 7)), 12))
            badge.setBrush(QBrush(qcolor(badge_fill, 235)))
            badge.setPen(QPen(qcolor(border, 150), 0.8))
            badge.setZValue(3.05)

            badge_label = QGraphicsSimpleTextItem(badge_text)
            badge_label.setFont(QFont("Segoe UI", 6, QFont.Bold))
            badge_label.setBrush(QBrush(qcolor(badge_text_color)))
            badge_label.setPos(x + 10, y + 6)
            badge_label.setZValue(3.1)

            self.scene_obj.addItem(badge)
            self.scene_obj.addItem(badge_label)

            self.base_items += [badge, badge_label]

        for rr in range(b.row, b.row + b.h):
            for cc in range(b.col, b.col + b.w):
                px, py = cc * TILE, rr * TILE

                if rr == b.row and cc % 2 == 0:
                    rib = QGraphicsLineItem(px + 4, y + 6, px + 4, y + max(9, h * 0.22))
                    rib.setPen(QPen(qcolor(border, 90), 0.8))
                    rib.setZValue(2.75)
                    self.scene_obj.addItem(rib)
                    self.base_items.append(rib)

                if (rr + cc) % 2 == 0 and rr != b.row:
                    win = QGraphicsRectItem(QRectF(px + 7, py + 8, 7, 5))
                    win.setBrush(QBrush(qcolor(window, 205)))
                    win.setPen(QPen(qcolor(border, 150), 0.5))
                    win.setZValue(2.8)
                    self.scene_obj.addItem(win)
                    self.base_items.append(win)

        door = QGraphicsRectItem(QRectF(x + w / 2 - 5, y + h - 12, 10, 10))
        door.setBrush(QBrush(qcolor("#6b3f1f")))
        door.setPen(QPen(qcolor("#3a2414"), 0.8))
        door.setZValue(2.9)

        self.scene_obj.addItem(door)
        self.base_items.append(door)

        label = self.add_label(b.label, (b.row, b.col + max(1, b.w // 2)), 7.0, "#fff1cb", b.label)
        self.label_items.append(label)

    def _building_by_key(self, key: str):
        for b in BUILDINGS:
            if b.key == key:
                return b
        return None

    def _draw_building_color_overlay(self, key: str, fill: str, border: str, z: float, alpha: int = 210, tooltip: str = "") -> None:
        b = self._building_by_key(key)
        if not b:
            return
        x, y = b.col * TILE, b.row * TILE
        w, h = b.w * TILE, b.h * TILE
        _base_fill, _base_border, window = BUILDING_STYLE.get(b.kind, BUILDING_STYLE["academic"])
        body = QGraphicsRectItem(QRectF(x + 3, y + 3, w - 6, h - 6))
        body.setBrush(QBrush(qcolor(fill, alpha)))
        body.setPen(QPen(qcolor(border, 230), 2.0))
        body.setZValue(z)
        body.setToolTip(tooltip or b.label)
        self.scene_obj.addItem(body)
        self.overlay_items.append(body)

        roof = QGraphicsRectItem(QRectF(x + 5, y + 5, w - 10, max(10, h * 0.22)))
        roof.setBrush(QBrush(qcolor(fill, min(245, alpha + 25))))
        roof.setPen(QPen(qcolor(border, 210), 1.1))
        roof.setZValue(z + 0.03)
        roof.setToolTip(tooltip or b.label)
        self.scene_obj.addItem(roof)
        self.overlay_items.append(roof)

        highlight = QGraphicsLineItem(x + 8, y + 9, x + w - 8, y + 9)
        highlight.setPen(QPen(qcolor("#fff3cf", 150), 1.2))
        highlight.setZValue(z + 0.08)
        highlight.setToolTip(tooltip or b.label)
        self.scene_obj.addItem(highlight)
        self.overlay_items.append(highlight)

        badge_text, badge_fill, badge_text_color = BUILDING_BADGE.get(b.kind, ("", "#ffffff", "#111827"))
        if badge_text:
            badge = QGraphicsRectItem(QRectF(x + 7, y + 7, min(42, max(20, len(badge_text) * 7)), 12))
            badge.setBrush(QBrush(qcolor(badge_fill, 235)))
            badge.setPen(QPen(qcolor(border, 150), 0.8))
            badge.setZValue(z + 0.18)
            badge.setToolTip(tooltip or b.label)

            badge_label = QGraphicsSimpleTextItem(badge_text)
            badge_label.setFont(QFont("Segoe UI", 6, QFont.Bold))
            badge_label.setBrush(QBrush(qcolor(badge_text_color)))
            badge_label.setPos(x + 10, y + 6)
            badge_label.setZValue(z + 0.2)
            badge_label.setToolTip(tooltip or b.label)

            self.scene_obj.addItem(badge)
            self.scene_obj.addItem(badge_label)
            self.overlay_items += [badge, badge_label]

        for rr in range(b.row, b.row + b.h):
            for cc in range(b.col, b.col + b.w):
                px, py = cc * TILE, rr * TILE

                if rr == b.row and cc % 2 == 0:
                    rib = QGraphicsLineItem(px + 4, y + 6, px + 4, y + max(9, h * 0.22))
                    rib.setPen(QPen(qcolor(border, 90), 0.8))
                    rib.setZValue(z + 0.12)
                    rib.setToolTip(tooltip or b.label)
                    self.scene_obj.addItem(rib)
                    self.overlay_items.append(rib)

                if (rr + cc) % 2 == 0 and rr != b.row:
                    win = QGraphicsRectItem(QRectF(px + 7, py + 8, 7, 5))
                    win.setBrush(QBrush(qcolor(window, 215)))
                    win.setPen(QPen(qcolor(border, 140), 0.5))
                    win.setZValue(z + 0.14)
                    win.setToolTip(tooltip or b.label)
                    self.scene_obj.addItem(win)
                    self.overlay_items.append(win)

        door = QGraphicsRectItem(QRectF(x + w / 2 - 5, y + h - 12, 10, 10))
        door.setBrush(QBrush(qcolor("#6b3f1f")))
        door.setPen(QPen(qcolor("#3a2414"), 0.8))
        door.setZValue(z + 0.16)
        door.setToolTip(tooltip or b.label)
        self.scene_obj.addItem(door)
        self.overlay_items.append(door)

    def _draw_stage6_graph_coloring_base(self) -> None:
        for b in BUILDINGS:
            x, y = b.col * TILE, b.row * TILE
            w, h = b.w * TILE, b.h * TILE
            body = QGraphicsRectItem(QRectF(x + 3, y + 3, w - 6, h - 6))
            body.setBrush(QBrush(qcolor("#f8fafc", 232)))
            body.setPen(QPen(qcolor("#94a3b8", 230), 1.5))
            body.setZValue(3.25)
            body.setToolTip("Chua to mau trong CSP graph coloring")
            self.scene_obj.addItem(body)
            self.effect_items.append(body)

            roof = QGraphicsRectItem(QRectF(x + 5, y + 5, w - 10, max(10, h * 0.22)))
            roof.setBrush(QBrush(qcolor("#ffffff", 240)))
            roof.setPen(QPen(qcolor("#cbd5e1", 210), 1.0))
            roof.setZValue(3.28)
            roof.setToolTip("Chua to mau trong CSP graph coloring")
            self.scene_obj.addItem(roof)
            self.effect_items.append(roof)

            highlight = QGraphicsLineItem(x + 8, y + 9, x + w - 8, y + 9)
            highlight.setPen(QPen(qcolor("#ffffff", 150), 1.1))
            highlight.setZValue(3.32)
            highlight.setToolTip("Chua to mau trong CSP graph coloring")
            self.scene_obj.addItem(highlight)
            self.effect_items.append(highlight)

            badge_text, badge_fill, badge_text_color = BUILDING_BADGE.get(b.kind, ("", "#ffffff", "#111827"))
            if badge_text:
                badge = QGraphicsRectItem(QRectF(x + 7, y + 7, min(42, max(20, len(badge_text) * 7)), 12))
                badge.setBrush(QBrush(qcolor("#ffffff", 230)))
                badge.setPen(QPen(qcolor("#94a3b8", 150), 0.8))
                badge.setZValue(3.42)

                badge_label = QGraphicsSimpleTextItem(badge_text)
                badge_label.setFont(QFont("Segoe UI", 6, QFont.Bold))
                badge_label.setBrush(QBrush(qcolor(badge_text_color, 180)))
                badge_label.setPos(x + 10, y + 6)
                badge_label.setZValue(3.44)

                self.scene_obj.addItem(badge)
                self.scene_obj.addItem(badge_label)
                self.effect_items += [badge, badge_label]

            for rr in range(b.row, b.row + b.h):
                for cc in range(b.col, b.col + b.w):
                    px, py = cc * TILE, rr * TILE
                    if rr == b.row and cc % 2 == 0:
                        rib = QGraphicsLineItem(px + 4, y + 6, px + 4, y + max(9, h * 0.22))
                        rib.setPen(QPen(qcolor("#94a3b8", 70), 0.8))
                        rib.setZValue(3.36)
                        self.scene_obj.addItem(rib)
                        self.effect_items.append(rib)
                    if (rr + cc) % 2 == 0 and rr != b.row:
                        win = QGraphicsRectItem(QRectF(px + 7, py + 8, 7, 5))
                        win.setBrush(QBrush(qcolor("#e2e8f0", 205)))
                        win.setPen(QPen(qcolor("#94a3b8", 120), 0.5))
                        win.setZValue(3.38)
                        self.scene_obj.addItem(win)
                        self.effect_items.append(win)

            door = QGraphicsRectItem(QRectF(x + w / 2 - 5, y + h - 12, 10, 10))
            door.setBrush(QBrush(qcolor("#6b3f1f", 210)))
            door.setPen(QPen(qcolor("#3a2414", 180), 0.8))
            door.setZValue(3.4)
            self.scene_obj.addItem(door)
            self.effect_items.append(door)

    def draw_sports_field(self, pos: GridPos, h: int, w: int) -> None:
        r, c = pos
        rect = QRectF(c * TILE, r * TILE, w * TILE, h * TILE)

        field = QGraphicsRectItem(rect.adjusted(5, 5, -5, -5))
        field.setBrush(QBrush(qcolor("#4fae54")))
        field.setPen(QPen(qcolor("#e7ffe3"), 2))
        field.setZValue(1.5)

        self.scene_obj.addItem(field)
        self.base_items.append(field)

        mid = QGraphicsLineItem(rect.center().x(), rect.top() + 8, rect.center().x(), rect.bottom() - 8)
        mid.setPen(QPen(qcolor("#e7ffe3", 160), 1.2))
        mid.setZValue(1.6)

        self.scene_obj.addItem(mid)
        self.base_items.append(mid)

    def draw_water(self, pos: GridPos, h: int, w: int) -> None:
        r, c = pos
        water = QGraphicsEllipseItem(c * TILE, r * TILE, w * TILE, h * TILE)
        water.setBrush(QBrush(qcolor("#58c7df")))
        water.setPen(QPen(qcolor("#1b7a9b"), 2))
        water.setZValue(1.4)
        self.scene_obj.addItem(water)
        self.base_items.append(water)

    def draw_parking(self, pos: GridPos, h: int, w: int) -> None:
        r, c = pos

        for rr in range(r, r + h, 2):
            for cc in range(c, c + w, 3):
                car = QGraphicsRectItem(QRectF(cc * TILE + 4, rr * TILE + 7, 17, 9))
                car.setBrush(QBrush(qcolor("#536dfe" if (rr + cc) % 2 else "#ff7043")))
                car.setPen(QPen(qcolor("#202a44"), 0.8))
                car.setZValue(1.8)
                self.scene_obj.addItem(car)
                self.base_items.append(car)

    def draw_campus_decoration(self) -> None:
        bench_cells = [(17, 22), (17, 24), (21, 19), (21, 27), (28, 33), (29, 34)]

        for r, c in bench_cells:
            if GRID[r][c] in {ROAD, PATH, PLAZA, FIELD, PARKING}:
                x, y = c * TILE, r * TILE

                seat = QGraphicsRectItem(QRectF(x + 4, y + 9, 16, 5))
                seat.setBrush(QBrush(qcolor("#7c4a23")))
                seat.setPen(QPen(qcolor("#3f2412"), 0.6))
                seat.setZValue(1.95)

                leg1 = QGraphicsRectItem(QRectF(x + 6, y + 14, 2, 5))
                leg2 = QGraphicsRectItem(QRectF(x + 16, y + 14, 2, 5))

                for leg in (leg1, leg2):
                    leg.setBrush(QBrush(qcolor("#4b2e18")))
                    leg.setPen(QPen(Qt.NoPen))
                    leg.setZValue(1.96)

                for it in (seat, leg1, leg2):
                    self.scene_obj.addItem(it)
                    self.base_items.append(it)

        for r, c in [(4, 18), (4, 31), (9, 10), (15, 10), (22, 10), (22, 31), (27, 39), (32, 23)]:
            if GRID[r][c] in {ROAD, PATH, PLAZA, PARKING}:
                x, y = c * TILE, r * TILE

                pole = QGraphicsLineItem(x + 12, y + 7, x + 12, y + 20)
                pole.setPen(QPen(qcolor("#475569"), 1.5))
                pole.setZValue(1.9)

                bulb = QGraphicsEllipseItem(x + 8, y + 3, 8, 8)
                bulb.setBrush(QBrush(qcolor("#fde68a", 210)))
                bulb.setPen(QPen(qcolor("#92400e"), 0.6))
                bulb.setZValue(1.91)

                for it in (pole, bulb):
                    self.scene_obj.addItem(it)
                    self.base_items.append(it)

    def clear_items(self, items: List[object]) -> None:
        while items:
            it = items.pop()

            try:
                self.scene_obj.removeItem(it)
            except RuntimeError:
                pass

    def set_coordinate_highlight(self, pos: Optional[GridPos], manual: bool = False) -> None:
        self.clear_items(self.coordinate_highlight_items)

        if pos is None or not in_bounds(pos):
            return

        r, c = pos
        fill = "#10b981" if manual else "#facc15"
        border = "#047857" if manual else "#b45309"
        text_color = "#ffffff" if manual else "#111827"
        tooltip = f"Nhan vat dang o X={c}, Y={r}"

        top_rect = QGraphicsRectItem(QRectF(c * TILE, -COORD_MARGIN, TILE, COORD_MARGIN))
        top_rect.setBrush(QBrush(qcolor(fill, 238)))
        top_rect.setPen(QPen(qcolor(border), 1.6))
        top_rect.setZValue(8.5)
        top_rect.setToolTip(tooltip)
        self.scene_obj.addItem(top_rect)

        left_rect = QGraphicsRectItem(QRectF(-COORD_MARGIN, r * TILE, COORD_MARGIN, TILE))
        left_rect.setBrush(QBrush(qcolor(fill, 238)))
        left_rect.setPen(QPen(qcolor(border), 1.6))
        left_rect.setZValue(8.5)
        left_rect.setToolTip(tooltip)
        self.scene_obj.addItem(left_rect)

        font = QFont("Segoe UI", 7, QFont.Bold)

        x_label = QGraphicsSimpleTextItem(str(c))
        x_label.setFont(font)
        x_label.setBrush(QBrush(qcolor(text_color)))
        x_br = x_label.boundingRect()
        x_label.setPos(c * TILE + (TILE - x_br.width()) / 2, -COORD_MARGIN + (COORD_MARGIN - x_br.height()) / 2 - 1)
        x_label.setZValue(8.8)
        x_label.setToolTip(tooltip)
        self.scene_obj.addItem(x_label)

        y_label = QGraphicsSimpleTextItem(str(r))
        y_label.setFont(font)
        y_label.setBrush(QBrush(qcolor(text_color)))
        y_br = y_label.boundingRect()
        y_label.setPos(-COORD_MARGIN + (COORD_MARGIN - y_br.width()) / 2, r * TILE + (TILE - y_br.height()) / 2 - 1)
        y_label.setZValue(8.8)
        y_label.setToolTip(tooltip)
        self.scene_obj.addItem(y_label)

        self.coordinate_highlight_items += [top_rect, left_rect, x_label, y_label]

    def set_algorithm_visual_mode(self, algorithm_name: str) -> None:
        """Configure stage-specific visuals without changing algorithm logic.

        Stage 4 has two different concepts:
        - AND-OR Graph Search: one real START and one GOAL; nondeterminism comes
          from action results, not from multiple starts.
        - Belief State algorithms: keep uncertain START? markers and enable
          fog-of-war that opens as the trace explores cells.
        """
        self.algorithm_name = algorithm_name or ""
        text = self.algorithm_name.lower()
        is_belief = "belief" in text

        self.show_uncertain_start_markers = bool(is_belief and self.stage.uncertain_starts)
        self.belief_fog_enabled = bool(is_belief and self.stage.uncertain_starts)
        self.hidden_belief_start = None
        self.fog_revealed_cells = set()

    def _expand_reveal_area(self, cells: Iterable[GridPos], radius: int = 1) -> set[GridPos]:
        revealed: set[GridPos] = set()
        for cell in cells:
            if not cell:
                continue
            r0, c0 = cell
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    if abs(dr) + abs(dc) <= radius + 1:
                        rr, cc = r0 + dr, c0 + dc
                        if 0 <= rr < ROWS and 0 <= cc < COLS:
                            revealed.add((rr, cc))
        return revealed

    def seed_belief_fog(self) -> None:
        base_cells = set(self.stage.uncertain_starts) | {self.stage.goal}
        if self.hidden_belief_start:
            base_cells.add(self.hidden_belief_start)
        self.fog_revealed_cells = self._expand_reveal_area(base_cells, radius=2)

    def reveal_belief_cells(self, cells: Iterable[GridPos], radius: int = 1) -> None:
        if not self.belief_fog_enabled:
            return
        before = len(self.fog_revealed_cells)
        self.fog_revealed_cells |= self._expand_reveal_area(cells, radius=radius)
        if len(self.fog_revealed_cells) != before:
            self.draw_belief_fog()

    def set_stage(self, stage: Stage) -> None:
        self.stage = stage
        self.current_path = []
        self._stage5_visible_opponents = []

        self.clear_items(self.effect_items)
        self.clear_items(self.fog_items)
        self.clear_items(self.overlay_items)
        self.clear_items(self.collision_items)
        self.clear_items(self.coordinate_highlight_items)

        if self.character_group:
            self.scene_obj.removeItem(self.character_group)
            self.character_group = None
        self.clear_belief_characters()

        if self.manual_group:
            self.scene_obj.removeItem(self.manual_group)
            self.manual_group = None

        self.draw_stage_effects()
        self.draw_start_goal(stage.start, stage.goal)

        if self.collision_visible:
            self.draw_collision_overlay()

    def reset_stage5_opponents(self) -> None:
        self._stage5_visible_opponents = []

        if self.belief_fog_enabled and self.stage.uncertain_starts:
            if not self.fog_revealed_cells:
                self.seed_belief_fog()
            self.draw_belief_fog()
            self.set_belief_character_cells(sorted(self.stage.uncertain_starts))
        else:
            self.clear_items(self.fog_items)
            self.set_character_cell(stage.start)

    def _add_environment_icon(self, pos: GridPos, kind: str, z: float = 3.55) -> None:
        _label, fill, border, tooltip = ENVIRONMENT_ICON.get(kind, ("", "#ffffff", "#334155", kind))
        item = self.add_rect(pos, qcolor(fill, 168), z, QPen(qcolor(border, 120), 1.15), 3)
        item.setToolTip(tooltip)
        self.effect_items.append(item)

        x, y = pos[1] * TILE, pos[0] * TILE

        def add(shape) -> None:
            shape.setZValue(z + 0.22)
            shape.setToolTip(tooltip)
            self.scene_obj.addItem(shape)
            self.effect_items.append(shape)

        def person(cx: float, cy: float, color: str) -> None:
            head = QGraphicsEllipseItem(cx - 2.3, cy - 7.5, 4.6, 4.6)
            head.setBrush(QBrush(qcolor(color)))
            head.setPen(QPen(qcolor("#4b1f12", 80), 0.4))
            add(head)

            body = QGraphicsRectItem(QRectF(cx - 3.0, cy - 2.8, 6.0, 7.0))
            body.setBrush(QBrush(qcolor(color, 230)))
            body.setPen(QPen(qcolor("#4b1f12", 70), 0.4))
            add(body)

        if kind == "rain":
            puddle = QGraphicsEllipseItem(x + 5, y + 13, 14, 6)
            puddle.setBrush(QBrush(qcolor("#60a5fa", 210)))
            puddle.setPen(QPen(qcolor("#1d4ed8", 180), 0.8))
            add(puddle)

            for dx in (7, 12, 17):
                drop = QGraphicsLineItem(x + dx, y + 5, x + dx - 2, y + 10)
                drop.setPen(QPen(qcolor("#1d4ed8", 210), 1.3))
                add(drop)

        elif kind == "mud":
            blob = QGraphicsEllipseItem(x + 5, y + 8, 14, 10)
            blob.setBrush(QBrush(qcolor("#8b5e34", 220)))
            blob.setPen(QPen(qcolor("#5c3518", 170), 0.8))
            add(blob)

            shine = QGraphicsEllipseItem(x + 8, y + 10, 5, 2.5)
            shine.setBrush(QBrush(qcolor("#c7a47a", 170)))
            shine.setPen(QPen(Qt.NoPen))
            add(shine)

        elif kind == "crowd":
            person(x + 8, y + 15, "#b45309")
            person(x + 12, y + 13, "#92400e")
            person(x + 16, y + 15, "#f97316")

        elif kind == "covered":
            roof = QGraphicsRectItem(QRectF(x + 4, y + 6, 16, 5))
            roof.setBrush(QBrush(qcolor("#16a34a", 220)))
            roof.setPen(QPen(qcolor("#14532d", 160), 0.8))
            add(roof)

            for px in (7, 17):
                post = QGraphicsLineItem(x + px, y + 11, x + px, y + 19)
                post.setPen(QPen(qcolor("#166534", 190), 1.4))
                add(post)

        elif kind in {"blocked", "crowd_block"}:
            if kind == "crowd_block":
                person(x + 8, y + 14, "#991b1b")
                person(x + 16, y + 14, "#dc2626")

            board = QGraphicsRectItem(QRectF(x + 4, y + 12, 16, 5))
            board.setBrush(QBrush(qcolor("#f97316", 230)))
            board.setPen(QPen(qcolor("#7f1d1d", 160), 0.8))
            add(board)

            for dx in (5, 11, 17):
                stripe = QGraphicsLineItem(x + dx, y + 16.8, x + dx + 4, y + 12.2)
                stripe.setPen(QPen(qcolor("#fff7ed", 230), 1.1))
                add(stripe)

            for px in (6, 18):
                leg = QGraphicsLineItem(x + px, y + 17, x + px, y + 21)
                leg.setPen(QPen(qcolor("#7f1d1d", 180), 1.2))
                add(leg)

        elif kind == "risk":
            p1 = (x + 12, y + 4)
            p2 = (x + 5, y + 18)
            p3 = (x + 19, y + 18)
            for a, b in ((p1, p2), (p2, p3), (p3, p1)):
                line = QGraphicsLineItem(a[0], a[1], b[0], b[1])
                line.setPen(QPen(qcolor("#991b1b", 230), 1.5))
                add(line)

            bang = QGraphicsSimpleTextItem("!")
            bang.setFont(QFont("Segoe UI", 11, QFont.Bold))
            bang.setBrush(QBrush(qcolor("#991b1b")))
            br = bang.boundingRect()
            bang.setPos(x + (TILE - br.width()) / 2, y + 6)
            add(bang)

    def _add_stage6_risk_corner_icon(self, pos: GridPos) -> None:
        x, y = pos[1] * TILE, pos[0] * TILE
        points = ((x + 14.0, y + 3.4), (x + 21.2, y + 15.6), (x + 7.0, y + 15.6))
        for a, b in zip(points, points[1:] + points[:1]):
            line = QGraphicsLineItem(a[0], a[1], b[0], b[1])
            line.setPen(QPen(qcolor("#991b1b", 245), 1.25))
            line.setZValue(7.55)
            line.setToolTip("risk: vi pham avoid_risk")
            self.scene_obj.addItem(line)
            self.effect_items.append(line)

        bang = QGraphicsSimpleTextItem("!")
        bang.setFont(QFont("Segoe UI", 7.5, QFont.Bold))
        bang.setBrush(QBrush(qcolor("#991b1b")))
        br = bang.boundingRect()
        bang.setPos(x + 14.0 - br.width() / 2, y + 7.1)
        bang.setZValue(7.6)
        bang.setToolTip("risk: vi pham avoid_risk")
        self.scene_obj.addItem(bang)
        self.effect_items.append(bang)

    def _draw_stage6_constraint_markers(self) -> None:
        from algorithms.csp_common import _csp_domains

        domains = _csp_domains(self.stage)
        flags_by_pos: dict[GridPos, set[str]] = {}
        for values in domains.values():
            for value in values:
                if value.risk:
                    flags_by_pos.setdefault(value.pos, set()).add("risk")
                if value.crowded:
                    flags_by_pos.setdefault(value.pos, set()).add("crowd")

        for pos in sorted(self.stage.blocked):
            flags_by_pos.setdefault(pos, set()).add("blocked")

        for pos, flags in sorted(flags_by_pos.items()):
            if "blocked" in flags:
                self._add_environment_icon(pos, "blocked", z=3.75)
                continue
            has_crowd = "crowd" in flags
            has_risk = "risk" in flags
            if has_crowd:
                self._add_environment_icon(pos, "crowd", z=3.55)
            if has_risk and has_crowd:
                self._add_stage6_risk_corner_icon(pos)
            elif has_risk:
                self._add_environment_icon(pos, "risk", z=3.55)

    def draw_stage_effects(self) -> None:
        if self.stage.idx == 6:
            self._draw_stage6_graph_coloring_base()
            return

        # Draw every environment effect using intuitive icons instead of just
        # colored blocks. This keeps the scoring idea readable in Stage 5:
        # rain/crowd/mud/risk reduce score, covered path is safer.
        visual_cells = set(self.stage.covered) | set(self.stage.high_cost) | set(self.stage.risk) | set(self.stage.blocked) | set(self.stage.opponent)
        for p in sorted(visual_cells):
            kind = stage_environment_kind(p, self.stage)
            if kind is None:
                continue
            z = 4.0 if kind in {"blocked", "crowd_block"} and p in (self.stage.blocked | self.stage.opponent) else 3.2
            self._add_environment_icon(p, kind, z=z)

        # Không vẽ bảng "Ký hiệu môi trường / điểm" trên map để giao diện gọn hơn.
        # Các ký hiệu môi trường sẽ được giải thích trong báo cáo.

    def set_belief_fog(self, enabled: bool, hidden_start: Optional[GridPos] = None) -> None:
        self.belief_fog_enabled = enabled
        self.show_uncertain_start_markers = enabled
        self.hidden_belief_start = hidden_start
        self.clear_items(self.fog_items)

        if enabled:
            self.seed_belief_fog()
            self.draw_belief_fog()
            self.set_belief_character_cells(sorted(self.stage.uncertain_starts))
        else:
            self.fog_revealed_cells = set()
            if self.character_group:
                self.scene_obj.removeItem(self.character_group)
                self.character_group = None
            self.clear_belief_characters()

            self.set_character_cell(self.stage.start)

    def draw_belief_fog(self) -> None:
        self.clear_items(self.fog_items)

        if not self.belief_fog_enabled:
            return

        revealed = set(self.fog_revealed_cells)
        # Keep START?/GOAL readable, but leave unreached campus areas under fog.
        revealed |= self._expand_reveal_area(set(self.stage.uncertain_starts) | {self.stage.goal}, radius=1)
        hidden: set[GridPos] = set()

        for r in range(ROWS):
            for c in range(COLS):
                if (r, c) in revealed:
                    continue
                hidden.add((r, c))
                rect = QGraphicsRectItem(QRectF(c * TILE, r * TILE, TILE, TILE))
                alpha = 92 + ((r * 17 + c * 29) % 42)
                rect.setBrush(QBrush(qcolor("#0f172a", alpha)))
                rect.setPen(QPen(Qt.NoPen))
                rect.setZValue(4.72)
                self.scene_obj.addItem(rect)
                self.fog_items.append(rect)

        for p in sorted(revealed):
            r, c = p
            if not any((r + dr, c + dc) in hidden for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                continue
            glow = QGraphicsEllipseItem(c * TILE - 10, r * TILE - 10, TILE + 20, TILE + 20)
            glow.setBrush(QBrush(qcolor("#bae6fd", 28)))
            glow.setPen(QPen(qcolor("#e0f2fe", 70), 1.0))
            glow.setZValue(4.76)
            glow.setToolTip("Ranh giới vùng đã quan sát trong Belief State")
            self.scene_obj.addItem(glow)
            self.fog_items.append(glow)

        for r in range(0, ROWS, 3):
            for c in range(0, COLS, 4):
                if (r, c) in revealed:
                    continue
                if (r * 13 + c * 17) % 4 == 0:
                    w = TILE * (2.5 + ((r + c) % 3) * 0.35)
                    h = TILE * (1.4 + ((r * 2 + c) % 3) * 0.22)
                    cloud = QGraphicsEllipseItem(c * TILE - 14, r * TILE - 9, w, h)
                    cloud.setBrush(QBrush(qcolor("#e0f2fe", 34)))
                    cloud.setPen(QPen(Qt.NoPen))
                    cloud.setZValue(4.74)
                    self.scene_obj.addItem(cloud)
                    self.fog_items.append(cloud)

                    mist = QGraphicsEllipseItem(c * TILE + 7, r * TILE + 3, w * 0.72, h * 0.82)
                    mist.setBrush(QBrush(qcolor("#ffffff", 20)))
                    mist.setPen(QPen(Qt.NoPen))
                    mist.setZValue(4.75)
                    self.scene_obj.addItem(mist)
                    self.fog_items.append(mist)

        title = QGraphicsSimpleTextItem("BELIEF STATE: bản đồ có sương mù")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setBrush(QBrush(qcolor("#e0f2fe", 240)))
        title.setPos(18, ROWS * TILE - 62)
        title.setZValue(9.8)

        self.scene_obj.addItem(title)
        self.fog_items.append(title)

        sub = QGraphicsSimpleTextItem("Giữ các START? không chắc chắn; trace đi tới đâu thì mở vùng bản đồ tới đó")
        sub.setFont(QFont("Segoe UI", 8))
        sub.setBrush(QBrush(qcolor("#bfdbfe", 235)))
        sub.setPos(19, ROWS * TILE - 38)
        sub.setZValue(9.8)

        self.scene_obj.addItem(sub)
        self.fog_items.append(sub)

        if self.hidden_belief_start:
            ring = self.add_rect(
                self.hidden_belief_start,
                qcolor("#ffffff", 70),
                8.9,
                QPen(qcolor("#38bdf8", 210), 2.0),
                1,
            )
            ring.setToolTip("True start đang bị ẩn trong sương mù. Agent không biết chắc vị trí này.")
            self.fog_items.append(ring)

    def draw_start_goal(self, start: GridPos, goal: GridPos) -> None:
        if self.show_uncertain_start_markers and self.stage.uncertain_starts:
            for pos in sorted(self.stage.uncertain_starts):
                rect = self.add_rect(pos, qcolor("#8b5cf6", 195), 6.2, QPen(qcolor("#ffffff"), 2), 3)
                self.effect_items.append(rect)

                label = self.add_label("START?", pos, 9.0, "#ede9fe", "Vị trí bắt đầu không chắc chắn")
                self.effect_items.append(label)

            rect = self.add_rect(goal, qcolor("#ec4899", 210), 6.2, QPen(qcolor("#ffffff"), 2), 3)
            self.effect_items.append(rect)

            label = self.add_label("GOAL", goal, 9.0, "#ffffff")
            self.effect_items.append(label)

            return

        for pos, text, color in [(start, "START", "#22c55e"), (goal, "GOAL", "#ec4899")]:
            rect = self.add_rect(pos, qcolor(color, 210), 6.2, QPen(qcolor("#ffffff"), 2), 3)
            self.effect_items.append(rect)

            label = self.add_label(text, pos, 9.0, "#ffffff")
            self.effect_items.append(label)

    def moving_opponent_cells(
        self,
        agent_pos: GridPos,
        route: Optional[Sequence[GridPos]] = None,
        limit: int = 2,
    ) -> List[GridPos]:
        if self.stage.idx != 5:
            self._stage5_visible_opponents = []
            return []

        route_list = list(route or [])
        if route:
            if agent_pos in route_list:
                last_index = len(route_list) - 1 - list(reversed(route_list)).index(agent_pos)
                route_list = route_list[: last_index + 1]
            else:
                route_list = []
            desired = opponent_positions_for_route(route_list, self.stage, limit) if route_list else fixed_opponent_starts(self.stage, limit)
        else:
            desired = fixed_opponent_starts(self.stage, limit)

        if not route_list or len(route_list) <= 1:
            self._stage5_visible_opponents = list(desired)
            return list(desired)

        previous = self._stage5_visible_opponents
        if previous and len(previous) == len(desired):
            stepped = advance_opponents(agent_pos, self.stage, previous)
            self._stage5_visible_opponents = stepped if len(stepped) == len(desired) else list(desired)
        else:
            self._stage5_visible_opponents = list(desired)

        return list(self._stage5_visible_opponents)

    def add_moving_opponent_marker(self, pos: GridPos) -> None:
        x, y = pos[1] * TILE, pos[0] * TILE
        ring = self.add_rect(pos, qcolor("#ef4444", 95), 7.15, QPen(qcolor("#7f1d1d"), 2.0), 2)
        ring.setToolTip("Đối thủ đang di chuyển để chặn/áp sát agent")
        self.overlay_items.append(ring)

        shadow = QGraphicsEllipseItem(x + 6, y + 18, 12, 4)
        shadow.setBrush(QBrush(qcolor("#000000", 70)))
        shadow.setPen(QPen(Qt.NoPen))
        shadow.setZValue(21.0)
        shadow.setToolTip("Đối thủ đang di chuyển để chặn/áp sát agent")
        self.scene_obj.addItem(shadow)
        self.overlay_items.append(shadow)

        body = QGraphicsRectItem(QRectF(x + 8, y + 9, 8, 10))
        body.setBrush(QBrush(qcolor("#dc2626")))
        body.setPen(QPen(qcolor("#7f1d1d"), 1))
        body.setZValue(21.1)
        body.setToolTip("Đối thủ đang di chuyển để chặn/áp sát agent")
        self.scene_obj.addItem(body)
        self.overlay_items.append(body)

        head = QGraphicsEllipseItem(x + 8, y + 3, 8, 7)
        head.setBrush(QBrush(qcolor("#fecaca")))
        head.setPen(QPen(qcolor("#7f1d1d"), 1))
        head.setZValue(21.2)
        head.setToolTip("Đối thủ đang di chuyển để chặn/áp sát agent")
        self.scene_obj.addItem(head)
        self.overlay_items.append(head)

    def _add_overlay_label(self, text: str, pos: GridPos, z: float, bg: str, fg: str, tooltip: str = "") -> None:
        center = self.cell_center(pos)
        label = QGraphicsSimpleTextItem(text)
        label.setFont(QFont("Segoe UI", 7.0, QFont.Bold))
        label.setBrush(QBrush(qcolor(fg)))
        br = label.boundingRect()
        w = br.width() + 8
        h = br.height() + 4
        box = QGraphicsRectItem(QRectF(center.x() - w / 2, center.y() - TILE * 0.98, w, h))
        box.setBrush(QBrush(qcolor(bg, 238)))
        box.setPen(QPen(qcolor(fg, 150), 0.9))
        box.setZValue(z)
        box.setToolTip(tooltip or text)
        self.scene_obj.addItem(box)
        self.overlay_items.append(box)

        label.setPos(center.x() - br.width() / 2, center.y() - TILE * 0.98 + 2)
        label.setZValue(z + 0.05)
        label.setToolTip(tooltip or text)
        self.scene_obj.addItem(label)
        self.overlay_items.append(label)

    def _add_arrow_between_cells(self, start: GridPos, end: GridPos, color: str, z: float = 7.0, dashed: bool = False, offset_px: float = 0.0) -> None:
        a = self.cell_center(start)
        b = self.cell_center(end)
        dx = b.x() - a.x()
        dy = b.y() - a.y()
        length = max(1.0, (dx * dx + dy * dy) ** 0.5)
        ux, uy = dx / length, dy / length
        px, py = -uy, ux

        ax = a.x() + px * offset_px
        ay = a.y() + py * offset_px
        bx = b.x() + px * offset_px
        by = b.y() + py * offset_px

        line = QGraphicsLineItem(ax, ay, bx, by)
        pen = QPen(qcolor(color, 235), 4.2)
        if dashed:
            pen.setStyle(Qt.DashLine)
        line.setPen(pen)
        line.setZValue(z)
        self.scene_obj.addItem(line)
        self.overlay_items.append(line)

        tip = QPointF(bx - ux * 5, by - uy * 5)
        left = QPointF(tip.x() - ux * 8 + px * 4.5, tip.y() - uy * 8 + py * 4.5)
        right = QPointF(tip.x() - ux * 8 - px * 4.5, tip.y() - uy * 8 - py * 4.5)
        head1 = QGraphicsLineItem(tip.x(), tip.y(), left.x(), left.y())
        head2 = QGraphicsLineItem(tip.x(), tip.y(), right.x(), right.y())
        for head in (head1, head2):
            head.setPen(QPen(qcolor(color, 235), 4.2))
            head.setZValue(z + 0.02)
            self.scene_obj.addItem(head)
            self.overlay_items.append(head)

    def _draw_and_or_overlay(
        self,
        current: GridPos,
        result_states: Sequence[GridPos],
        reached: Sequence[GridPos],
        final_path: Optional[Sequence[GridPos]],
        action_label: str = "",
        branch_paths: Optional[Sequence[Sequence[GridPos]]] = None,
    ) -> None:
        branch_colors = ["#16a34a", "#7c3aed", "#0ea5e9", "#db2777"]
        for branch_index, path in enumerate(branch_paths or []):
            if len(path) < 2:
                continue
            color = branch_colors[branch_index % len(branch_colors)]
            sign = -1 if branch_index % 2 == 0 else 1
            offset_px = sign * (5.0 + 3.0 * (branch_index // 2))
            for a, b in zip(path, path[1:]):
                self._add_arrow_between_cells(a, b, color, z=6.25, dashed=branch_index > 0, offset_px=offset_px)

    def _draw_belief_paths(self, paths: Optional[Sequence[Sequence[GridPos]]]) -> None:
        colors = ["#2563eb", "#f97316", "#7c3aed", "#059669"]
        for index, path in enumerate(paths or []):
            if len(path) < 2:
                continue
            color = colors[index % len(colors)]
            sign = -1 if index % 2 == 0 else 1
            offset_px = sign * (4.5 + 3.0 * (index // 2))
            for a, b in zip(path, path[1:]):
                self._add_arrow_between_cells(a, b, color, z=6.18, dashed=False, offset_px=offset_px)
            for cell in path:
                marker = self.add_rect(cell, qcolor(color, 70), 6.12, QPen(qcolor(color, 180), 1.0), 7)
                marker.setToolTip(f"Duong belief START? {index + 1}")
                self.overlay_items.append(marker)

    def set_trace_overlay(
        self,
        current: Optional[GridPos],
        frontier: Sequence[GridPos],
        reached: Sequence[GridPos],
        neighbors_: Sequence[GridPos],
        final_path: Optional[Sequence[GridPos]] = None,
        opponent_route: Optional[Sequence[GridPos]] = None,
        move_character: bool = True,
        csp_mode: bool = False,
        removed_cells: Optional[Sequence[GridPos]] = None,
        failed_cells: Optional[Sequence[GridPos]] = None,
        checkpoint_cells: Optional[Sequence[GridPos]] = None,
        and_or_mode: bool = False,
        and_or_action: str = "",
        and_or_branch_paths: Optional[Sequence[Sequence[GridPos]]] = None,
        csp_color_cells: Optional[dict[GridPos, str]] = None,
        belief_paths: Optional[Sequence[Sequence[GridPos]]] = None,
    ) -> None:
        self.clear_items(self.overlay_items)

        if and_or_mode and current:
            self._draw_and_or_overlay(current, frontier, reached, final_path, and_or_action, and_or_branch_paths)
            if move_character and self.manual_group is None:
                self.set_character_cell(current)
            return

        if belief_paths:
            self._draw_belief_paths(belief_paths)

        if csp_mode and csp_color_cells:
            from algorithms.csp_common import csp_building_for_pos

            for pos, color_hex in csp_color_cells.items():
                key = csp_building_for_pos(pos)
                if key:
                    self._draw_building_color_overlay(key, color_hex, "#1f2937", 5.35, 218, "Mau da gan trong assignment CSP")

        if final_path:
            for a, b in zip(final_path, final_path[1:]):
                ca, cb = self.cell_center(a), self.cell_center(b)

                line = QGraphicsLineItem(ca.x(), ca.y(), cb.x(), cb.y())
                line.setPen(QPen(qcolor("#ef4444", 230), 5))
                line.setZValue(5.25)

                self.scene_obj.addItem(line)
                self.overlay_items.append(line)

            for p in final_path:
                item = self.add_rect(p, qcolor("#ef4444", 185), 5.3, QPen(qcolor("#b91c1c"), 1.5), 6)
                self.overlay_items.append(item)

        for p in reached[-250:]:
            if p != current:
                if csp_mode:
                    from algorithms.csp_common import csp_building_for_pos

                    key = csp_building_for_pos(p)
                    if key and not (csp_color_cells and p in csp_color_cells):
                        self._draw_building_color_overlay(key, "#dbeafe", "#2563eb", 5.42, 85, "Toa nha da gan mau")
                color = "#2563eb" if csp_mode else "#8b5cf6"
                pen = QPen(qcolor("#1d4ed8"), 1.4) if csp_mode else QPen(Qt.NoPen)
                item = self.add_rect(p, qcolor(color, 145 if csp_mode else 115), 5.5, pen, 5)
                self.overlay_items.append(item)

        for p in frontier[:250]:
            if csp_mode:
                from algorithms.csp_common import csp_building_for_pos

                key = csp_building_for_pos(p)
                if key and not (csp_color_cells and p in csp_color_cells):
                    self._draw_building_color_overlay(key, "#bbf7d0", "#16a34a", 5.45, 70, "Domain con hop le")
            color = "#bbf7d0" if csp_mode else "#facc15"
            border = "#16a34a" if csp_mode else "#b45309"
            item = self.add_rect(p, qcolor(color, 170), 5.8, QPen(qcolor(border), 1), 5)
            self.overlay_items.append(item)

        for p in (removed_cells or [])[:250]:
            if csp_mode:
                from algorithms.csp_common import csp_building_for_pos

                key = csp_building_for_pos(p)
                if key and csp_color_cells and p in csp_color_cells:
                    self._draw_building_color_overlay(key, csp_color_cells[p], "#4b5563", 5.48, 155, "Mau/domain bi loai sau khi thu")
                    item = self.add_rect(p, qcolor("#9ca3af", 95), 6.05, QPen(qcolor("#4b5563"), 1.6), 4)
                    self.overlay_items.append(item)
                    continue
                if key:
                    self._draw_building_color_overlay(key, "#9ca3af", "#4b5563", 5.48, 95, "Mau/domain bi loai")
            item = self.add_rect(p, qcolor("#9ca3af", 150), 6.05, QPen(qcolor("#4b5563"), 1.1), 5)
            self.overlay_items.append(item)

        for p in (failed_cells or [])[:250]:
            if csp_mode:
                from algorithms.csp_common import csp_building_for_pos

                key = csp_building_for_pos(p)
                if key and csp_color_cells and p in csp_color_cells:
                    self._draw_building_color_overlay(key, csp_color_cells[p], "#dc2626", 5.5, 185, "Thu mau nay nhung vi pham constraint")
                    item = self.add_rect(p, qcolor("#fecaca", 95), 6.1, QPen(qcolor("#dc2626"), 2.0), 3)
                    self.overlay_items.append(item)
                    continue
                if key:
                    self._draw_building_color_overlay(key, "#fecaca", "#dc2626", 5.5, 125, "Vi pham constraint")
            item = self.add_rect(p, qcolor("#fecaca", 175), 6.1, QPen(qcolor("#dc2626"), 1.3), 5)
            self.overlay_items.append(item)

        for p in neighbors_:
            if csp_mode:
                from algorithms.csp_common import csp_building_for_pos

                key = csp_building_for_pos(p)
                if key and csp_color_cells and p in csp_color_cells:
                    self._draw_building_color_overlay(key, csp_color_cells[p], "#ca8a04", 5.72, 225, "Dang thu mau nay cho toa nha")
                    item = self.add_rect(p, qcolor("#fde68a", 120), 6.0, QPen(qcolor("#ca8a04"), 1.8), 3)
                    self.overlay_items.append(item)
                    continue
                if key:
                    self._draw_building_color_overlay(key, "#fde68a", "#ca8a04", 5.55, 110, "Dang thu gan mau")
            color = "#fde68a" if csp_mode else "#38bdf8"
            border = "#ca8a04" if csp_mode else "#0369a1"
            item = self.add_rect(p, qcolor(color, 190 if csp_mode else 170), 6.0, QPen(qcolor(border), 1.3), 4)
            self.overlay_items.append(item)

        for index, p in enumerate(checkpoint_cells or [], 1):
            item = self.add_rect(p, qcolor("#22c55e", 220), 7.2, QPen(qcolor("#ffffff"), 2.0), 3)
            item.setToolTip(f"Da ghe checkpoint CSP X{index}: {p}")
            self.overlay_items.append(item)

            label = QGraphicsSimpleTextItem(f"X{index}")
            label.setFont(QFont("Segoe UI", 7.4, QFont.Bold))
            label.setBrush(QBrush(qcolor("#ffffff")))
            br = label.boundingRect()
            center = self.cell_center(p)
            label.setPos(center.x() - br.width() / 2, center.y() - br.height() / 2)
            label.setZValue(7.35)
            label.setToolTip(f"Da ghe checkpoint CSP X{index}: {p}")
            self.scene_obj.addItem(label)
            self.overlay_items.append(label)

        if current:
            if csp_mode:
                from algorithms.csp_common import csp_building_for_pos

                key = csp_building_for_pos(current)
                if key and csp_color_cells and current in csp_color_cells:
                    self._draw_building_color_overlay(key, csp_color_cells[current], "#92400e", 5.78, 232, "Toa nha dang xet / dang thu mau")
                elif key:
                    self._draw_building_color_overlay(key, "#fde68a", "#92400e", 5.65, 120, "Toa nha dang xet")
            current_color = "#facc15" if csp_mode else "#2563eb"
            current_border = "#92400e" if csp_mode else "#ffffff"
            item = self.add_rect(current, qcolor(current_color, 230), 6.5, QPen(qcolor(current_border), 2), 3)
            self.overlay_items.append(item)

            route_for_opponent = opponent_route if opponent_route is not None else final_path
            for enemy_pos in self.moving_opponent_cells(current, route_for_opponent):
                self.add_moving_opponent_marker(enemy_pos)

            if move_character and self.manual_group is None:
                self.set_character_cell(current)

        if self.belief_fog_enabled:
            reveal_cells = []
            if current:
                reveal_cells.append(current)
            reveal_cells.extend(list(reached[-50:]))
            reveal_cells.extend(list(frontier[:24]))
            reveal_cells.extend(list(neighbors_[:24]))
            if final_path:
                reveal_cells.extend(list(final_path))
            for path in belief_paths or []:
                reveal_cells.extend(list(path))
            self.reveal_belief_cells(reveal_cells, radius=2)

    def set_final_path(self, path: Sequence[GridPos]) -> None:
        self.current_path = list(path)
        self.set_trace_overlay(None, [], [], [], self.current_path)

        if self.belief_fog_enabled and path:
            self.reveal_belief_cells(path, radius=2)

        if path:
            if self.belief_fog_enabled and self.stage.uncertain_starts:
                self.set_belief_character_cells(sorted(self.stage.uncertain_starts))
            else:
                self.set_character_cell(path[0])

    def create_character(self, pos: GridPos, manual: bool = False) -> QGraphicsItemGroup:
        group = QGraphicsItemGroup()

        x, y = pos[1] * TILE, pos[0] * TILE

        shadow = QGraphicsEllipseItem(x + 5, y + 18, 14, 4)
        shadow.setBrush(QBrush(qcolor("#000000", 70)))
        shadow.setPen(QPen(Qt.NoPen))

        body = QGraphicsRectItem(QRectF(x + 8, y + 9, 9, 10))
        body.setBrush(QBrush(qcolor("#3b82f6" if not manual else "#10b981")))
        body.setPen(QPen(qcolor("#1e3a8a"), 1))

        head = QGraphicsRectItem(QRectF(x + 8, y + 3, 9, 7))
        head.setBrush(QBrush(qcolor("#ffd7a8")))
        head.setPen(QPen(qcolor("#9a5a26"), 1))

        hair = QGraphicsRectItem(QRectF(x + 8, y + 2, 9, 3))
        hair.setBrush(QBrush(qcolor("#2f2017")))
        hair.setPen(QPen(Qt.NoPen))

        bag = QGraphicsRectItem(QRectF(x + 5, y + 10, 4, 7))
        bag.setBrush(QBrush(qcolor("#f97316")))
        bag.setPen(QPen(Qt.NoPen))

        for it in (shadow, body, head, hair, bag):
            group.addToGroup(it)

        group.setZValue(20)

        self.scene_obj.addItem(group)

        return group

    def set_character_cell(self, pos: GridPos) -> None:
        self.clear_belief_characters()
        if self.character_group is None:
            self.character_group = self.create_character(pos, manual=False)
        else:
            self.character_group.setPos(
                pos[1] * TILE - self.character_group.boundingRect().left(),
                pos[0] * TILE - self.character_group.boundingRect().top(),
            )

        if self.character_group:
            self.scene_obj.removeItem(self.character_group)

        self.character_group = self.create_character(pos, manual=False)
        self.set_coordinate_highlight(pos)

    def clear_belief_characters(self) -> None:
        for group in self.belief_character_groups:
            self.scene_obj.removeItem(group)
        self.belief_character_groups = []

    def set_belief_character_cells(self, cells: Sequence[GridPos]) -> None:
        if self.character_group:
            self.scene_obj.removeItem(self.character_group)
            self.character_group = None
        self.clear_belief_characters()

        unique: List[GridPos] = []
        for cell in cells:
            if cell not in unique:
                unique.append(cell)

        for cell in unique:
            self.belief_character_groups.append(self.create_character(cell, manual=False))

        if unique:
            self.set_coordinate_highlight(unique[0])

    def set_manual_cell(self, pos: GridPos) -> None:
        if self.manual_group:
            self.scene_obj.removeItem(self.manual_group)

        self.manual_group = self.create_character(pos, manual=True)
        self.set_coordinate_highlight(pos, manual=True)

    def draw_collision_overlay(self) -> None:
        self.clear_items(self.collision_items)

        for r in range(ROWS):
            for c in range(COLS):
                p = (r, c)

                if not is_walkable(p, self.stage):
                    reason = collision_reason(p, self.stage)

                    if reason.startswith("Tòa nhà") or "Chướng" in reason or "Đối thủ" in reason:
                        color, alpha = "#dc2626", 82
                        pen = QPen(qcolor("#7f1d1d", 120), 0.7)
                    else:
                        color, alpha = "#0f172a", 34
                        pen = QPen(Qt.NoPen)

                    item = self.add_rect(p, qcolor(color, alpha), 4.85, pen, 2)
                    item.setToolTip(reason)

                    self.collision_items.append(item)

    def toggle_collision(self, visible: Optional[bool] = None) -> None:
        if visible is None:
            self.collision_visible = not self.collision_visible
        else:
            self.collision_visible = visible

        if self.collision_visible:
            self.draw_collision_overlay()
        else:
            self.clear_items(self.collision_items)

    def toggle_labels(self, visible: Optional[bool] = None) -> None:
        if visible is None:
            self.labels_visible = not self.labels_visible
        else:
            self.labels_visible = visible

        for item in self.label_items:
            item.setVisible(self.labels_visible)

    def zoom_in(self) -> None:
        self.scale(1.16, 1.16)
        self.zoom_level *= 1.16

    def zoom_out(self) -> None:
        self.scale(1 / 1.16, 1 / 1.16)
        self.zoom_level /= 1.16

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()

            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = self.mapToScene(event.pos())
            row = int(pos.y() // TILE)
            col = int(pos.x() // TILE)

            if in_bounds((row, col)):
                self.cell_clicked.emit((row, col))

        super().mousePressEvent(event)

    def is_valid_manual_move(self, pos: GridPos) -> bool:
        return is_walkable(pos, self.stage)
