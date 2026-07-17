# Changelog

## 0.1.1 (미발행 — 다음 릴리스에 포함)

- `loopsym.__version__` 추가 — `importlib.metadata.version("loopsym")` 기반
  (미설치 소스 트리/Pyodide 에서는 `"unknown"` 폴백).

## 0.1.0 — 2026-07-18 (PyPI 첫 업로드)

- 엔진: Block/Diagram/위상정렬/대수루프 검출, RK4 고정스텝, 이산 블록
  (UnitDelay/DiscreteIntegrator/DiscreteTF), Subsystem/마스크, Mux/Demux,
  JSON 저장/불러오기, 실시간 모드, ROS2 Pub/Sub.
- 뷰어: 단일 HTML + Pyodide 단일 엔진 (신호사슬 팔레트, 서브시스템 진입).
- 드론 팔레트: QuadPlant(6-DoF)/PID/Rate·Attitude·PositionController/
  QuadXMixer (PX4 v1.16 검증본 이식) + 화이트박스 조립 블록.
- 센서: SensorBlock fidelity 규약(포트 불변) + IMU(ideal/noisy, seed 고정).
- 추정: ComplementaryFilter (Mahony).
