"""예제 6 — ROS2 turtlesim 데모 [CLD-P44a]: 다이어그램이 곧 ROS2 노드.

블록 다이어그램으로 만든 go-to-goal P 제어기가 turtlesim 거북이를
목표점 (9, 9) 로 몰고 간다. 폐루프 전체가 실제 ROS2 토픽을 왕복한다:

  Ros2Subscribe(/turtle1/pose: x,y,θ) ─▶ PyFunction(P 제어기) ─▶
  Ros2Publish(/turtle1/cmd_vel: linear.x, angular.z)

실행 (turtlesim 을 자동으로 띄운다):
  python examples/ex6_ros2_turtlesim.py            # 창 표시
  python examples/ex6_ros2_turtlesim.py --headless # CI/원격 (offscreen)

뷰어에서 라이브로: python -m loopsym.server 를 켜고 ex6_diagram.html 을
열어 "실시간" 체크 후 ▶ — 단, ROS2 블록은 rclpy 가 필요하므로 서버
모드에서만 실행된다 (Pyodide 는 에러 안내).
"""

import math
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loopsym import (
    Diagram, PyFunction, Ros2Publish, Ros2Subscribe, Scope,
    render_html, run_realtime,
)
from loopsym import ros2 as bs_ros2

GOAL = (9.0, 9.0)
DT = 0.02        # 50Hz — P40/P42 에서 검증한 주기


def build():
    bd = Diagram()
    sub = bd.add(Ros2Subscribe("/turtle1/pose", "turtlesim/msg/Pose",
                               fields=["x", "y", "theta"], st=DT,
                               defaults=[5.544, 5.544, 0.0], name="pose"))
    # go-to-goal P 제어기: v = Kv·거리 (상한), ω = Kw·헤딩오차 (wrap 포함)
    gx, gy = GOAL
    ctrl = bd.add(PyFunction(
        f"(min(2.0, 1.2*sqrt(({gx}-u0)**2 + ({gy}-u1)**2)), "
        f"4.0*atan2(sin(atan2({gy}-u1, {gx}-u0) - u2), "
        f"cos(atan2({gy}-u1, {gx}-u0) - u2)))",
        n_in=3, n_out=2, name="goto_ctrl"))
    pub = bd.add(Ros2Publish("/turtle1/cmd_vel", "geometry_msgs/msg/Twist",
                             fields=["linear.x", "angular.z"], name="cmd"))
    sc = bd.add(Scope(n_in=2, labels=["x", "y"], name="scope"))
    bd.connect(sub[0], ctrl[0]); bd.connect(sub[1], ctrl[1]); bd.connect(sub[2], ctrl[2])
    bd.connect(ctrl[0], pub[0]); bd.connect(ctrl[1], pub[1])
    bd.connect(sub[0], sc[0]); bd.connect(sub[1], sc[1])
    return bd, sub, sc


def main():
    headless = "--headless" in sys.argv
    env = dict(os.environ)
    if headless:
        env["QT_QPA_PLATFORM"] = "offscreen"

    bd, sub, sc = build()
    print("html :", render_html(
        bd, os.path.join(os.path.dirname(__file__), "ex6_diagram.html"),
        title="ex6 — ROS2 turtlesim go-to-goal (서버 모드 + 실시간 체크)"))

    print("turtlesim 기동…" + (" (offscreen)" if headless else ""))
    # start_new_session: `ros2 run` 래퍼만 terminate 하면 자식 turtlesim_node 가
    # 고아로 살아남는다 (잔존 노드가 다음 실행의 토픽을 오염 — 실측 사고).
    # 프로세스 그룹으로 묶어 종료 시 killpg 로 전부 정리한다.
    turtle = subprocess.Popen(["ros2", "run", "turtlesim", "turtlesim_node"],
                              env=env, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        # 첫 pose 수신 대기 (defaults 에서 실측 래치로 바뀔 때까지)
        for _ in range(100):
            if sub._latch != tuple(sub.defaults):
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("turtlesim pose 수신 실패 — ROS2 환경 확인")

        print(f"시작 pose ({sub._latch[0]:.2f}, {sub._latch[1]:.2f}) → 목표 {GOAL}, "
              f"실시간 12s @ {1/DT:.0f}Hz …")
        stats = run_realtime(bd, t_end=12.0, dt=DT)

        x, y, _ = sub._latch
        dist = math.hypot(GOAL[0] - x, GOAL[1] - y)
        print(f"최종 pose ({x:.2f}, {y:.2f}) — 목표까지 {dist:.3f} m | "
              f"지터 p99 {stats['p99']:.2f}ms, miss {stats['miss_pct']:.2f}%")
        ok = dist < 0.3
        print("판정:", "PASS ✅ (목표 도달)" if ok else f"FAIL ❌ (허용 0.3)")
        return 0 if ok else 1
    finally:
        import signal
        try:
            os.killpg(os.getpgid(turtle.pid), signal.SIGTERM)   # 래퍼+자식 전부
        except ProcessLookupError:
            pass
        turtle.wait(timeout=5)
        bs_ros2.shutdown()


if __name__ == "__main__":
    sys.exit(main())
