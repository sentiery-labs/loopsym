"""ROS2 블록 [CLD-P44a] 테스트 — rclpy 없으면 skip.

외부 노드 없이 검증한다: 같은 다이어그램 안에서 Publish 블록이 토픽으로
내보낸 값을 Subscribe 블록이 DDS 를 한 바퀴 돌아 다시 받는 루프백.
(publish → 미들웨어 → subscribe 경로 전체가 실제로 동작해야 통과)
"""

import json
import os
import sys

import pytest

rclpy = pytest.importorskip("rclpy", reason="rclpy 없음 — ROS2 환경에서 실행")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blocksim import (            # noqa: E402
    Diagram, Gain, Ros2Publish, Ros2Subscribe, Scope, Sine,
    export_json, load_json, run_realtime,
)
from blocksim import ros2 as bs_ros2   # noqa: E402

DT = 0.02


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    bs_ros2.shutdown()


def loopback_diagram(topic="/bs_test_loop"):
    """Sine → Publish ~~DDS~~ Subscribe → Scope."""
    bd = Diagram()
    src = bd.add(Sine(amp=1.0, freq_hz=1.0, name="src"))
    pub = bd.add(Ros2Publish(topic, "geometry_msgs/msg/Vector3",
                             fields=["x"], name="pub"))
    sub = bd.add(Ros2Subscribe(topic, "geometry_msgs/msg/Vector3",
                               fields=["x"], st=DT, name="sub"))
    sc = bd.add(Scope(n_in=2, labels=["sent", "received"], name="scope"))
    bd.connect(src, pub)
    bd.connect(src, sc[0])
    bd.connect(sub, sc[1])
    return bd, sc


def test_pub_sub_loopback_realtime():
    bd, sc = loopback_diagram()
    stats = run_realtime(bd, t_end=1.5, dt=DT)
    assert stats["stopped"] is False
    received = sc.data[1]
    # DDS 발견(discovery)에 몇백 ms 걸릴 수 있다 — 후반부만 판정
    tail = received[len(received) // 2:]
    assert max(abs(v) for v in tail) > 0.5, \
        f"루프백 수신 없음 (tail max {max(map(abs, tail)):.3f})"
    # 수신값은 보낸 사인 파형의 (지연된) 값이어야 한다 — 범위 검사
    assert all(abs(v) <= 1.0 + 1e-9 for v in received)


def test_subscribe_defaults_before_first_message():
    """메시지가 없는 토픽 → defaults 가 그대로 나온다."""
    bd = Diagram()
    sub = bd.add(Ros2Subscribe("/bs_test_silent", "geometry_msgs/msg/Vector3",
                               fields=["x", "y"], st=DT, defaults=[7.0, -3.0]))
    sc = bd.add(Scope(n_in=2, name="sc"))
    bd.connect(sub[0], sc[0]); bd.connect(sub[1], sc[1])
    run_realtime(bd, t_end=0.2, dt=DT)
    assert sc.data[0][-1] == 7.0 and sc.data[1][-1] == -3.0


def test_ros2_blocks_json_roundtrip():
    """export_json → load_json 라운드트립 (뷰어 저장/열기 경로)."""
    bd, _ = loopback_diagram(topic="/bs_test_rt")
    j = json.loads(json.dumps(export_json(bd)))
    bd2 = load_json(j)
    types = sorted(type(b).__name__ for b in bd2.blocks)
    assert types == ["Ros2Publish", "Ros2Subscribe", "Scope", "Sine"]
    sub = [b for b in bd2.blocks if type(b).__name__ == "Ros2Subscribe"][0]
    assert sub.topic == "/bs_test_rt" and sub.fields == ["x"] and sub.st == DT


def test_publish_only_on_major_steps():
    """RK4 중간 평가에서 중복 발행되지 않는다 (Scope.record 훅 검증)."""
    bd = Diagram()
    src = bd.add(Sine(name="s"))
    pub = bd.add(Ros2Publish("/bs_test_count", "geometry_msgs/msg/Vector3",
                             fields=["x"], name="p"))
    bd.connect(src, pub)
    n_pub = 0
    orig = pub._pub.publish

    def counting(msg, _orig=orig):
        nonlocal n_pub
        n_pub += 1
        _orig(msg)

    pub._pub.publish = counting
    run_realtime(bd, t_end=0.2, dt=DT)          # 11 major steps
    assert n_pub == round(0.2 / DT) + 1, f"발행 횟수 {n_pub} ≠ major step 수"
