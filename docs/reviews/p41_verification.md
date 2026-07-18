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
git -C ~/PX4-Autopilot describe --tags         # v1.16.x 여야 함
df -BG /tmp | tail -1                          # 여유 ≥ 2GB

# 1) loopsym 소스 준비 (이미 체크아웃/설치돼 있으면 생략)
cd ~/Projects/px4_simulink/loopsym
git log --oneline -1                           # 현재 커밋 확인
git merge-base --is-ancestor 82cb376 HEAD && echo "82cb376 후손(OK)"
python3 -m venv .venv-p41 && . .venv-p41/bin/activate   # 깨끗한 venv 권장
python -m pip install -e ".[mavlink]"          # setuptools>=64 로 editable 동작
                                               # (라운드 1 실패는 §6 수정으로 해소)

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

## 4. 실패 시나리오 — "이렇게 실패해야 정상" (유발 명령 병기)

| 상황 | 유발 명령 | 기대 동작 |
|---|---|---|
| PX4 미빌드/경로 오류 | `HOME=/tmp python3 examples/ex11_px4_sitl.py` (px4dir 기본값이 $HOME 기준) | 시뮬 첫 스텝에서 `RuntimeError: px4 SITL 바이너리 없음: <경로> (make px4_sitl 먼저)` |
| pymavlink 미설치 | 새 venv 에 `pip install -e .` (extra 없이) 후 ex11 실행 | 시뮬 첫 스텝에서 `ImportError: ... pip install "loopsym[mavlink]" ...` (임포트 시점이 아니라 실행 시점 — 코어 무의존성 원칙) |
| TCP 4560 점유 | `python3 -m http.server 4560 &` 후 ex11 실행, 끝나면 `kill %1` (Codex 라운드 1 검증 방식) | `_connect` 에서 `OSError: [Errno 98] Address already in use`, exit 1 |
| PX4 가 접속 안 옴 | `python3 - <<'EOF'` 로 `MavlinkHil(autostart=False)` 를 넣은 ex11 build() 실행 (SITL 안 띄운 상태) `EOF` | 30초 후 `RuntimeError: PX4 가 30초 내에 TCP 4560 에 접속하지 않음 (로그: /tmp/loopsym_px4_sitl.log)` — 로그 파일에 PX4 쪽 원인 |
| lockstep 중 PX4 정지/actuator 두절 | 실행 중 다른 터미널에서 `pkill -STOP -x px4` (재개: `-CONT`) | **예외가 아니라 성능 실패**: 스텝마다 0.2s 타임아웃 후 진행(마지막 명령 래치 유지) → link_ratio 하락 → 판정 1 FAIL. 시뮬 자체는 완주 |
| `/tmp` 여유 < 2GB | 유발 비실용 — 코드 경로 검증만 | 기동 전 `RuntimeError: 디스크 여유 < 2GB ...` |
| SITL 로그 폭주 (>500MB) | 유발 비실용 — 코드 경로 검증만 | 1Hz 감시가 `RuntimeError: SITL 로그 NNNMB 초과 — 폭주로 판단, 중단 (SITL 은 종료함)` + teardown 실행 |

## 5. 검증란

| # | 항목 | 자체 검증 (Claude, 2026-07-19) | Codex |
|---|---|---|---|
| 1 | 전제 재현 (§1 표의 요구가 문서만으로 충족 가능한가) | ✅ 실측값 기입 — 단 PX4 빌드 자체(~수십 분)는 절차 밖 전제 | ❌ §2 명령을 처음부터 그대로 실행했으나 `python3 -m pip install -e ".[mavlink]"`가 `build backend is missing the 'build_editable' hook`으로 종료됐다. venv 생성이나 setuptools/빌드 백엔드 업그레이드가 문서에 없어 여기서 재현 절차가 막힌다. 전제 확인 명령에는 §1의 PX4 v1.16 및 loopsym ≥`82cb376` 확인도 빠져 있다. [원출력](#codex-최우선-발견--설치-단계에서-중단) |
| 2 | ex11 실행 완주 + exit 0 | ✅ 첫 실행 PASS (아래 출력) | ✅ 설치 실패와 별개로 이미 준비돼 있던 현재 환경에서 문서의 실행 명령을 그대로 수행했다. `python3 examples/ex11_px4_sitl.py`는 3.81초 wall time에 exit `0`, 최종 `결과: PASS`로 완주했다. 이는 처음부터 재현 성공이 아니라 **기설치 pymavlink 환경에서 실행 자체가 성공**했다는 판정이다. |
| 3 | 판정 1 — 링크 | ✅ actuator 100% | ✅ 출력 `lockstep 링크 : actuator 100% PASS`. 기준 `link_ratio > 0.9`를 통과한다. 코드도 `hil.link_ratio > 0.9`로 판정하며, 수신 성공 스텝/전체 update 스텝 비율 정의와 일치한다. |
| 4 | 판정 2 — 고도 | ✅ 말기5s 평균 2.51m, std 0.00 | ✅ 출력 `말기5s 평균 2.51m (std 0.00) PASS`. 평균은 `(1.5,4.0)` 안이고 std는 `0.3` 미만이다. 코드의 tail은 `int(5.0/0.004)=1250`, 고도는 `-pD`, 평균/모표준편차 정의도 §3과 일치한다. |
| 5 | 판정 3 — 자세 | ✅ \|qx\|max 0.005 | ✅ 독립 실행값은 `\|qx\|max 0.006 PASS`로 자체 검증값 0.005와 소폭 달랐지만 기준 `sin(10°)≈0.1736`보다 충분히 작다. 코드는 전 구간 `max(abs(qx))`와 `sin(radians(20)/2)`를 비교해 §3과 일치한다. |
| 6 | 가드 — 잔존 프로세스/로그 | ✅ pgrep 잔존 0, 로그 2.6KB | ✅ 정상 종료 직후 문서 명령 출력은 `잔존 없음(OK)`. `/tmp/loopsym_px4_sitl.log`는 `2333` bytes로 500MB 미만이며 “수 KB” 조건과 일치했다. 포트 실패 보조 재현 후에도 PX4 잔존 0, 포트 4560/18570 모두 해제됨을 확인했다. |
| 7 | 실패 시나리오 최소 1개 재현 (§4 중 택 — 권장: 포트 점유 or autostart=False) | ⬜ 미실측 (구현 코드 경로 기준 기술) | ✅ TCP 4560을 임시 서버로 점유한 뒤 ex11을 실행해 exit `1`과 `_connect`의 `OSError: [Errno 98] Address already in use`를 재현했다. §4 기대 오류와 정확히 일치한다. 단, §4에는 실패 상태를 만드는 실행 명령이 없어서 점유 명령은 Codex가 보충했다. [재현 출력](#codex-실패-시나리오--tcp-4560-점유) |

**Codex 독립 판정: 6/7 통과. 최우선 실패는 #1 설치 절차다.**

## Codex 독립 재검증 기록

### Codex 최우선 발견 — 설치 단계에서 중단

문서 §2의 명령을 순서대로 실행했다. 최초 전제 확인은 다음과 같았다.

```text
px4 없음(OK)
포트 비어있음(OK)
/home/sentiary/PX4-Autopilot/build/px4_sitl_default/bin/px4
/home/sentiary/PX4-Autopilot/build/px4_sitl_default/rootfs
/dev/nvme0n1p2  94G  53G  37G  59%  /
```

이어 문서의 설치 명령을 수정 없이 실행했다.

```bash
cd ~/Projects/px4_simulink/loopsym
python3 -m pip install -e ".[mavlink]"
```

```text
Obtaining file:///home/sentiary/Projects/px4_simulink/loopsym
Installing build dependencies: finished with status 'done'
Checking if build backend supports build_editable: finished with status 'done'
ERROR: Project ... has a 'pyproject.toml' and its build backend is missing the
'build_editable' hook. Since it does not have a 'setup.py' nor a 'setup.cfg',
it cannot be installed in editable mode.
```

따라서 문서만 따르는 신규 재현자는 이 지점에서 중단된다. 이번 정상 실행은 이 머신에
이미 `pymavlink 2.4.49`와 소스 import 경로가 있었기 때문에 가능했으며, 실패한 설치
명령의 대체가 아니다.

추가로 §1은 PX4 v1.16과 loopsym `82cb376` 이상을 필수로 적었지만 §2 전제 확인
블록에는 이를 검사하는 명령이 없다. Codex가 별도로 확인한 현재 값은 PX4
`v1.16.0`/`6ea3539157`, loopsym HEAD는 `82cb376`의 후손이어서 이번 머신은 조건을
만족했다. 하지만 문서의 재현 명령만 실행하면 이 사실을 검증할 수 없다.

### Codex 정상 시나리오 원출력

설치 단계 실패를 보존한 상태에서, 기존 환경으로 문서의 실행 명령을 그대로 시도했다.

```bash
python3 examples/ex11_px4_sitl.py
```

```text
[ex11] 60s lockstep (250Hz) — t=20s arm+takeoff …
[MavlinkHil px4_sitl] PX4 접속 — lockstep 시작
[MavlinkHil px4_sitl] t=20.0s arm+takeoff 전송
[MavlinkHil px4_sitl] t=23.0s arm+takeoff 전송

===== PX4 SITL x loopsym plant (MavlinkHil) =====
 lockstep 링크 : actuator 100% PASS
 이륙+고도유지 : 말기5s 평균 2.51m (std 0.00) PASS
 자세 안정     : |qx|max 0.006 PASS
 결과: PASS — 실제 PX4 v1.16 펌웨어가 loopsym plant 를 비행
=================================================
뷰어: .../examples/ex11_diagram.html
```

프로세스 exit code는 `0`, wall time은 `3.81s`였다. 자체 검증의 qx 0.005와 독립
실행의 0.006은 출력 정밀도에서 다르지만 둘 다 동일 기준을 넉넉히 통과한다.

판정 구현도 대조했다.

```text
tail = int(5.0 / 0.004) = 1250
alt = -pD
ok_to = 1.5 < alt_mean < 4.0 and alt_std < 0.3
ok_att = max(abs(qx)) < sin(radians(20) / 2)
ok_link = link_ratio > 0.9
```

이는 §3의 측정 창, 부호, 임계값과 모두 일치한다.

### Codex 가드 원출력

정상 실행 직후 문서의 사후 확인 명령을 그대로 실행했다.

```text
잔존 없음(OK)
-rw-rw-r-- 1 sentiary sentiary 2333 Jul 19 02:32 /tmp/loopsym_px4_sitl.log
```

### Codex 실패 시나리오 — TCP 4560 점유

문서 §4에는 기대 오류는 있지만 실패 상태를 만드는 명령이 없다. 동작을 대조하기 위해
Codex가 아래 첫 명령을 보충했고, 나머지는 문서의 포트 확인/ex11 명령을 사용했다.

```bash
python3 -m http.server 4560 --bind 127.0.0.1
ss -tlnp | grep -E "4560|18570"
python3 examples/ex11_px4_sitl.py
```

점유 확인:

```text
LISTEN 0 5 127.0.0.1:4560 0.0.0.0:* users:(("python3",pid=272657,fd=3))
```

ex11은 exit `1`로 종료했고 핵심 traceback은 다음과 같았다.

```text
File "loopsym/mavlink.py", line 160, in _connect
  self._conn = mavutil.mavlink_connection("tcpin:127.0.0.1:4560")
...
OSError: [Errno 98] Address already in use
```

이는 §4의 TCP 4560 점유 기대 동작과 일치한다. 임시 서버 종료 후 확인 결과는
`잔존 없음(OK)`, `포트 비어있음(OK)`였다.

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

## 6. 라운드 2 후속 조치 (Codex 판정 반영, 2026-07-19)

**❌#1 본체 수정** — 원인: `[build-system] requires = ["setuptools>=61"]`.
PEP 660 editable(`build_editable` 훅)은 **setuptools 64** 부터라, setup.py 없는
이 프로젝트는 구형 빌드 환경에서 `pip install -e .` 가 실패했다.
`setuptools>=64` 로 수정 (커밋 참조).

수정 실측 — **깨끗한 venv + Ubuntu 22.04 기본 pip 22.0.2** (라운드 1 실패와
같은 구형 조건):

```text
$ python3 -m venv vedit && vedit/bin/pip --version
pip 22.0.2 (python 3.10)
$ vedit/bin/pip install -e ".[mavlink]"
(성공)
$ vedit/bin/python -c "from loopsym import MavlinkHil; import loopsym; print(loopsym.__version__)"
editable OK, v0.1.1
```

**문서 보강** — §2 전제 확인에 PX4 버전(`git describe`)·loopsym 커밋
(`merge-base --is-ancestor 82cb376`) 확인 명령과 깨끗한 venv 생성 단계 추가.
§4 에 실패 유발 명령 병기 (4560 점유는 Codex 의 http.server 방식 채택).

이 수정은 CHANGELOG 0.1.2 후보에 등록 — editable install 은 배포(소스 설치)
사용자도 겪는 문제다. Codex 재검증 대상: §5 #1 을 이 수정 기준으로 재판정.
