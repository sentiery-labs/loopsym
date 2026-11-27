"""loopsym.world — 3D 월드 시뮬레이터(SENTIERY) lockstep 연동.

ARCHITECTURE §2 의 fidelity Level 2 "world" 경로. loopsym 이 시간의 주인이고
유일한 적분 주체다. 월드는 받은 자세 그대로 기체를 그리고, 그 자리의 거리계·
카메라·충돌 값을 돌려준다.

    [QuadPlant] ─ 상태 13 ─┐
    [모터 명령] ─ N ───────┴▶ [WorldLink] ── step (TCP 9431) ──▶ 3D 월드
                              │  link_ok      ◀── frame ────────  (거리·영상·충돌)
                              │  collided
                              └  ground_up_m
    [Rangefinder(fidelity="world")], [Camera] 는 WorldLink 의 마지막 frame 을 읽는다.

- **센서 값은 한 샘플 늦다**: 샘플 k 의 update() 에서 step 을 보내고 frame 을 받으면
  센서 블록은 그 값을 샘플 k+1 에 내보낸다. 첫 샘플(t=0)은 "값 없음".
- 실행마다 reset 부터, seq 0 부터. 실행이 어떻게 끝나든 finish() 에서 bye.
- 통신 규약: docs/world_link_protocol.md (loopsym/world_protocol.py).
- 코어 의존성 0: socket 은 접속할 때 임포트한다. 브라우저(Pyodide)에서는
  임포트는 되고, 실행하면 안내 오류로 멈춘다.
"""

import sys

from .core import Block
from .world_protocol import (
    BYE, DEFAULT_PORT, PROTO_VERSION, RESET, ProtocolError, encode, hello, read_message,
    socket_reader, step,
)


class WorldLinkError(RuntimeError):
    """3D 월드와 주고받기가 안 됨(접속·시간 초과·규약·월드 쪽 오류)."""


class WorldCollision(WorldLinkError):
    """기체가 3D 월드의 무언가와 부딪혔다(stop_on_collision=True)."""


def find_link(blocks, name):
    """펼친 블록 목록에서 WorldLink 를 찾는다.

    name 이 비면 다이어그램의 유일한 WorldLink, 아니면 그 이름. 없거나 둘 이상이면 ValueError."""
    links = [b for b in blocks if isinstance(b, WorldLink)]
    names = [b.name for b in links]
    if name:
        found = [b for b in links if b.name == name]
        if len(found) == 1:
            return found[0]
        if not found:
            raise ValueError(f"WorldLink '{name}' 를 찾을 수 없습니다 — 다이어그램의 WorldLink: {names}")
        raise ValueError(f"이름이 '{name}' 인 WorldLink 가 {len(found)}개입니다 — 이름을 다르게 지으세요")
    if len(links) == 1:
        return links[0]
    if not links:
        raise ValueError("다이어그램에 WorldLink 가 없습니다 — fidelity='world' 센서는 WorldLink 블록이 필요합니다")
    raise ValueError(f"WorldLink 가 여럿입니다 {names} — 센서의 link= 에 이름을 적으세요")


class WorldLink(Block):
    """3D 월드 연동 (Interfaces). 샘플마다 기체 상태를 보내고 월드의 frame 을 받는다.

    입력(13 + n_motors): qw qx qy qz | p q r | pN pE pD | vN vE vD (QuadPlant 출력과 1:1)
                         + 모터 명령 m1..mN [0..1] (월드의 프로펠러 표시용)
    출력(3): link_ok(0/1) | collided(0/1, 마지막 frame) | ground_up_m(기체 아래 지면 높이)
             — 모두 한 샘플 늦다. 첫 샘플은 (0, 0, 0).

    파라미터:
      host, port         3D 월드 주소 (기본 127.0.0.1:9431)
      st                 연동 샘플 시간 (기본 0.04 = 25 Hz, dt 의 정수배)
      n_motors           로터 수 (기본 4)
      stop_on_collision  True 면 충돌 시 시각·부딪힌 것 이름을 넣은 WorldCollision 으로 멈춤
      connect_timeout    TCP 접속 제한 시간 [s]
      hello_timeout      첫 인사(hello_ok) 제한 시간 [s] — 월드가 장면을 띄우는 시간
      frame_timeout      reset_ok·frame 제한 시간 [s]

    거리계·카메라 설정은 각 센서 블록(Rangefinder, Camera)이 갖고, 시뮬레이터를
    만들 때 이 블록에 스스로 등록한다(resolve_links). hello 에 모아 보낸다.
    """

    n_out = 3
    dstate_size = 1             # 값은 안 쓰지만, 이산 블록으로 등록해 st 마다 update() 를 받는다
    feedthrough = False

    def __init__(self, host="127.0.0.1", port=DEFAULT_PORT, st=0.04, n_motors=4,
                 stop_on_collision=True, connect_timeout=5.0, hello_timeout=30.0,
                 frame_timeout=5.0, name=None):
        super().__init__(name)
        self.host = host
        self.port = int(port)
        self.st = self.sample_time = st
        self.n_motors = int(n_motors)
        if self.n_motors < 1:
            raise ValueError(f"{self.name}: n_motors 는 1 이상이어야 합니다: {n_motors}")
        self.n_in = 13 + self.n_motors
        self.stop_on_collision = bool(stop_on_collision)
        self.connect_timeout = connect_timeout
        self.hello_timeout = hello_timeout
        self.frame_timeout = frame_timeout
        self.camera = None          # Camera 블록이 resolve_links 에서 등록
        self.rangefinder = None     # Rangefinder(fidelity="world") 가 resolve_links 에서 등록
        self.hello_ok = None
        self.latest = None          # 마지막 frame 머리
        self.latest_body = b""      # 마지막 frame 몸(영상 바이트)
        self._sock = None
        self._recv = None
        self._seq = 0
        self._p_prev = None
        self._new_run = True

    # ---------------- 실행 시작 / 끝 ----------------
    def dinitial(self):
        self._seq = 0
        self._p_prev = None
        self.latest = None
        self.latest_body = b""
        self._new_run = True        # 다음 update() 에서 reset 부터
        return (0.0,)

    def finish(self):
        """실행이 끝나면(정상·예외·정지) bye 를 보내고 닫는다. 예외는 삼킨다."""
        sock, self._sock, self._recv = self._sock, None, None
        if sock is None:
            return
        try:
            sock.sendall(encode(BYE))
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    # ---------------- 매 샘플 ----------------
    def output(self, t, u, xd):
        f = self.latest
        if f is None:
            return (0.0, 0.0, 0.0)
        return (1.0, 1.0 if f.get("collided") else 0.0, float(f.get("ground_up_m") or 0.0))

    def update(self, t, u, xd):
        if self._sock is None:
            self._connect(t)
        if self._new_run:
            self._send(RESET, t)
            self._expect("reset_ok", self.frame_timeout, t)
            self._new_run = False
        p = tuple(u[7:10])
        prev = self._p_prev if self._p_prev is not None else p
        self._send(step(self._seq, t, u[0:4], p, prev, u[10:13], u[4:7], u[13:13 + self.n_motors]), t)
        head, body = self._expect("frame", self.frame_timeout, t)
        if head.get("seq") != self._seq:
            raise WorldLinkError(
                f"{self.name}: t={t:.3f}s seq 가 맞지 않습니다 — 보낸 seq {self._seq}, 받은 seq {head.get('seq')}")
        self._accept_frame(head, body, t)
        self._p_prev = p
        self._seq += 1
        if head.get("collided") and self.stop_on_collision:
            raise WorldCollision(f"t={t:.2f}s 충돌: {head.get('collided_with') or '(이름 없음)'}")
        return xd

    def _accept_frame(self, head, body, t):
        """받은 frame 을 마지막 값으로 저장한다."""
        self.latest = head
        self.latest_body = body

    # ---------------- 소켓 ----------------
    def _connect(self, t):
        if sys.platform == "emscripten":
            raise WorldLinkError(
                "WorldLink 는 브라우저(Pyodide) 안에서는 실행할 수 없습니다 — "
                "로컬 서버 모드(python -m loopsym.server)나 파이썬 스크립트에서 실행하세요.")
        import socket
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
        except OSError as e:
            raise WorldLinkError(
                f"SENTIERY 3D 월드에 접속할 수 없습니다 ({self.host}:{self.port}). "
                f"Unity 를 먼저 켜고 loopsym 연동 대기 상태로 두세요. ({e})") from None
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)   # 작은 메시지 lockstep — 지연 없이
        self._sock, self._recv = sock, socket_reader(sock)
        cam = self.camera.hello_settings() if self.camera is not None else None
        rf = {"max_m": float(self.rangefinder.max_range)} if self.rangefinder is not None else None
        self._send(hello(self.n_motors, self.st, cam, rf), t)
        head, _ = self._expect("hello_ok", self.hello_timeout, t)
        if head.get("proto") != PROTO_VERSION:
            msg = (f"통신 규약 버전이 다릅니다: loopsym {PROTO_VERSION}, "
                   f"3D 월드 {head.get('proto')} — 두 쪽을 같은 버전으로 맞추세요")
            try:
                sock.sendall(encode({"type": "error", "message": msg}))
            except OSError:
                pass
            self._close_quietly()
            raise WorldLinkError(f"{self.name}: {msg}")
        self.hello_ok = head

    def _close_quietly(self):
        sock, self._sock, self._recv = self._sock, None, None
        try:
            sock.close()
        except OSError:
            pass

    def _send(self, header, t):
        try:
            self._sock.sendall(encode(header))
        except OSError as e:
            raise WorldLinkError(
                f"{self.name}: t={t:.3f}s seq={self._seq} '{header['type']}' 를 보내지 못했습니다 — "
                f"3D 월드 연결이 끊겼습니다 ({e})") from None

    def _expect(self, kind, timeout, t):
        """메시지 하나를 받아 type 이 kind 인지 확인한다."""
        import socket
        self._sock.settimeout(timeout)
        where = f"{self.name}: t={t:.3f}s seq={self._seq}"
        try:
            head, body = read_message(self._recv)
        except socket.timeout:
            raise WorldLinkError(
                f"{where} 에서 3D 월드가 {timeout}s 동안 '{kind}' 를 보내지 않았습니다") from None
        except ProtocolError as e:
            raise WorldLinkError(f"{where} '{kind}' 를 받지 못했습니다 — {e}") from None
        except OSError as e:
            raise WorldLinkError(f"{where} 3D 월드 연결이 끊겼습니다 ({e})") from None
        if head["type"] == "error":
            raise WorldLinkError(f"{where} 3D 월드 오류: {head.get('message', '(이유 없음)')}")
        if head["type"] != kind:
            raise WorldLinkError(f"{where} '{kind}' 를 기다렸는데 '{head['type']}' 가 왔습니다")
        return head, body
