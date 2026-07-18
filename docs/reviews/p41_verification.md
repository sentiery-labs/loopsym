# P41 1단계 (MavlinkHil × PX4 SITL) 독립 검증 절차서

- 대상 커밋: `82cb376` (loopsym main)
- 대상 주장: "실제 PX4 v1.16 펌웨어(EKF2+commander+제어기)가 loopsym plant 를
  비행한다 — actuator 링크 100%, 이륙 후 2.5m 호버, 자세 안정"
- 이 문서는 재현 절차서다. 구현자(Claude) 로컬 실측(2026-07-19, 아래 자체
  검증란)을 Codex 가 독립 재현하고 ✅/❌ + 근거를 남기는 것이 목적이다.

## 1. 전제 조건 (암묵 전제 전부 명시)

### 1-1. PX4 펌웨어 (가장 큰 암묵 전제)

| 항목 | 요구 | 구현자 머신 실측 |
|---|---|---|
| 소스 위치 | `$HOME/PX4-Autopilot` (블록 `px4dir` 파라미터 기본값 — 다른 경로면 `MavlinkHil(px4dir=...)` 로 지정) | `/home/sentiary/PX4-Autopilot` |
| 버전 | v1.16 계열 (센서 합성 규약이 이 버전 기준) | `git describe` = **v1.16.0** (`6ea3539157`) |
| 빌드 | `make px4_sitl_default` 완료 — 다음 두 경로가 존재해야 함:<br>`build/px4_sitl_default/bin/px4` (바이너리)<br>`build/px4_sitl_default/rootfs/` (작업 디렉토리 — 빌드/최초 실행이 생성) | 둘 다 존재 |
| lockstep | `px4_sitl_default` 타깃은 lockstep 기본 활성 (별도 설정 불필요) | 기본값 사용 |
| 기체 모델 | `PX4_SIM_MODEL=none_iris` — **블록이 SITL 기동 시 스스로 설정**하므로 사용자가 환경변수를 만질 필요 없음 | 블록 내부 처리 |

### 1-2. 네트워크 포트 (localhost)

| 포트 | 용도 | 방향 |
|---|---|---|
| TCP **4560** | HIL lockstep — **loopsym 이 서버로 bind**, PX4 SITL 이 클라이언트로 접속 | 수신 대기 |
| UDP **18570** | PX4 SITL 의 GCS mavlink 포트 — loopsym 가상 GCS 가 여기로 송신 (arm/takeoff, STATUSTEXT 수신) | 송신 |

실행 전 두 포트가 비어 있어야 한다: `ss -tlnp | grep -E "4560|18570"` → 출력 없음.
QGroundControl 이나 다른 SITL 이 떠 있으면 충돌한다.

### 1-3. 파이썬 의존성

| 항목 | 요구 | 구현자 머신 실측 |
|---|---|---|
| Python | ≥3.9 (이 머신들엔 unversioned `python` 이 없음 — **`python3` 로 실행**) | 3.10.12 |
| pymavlink | `[mavlink]` extra. ⚠ **0.1.1 wheel 에는 이 extra 가 없다** (미발행 기능) — 소스 체크아웃에서 `pip install -e ".[mavlink]"` 또는 `pip install pymavlink` | 2.4.49 |
| loopsym | **소스 체크아웃 `82cb376` 이상** (MavlinkHil 은 PyPI 0.1.1 에 없음) | editable 설치 |

### 1-4. 시스템 전제

- `/tmp` 쓰기 가능. SITL 로그는 `/tmp/loopsym_px4_sitl.log` 에 생성.
- `/tmp` 파일시스템 여유 **≥ 2GB** (블록이 기동 전 검사 — 미달 시 에러).
- ⚠ **파괴적 동작 고지**: 블록은 기동 전과 종료 시 `pkill -9 -x px4` 를
  실행한다 — **이 머신에서 돌던 다른 px4 프로세스가 있으면 죽는다.**
  검증 머신에 보호할 px4 프로세스가 없는지 먼저 확인할 것 (`pgrep -ax px4`).
- 홈 좌표/지자기는 모듈 상수 (Natick, MA + 해당 위치 WMM 값) — 설정 불필요.
  EKF2 의 지자기 선언각/복각 검사를 통과하기 위한 값이므로 변경하지 말 것.

## 2. 재현 명령 (깨끗한 상태 → ex11)

```bash
# 0) 전제 확인
pgrep -ax px4 || echo "px4 없음(OK)"          # 보호할 프로세스 없는지
ss -tlnp | grep -E "4560|18570" || echo "포트 비어있음(OK)"
ls ~/PX4-Autopilot/build/px4_sitl_default/bin/px4
ls -d ~/PX4-Autopilot/build/px4_sitl_default/rootfs
df -BG /tmp | tail -1                          # 여유 ≥ 2GB

# 1) loopsym 소스 준비 (이미 체크아웃/설치돼 있으면 생략)
cd ~/Projects/px4_simulink/loopsym             # 대상 커밋 82cb376 이상
python3 -m pip install -e ".[mavlink]"

# 2) 실행 (SITL 자동 기동 포함 — 별도 터미널 불필요)
python3 examples/ex11_px4_sitl.py
#   60s 시뮬 lockstep. wall 시간은 PX4 처리 속도 종속 — 로컬에서 수 분 이내
#   (timeout 을 걸려면 10분 권장). exit code 0 = PASS, 1 = FAIL.

# 3) 사후 확인 (가드 검증)
pgrep -ax px4 || echo "잔존 없음(OK)"          # atexit teardown
ls -la /tmp/loopsym_px4_sitl.log               # 수 KB 수준이어야 정상
```

## 3. 판정 기준

시나리오: t=0 지상 정지(ground 모델) → t=20s 가상 GCS 가 force-arm +
NAV_TAKEOFF → PX4 가 MIS_TAKEOFF_ALT(기본 2.5m)로 이륙·호버 → t=60s 종료.

| # | 주장 | 수치 기준 | 측정 정의 |
|---|---|---|---|
| 1 | actuator 링크 | `link_ratio > 0.9` (실측 1.00) | 전 구간 15,000 스텝(250Hz×60s) 중 HIL_ACTUATOR_CONTROLS 를 0.2s 내 수신한 스텝 비율 |
| 2 | 이륙+고도유지 | 평균 ∈ (1.5, 4.0) m **그리고** std < 0.3 m (실측 2.51m / 0.00) | **말기 5초 창** = 마지막 1,250 샘플 (시뮬 t∈(55,60]s) 의 고도(=−pD) 평균/표준편차. MIS_TAKEOFF_ALT 2.5m 호버 판정 |
| 3 | 자세 안정 | `max|qx| < sin(10°) ≈ 0.1736` (실측 0.005) | **전 구간** qx 절대값 최대. 순수 롤 가정에서 qx=sin(roll/2) 이므로 roll<20° 상당 (MATLAB 브리지의 eul 20° 기준을 쿼터니언 성분으로 옮긴 것) |

세 기준은 `examples/ex11_px4_sitl.py` 가 자동 판정해 표로 출력하고 exit
code 에 반영한다. 판정 로직 자체도 검증 대상 — 스크립트의 tail/threshold
정의가 위 표와 일치하는지 대조할 것.

부수 판정(가드): 실행 종료 후 잔존 `px4` 프로세스 0, SITL 로그 < 500MB
(실측 ~2.6KB).

## 4. 실패 시나리오 — "이렇게 실패해야 정상"

| 상황 | 기대 동작 |
|---|---|
| PX4 미빌드/경로 오류 | 시뮬 첫 스텝에서 `RuntimeError: px4 SITL 바이너리 없음: <경로> (make px4_sitl 먼저)` |
| pymavlink 미설치 | 시뮬 첫 스텝에서 `ImportError: ... pip install "loopsym[mavlink]" ...` (임포트 시점이 아니라 실행 시점 — 코어 무의존성 원칙) |
| TCP 4560 점유 | `_connect` 에서 `OSError: [Errno 98] Address already in use` |
| PX4 가 접속 안 옴 (기동 실패, 또는 `autostart=False` 인데 SITL 이 안 떠 있음) | 30초 후 `RuntimeError: PX4 가 30초 내에 TCP 4560 에 접속하지 않음 (로그: /tmp/loopsym_px4_sitl.log)` — 로그 파일에 PX4 쪽 원인 |
| lockstep 중 PX4 정지/actuator 두절 | **예외가 아니라 성능 실패**: 스텝마다 0.2s 타임아웃 후 진행(마지막 명령 래치 유지) → link_ratio 하락 → 판정 1 FAIL. 시뮬 자체는 완주 |
| `/tmp` 여유 < 2GB | 기동 전 `RuntimeError: 디스크 여유 < 2GB ...` |
| SITL 로그 폭주 (>500MB) | 1Hz 감시가 `RuntimeError: SITL 로그 NNNMB 초과 — 폭주로 판단, 중단 (SITL 은 종료함)` + teardown 실행 |

## 5. 검증란

| # | 항목 | 자체 검증 (Claude, 2026-07-19) | Codex |
|---|---|---|---|
| 1 | 전제 재현 (§1 표의 요구가 문서만으로 충족 가능한가) | ✅ 실측값 기입 — 단 PX4 빌드 자체(~수십 분)는 절차 밖 전제 | ⬜ |
| 2 | ex11 실행 완주 + exit 0 | ✅ 첫 실행 PASS (아래 출력) | ⬜ |
| 3 | 판정 1 — 링크 | ✅ actuator 100% | ⬜ |
| 4 | 판정 2 — 고도 | ✅ 말기5s 평균 2.51m, std 0.00 | ⬜ |
| 5 | 판정 3 — 자세 | ✅ \|qx\|max 0.005 | ⬜ |
| 6 | 가드 — 잔존 프로세스/로그 | ✅ pgrep 잔존 0, 로그 2.6KB | ⬜ |
| 7 | 실패 시나리오 최소 1개 재현 (§4 중 택 — 권장: 포트 점유 or autostart=False) | ⬜ 미실측 (구현 코드 경로 기준 기술) | ⬜ |

자체 검증 실측 출력:

```text
===== PX4 SITL x loopsym plant (MavlinkHil) =====
 lockstep 링크 : actuator 100% PASS
 이륙+고도유지 : 말기5s 평균 2.51m (std 0.00) PASS
 자세 안정     : |qx|max 0.005 PASS
 결과: PASS — 실제 PX4 v1.16 펌웨어가 loopsym plant 를 비행
=================================================
```

알려진 한계 (판정 대상 아님, 정직 고지):
- §4 실패 시나리오 중 실측한 것은 정상 경로뿐 — 표의 에러 문구는 구현
  코드에서 옮겼으며 실측 재현은 자체 검증란 #7 과 함께 Codex 라운드 몫.
- wall 시간은 미계측 (timeout 10분 내 완주만 확인).
- 2단계(Pixhawk HITL, transport=serial)는 이 문서 범위 밖 — 실물 연결 후 별도.
