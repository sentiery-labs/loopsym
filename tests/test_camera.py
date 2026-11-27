"""Camera + Image — 3D 월드 아래 방향 카메라 (가짜 월드 서버로 시험)."""

import pytest

from loopsym import Constant, Diagram, Scope, run
from loopsym.world import Camera, Image, WorldLink, WorldLinkError
from tests.fake_world import FakeWorld

DT = 0.01
STATE = (1, 0, 0, 0, 0, 0, 0, 0, 0, -10, 0, 0, 0)
W, H = 64, 48


def _diagram(port, cam):
    """상수 상태 → WorldLink(+모터) 와 Camera → Scope(frame_seq, age_s)."""
    bd = Diagram()
    link = bd.add(WorldLink(port=port, st=0.04, name="link"))
    bd.add(cam)
    for i, v in enumerate(STATE):
        c = bd.add(Constant(float(v)))
        bd.connect(c, link[i])
        bd.connect(c, cam[i])
    for i in range(4):
        bd.connect(bd.add(Constant(0.5)), link[13 + i])
    sc = bd.add(Scope(2, labels=["frame_seq", "age_s"]))
    bd.connect(cam[0], sc[0])
    bd.connect(cam[1], sc[1])
    return bd, sc


def _gray(every=1, size=W * H, fmt="gray8", w=W, h=H):
    """every 샘플마다 영상을 붙여 주는 respond. 픽셀 값 = seq."""
    def respond(s):
        if s["seq"] % every:
            return {}, b""
        return ({"camera": {"seq": s["seq"], "width": w, "height": h, "format": fmt}},
                bytes([s["seq"] % 256]) * size)
    return respond


def _samples(sc, ch):
    """WorldLink 샘플 시점(0.04 간격)의 값만."""
    return [v for t, v in zip(sc.t, sc.data[ch]) if abs(t / 0.04 - round(t / 0.04)) < 1e-9]


def test_hello_carries_camera_settings():
    with FakeWorld(respond=_gray()) as w:
        bd, _ = _diagram(w.port, Camera(width=W, height=H))
        run(bd, 0.08, DT)
    assert w.received[0]["camera"] == {"width": 64, "height": 48, "hfov_deg": 90.0,
                                       "format": "gray8", "every": 1, "mount": "body"}


def test_image_built_with_intrinsics():
    cam = Camera(width=W, height=H)
    with FakeWorld(respond=_gray()) as w:
        bd, _ = _diagram(w.port, cam)
        run(bd, 0.08, DT)
    img = cam.latest
    assert isinstance(img, Image)
    assert (img.width, img.height, img.fmt, img.channels) == (64, 48, "gray8", 1)
    assert img.fx == pytest.approx(32.0, abs=1e-9) and img.fy == pytest.approx(32.0, abs=1e-9)
    assert (img.cx, img.cy) == (32.0, 24.0)
    assert len(img.data) == 3072
    assert img.seq == 2 and img.t == pytest.approx(0.08) and img.data[0] == 2


def test_wrong_image_size_raises():
    with FakeWorld(respond=_gray(size=3000)) as w:
        bd, _ = _diagram(w.port, Camera(width=W, height=H))
        with pytest.raises(WorldLinkError, match="3072"):
            run(bd, 0.2, DT)


def test_changed_resolution_raises():
    with FakeWorld(respond=_gray(size=32 * 24, w=32, h=24)) as w:
        bd, _ = _diagram(w.port, Camera(width=W, height=H))
        with pytest.raises(WorldLinkError, match="32×24"):
            run(bd, 0.2, DT)


def test_missing_intrinsics_raises():
    hello_ok = {"type": "hello_ok", "proto": 1, "world": "Fake",
                "origin": {"lat": 0, "lon": 0, "alt_m": 0}, "camera": None, "app": "fake"}
    with FakeWorld(hello_ok=hello_ok) as w:
        bd, _ = _diagram(w.port, Camera(width=W, height=H))
        with pytest.raises(WorldLinkError, match="내부 값"):
            run(bd, 0.2, DT)


def test_every_two_frames():
    with FakeWorld(respond=_gray(every=2)) as w:
        bd, sc = _diagram(w.port, Camera(width=W, height=H, every=2))
        run(bd, 0.2, DT)
    assert w.received[0]["camera"]["every"] == 2
    assert _samples(sc, 0) == [-1.0, 0.0, 0.0, 2.0, 2.0, 4.0]


def test_age_output():
    with FakeWorld(respond=_gray(every=2)) as w:
        bd, sc = _diagram(w.port, Camera(width=W, height=H, every=2))
        run(bd, 0.2, DT)
    assert _samples(sc, 1) == pytest.approx([0.0, 0.04, 0.08, 0.04, 0.08, 0.04])


def test_save_pgm(tmp_path):
    out = tmp_path / "frames"
    with FakeWorld(respond=_gray()) as w:
        bd, _ = _diagram(w.port, Camera(width=W, height=H, save_dir=str(out), save_every=1))
        run(bd, 0.08, DT)
    raw = (out / "frame_000000.pgm").read_bytes()
    assert raw.startswith(b"P5\n64 48\n255\n")
    assert len(raw) == len(b"P5\n64 48\n255\n") + 3072
    assert sorted(p.name for p in out.iterdir()) == ["frame_000000.pgm", "frame_000001.pgm",
                                                     "frame_000002.pgm"]


def test_save_ppm_rgb(tmp_path):
    img = Image(2, 1, "rgb8", bytes([255, 0, 0, 0, 0, 255]), 0.0, 5, 1.0, 1.0, 1.0, 0.5)
    img.save_pnm(str(tmp_path / "x.ppm"))
    assert (tmp_path / "x.ppm").read_bytes() == b"P6\n2 1\n255\n" + bytes([255, 0, 0, 0, 0, 255])


def test_camera_only_world():
    with pytest.raises(NotImplementedError):
        Camera(fidelity="ideal")


def test_invalid_format_raises():
    with pytest.raises(ValueError, match="rgba"):
        Camera(fmt="rgba")
    with pytest.raises(ValueError, match="mount"):
        Camera(mount="side")
    with pytest.raises(ValueError, match="every"):
        Camera(every=0)
    with pytest.raises(ValueError, match="6220800"):
        Camera(width=4000, height=3000, fmt="rgb8")


def test_ports():
    cam = Camera()
    assert (cam.n_in, cam.n_out, cam.dstate_size) == (13, 2, 1)


def test_to_numpy_shape():
    pytest.importorskip("numpy")
    gray = Image(W, H, "gray8", bytes(W * H), 0.0, 0, 32.0, 32.0, 32.0, 24.0)
    assert gray.to_numpy().shape == (48, 64)
    rgb = Image(W, H, "rgb8", bytes(W * H * 3), 0.0, 0, 32.0, 32.0, 32.0, 24.0)
    assert rgb.to_numpy().shape == (48, 64, 3)
