"""loopsym.navigation — 항법/유도 팔레트 (ARCHITECTURE §1 Navigation).

WaypointManager: 웨이포인트 순회 유도 (13주차 커리큘럼).
위치 setpoint 를 내는 가장 단순한 미션 계층 — 아래의 위치제어 캐스케이드가
실제 유도(위치오차→속도명령)를 수행한다. L1/NPFG 급은 후속 (MATLAB 라인 참조).
"""

import math

from .core import Block


def _parse_waypoints(spec):
    """"N,E,D; N,E,D; ..." 문자열 → [(N,E,D), ...].  리스트 입력도 허용."""
    if isinstance(spec, str):
        pts = []
        for chunk in spec.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            v = [float(x) for x in chunk.split(",")]
            if len(v) != 3:
                raise ValueError(f"웨이포인트는 'N,E,D' 3개씩: {chunk!r}")
            pts.append(tuple(v))
    else:
        pts = [tuple(float(x) for x in p) for p in spec]
    if not pts:
        raise ValueError("웨이포인트가 비어 있음")
    return pts


class WaypointManager(Block):
    """웨이포인트 순회: 현재 위치가 반경 안에 들어오면 다음 지점으로 전환.

    입력: pos N/E/D [0..2]
    출력: pos_sp N/E/D [0..2], wp_idx [3] (도달한 웨이포인트 수 — 전부 돌면
          len(waypoints), setpoint 는 마지막 지점 유지)
    파라미터 waypoints: "N,E,D; N,E,D; ..." (NED, 고도 5m = D −5)
    이산상태(1): 현재 인덱스.  radius: 도달 판정 반경 [m].
    """

    n_in = 3
    n_out = 4
    dstate_size = 1

    def __init__(self, waypoints="2,0,-6; 2,2,-6; 0,0,-5", radius=0.5,
                 st=0.004, name=None):
        super().__init__(name)
        self.waypoints = waypoints          # 원문 보존 (JSON 라운드트립)
        self._wps = _parse_waypoints(waypoints)
        self.radius = radius
        self.st = self.sample_time = st

    def output(self, t, u, xd):
        i = min(int(xd[0]), len(self._wps) - 1)
        wp = self._wps[i]
        return (wp[0], wp[1], wp[2], xd[0])

    def update(self, t, u, xd):
        i = int(xd[0])
        if i >= len(self._wps):
            return xd
        wp = self._wps[min(i, len(self._wps) - 1)]
        d = math.dist(u[0:3], wp)
        return (i + 1.0,) if d < self.radius else xd
