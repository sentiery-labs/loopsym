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


# ---------------------------------------------------------------- 내보내기 / 저장·불러오기 / 뷰어
def test_package_exports():
    import loopsym
    for n in ("WorldLink", "Camera", "Image", "Rangefinder", "WorldLinkError", "WorldCollision"):
        assert hasattr(loopsym, n), n


def test_json_roundtrip_world_blocks():
    from loopsym import QuadPlant, export_json, load_json
    from loopsym.sensors import Rangefinder
    from loopsym.world import Camera
    bd = Diagram()
    plant = bd.add(QuadPlant(ground=True, name="plant"))
    link = bd.add(WorldLink(port=9500, st=0.04, frame_timeout=2.5, name="link"))
    rf = bd.add(Rangefinder(fidelity="world", max_range=80.0, link="link", name="rf"))
    cam = bd.add(Camera(width=320, height=240, every=2, mount="level", save_dir="out",
                        save_every=5, link="link", name="cam"))
    for i in range(4):
        bd.connect(bd.add(Constant(0.5)), plant[i])
        bd.connect(bd.add(Constant(0.5)), link[13 + i])
    for i in range(13):
        bd.connect(plant[i], link[i])
        bd.connect(plant[i], rf[i])
        bd.connect(plant[i], cam[i])
    sc = bd.add(Scope(2))
    bd.connect(rf[0], sc[0])
    bd.connect(cam[0], sc[1])
    back = load_json(export_json(bd))
    by = {b.name: b for b in back.blocks}
    assert by["plant"].ground is True
    l2 = by["link"]
    assert isinstance(l2, WorldLink)
    assert (l2.port, l2.st, l2.frame_timeout, l2.n_motors) == (9500, 0.04, 2.5, 4)
    assert (by["rf"].fidelity, by["rf"].max_range, by["rf"].link) == ("world", 80.0, "link")
    c2 = by["cam"]
    assert (c2.width, c2.height, c2.every, c2.mount, c2.save_dir, c2.save_every, c2.link) == \
        (320, 240, 2, "level", "out", 5, "link")


def _viewer_def(src, cls):
    import re
    m = re.search(r"\n  " + cls + r": \{(.*?)\n  [A-Za-z0-9_]+: \{|\n  " + cls + r": \{(.*?)\n\};", src, re.S)
    assert m, f"viewer.html 에 {cls} 정의가 없음"
    return m.group(1) or m.group(2)


def test_viewer_defs_match_python_ports():
    import os
    from loopsym.viz import _PARAMS
    src = open(os.path.join(os.path.dirname(__file__), "..", "loopsym", "viewer.html"),
               encoding="utf-8").read()
    for cls, n_out in (("WorldLink", 3), ("Rangefinder", 2), ("Camera", 2)):
        d = _viewer_def(src, cls)
        assert f"nOut: () => {n_out}" in d, cls
        for p in _PARAMS[cls]:
            assert f"{p}:" in d.split("defaults:")[1].split("}")[0], f"{cls}.{p} 기본값 없음"
    assert "13 + Number(p.n_motors)" in _viewer_def(src, "WorldLink")
    assert "ground:" in _viewer_def(src, "QuadPlant")
    assert 'hasBlockType(model, "WorldLink")' in src


# ---------------------------------------------------------------- 예제 ex12
def test_example_ex12_runs_against_fake_world():
    import importlib.util
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "examples", "ex12_sentiery_world.py")
    spec = importlib.util.spec_from_file_location("ex12_sentiery_world", path)
    ex12 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ex12)
    with FakeWorld() as w:
        bd, sc_pos, sc_alt = ex12.build(port=w.port, camera=False)
        Simulator(bd).run(2.0, 0.004)
        assert w.wait_for("bye")
    assert len(w.steps) == 51
    assert w.received[0]["rangefinder"] == {"max_m": 100.0} and w.received[0]["camera"] is None
    assert sc_alt.data[0][-1] > 0.0                     # 이륙 중 (고도 증가)
    assert "광개토관" in ex12.__doc__


def test_example_ex12_summary_reports_collision(capsys):
    """충돌로 멈추면 (출력은 한 샘플 늦어 Scope 에 안 남아도) 요약에 충돌이 나와야 한다."""
    import importlib.util
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "examples", "ex12_sentiery_world.py")
    spec = importlib.util.spec_from_file_location("ex12_sentiery_world", path)
    ex12 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ex12)
    with FakeWorld(respond=_hit_at_3) as w:
        rc = ex12.main(["--port", str(w.port), "--t-end", "0.4", "--no-camera"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "광개토관" in out and "충돌 있음" in out


def test_diverged_state_raises_before_sending():
    """발산한 상태(NaN)는 JSON 에 실을 수 없다 — 보내기 전에 시각·seq 와 함께 멈춘다."""
    with FakeWorld() as w:
        bd = Diagram()
        link = bd.add(WorldLink(port=w.port, st=0.04))
        for i, v in enumerate(STATE):
            bd.connect(bd.add(Constant(float("nan") if i == 9 else float(v))), link[i])
        for i in range(4):
            bd.connect(bd.add(Constant(0.5)), link[13 + i])
        with pytest.raises(WorldLinkError, match="발산") as ei:
            run(bd, T_END, DT)
        assert w.wait_for("bye")
    assert "seq=0" in str(ei.value) and w.steps == []
