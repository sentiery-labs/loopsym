# loopsym 플랫폼 아키텍처 — 드론/로봇 개발 플랫폼 설계 문서

> 이 문서는 loopsym의 장기 설계 기준(north star)이다.
> 모든 블록/팔레트/커리큘럼 작업은 이 문서와 일관성을 유지해야 한다.
> 상태: 확정 (2026-07-14) | 작성: 충박사 + Claude 설계 세션

---

## 1. 조직 원리: 신호 사슬 = 팔레트 구조

플랫폼의 블록 팔레트는 실제 드론/로봇의 신호 흐름을 그대로 반영한다.
새 카테고리를 발명하지 않는다. PX4/ArduPilot의 아키텍처가 곧 팔레트 구조다.

```
[센서] → [상태추정] → [항법/유도] → [제어] → [할당] → [구동기] → [플랜트] → (센서로 순환)
```

### 팔레트 카테고리 (확정)

| 카테고리 | 블록 예시 | 상태 |
|---|---|---|
| Sources/Sinks | Constant, Step, Sine, Scope, Logger | 기존 |
| Math | Gain, Sum, Product, Saturation, PyFunction | 기존 |
| Continuous/Discrete | Integrator, TransferFunction, UnitDelay, ... | 기존 |
| Sensors | IMU(가속도+자이로), GPS, Barometer, Magnetometer, Rangefinder, OpticalFlow | 신규 — §2 규약 적용 |
| Estimation | Complementary Filter, EKF(간이), Attitude Fusion | 신규 |
| Navigation | Waypoint Manager, Path Follower, L1 Guidance | 신규 |
| Control | PID, Rate Controller, Attitude Controller, Position Controller (PX4 v1.16 대응) | PX4 MATLAB 코드 이식 |
| Allocation | Mixer (quad X/+, hexa X, octo X), Tiltrotor Mixer | PX4 MATLAB 코드 이식 |
| Plant | 6-DoF Multirotor(프레임 선택), 6-DoF Tiltrotor, Motor Dynamics, **Gazebo Bridge** | 6-DoF는 P40 벤치마크 코드 승격 |
| Interfaces | MAVLink Source/Sink (P41), ROS2 Pub/Sub (P44), Serial(HILS) | P41/P44에서 진행 중 |

> 2026-07-18 개정(충박사 결정): Plant 를 표/팔레트에서 신호사슬 끝(맨 오른쪽)으로
> 이동 — §1 신호사슬 다이어그램과 순서 일치. Allocation 의 Mixer 는 프레임
> (quad X/+, hexa, octo) 선택형.

뷰어의 블록 팔레트 UI도 이 카테고리 순서(왼쪽→오른쪽 = 신호 흐름 순서)로 표시한다.

---

## 2. 센서 블록 공통 규약 — Fidelity Levels (핵심 설계 결정)

### 원칙

**같은 센서 블록이 파라미터 하나로 충실도를 올린다. 포트 시그니처는 절대 불변.**

학생의 다이어그램은 학기 초에 한 번 그리면 학기 말(실기체)까지 같은 그림이다.
센서/플랜트 블록의 fidelity 드롭다운만 바뀐다. 이것이 플랫폼의 킬러 컨셉이다:
"시뮬레이션에서 실기체까지, 다이어그램은 하나."

### Fidelity 4단계

```
Level 0 "ideal"    — plant 상태를 그대로 통과 (진리값, 지연/노이즈 없음)
Level 1 "noisy"    — 수식 노이즈 모델 적용:
                     bias + white noise (noise density) + 샘플레이트 제한
                     (+ 센서별 특화: GPS는 지연+점프, Baro는 드리프트 등)
Level 2 "gazebo"   — 해당 센서의 gz topic 구독으로 출력 교체
Level 3 "hardware" — 실기체에서 MAVLink 수신 (IMU: HIGHRES_IMU,
                     GPS: GPS_RAW_INT 등)으로 출력 교체
```

### 구현 규약

- 모든 센서 블록은 `fidelity` 마스크 파라미터를 가진다 (enum: ideal/noisy/gazebo/hardware)
- fidelity 변경 시 입출력 포트 수/이름/차원이 바뀌면 안 된다
- Level 1의 노이즈 파라미터는 마스크로 노출: bias, noise_density, sample_rate_hz
  (기본값은 실제 센서 datasheet 근사치 — 예: ICM-42688 급)
- Level 2/3은 내부적으로 Interfaces 계층(gz bridge, MAVLink)을 사용하되,
  다이어그램상으로는 여전히 "IMU 블록"으로 보인다
- noisy 노이즈는 시드 고정 가능해야 한다 (자동채점/회귀 테스트용)

### Plant 블록도 같은 원리

- 자체 6-DoF 블록 ↔ Gazebo Bridge 블록은 포트 호환으로 맞교체 가능
- HILS에서는 plant 블록을 제거하고 실기체가 plant 역할 (Interfaces 경유)

---

## 3. 15주 커리큘럼 대응 (P21과 정합)

> 2026-07-14 개정: 충박사 결정 ③ **하이브리드** — 전반은 엔진 제작(파이썬 수업),
> 후반이 이 문서의 팔레트 개방 트랙. 주차 상세 정본 = `docs/curriculum_15weeks.md`.

| 주차 | 트랙 | 여는 팔레트 | 학생 경험 |
|---|---|---|---|
| 1~6 | 엔진 제작 | (자기 엔진) | 블록/그래프/위상정렬/대수루프/RK4 를 바닥부터 |
| 7 | ★브리지 | Math, Sources | 내 엔진 ↔ 정식 loopsym 교차 검증 (6자리 일치) |
| 8 | 팔레트 개방 | Plant | 6-DoF 이해, 개루프 불안정 체험 |
| 9~10 | 팔레트 개방 | Control, Allocation | 샘플링/이산 + PID→rate→attitude→position 폐루프 |
| 11~12 | 팔레트 개방 | Sensors, Estimation | **ideal→noisy 전환으로 기체가 흔들리는 것을 목격 → 필터로 복구.** 상태추정의 존재 이유를 체험 |
| 13 | 팔레트 개방 | Navigation | waypoint 미션 + 실시간 모드/ROS2 turtlesim |
| 14 | 팔레트 개방 | Interfaces | plant를 Gazebo로 교체 (P44b; 대체안 ROS2 실기체 데모) |
| 15 | — | — | HILS 시연 + 프로젝트 발표 |

11주차의 "ideal→noisy 전환 순간"이 교육적 하이라이트다.
이 데모가 성립하도록 센서 규약(§2)이 설계되었다.

---

## 4. 작업 순서 (WORKPLAN 반영 지침)

우선순위 원칙: **P42 → P21/P22(수업 데드라인 8월) → 나머지.**
플랫폼 확장(P44b/P46/P47, 센서 팔레트 전체)은 커리큘럼 트랙을 앞지르지 않는다.

### 즉시 착수 가능 (P42 완료 후)

**T1. 팔레트 재편** — 기존 블록 19종을 §1 카테고리로 재분류 (코드 이동 없이
메타데이터/뷰어 팔레트 표시만). 신규 카테고리는 빈 상태로 표시.

**T2. 센서 규약 검증 — IMU 하나만**
- SensorBlock 공통 베이스 (fidelity 파라미터, 포트 불변 규약) 구현
- IMU 블록: ideal + noisy 두 레벨만 구현 (gazebo/hardware는 enum만 예약)
- 데모: 6-DoF 호버 다이어그램에 IMU를 물리고 ideal↔noisy 전환 시
  자세 추정 열화를 Scope로 확인
- **여기서 멈춘다.** GPS/Baro/나머지는 IMU 규약이 검증된 뒤 복제.

### 후속 (커리큘럼 트랙과 병행 판단)

- T3. 나머지 센서 (GPS, Baro, Mag, Rangefinder) — IMU 패턴 복제
- T4. Estimation 팔레트 (Complementary Filter 우선)
- T5. Control/Allocation 팔레트 — PX4 v1.16 MATLAB 코드 이식
  (기존 px4_simulink 프로젝트의 mc_rate_control.m 등이 원본)
- T6. Gazebo fidelity (Level 2) — P44b와 통합
- T7. Hardware fidelity (Level 3) — P41 MAVLink 블록과 통합

---

## 5. 이 문서와 기존 워크플랜의 관계

- P40(실시간 스파이크): 완료 — Level 2~3 실행의 기반 검증
- P41(MAVLink 블록): Interfaces 팔레트의 첫 구현체
- P42(실시간 러너): Level 2~3을 돌리는 엔진
- P44(ROS2/Gazebo): Interfaces 팔레트 + Plant Level 2
- P21/P22(커리큘럼): §3의 주차 구성과 정합 유지

즉 기존 P번호 작업들은 모두 이 아키텍처의 부품이다.
새 작업을 등록할 때 이 문서의 §1~§3과 충돌하면 이 문서를 먼저 개정한다.

---

## 부록 A. 현황 대응표 (2026-07-14, WORKPLAN 카드 매핑 — 갱신은 WORKPLAN 에서)

| 이 문서 | WORKPLAN 카드 | 상태 (7/14) |
|---|---|---|
| §4 T1 팔레트 재편 | [CLD-P61] | ⬜ 착수 가능 (커리큘럼 트랙 우선 원칙 적용) |
| §4 T2 센서 규약 + IMU | [CLD-P62] | ⬜ 착수 가능 — **IMU 검증 후 멈춤** (§4 명시) |
| §4 T3 나머지 센서 | [CLD-P63] | ⬜ P62 검증 후 |
| §4 T4 Estimation 팔레트 | [CLD-P64] | ⬜ |
| §4 T5 Control/Allocation 이식 | [CLD-P65] | ⬜ 원본 = px4_controller/ (소스 대조 검증 완료본) |
| §4 T6 Gazebo fidelity | P44b 와 통합 | ⬜ 보류 (사용자 지시 7/14: P44b 착수 금지) |
| §4 T7 Hardware fidelity | P41/P43 과 통합 | 🟡 P41 스파이크 준비완료 (실기체 대기) |
| §5 P40/P42/P44a | — | ✅ 완료 (P40 재검증 PASS, 실시간 러너, ROS2 블록+turtlesim) |
| §3 커리큘럼 대응 | [OPS-P21] | ✅ 해소(7/14) — **하이브리드 확정**, curriculum_15weeks.md 개정 완료. P22 착수 가능 |
