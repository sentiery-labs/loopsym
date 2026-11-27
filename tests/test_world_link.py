"""WorldLink — 3D 월드 lockstep 연동 블록 (가짜 월드 서버로 시험)."""

import socket

import pytest

from loopsym import Constant, Diagram, Scope, Simulator, run
from loopsym.world import WorldCollision, WorldLink, WorldLinkError, find_link
from tests.fake_world import FakeWorld

DT = 0.01
T_END = 0.2
STATE = (1, 0, 0, 0, 0, 0, 0, 0, 0, -10, 0, 0, 0)    # q | pqr | NED | vNED


def _diagram(port, **kw):
    """상수 상태 13개 + 모터 4개 → WorldLink → Scope(3)."""
    bd = Diagram()
    link = bd.add(WorldLink(port=port, st=0.04, **kw))
    for i, v in enumerate(STATE):
        bd.connect(bd.add(Constant(float(v))), link[i])
    for i in range(4):
        bd.connect(bd.add(Constant(0.5)), link[13 + i])
    sc = bd.add(Scope(3, labels=["link_ok", "collided", "ground_up"]))
    for i in range(3):
        bd.connect(link[i], sc[i])
    return bd, link, sc


def _types(w):
    return [m["type"] for m in w.received]


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_ports():
    link = WorldLink(n_motors=6)
    assert (link.n_in, link.n_out, link.dstate_size, link.feedthrough) == (19, 3, 1, False)
    assert link.sample_time == 0.04 and link.port == 9431 and link.host == "127.0.0.1"


def test_handshake_and_reset_order():
    with FakeWorld() as w:
        bd, _, _ = _diagram(w.port)
        run(bd, T_END, DT)
        assert w.wait_for("bye")
    assert _types(w) == ["hello", "reset"] + ["step"] * 6 + ["bye"]
    hello = w.received[0]
    assert hello["proto"] == 1 and hello["rotors"] == 4 and hello["link_st"] == 0.04
    assert hello["camera"] is None and hello["rangefinder"] is None


def test_seq_and_time_per_sample():
    with FakeWorld() as w:
        bd, _, _ = _diagram(w.port)
        run(bd, T_END, DT)
    assert [s["seq"] for s in w.steps] == [0, 1, 2, 3, 4, 5]
    assert [s["t"] for s in w.steps] == pytest.approx([k * 0.04 for k in range(6)])
    s0 = w.steps[0]
    assert s0["q"] == [1, 0, 0, 0] and s0["p_ned"] == [0, 0, -10]
    assert s0["motors"] == [0.5] * 4 and s0["armed"] is True


def test_first_step_prev_equals_current():
    with FakeWorld() as w:
        bd, _, _ = _diagram(w.port)
        run(bd, T_END, DT)
    assert w.steps[0]["p_ned_prev"] == w.steps[0]["p_ned"]
    assert w.steps[1]["p_ned_prev"] == w.steps[0]["p_ned"]


def test_outputs_lag_one_sample():
    with FakeWorld(respond=lambda s: ({"ground_up_m": 12.5}, b"")) as w:
        bd, _, sc = _diagram(w.port)
        run(bd, T_END, DT)
    for t, ok, up in zip(sc.t, sc.data[0], sc.data[2]):
        if t < 0.04 - 1e-9:
            assert (ok, up) == (0.0, 0.0), t
        else:
            assert (ok, up) == (1.0, 12.5), t


def test_frame_timeout_raises_with_seq():
    with FakeWorld(delay_s=0.5) as w:
        bd, _, _ = _diagram(w.port, frame_timeout=0.1)
        with pytest.raises(WorldLinkError, match="seq"):
            run(bd, T_END, DT)


def test_server_closes_mid_run_raises():
    with FakeWorld(close_after_steps=2) as w:
        bd, _, _ = _diagram(w.port)
        with pytest.raises(WorldLinkError, match="seq"):
            run(bd, T_END, DT)
    assert len(w.steps) == 2


def test_proto_mismatch_raises():
    with FakeWorld(proto=2) as w:
        bd, _, _ = _diagram(w.port)
        with pytest.raises(WorldLinkError) as ei:
            run(bd, T_END, DT)
    msg = str(ei.value)
    assert "1" in msg and "2" in msg and "버전" in msg
    assert "step" not in _types(w)


def test_world_error_message_raises():
    with FakeWorld(hello_ok={"type": "error", "message": "월드 준비 안 됨"}) as w:
        bd, _, _ = _diagram(w.port)
        with pytest.raises(WorldLinkError, match="월드 준비 안 됨"):
            run(bd, T_END, DT)


def _hit_at_3(s):
    hit = s["seq"] >= 3
    return {"collided": hit, "collided_with": "광개토관" if hit else None}, b""


def test_collision_stops_run():
    with FakeWorld(respond=_hit_at_3) as w:
        bd, _, _ = _diagram(w.port)
        with pytest.raises(WorldCollision, match="광개토관") as ei:
            run(bd, T_END, DT)
    assert "t=0.12" in str(ei.value)
    assert isinstance(ei.value, WorldLinkError)


def test_bye_sent_after_collision():
    with FakeWorld(respond=_hit_at_3) as w:
        bd, _, _ = _diagram(w.port)
        with pytest.raises(WorldCollision):
            run(bd, T_END, DT)
        assert w.wait_for("bye")
    assert _types(w)[-1] == "bye"


def test_collision_without_stop_continues():
    with FakeWorld(respond=_hit_at_3) as w:
        bd, _, sc = _diagram(w.port, stop_on_collision=False)
        run(bd, T_END, DT)
    assert len(w.steps) == 6
    assert sc.data[1][-1] == 1.0


def test_bye_sent_after_normal_run():
    with FakeWorld() as w:
        bd, _, _ = _diagram(w.port)
        run(bd, T_END, DT)
        assert w.wait_for("bye")
    assert _types(w)[-1] == "bye"


def test_rerun_sends_reset_and_matches():
    with FakeWorld(respond=lambda s: ({"ground_up_m": float(s["seq"])}, b"")) as w:
        bd, _, sc = _diagram(w.port)
        sim = Simulator(bd)
        sim.run(T_END, DT)
        n1 = len(sc.t)
        first = [list(ch) for ch in sc.data]
        sim.run(T_END, DT)
        second = [ch[n1:] for ch in sc.data]
        assert w.wait_for("bye")
    assert first == second
    assert _types(w).count("reset") == 2
    assert [s["seq"] for s in w.steps] == [0, 1, 2, 3, 4, 5] * 2


def test_unity_not_running_message():
    bd, _, _ = _diagram(_free_port(), connect_timeout=1.0)
    with pytest.raises(WorldLinkError, match="Unity 를 먼저 켜고"):
        run(bd, T_END, DT)


def test_browser_guard(monkeypatch):
    bd, _, _ = _diagram(_free_port())
    monkeypatch.setattr("sys.platform", "emscripten")
    with pytest.raises(WorldLinkError, match="브라우저"):
        run(bd, T_END, DT)


def test_find_link_by_name_and_default():
    a = WorldLink(name="linkA")
    b = WorldLink(name="linkB")
    k = Constant(1.0)
    assert find_link([k, a], "") is a
    assert find_link([k, a, b], "linkB") is b
    with pytest.raises(ValueError, match="linkA"):
        find_link([a, b], "")
    with pytest.raises(ValueError, match="없"):
        find_link([k], "")
    with pytest.raises(ValueError, match="linkC"):
        find_link([a, b], "linkC")
