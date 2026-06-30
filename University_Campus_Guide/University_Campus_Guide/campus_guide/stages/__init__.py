from __future__ import annotations

from typing import Dict

from map_data import Stage

from stages.stage1 import STAGE as STAGE_1
from stages.stage2 import STAGE as STAGE_2
from stages.stage3 import STAGE as STAGE_3
from stages.stage4 import STAGE as STAGE_4
from stages.stage5 import STAGE as STAGE_5
from stages.stage6 import STAGE as STAGE_6


STAGES: Dict[int, Stage] = {
    1: STAGE_1,
    2: STAGE_2,
    3: STAGE_3,
    4: STAGE_4,
    5: STAGE_5,
    6: STAGE_6,
}


__all__ = ["STAGES", "STAGE_1", "STAGE_2", "STAGE_3", "STAGE_4", "STAGE_5", "STAGE_6"]
