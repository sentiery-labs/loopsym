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
| `blocksim/realtime.py` | **실시간 모드**: `run_realtime()` — 절대 데드라인 + hybrid sleep 페이서, 지터 계측 | 실시간 시스템, 스케줄링 |
| `examples/ex5_realtime_demo.py` | P40 데모(이산 PI 50Hz)를 뷰어에서 라이브로 | 실시간 vs 배치 |
| `examples/ex1_pi_closed_loop.py` | PI 제어 폐루프 (2차 플랜트) | 폐루프, 정상상태 오차 0 |
| `examples/ex2_pendulum_pyfunction.py` | 비선형 진자 + PD (PyFunction) | 왜 적분항이 필요한가 |
| `examples/ex3_subsystem.py` | 마스크 PI 서브시스템 (`Gain(k="$Kp")`) | 계층화, flatten, 마스크 |
| `examples/ex4_discrete_pi.py` | 연속 PI vs 이산 PI (Ts 영향) | 샘플링, PX4 로 가는 다리 |
| `tests/` | pytest 회귀 + **Pyodide 스모크**(뷰어 실행 경로 검증) | — |
| `docs/` | 15주 커리큘럼 설계, P14/P40 스파이크 결과 | — |
| `benchmarks/` | **실시간 지터 재검증** (`p40_realtime.py --hz --duration`) + 결과 리포트 | — |
| `spikes/`, `hardware/` | 최초 실시간 스파이크(폐기됨 — benchmarks 가 유효), Bebop 2 스파이크(+안전 체크리스트) | — |

개발: `pip install -e ".[dev]"` + `npm install` 후 `python -m pytest tests/ -q` (node+pyodide 있으면 뷰어 스모크 포함)

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
- 우측 인스펙터에서 파라미터 수정 후 ▶ 실행 — **Pyodide 가 파이썬 blocksim
  엔진을 브라우저 안에서 그대로 실행** (아래 아키텍처 참조)
- "Python 코드" 버튼: 현재 다이어그램을 (서브시스템 포함) blocksim 스크립트로 역생성
- `PyFunction` 은 식 문자열(`"6.0*(u0-u1) - 2.0*u2"`)로 쓰면 뷰어에서도 실행 가능

### 뷰어 아키텍처 — 시뮬레이션 엔진은 파이썬 하나뿐 (2026-07 변경)

초기 뷰어는 파이썬 엔진을 JS 로 복제해 갖고 있었다(수동 동기화 +
`test_viewer_sync.py` 로 검증). 블록이 늘 때마다 두 벌을 고쳐야 하고
어긋나면 "뷰어와 파이썬 결과가 다른" 최악의 교육 사고가 나므로, JS 엔진을
**폐기**하고 Pyodide 로 전환했다 (git 히스토리에 구현이 남아 있다 —
"파이썬 엔진을 JS 로 포팅해 보기"는 심화 과제로 재사용 가능).

- 뷰어 JS 의 역할: ① 블록 편집 ② 모델 JSON 직렬화 ③ Pyodide 로드 +
  `blocksim.webapi.run_simulation(diagram_json, t_end, dt)` 호출 ④ Scope 렌더링
- `render_html()` 이 만드는 HTML 에는 엔진 소스(.py)가 심어져 있어 단독으로
  동작한다. 원본 `viewer.html` 을 직접 열 때는 옆의 .py 를 fetch 하므로
  repo 를 HTTP 로 서빙해야 한다 (`python -m http.server`).
- 최초 실행 시 Pyodide 로딩 ~5초 (이후 재실행은 즉시). **오프라인 교실**은
  `python tools/vendor_pyodide.py` 로 로컬 사본을 설치하면 CDN 없이 동작.
- 검증: `tests/test_pyodide_smoke.py` 가 node + pyodide(npm) 로 뷰어와 같은
  실행 경로를 헤드리스로 돌려 네이티브 엔진·회귀 기준값과 대조한다
  (repo 루트에서 `npm install` 필요; CI 에서 항상 실행).

### 로컬 서버 모드 (`python -m blocksim.server`)

같은 뷰어가 로컬 파이썬 서버에 붙어 시뮬레이션을 돌리는 두 번째 모드.
HILS(실제 Pixhawk 연결)와 실시간 러너는 브라우저 샌드박스 밖이 필요하므로
이 모드에서만 동작하게 된다.

```bash
pip install -e ".[server]"        # fastapi + uvicorn
python -m blocksim.server         # ws://localhost:8765
```

- 뷰어는 페이지 로드 때 자동 감지: 서버가 있으면 좌상단 배지가
  **Local Server**, 없으면 **Browser (Pyodide)** (사용자 개입 없는 폴백).
  서버를 나중에 켰다면 뷰어를 새로고침.
- 서버 모드에서는 결과가 **스트리밍**되고(진행 중 Scope 가 갱신됨),
  ▶ 버튼이 **■ 정지**로 바뀌어 긴 실행을 중단할 수 있다 (1초 내 반영).
- 스레딩 원칙: *physics never waits for the viewer* — 시뮬 루프는 전용
  스레드, 전송은 non-blocking queue(가득 차면 오래된 청크 폐기).
  프로토콜/구조는 `blocksim/server.py` docstring 참조.
- 두 모드는 같은 파이썬 엔진을 부르므로 결과가 동일하다
  (`tests/test_server.py` 가 ex1~ex4 로 검증).

### 실시간 모드 (external mode) — [CLD-P42]

서버 모드에서는 **"실시간" 체크박스**가 나타난다. 켜고 실행하면 시뮬레이션
시간이 벽시계에 1:1 로 페이싱되어 **Scope 가 라이브로 흐르고**, 완료 시
상태줄에 지터 통계(p99/miss율)가 표시된다. 실기체 블록(Bebop/ROS2/MAVLink)과
HILS 는 전부 이 모드 위에 얹힌다.

```python
from blocksim import run_realtime
stats = run_realtime(bd, t_end=10.0, dt=0.02)          # 50Hz, 벽시계 10초
stats = run_realtime(bd, t_end=10.0, dt=0.02, speed=2) # 2배속
# stats: p50/p95/p99/max/miss_pct/burst + stopped/elapsed_s
```

- 수치 결과는 배치 `run()` 과 **비트 단위로 동일** — 페이싱은 스텝 사이의
  대기일 뿐 적분에 관여하지 않는다 (`tests/test_realtime.py` 검증).
- 스케줄러(절대 데드라인 + coarse sleep/fine busy-wait)는 P40 재검증에서
  250Hz p99 4.002ms 를 실측한 그 코드다 (`blocksim/realtime.py` 공용).
- 데모: `python examples/ex5_realtime_demo.py` → 서버 켜고 ex5_diagram.html
  에서 "실시간" 체크 후 실행.

## 실시간 성능 (실측, 2026-07-14)

**250Hz 에서, 6-DoF 쿼드 물리(블록 그래프 경유) + MAVLink HIL_SENSOR
인코딩/송신 + WebSocket 10Hz 뷰어 스트리밍을 동시에 건 조건에서 p99 스텝
간격 4.002ms** (주기 4ms, deadline miss 0.003%, 연속 miss ≤1; 일반 리눅스
데스크탑, GC 켠 상태, 5분 측정). 500Hz 에서도 p99 2.000ms.
→ 파이썬 벽시계 루프로 HILS 급 상위 제어 타당. 재현:
`python benchmarks/p40_realtime.py` (조건·수치: `benchmarks/results/20260714_p40.md`).

## 설계 노트 (Simulink 와의 대응)

- **feedthrough**: 출력이 현재 입력에 즉시 의존하면 True. `Integrator` /
  `TransferFunction`(strictly proper) 은 False — 이 블록들이 피드백 루프를
  끊어 주며, 하나도 없이 닫힌 고리는 `AlgebraicLoopError`.
- **실행 의미론**: ① 상태 블록 출력(상태만으로 결정) → ② feedthrough 블록을
  위상 순서로 → ③ 상태 미분 수집 → RK4. Simulink 의 minor/major step 구조의
  단순화판.
- 신호는 스칼라 하나로 제한 (벡터 신호·서브시스템은 확장 과제).
