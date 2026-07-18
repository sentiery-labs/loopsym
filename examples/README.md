# examples/ — 예제 카탈로그

처음이면 **ex1** 부터. 각 예제는 실행하면 터미널에 결과 수치와 생성물
경로를 출력한다. `*_diagram.html` 은 브라우저로 열어 편집/재실행 가능.

> 설치: `python -m pip install -e ".[examples]"` (소스 체크아웃, matplotlib 포함).
> PyPI 설치자는 저장소 없이 번들 예제부터: `loopsym --example pi`

| 예제 | 내용 | 난이도 | 실행 시간 | 필요한 것 | 생성물 |
|------|------|:---:|:---:|-----------|--------|
| ex1_pi_closed_loop | PI 폐루프 (2차 플랜트) — 정상상태 오차 0 | ★ | ~1s | `[examples]` (matplotlib) | PNG + HTML |
| ex2_pendulum_pyfunction | 비선형 진자 + PD — 왜 적분항이 필요한가 | ★ | ~1s | `[examples]` | PNG + HTML |
| ex3_subsystem | 마스크 PI 서브시스템 (`$Kp`) — 계층화 | ★ | ~1s | `[examples]` | PNG + HTML |
| ex4_discrete_pi | 연속 vs 이산 PI — 샘플링 영향 | ★★ | ~1s | `[examples]` | PNG + HTML |
| ex5_realtime_demo | 실시간 모드 — 벽시계 페이싱 + 지터 통계 | ★★ | 벽시계 ~3s | 코어 (라이브 뷰어는 `[server]`) | HTML |
| ex6_ros2_turtlesim | ROS2 turtlesim go-to-goal — 다이어그램이 곧 노드 | ★★★ | ~30s | ROS2 Humble + rclpy + turtlesim | 실기 데모 |
| ex7_drone_hover | PX4 위치제어 폐루프 (드론 팔레트) | ★★ | ~2s | 코어만 | HTML |
| ex8_imu_fidelity | IMU ideal↔noisy — "다이어그램은 하나" | ★★ | ~2s | 코어만 | HTML |
| ex9_px4_whitebox | PX4 화이트박스 — 제어기/플랜트 안으로 (서브시스템) | ★★★ | ~5s | 코어만 | HTML |
| ex10_joystick_fly | 게임패드 수동 비행 + 모드 전환 | ★★★ | 실시간 | `[server]` + 게임패드 | HTML + 라이브 |

권장 순서: ex1 → ex4 (엔진 개념) → ex7 → ex9 (드론 신호사슬) → ex8
(센서/추정 동기) → ex5/ex10 (실시간/조종) → ex6 (미들웨어).
수업용 주차별 자료는 `course/` (노트북 + 자동 채점기).
