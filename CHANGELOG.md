# Changelog

## 미발행 (0.1.2 후보)

- **editable install 수정** — `[build-system] requires = ["setuptools>=64"]`
  (PEP 660 `build_editable` 훅). 61 이면 setup.py 없는 이 프로젝트의
  `pip install -e .` 가 구형 빌드 환경(Ubuntu 22.04 기본 pip 등)에서
  실패했다 (Codex P41 판정 #1). 깨끗한 venv + pip 22.0.2 실측 통과.

- **MavlinkHil 블록** (CLD-P41, fidelity Level 3 — 1단계 SITL): 실제 PX4
  펌웨어(EKF2+commander+제어기)가 loopsym plant 를 비행. TCP 4560 lockstep,
  HIL_SENSOR(250Hz)/HIL_GPS(10Hz) 합성(STALE 방지 잡음, home WMM 지자기),
  가상 GCS arm/takeoff, SITL 자동기동+고아/디스크/로그 가드.
  `pip install "loopsym[mavlink]"` (pymavlink). Pixhawk HITL(transport
  serial)은 2단계 예약. 실측: 링크 100%, 이륙 2.51m 호버 PASS
  (`examples/ex11_px4_sitl.py`).
- QuadPlant `ground` 파라미터 — 지상 시동용 최소 지면 모델.

## 0.1.1 (빌드 완료 — PyPI 업로드 대기)

UX 리뷰(docs/reviews/ux_review_codex.md) 대응 릴리스 — 골든 패스:
`pip install loopsym` → `loopsym` → ▶ 실행 → Scope.

- **함수형 PyFunction** (Simulink MATLAB Function 스타일) — `def f(t, a, b):
  … return x, y` 를 쓰면 시그니처에서 입력 포트 수/이름, return 에서 출력
  수를 자동 추론 (여러 def = 마지막이 블록 함수, 위는 헬퍼). 뷰어 코드
  편집기 저장 시 n_in/n_out 자동 설정 + 인자 이름이 포트 라벨로 표시.
- **인자 없는 `loopsym` = PI 데모** (연결 완료 + Scope). `--blank` 빈 캔버스,
  `--example pi|pendulum|discrete_pi` 번들 예제, `--help` 에 모드 안내.
- 번들 예제 JSON 3종을 패키지 데이터로 포함 (`loopsym/examples/*.json`,
  정본 = `tools/gen_bundled_examples.py`, 회귀 기준값 재현 검증).
- 뷰어: "새로 시작"(빈 캔버스) 버튼, "초기 모델" → "되돌리기" 개명,
  오프라인 실패 시 복구 명령(`python -m loopsym.server`) 상태줄 안내.
- `[project.urls]` (Repository/Issues/Changelog) 추가.
- **wheel 설치 검증 CI** (`tools/check_wheel.py`) — 깨끗한 venv 에 wheel 을
  설치해 CLI/`-m` 실행/버전/번들 데모 렌더/네이티브 시뮬 기준값을 검사.
- README 개편: PyPI 3단계 빠른 시작(첫 실행 CDN 조건 명시), 소스 개발 절
  분리(`[examples]` extra), 서버/오프라인 명령 정정, 데스크톱 전용(≥1024px)
  명시, `examples/README.md` 카탈로그.
- `loopsym.__version__` 추가 — `importlib.metadata.version("loopsym")` 기반
  (미설치 소스 트리/Pyodide 에서는 `"unknown"` 폴백).
- **`loopsym` CLI** (`loopsym [model.json]`, `python -m loopsym`) — 뷰어를
  크로미엄 `--app` 모드의 독립 프로그램 창으로 연다 (의존성 0, 폴백 = 브라우저 탭).
- **Joystick 블록** (Interfaces) — 브라우저 Gamepad API → 서버 → 블록으로
  실시간 조종 (RC Mode 2 매핑, 버튼 모드 래치, 입력 없으면 중립+호버 추력).
  데모 `examples/ex10_joystick_fly.py` (수동 자세 ↔ 위치유지 모드 전환).
- 뷰어: 계측기 워크벤치 디자인, Scope 팝업 창, 포트 이름 라벨/툴팁,
  서브시스템 겉면 포트 이름, `render_html(t_end=, dt=, save_name=)`,
  file:// Pyodide CDN 폴백, 믹서/플랜트 프레임 선택(quad X/+, hexa, octo),
  WaypointManager(Navigation) 블록.

## 0.1.0 — 2026-07-18 (PyPI 첫 업로드)

- 엔진: Block/Diagram/위상정렬/대수루프 검출, RK4 고정스텝, 이산 블록
  (UnitDelay/DiscreteIntegrator/DiscreteTF), Subsystem/마스크, Mux/Demux,
  JSON 저장/불러오기, 실시간 모드, ROS2 Pub/Sub.
- 뷰어: 단일 HTML + Pyodide 단일 엔진 (신호사슬 팔레트, 서브시스템 진입).
- 드론 팔레트: QuadPlant(6-DoF)/PID/Rate·Attitude·PositionController/
  QuadXMixer (PX4 v1.16 검증본 이식) + 화이트박스 조립 블록.
- 센서: SensorBlock fidelity 규약(포트 불변) + IMU(ideal/noisy, seed 고정).
- 추정: ComplementaryFilter (Mahony).
