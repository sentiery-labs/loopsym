"""시험용 가짜 3D 월드 서버 — docs/world_link_protocol.md 의 월드 쪽을 흉내낸다.

    with FakeWorld() as w:
        ... WorldLink(port=w.port) 로 실행 ...
    w.received   # 받은 머리 전부(순서대로), w.steps = 그중 step 만

- 접속 하나가 끝나면(bye·끊김) 다음 접속을 다시 받는다 → 같은 FakeWorld 로 여러 번 실행.
- respond(step_header) -> (dict, bytes): 돌려준 dict 는 기본 frame 위에 덮어쓴다
  (바꿀 키만 주면 된다). 기본 frame: range_m = -p_ned[2], range_valid True,
  ground_up_m 0, collided False, camera None, 몸 없음.
- hello_ok: 주면 그대로 보낸다. 안 주면 hello 의 camera 로 이상적 내부 값을 만든다.
- delay_s: frame 답 전에 잠. close_after_steps: n 번째 step 을 받으면 답 없이 닫음.
"""

import math
import socket
import threading
import time

from loopsym.world_protocol import ProtocolError, encode, read_message


class _Stopped(Exception):
    """시험이 끝나 서버를 멈춘다."""


class FakeWorld:
    def __init__(self, respond=None, hello_ok=None, delay_s=0.0, close_after_steps=None, proto=1):
        self.respond = respond
        self.hello_ok = hello_ok
        self.delay_s = delay_s
        self.close_after_steps = close_after_steps
        self.proto = proto
        self.received = []
        self.steps = []
        self.connections = 0
        self._cond = threading.Condition()
        self._stop = threading.Event()
        self._conn = None

    # ------------------------------------------------------------ 수명
    def __enter__(self):
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(1)
        self._srv.settimeout(0.1)
        self.port = self._srv.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        # 클라이언트가 이미 닫았으면 남은 메시지(bye 등)를 다 읽고 끝나도록 잠깐 기다린다
        self._stop.set()
        self._thread.join(timeout=2.0)
        self._srv.close()
        return False

    def wait_for(self, type_, timeout=2.0):
        """받은 머리 중 type_ 이 나올 때까지 기다린다. 나오면 True."""
        with self._cond:
            return self._cond.wait_for(
                lambda: any(m.get("type") == type_ for m in self.received), timeout)

    # ------------------------------------------------------------ 서버 스레드
    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._srv.accept()
            except (socket.timeout, OSError):
                continue
            self.connections += 1
            with conn:
                conn.settimeout(0.1)
                try:
                    self._handle(conn)
                except (ProtocolError, OSError):
                    pass

    def _recv(self, conn):
        """메시지 하나. 기다리다 stop 이 오면 None (클라이언트가 안 닫은 채 시험이 끝남)."""
        def recv_exact(n):
            buf = bytearray()
            while len(buf) < n:
                try:
                    chunk = conn.recv(n - len(buf))
                except socket.timeout:
                    if self._stop.is_set():
                        raise _Stopped from None
                    continue
                if not chunk:
                    break
                buf += chunk
            return bytes(buf)
        try:
            return read_message(recv_exact)
        except _Stopped:
            return None

    def _handle(self, conn):
        while True:
            msg = self._recv(conn)
            if msg is None:
                return
            head, _ = msg
            with self._cond:
                self.received.append(head)
                if head["type"] == "step":
                    self.steps.append(head)
                self._cond.notify_all()
            kind = head["type"]
            if kind == "hello":
                conn.sendall(encode(self._hello_ok(head)))
            elif kind == "reset":
                conn.sendall(encode({"type": "reset_ok"}))
            elif kind == "step":
                if self.close_after_steps is not None and len(self.steps) >= self.close_after_steps:
                    return
                if self.delay_s:
                    time.sleep(self.delay_s)
                frame, body = self._frame(head)
                conn.sendall(encode(frame, body))
            elif kind in ("bye", "error"):
                return

    def _hello_ok(self, hello):
        if self.hello_ok is not None:
            return self.hello_ok
        cam = hello.get("camera")
        intr = None
        if cam:
            w, h = cam["width"], cam["height"]
            f = w / (2.0 * math.tan(math.radians(cam["hfov_deg"]) / 2.0))
            intr = {"width": w, "height": h, "fx": f, "fy": f, "cx": w / 2.0, "cy": h / 2.0}
        return {"type": "hello_ok", "proto": self.proto, "world": "Fake",
                "origin": {"lat": 37.5508, "lon": 127.0742, "alt_m": 17.9},
                "camera": intr, "app": "fake"}

    def _frame(self, step):
        frame = {"type": "frame", "seq": step["seq"], "t": step["t"],
                 "range_m": -step["p_ned"][2], "range_valid": True, "ground_up_m": 0.0,
                 "collided": False, "collided_with": None, "camera": None}
        body = b""
        if self.respond is not None:
            head, body = self.respond(step)
            frame.update(head)
        return frame, body
