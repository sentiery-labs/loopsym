"""loopsym.joystick — 조이스틱/게임패드 입력 블록 (Interfaces 팔레트).

입력 경로: 뷰어(브라우저 Gamepad API) → WebSocket → 서버 → 블록.
브라우저가 장치 드라이버를 처리하므로 의존성 0, Windows/리눅스/맥 공통.
실시간 모드(P42)에서 라이브 조종이 되고, 입력이 없는 배치 실행에서는
중립 스틱 + idle_thrust 를 내보내 회귀/채점이 재현 가능하다.

스틱 매핑 = RC Mode 2 (표준 게임패드 배치):
  왼스틱 상하 = thrust [0..1] (위=1),  왼스틱 좌우 = yaw   [-1..1]
  오른스틱 좌우 = roll [-1..1],        오른스틱 상하 = pitch [-1..1] (위=+)
mode 출력 = 버튼 래치: mode_btns="0,1" 이면 버튼0→1, 버튼1→2 (누를 때 전환 유지).
출력은 '스틱 위치'다 — 각도/속도로의 스케일은 다이어그램의 Gain 이 담당.
"""

from .core import Block


class Joystick(Block):
    """게임패드 → roll/pitch/yaw [-1..1], thrust [0..1], mode (버튼 래치).

    출력: roll [0], pitch [1], yaw [2], thrust [3], mode [4]
    서버가 실행 시작 때 attach() 로 라이브 상태(dict)를 연결한다 —
    없으면(배치/Pyodide) 중립: (0,0,0, idle_thrust, 0).
    """

    n_in = 0
    n_out = 5
    dstate_size = 1          # mode 래치
    feedthrough = False

    def __init__(self, deadzone=0.05, idle_thrust=0.5, mode_btns="0,1",
                 st=0.004, name=None):
        super().__init__(name)
        self.deadzone = deadzone
        self.idle_thrust = idle_thrust
        self.mode_btns = mode_btns
        self._btns = [int(x) for x in str(mode_btns).split(",") if x.strip() != ""]
        self.st = self.sample_time = st
        self._live = None    # 서버가 주입: {"axes": [...], "buttons": [0/1,...]}

    def attach(self, state):
        """서버 실행 루프가 호출 — 라이브 입력 dict 연결 (스레드 안전: 참조 교체뿐)."""
        self._live = state

    def _axis(self, i):
        axes = (self._live or {}).get("axes") or ()
        v = float(axes[i]) if i < len(axes) else 0.0
        return 0.0 if abs(v) < self.deadzone else v

    def output(self, t, u, xd):
        if not (self._live or {}).get("axes"):
            return (0.0, 0.0, 0.0, self.idle_thrust, xd[0])   # 입력 없음 = 중립
        return (self._axis(2),            # roll  (오른스틱 좌우)
                -self._axis(3),           # pitch (오른스틱 상하, 위=+)
                self._axis(0),            # yaw   (왼스틱 좌우)
                min(max((1.0 - self._axis(1)) / 2.0, 0.0), 1.0),   # thrust
                xd[0])

    def update(self, t, u, xd):
        pressed = (self._live or {}).get("buttons") or ()
        mode = xd[0]
        for k, b in enumerate(self._btns):
            if b < len(pressed) and pressed[b]:
                mode = float(k + 1)       # 마지막으로 누른 버튼이 이긴다 (래치)
        return (mode,)
