"""CLI (loopsym / python -m loopsym) — 데모 로드/옵션 분기 (브라우저는 안 연다)."""

import json

import pytest

import loopsym.__main__ as cli
from loopsym import Scope, Simulator, load_json


@pytest.fixture
def opened(monkeypatch):
    """open_app 을 가로채 인자만 기록 — 실제 브라우저 실행 방지."""
    calls = []
    monkeypatch.setattr("loopsym.app.open_app",
                        lambda model=None, **kw: calls.append((model, kw)) or "/tmp/x.html")
    return calls


def test_default_is_pi_demo(opened):
    assert cli.main([]) == 0
    model, kw = opened[0]
    assert isinstance(model, dict)
    types = [b["type"] for b in model["blocks"]]
    assert "Scope" in types and "Subsystem" in types      # 연결 완료된 PI 데모
    assert kw["t_end"] == 10.0 and kw["dt"] == 0.01


def test_blank(opened):
    cli.main(["--blank"])
    model, kw = opened[0]
    assert model is None                                   # 빈 캔버스


def test_example_pendulum(opened):
    cli.main(["--example", "pendulum"])
    model, kw = opened[0]
    assert kw["t_end"] == 8.0 and kw["dt"] == 0.005
    assert any(b["type"] == "PyFunction" for b in model["blocks"])


def test_exclusive_options(opened):
    with pytest.raises(SystemExit):
        cli.main(["--blank", "--example", "pi"])


def test_help_mentions_modes(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    for kw in ("--blank", "--example", "MODEL.json", "loopsym.server"):
        assert kw in out                                   # 수용 기준 5


def test_bundled_examples_run():
    """번들 3종이 회귀 기준값을 재현한다 (wheel 데모 정본 무결성)."""
    for name, (T, dt), ref in (("pi", (10.0, 0.01), 1.000189),
                               ("pendulum", (8.0, 0.005), 0.306499),
                               ("discrete_pi", (10.0, 0.01), 1.000087)):
        bd = load_json(cli._load_bundled(name))
        sim = Simulator(bd)
        sim.run(T, dt)
        sc = [b for b in sim.bd.blocks if isinstance(b, Scope)][0]
        assert sc.data[1][-1] == pytest.approx(ref, abs=5e-7), name
