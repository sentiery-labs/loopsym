"""ex9 화이트박스 ↔ 모놀리식 제어기 동등성 (Simulink 블록판↔함수판 검증의 재현).

화이트박스(기본 블록 조립 서브시스템)와 검증된 한 덩어리 블록이 같은
알고리즘임을 폐루프 궤적 일치로 보증한다. 한쪽만 고치면 여기서 깨진다.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))

from loopsym import Simulator  # noqa: E402

from ex7_drone_hover import build as build_mono  # noqa: E402
from ex9_px4_whitebox import build as build_wb, DT  # noqa: E402


def test_whitebox_matches_monolithic():
    bd_wb, sc_wb = build_wb()
    bd_m, sc_m = build_mono()
    Simulator(bd_wb).run(4.0, DT)
    Simulator(bd_m).run(4.0, DT)
    dmax = max(abs(a - b) for cha, chb in zip(sc_wb.data, sc_m.data)
               for a, b in zip(cha, chb))
    assert dmax < 1e-9, f"화이트박스 ↔ 모놀리식 궤적 불일치: {dmax:.2e} m"
