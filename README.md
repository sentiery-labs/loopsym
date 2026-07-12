# blocksim — 교육용 파이썬 블록 다이어그램 시뮬레이터

Simulink의 핵심 원리(블록·와이어·실행 순서·solver)를 파이썬으로 직접
만들어 보는 수업용 미니 엔진. 전체가 순수 파이썬 몇 백 줄이라 학생이
15주 안에 바닥부터 따라 만들 수 있는 규모다.

## 구성

| 파일 | 내용 | 수업 주제 |
|------|------|-----------|
| `blocksim/core.py` | `Block` 베이스 클래스, `Diagram`, 위상 정렬 + 대수 루프 검출 | 클래스/상속, 그래프 알고리즘 |
| `blocksim/blocks.py` | Step·Gain·Sum·Product·Integrator·TransferFunction·**PyFunction**·Scope + **Subsystem**(Inport/Outport, **마스크**) + **이산 블록**(UnitDelay·DiscreteIntegrator·DiscreteTF) + Mux/Demux | 상태공간, feedthrough, 샘플링 |
| `blocksim/sim.py` | **flatten**(서브시스템 펼치기) + 고정 스텝 RK4 + 이산 상태 실행 | 수치적분, 안정성, 계층 구조 |
| `blocksim/viz.py` + `viewer.html` | 인터랙티브 뷰어 + `save_json`/`load_json` | — |
| `examples/ex1_pi_closed_loop.py` | PI 제어 폐루프 (2차 플랜트) | 폐루프, 정상상태 오차 0 |
| `examples/ex2_pendulum_pyfunction.py` | 비선형 진자 + PD (PyFunction) | 왜 적분항이 필요한가 |
| `examples/ex3_subsystem.py` | 마스크 PI 서브시스템 (`Gain(k="$Kp")`) | 계층화, flatten, 마스크 |
| `examples/ex4_discrete_pi.py` | 연속 PI vs 이산 PI (Ts 영향) | 샘플링, PX4 로 가는 다리 |
| `tests/` | pytest 회귀 + **파이썬↔JS 엔진 동기화** 테스트 | — |
| `docs/` | 15주 커리큘럼 설계, P14/P40 스파이크 결과 | — |
| `spikes/`, `hardware/` | 실시간 루프 지터 측정, Bebop 2 스파이크(+안전 체크리스트) | — |

개발: `pip install -e ".[dev]"` 후 `python -m pytest tests/ -q` (node 있으면 JS 동기화 테스트 포함)

## 빠른 시작

```bash
cd pyblocks
python3 examples/ex1_pi_closed_loop.py   # ex1_result.png + ex1_diagram.html 생성
```

```python
from blocksim import *

bd = Diagram()
ref   = bd.add(Step(t_on=1.0))
err   = bd.add(Sum("+-"))
plant = bd.add(TransferFunction([1], [1, 2, 1]))
ctrl  = bd.add(PyFunction("3.0*u0", n_in=1))     # <- MATLAB Function 블록처럼
scope = bd.add(Scope(n_in=2))

bd.connect(ref, err[0]); bd.connect(plant, err[1])
bd.connect(err, ctrl);   bd.connect(ctrl, plant)
bd.connect(ref, scope[0]); bd.connect(plant, scope[1])

run(bd, t_end=10.0, dt=0.01)
render_html(bd, "diagram.html")   # 브라우저에서 구조 확인/편집/재실행
```

## 다이어그램 뷰어 (`render_html`)

- Simulink 식 도형: Gain ▷ 삼각형(값 내부 표시), Sum ○ 원(부호 표시),
  Product ×/÷, Integrator `1/s`, TransferFunction 분수 표기, Scope 파형 아이콘
- 블록 드래그, 출력→입력 포트 드래그로 와이어 연결/재연결, Delete 로 삭제
- **Shift+클릭 다중 선택 → "서브시스템으로 묶기"** (경계 Inport/Outport 자동 생성),
  더블클릭으로 내부 진입(브레드크럼/Esc 로 상위), "풀기"로 해체
- 우측 인스펙터에서 파라미터 수정 후 ▶ 실행 — 브라우저 안 JS 엔진이
  파이썬 엔진과 **동일한 의미론**(flatten, 2단계 평가, 위상 정렬, RK4)으로 재시뮬레이션
- "Python 코드" 버튼: 현재 다이어그램을 (서브시스템 포함) blocksim 스크립트로 역생성
- `PyFunction` 은 식 문자열(`"6.0*(u0-u1) - 2.0*u2"`)로 쓰면 뷰어에서도 실행 가능

## 설계 노트 (Simulink 와의 대응)

- **feedthrough**: 출력이 현재 입력에 즉시 의존하면 True. `Integrator` /
  `TransferFunction`(strictly proper) 은 False — 이 블록들이 피드백 루프를
  끊어 주며, 하나도 없이 닫힌 고리는 `AlgebraicLoopError`.
- **실행 의미론**: ① 상태 블록 출력(상태만으로 결정) → ② feedthrough 블록을
  위상 순서로 → ③ 상태 미분 수집 → RK4. Simulink 의 minor/major step 구조의
  단순화판.
- 신호는 스칼라 하나로 제한 (벡터 신호·서브시스템은 확장 과제).
