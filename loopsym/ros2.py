"""loopsym.ros2 — ROS2 토픽 Subscribe/Publish 블록. [CLD-P44a]

다이어그램이 곧 ROS2 노드가 된다: run_realtime() 이 벽시계 루프를 돌고,
Ros2Subscribe 가 소스(토픽→스칼라), Ros2Publish 가 싱크(스칼라→토픽).
제어기 블록들은 그 사이에 평소처럼 그린다.

    sub(/turtle1/pose) ─▶ [제어기 블록들] ─▶ pub(/turtle1/cmd_vel)

원칙:
  - rclpy 는 블록을 실제로 만들 때만 임포트 — loopsym 코어의 무의존성
    유지 (rclpy 없는 환경/Pyodide 에서도 이 모듈의 임포트 자체는 안전).
  - physics never waits: 수신 콜백은 rclpy 스핀 스레드(별도)에서 돌고
    최신값 래치만 놓고 간다. 제어 루프는 래치를 읽을 뿐 절대 블로킹 없음.
  - 실시간 모드(run_realtime / 서버 "realtime")에서 쓰도록 설계.
    배치 sim 모드에서도 돌긴 하지만 벽시계보다 빨리 돌므로 의미가 없다.

프로세스당 rclpy 노드 1개("loopsym")를 공유한다. 끝나면 shutdown().
"""

import importlib
import threading

from .blocks import Scope
from .core import Block

_bridge = None
_lock = threading.Lock()


def _msg_class(type_str):
    """"geometry_msgs/msg/Twist" (또는 "geometry_msgs/Twist") → 메시지 클래스."""
    parts = type_str.split("/")
    return getattr(importlib.import_module(parts[0] + ".msg"), parts[-1])


def _get_field(msg, path):
    for p in path.split("."):
        msg = getattr(msg, p)
    return float(msg)


def _set_field(msg, path, value):
    *head, last = path.split(".")
    for p in head:
        msg = getattr(msg, p)
    setattr(msg, last, float(value))


class _Bridge:
    """공유 rclpy 노드 + 스핀 스레드 (프로세스당 1개)."""

    def __init__(self):
        try:
            import rclpy
            from rclpy.executors import SingleThreadedExecutor
        except ImportError as e:
            raise ImportError(
                "Ros2 블록은 rclpy 가 필요합니다 — 로컬 서버 모드/네이티브 파이썬에서 "
                "실행하세요 (Pyodide 브라우저 모드 불가). ROS2 환경을 source 했는지 확인."
            ) from e
        self.rclpy = rclpy
        if not rclpy.ok():
            rclpy.init()
        self.node = rclpy.create_node("loopsym")
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)
        self.thread = threading.Thread(target=self.executor.spin,
                                       daemon=True, name="loopsym-ros2-spin")
        self.thread.start()


def bridge():
    global _bridge
    with _lock:
        if _bridge is None:
            _bridge = _Bridge()
        return _bridge


def shutdown():
    """공유 노드/스핀 스레드 정리 (데모·테스트 종료 시 호출)."""
    global _bridge
    with _lock:
        if _bridge is None:
            return
        b, _bridge = _bridge, None
    b.executor.shutdown(timeout_sec=1.0)
    b.node.destroy_node()
    if b.rclpy.ok():
        b.rclpy.shutdown()
    b.thread.join(timeout=2.0)


class Ros2Subscribe(Block):
    """토픽의 필드들을 스칼라 출력으로 — ZOH 스냅샷 소스.

    이산 블록으로 만든 이유: 매 sample_time 마다 '마지막으로 도착한
    메시지'를 스냅샷해 다음 구간 동안 상수로 내보낸다. RK4 의 중간
    평가들이 전부 같은 값을 보게 되고(스텝 중간에 메시지가 와도 수치가
    안 흔들림), 한 샘플 지연은 실제 센서 지연과 같은 의미론이다.

        Ros2Subscribe("/turtle1/pose", "turtlesim/msg/Pose",
                      fields=["x", "y", "theta"], st=0.02)
    """

    n_in = 0
    feedthrough = False

    def __init__(self, topic, msg_type, fields, st=0.02, defaults=None, name=None):
        super().__init__(name)
        self.topic, self.msg_type = topic, msg_type
        self.fields = list(fields)
        self.st = self.sample_time = st
        self.n_out = self.dstate_size = len(self.fields)
        self.defaults = list(defaults) if defaults else [0.0] * len(self.fields)
        self._latch = tuple(self.defaults)      # 스핀 스레드가 갱신, 루프는 읽기만

        def cb(msg, _self=self):
            _self._latch = tuple(_get_field(msg, f) for f in _self.fields)

        self._sub = bridge().node.create_subscription(
            _msg_class(msg_type), topic, cb, 10)

    def dinitial(self):
        return tuple(self.defaults)

    def output(self, t, u, x):
        return x                                # 스냅샷(이산 상태)을 그대로

    def update(self, t, u, xd):
        return self._latch                      # 다음 구간용 스냅샷


class Ros2Publish(Scope):
    """입력 스칼라들을 토픽 필드에 실어 발행 — 싱크.

    Scope 를 상속하는 이유: Simulator 는 Scope(싱크)의 record() 를
    **major step 에서 한 번만** 불러 준다 — RK4 중간 평가(스텝당 4회)에서
    중복 발행되지 않는 유일한 훅이다. (Scope 의 기록 리스트는 안 쓴다.)

        Ros2Publish("/turtle1/cmd_vel", "geometry_msgs/msg/Twist",
                    fields=["linear.x", "angular.z"])
    """

    def __init__(self, topic, msg_type, fields, name=None):
        super().__init__(n_in=len(fields), labels=list(fields), name=name)
        self.topic, self.msg_type = topic, msg_type
        self.fields = list(fields)
        self._cls = _msg_class(msg_type)
        self._pub = bridge().node.create_publisher(self._cls, topic, 10)

    def record(self, t, u):
        msg = self._cls()
        for f, v in zip(self.fields, u):
            _set_field(msg, f, v)
        self._pub.publish(msg)
