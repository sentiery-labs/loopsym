"""loopsym.world_protocol — 3D 월드 시뮬레이터 연동 통신 규약 v1.

loopsym(클라이언트) 과 3D 월드 시뮬레이터(서버, 예: SENTIERY) 가 TCP 한 연결로
lockstep 으로 주고받는 메시지의 틀. 소켓은 모른다 — 바이트를 만들고 읽기만 한다.
정본 문서: docs/world_link_protocol.md

메시지 하나 = [u32 LE 머리 길이][머리 JSON UTF-8][u32 LE 몸 길이][몸 바이트]
몸은 영상이 있을 때만 쓰고, 없으면 길이 0.

| type     | 방향 | 머리 키 |
|----------|------|---------|
| hello    | →    | proto, vehicle("quad"), rotors, link_st, camera(null 또는 {width, height, hfov_deg, format, every, mount}), rangefinder(null 또는 {max_m}) |
| hello_ok | ←    | proto, world, origin{lat, lon, alt_m}, camera(null 또는 {width, height, fx, fy, cx, cy}), app |
| reset    | →    | (없음) |
| reset_ok | ←    | (없음) |
| step     | →    | seq, t, q[w,x,y,z], p_ned, p_ned_prev, v_ned, omega_frd, motors, armed(= max(motors) > 0) |
| frame    | ←    | seq, t, range_m(null 가능), range_valid, ground_up_m, collided, collided_with(null 가능), camera(null 또는 {seq, width, height, format}) + 몸 = 영상 |
| bye      | ↔    | (없음) |
| error    | ↔    | message |
"""

import json
import struct

PROTO_VERSION = 1
DEFAULT_PORT = 9431
MAX_HEADER = 65536                 # 머리 JSON 최대 바이트
MAX_BODY = 6_220_800               # 몸 최대 바이트 = 1920 × 1080 × 3 (가장 큰 영상)

RESET = {"type": "reset"}
BYE = {"type": "bye"}

_U32 = struct.Struct("<I")


class ProtocolError(Exception):
    """메시지 틀이 규약과 맞지 않거나 연결이 중간에 끊겼다."""


def encode(header, body=b""):
    """머리(dict) + 몸(bytes) → 보낼 바이트 한 덩어리."""
    try:
        head = json.dumps(header, ensure_ascii=False, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except ValueError as e:     # NaN/Infinity 는 JSON 이 아니다
        raise ProtocolError(f"머리에는 유한한 숫자만 실을 수 있습니다: {e}") from None
    if len(head) > MAX_HEADER:
        raise ProtocolError(f"머리가 너무 큽니다: {len(head)} 바이트 (최대 {MAX_HEADER})")
    body = bytes(body)
    if len(body) > MAX_BODY:
        raise ProtocolError(f"몸이 너무 큽니다: {len(body)} 바이트 (최대 {MAX_BODY})")
    return _U32.pack(len(head)) + head + _U32.pack(len(body)) + body


def _read(recv_exact, n, what):
    data = recv_exact(n)
    if len(data) < n:
        raise ProtocolError(f"연결 끊김: {what} 를 {n} 바이트 중 {len(data)} 바이트만 받음")
    return data


def read_message(recv_exact):
    """메시지 하나를 읽어 (머리 dict, 몸 bytes) 를 돌려준다.

    recv_exact(n) 는 정확히 n 바이트를 주거나, 연결이 끝났으면 더 짧게 준다."""
    (n_head,) = _U32.unpack(_read(recv_exact, 4, "머리 길이"))
    if n_head > MAX_HEADER:
        raise ProtocolError(f"머리 길이 {n_head} 가 최대 {MAX_HEADER} 를 넘습니다")
    raw = _read(recv_exact, n_head, "머리")
    try:
        header = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise ProtocolError(f"머리가 UTF-8 JSON 이 아닙니다: {e}") from None
    if not isinstance(header, dict) or not isinstance(header.get("type"), str):
        raise ProtocolError("머리는 문자열 'type' 을 가진 JSON 객체여야 합니다")
    (n_body,) = _U32.unpack(_read(recv_exact, 4, "몸 길이"))
    if n_body > MAX_BODY:
        raise ProtocolError(f"몸 길이 {n_body} 가 최대 {MAX_BODY} 를 넘습니다")
    body = _read(recv_exact, n_body, "몸") if n_body else b""
    return header, body


def socket_reader(sock):
    """sock.recv 를 n 바이트가 찰 때까지 되풀이하는 recv_exact 를 돌려준다.

    상대가 연결을 닫으면 받은 데까지(짧게) 돌려준다. 시간 초과 예외는 그대로 올린다."""
    def recv_exact(n):
        buf = bytearray()
        while len(buf) < n:
            chunk = sock.recv(min(n - len(buf), 1 << 20))
            if not chunk:
                break
            buf += chunk
        return bytes(buf)
    return recv_exact


def hello(rotors, link_st, camera, rangefinder):
    """첫 인사. camera/rangefinder 는 센서 블록이 없으면 None."""
    return {"type": "hello", "proto": PROTO_VERSION, "vehicle": "quad",
            "rotors": int(rotors), "link_st": float(link_st),
            "camera": camera, "rangefinder": rangefinder}


def step(seq, t, q, p_ned, p_ned_prev, v_ned, omega_frd, motors):
    """샘플 하나의 기체 상태. armed = 모터 명령 중 하나라도 0 보다 큼."""
    motors = [float(m) for m in motors]
    return {"type": "step", "seq": int(seq), "t": float(t),
            "q": [float(v) for v in q],
            "p_ned": [float(v) for v in p_ned],
            "p_ned_prev": [float(v) for v in p_ned_prev],
            "v_ned": [float(v) for v in v_ned],
            "omega_frd": [float(v) for v in omega_frd],
            "motors": motors,
            "armed": bool(motors) and max(motors) > 0.0}
