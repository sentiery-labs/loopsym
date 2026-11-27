"""3D 월드 연동 통신 규약 v1 (loopsym.world_protocol) — docs/world_link_protocol.md."""

import json
import struct

import pytest

from loopsym.world_protocol import (
    BYE, DEFAULT_PORT, MAX_BODY, MAX_HEADER, PROTO_VERSION, RESET, ProtocolError,
    encode, hello, read_message, step,
)


def _reader(raw):
    """바이트를 앞에서부터 잘라 주는 recv_exact 대역 (끝나면 짧게 준다)."""
    buf = bytearray(raw)

    def recv_exact(n):
        out = bytes(buf[:n])
        del buf[:n]
        return out
    return recv_exact


def test_constants():
    assert (PROTO_VERSION, DEFAULT_PORT, MAX_HEADER, MAX_BODY) == (1, 9431, 65536, 6_220_800)
    assert RESET == {"type": "reset"} and BYE == {"type": "bye"}


def test_roundtrip_header_and_body():
    raw = encode({"type": "frame", "seq": 3}, b"\x01\x02")
    assert read_message(_reader(raw)) == ({"type": "frame", "seq": 3}, b"\x01\x02")


def test_roundtrip_korean_text():
    raw = encode({"type": "frame", "collided_with": "광개토관"})
    assert read_message(_reader(raw))[0]["collided_with"] == "광개토관"


def test_length_prefix_is_little_endian():
    raw = encode({"type": "bye"})
    n = int.from_bytes(raw[:4], "little")
    assert json.loads(raw[4:4 + n]) == {"type": "bye"} and raw[4 + n:] == b"\x00\x00\x00\x00"


def test_oversize_header_rejected():
    raw = struct.pack("<I", MAX_HEADER + 1) + b"{}" + struct.pack("<I", 0)
    with pytest.raises(ProtocolError):
        read_message(_reader(raw))


def test_oversize_body_rejected():
    head = b'{"type":"frame"}'
    raw = struct.pack("<I", len(head)) + head + struct.pack("<I", MAX_BODY + 1)
    with pytest.raises(ProtocolError):
        read_message(_reader(raw))


def test_encode_rejects_oversize_body():
    with pytest.raises(ProtocolError):
        encode({"type": "frame"}, b"\x00" * (MAX_BODY + 1))


def test_truncated_stream_raises():
    raw = encode({"type": "frame", "seq": 1})[:7]      # 머리 중간에서 끊김
    with pytest.raises(ProtocolError, match="끊김"):
        read_message(_reader(raw))


def test_header_must_be_json_object():
    head = b"[1,2]"
    raw = struct.pack("<I", len(head)) + head + struct.pack("<I", 0)
    with pytest.raises(ProtocolError):
        read_message(_reader(raw))


def test_header_must_have_type():
    head = b'{"seq":1}'
    raw = struct.pack("<I", len(head)) + head + struct.pack("<I", 0)
    with pytest.raises(ProtocolError):
        read_message(_reader(raw))


def test_step_message_fields():
    m = step(7, 0.28, (1, 0, 0, 0), (1, 2, -3), (1, 2, -2.9), (0, 0, 0), (0, 0, 0), (0.5, 0.5, 0.5, 0.5))
    assert m == {"type": "step", "seq": 7, "t": 0.28, "q": [1, 0, 0, 0], "p_ned": [1, 2, -3],
                 "p_ned_prev": [1, 2, -2.9], "v_ned": [0, 0, 0], "omega_frd": [0, 0, 0],
                 "motors": [0.5, 0.5, 0.5, 0.5], "armed": True}


def test_step_not_armed_when_motors_zero():
    m = step(0, 0.0, (1, 0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0, 0))
    assert m["armed"] is False


def test_hello_message_fields():
    m = hello(4, 0.04, None, {"max_m": 100.0})
    assert m == {"type": "hello", "proto": 1, "vehicle": "quad", "rotors": 4, "link_st": 0.04,
                 "camera": None, "rangefinder": {"max_m": 100.0}}


# ---------------------------------------------------------------- 시험용 가짜 월드 서버
def test_fake_world_handshake():
    import socket
    from loopsym.world_protocol import socket_reader
    from tests.fake_world import FakeWorld
    with FakeWorld() as w:
        with socket.create_connection(("127.0.0.1", w.port), timeout=2.0) as s:
            s.sendall(encode(hello(4, 0.04, {"width": 64, "height": 48, "hfov_deg": 90.0,
                                              "format": "gray8", "every": 1, "mount": "body"}, None)))
            head, body = read_message(socket_reader(s))
            assert head["type"] == "hello_ok" and head["proto"] == 1 and body == b""
            assert head["camera"]["fx"] == pytest.approx(32.0)
            s.sendall(encode(RESET))
            assert read_message(socket_reader(s))[0]["type"] == "reset_ok"
            s.sendall(encode(step(0, 0.0, (1, 0, 0, 0), (0, 0, -10), (0, 0, -10),
                                  (0, 0, 0), (0, 0, 0), (0, 0, 0, 0))))
            frame, _ = read_message(socket_reader(s))
            assert frame["seq"] == 0 and frame["range_m"] == pytest.approx(10.0)
            s.sendall(encode(BYE))
        assert w.wait_for("bye")
    assert [m["type"] for m in w.received] == ["hello", "reset", "step", "bye"]
