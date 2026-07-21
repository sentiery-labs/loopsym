"""loopsym.mavlink — MAVLink HIL 블록: 실제 PX4 펌웨어가 loopsym plant 를 비행.

[CLD-P41] fidelity Level 3 경로의 1단계 (SITL). ARCHITECTURE §2 의 사다리에서
"제어기를 진짜 펌웨어로 교체"에 해당한다:

    [loopsym plant] ─ 상태 13 ─▶ [MavlinkHil] ─ HIL_SENSOR/HIL_GPS (TCP 4560) ─▶ PX4 SITL
                                              ◀─ HIL_ACTUATOR_CONTROLS ────────  (실펌웨어:
    [loopsym plant] ◀─ 모터 u1..u4 ──────────┘                                    EKF2+제어기)

- **lockstep**: 우리가 보내는 HIL_SENSOR 의 time_usec 이 PX4 의 시계를
  전진시킨다 → 시뮬레이션은 결정적. 배치(sim) 모드로 돌리면 된다.
- Pixhawk 실물(HITL)은 전송계층만 시리얼로 바꾸면 같은 메시지 흐름
  (SYS_HITL=1) — transport 파라미터로 예약 (2단계).
- pymavlink 는 블록 초기화 때만 임포트 (코어 무의존성 유지, Pyodide 는
  임포트 안전 + 실행 시 안내 에러):  pip install "loopsym[mavlink]"

이식 원본: px4_controller/tools/run_px4_sitl_bridge.m (2026-07-04 검증,
함정 포함 — 센서 STALE 방지 미세잡음, home WMM 지자기, 고아 SITL 가드).
"""

import atexit
import math
import os
import random
import subprocess
import time

from .core import Block

# home (Natick, MA) — EKF2 는 home 좌표의 WMM(세계자기모델)과 선언각/복각을
# 비교하므로 '실제' 지자기 NED 를 줘야 한다 (H~19µT, 복각 +68°, 편각 -14.5°).
_LAT0, _LON0, _ALT0 = 42.299886, -71.350447, 50.0
_MAG_NED_GAUSS = (0.187, -0.049, 0.494)
_R_EARTH = 6378137.0


def _mavutil():
    try:
        from pymavlink import mavutil
        return mavutil
    except ImportError as e:
        raise ImportError(
            "MavlinkHil 블록은 pymavlink 가 필요합니다: "
            'python -m pip install "loopsym[mavlink]" '
            "(네이티브/서버 모드 전용 — Pyodide 브라우저 모드 불가)") from e


def synth_hil_sensor(q, omega, vel, vel_prev, p_down, st, g, rng):
    """참 상태 → PX4 HIL_SENSOR 필드 (미세잡음 포함 — 순수 함수, 단위테스트용).

    ★미세잡음 필수: PX4 sensors 모듈의 data validator 는 '완벽히 일정한' 값을
    고착(STALE)으로 판정해 센서를 격리한다 (실센서는 항상 잡음이 있다)."""
    qw, qx, qy, qz = q
    # R(q)' : NED -> body
    def to_body(v):
        return (v[0]*(1 - 2*(qy*qy + qz*qz)) + v[1]*2*(qx*qy + qw*qz) + v[2]*2*(qx*qz - qw*qy),
                v[0]*2*(qx*qy - qw*qz) + v[1]*(1 - 2*(qx*qx + qz*qz)) + v[2]*2*(qy*qz + qw*qx),
                v[0]*2*(qx*qz + qw*qy) + v[1]*2*(qy*qz - qw*qx) + v[2]*(1 - 2*(qx*qx + qy*qy)))

    a_ned = tuple((v - vp) / st for v, vp in zip(vel, vel_prev))
    f_b = to_body((a_ned[0], a_ned[1], a_ned[2] - g))          # 비력 (레벨 호버 = [0,0,-g])
    mag_b = to_body(_MAG_NED_GAUSS)
    alt = -p_down + _ALT0
    pres = 1013.25 * (1 - 2.25577e-5 * alt) ** 5.255877        # 표준대기 [hPa]
    n = rng.gauss
    return {
        "acc": tuple(v + n(0, 0.02) for v in f_b),
        "gyro": tuple(v + n(0, 0.001) for v in omega),
        "mag": tuple(v + n(0, 0.002) for v in mag_b),
        "abs_pressure": pres + n(0, 0.02),
        "pressure_alt": alt,
    }


def _git(px4dir, *args):
    try:
        r = subprocess.run(["git", "-C", px4dir, *args],
                           capture_output=True, text=True, timeout=3)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _px4_version(px4dir):
    """빌드된 소스트리의 펌웨어 버전+커밋해시 (best-effort — 실바이너리 기동 증거).

    관객이 화면만 보고 '진짜 v1.16 펌웨어'임을 독립적으로 확인하는 근거 (C-6).
    커밋해시는 rev-parse 로 항상 뽑는다 — HEAD 가 태그에 정확히 놓이면
    `describe --tags` 는 해시를 떼어내 태그만 돌려주기 때문(해시 조용히 유실).
    git 없거나 소스트리 아니면 빈 문자열."""
    h = _git(px4dir, "rev-parse", "--short", "HEAD")
    if not h:
        return ""
    tag = _git(px4dir, "describe", "--tags", "--always")
    return f"{tag} ({h})" if tag and h not in tag else (tag or h)


def _guard_and_launch_sitl(px4dir, log_path):
    """SITL 기동 + 고아/디스크 가드 (2026-07-04 38GB 사고 재발 방지)."""
    subprocess.run(["pkill", "-9", "-x", "px4"], stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    stale = "/tmp/px4_sitl.log"
    if os.path.exists(stale):
        os.remove(stale)
    st = os.statvfs(os.path.dirname(log_path) or ".")
    if st.f_bavail * st.f_frsize / 2**30 < 2:
        raise RuntimeError("디스크 여유 < 2GB — SITL 로그 쓸 공간 부족. 정리 후 재시도.")
    px4bin = os.path.join(px4dir, "build", "px4_sitl_default", "bin", "px4")
    rootfs = os.path.join(px4dir, "build", "px4_sitl_default", "rootfs")
    if not os.path.exists(px4bin):
        raise RuntimeError(f"px4 SITL 바이너리 없음: {px4bin} (make px4_sitl 먼저)")
    env = dict(os.environ, PX4_SIM_MODEL="none_iris")
    logf = open(log_path, "w")
    proc = subprocess.Popen([px4bin, "-d"], cwd=rootfs, env=env,
                            stdout=logf, stderr=subprocess.STDOUT,
                            start_new_session=True)
    atexit.register(_teardown_sitl)
    ver = _px4_version(px4dir)
    print(f"[PX4] 기동 — 실 SITL 바이너리 {px4bin} (PID {proc.pid})"
          + (f", 펌웨어 {ver}" if ver else ""))
    return proc


def _teardown_sitl():
    subprocess.run(["pkill", "-9", "-x", "px4"], stderr=subprocess.DEVNULL)


class MavlinkHil(Block):
    """PX4 SITL HIL 브리지 블록 — 진짜 펌웨어(EKF2+commander+제어기)가 제어기 자리.

    입력(13, QuadPlant 출력과 1:1): qw qx qy qz | p q r | pN pE pD | vN vE vD
    출력(4): 모터 u1..u4 [0..1] (HIL_ACTUATOR_CONTROLS — 마지막 수신값 래치)

    파라미터:
      st          샘플타임 (0.004 = 250Hz, px4-rc.simulator IMU_INTEG_RATE)
      px4dir      PX4-Autopilot 경로 ("" = $HOME/PX4-Autopilot). autostart 용
      autostart   True 면 SITL 자동 기동/종료 (가드 포함). False = 이미 떠 있는 SITL
      takeoff_at  이 시각[s]에 가상 GCS 로 force-arm + NAV_TAKEOFF 전송 (0 = 안 함;
                  EKF 정렬에 ~20s 필요)
      transport   "sitl" (TCP 4560 서버). "serial:..." 은 Pixhawk HITL 용 예약

    lockstep 이므로 배치(sim) 모드에서 돌린다 — 실행 속도는 PX4 가 정한다.
    """

    n_in = 13
    n_out = 4
    # dstate 값 자체는 안 쓰지만, 이산 블록으로 등록해 매 st 마다 update() 를 받는다
    dstate_size = 1
    feedthrough = False

    def __init__(self, st=0.004, px4dir="", autostart=True, takeoff_at=20.0,
                 transport="sitl", name=None):
        super().__init__(name)
        self.st = self.sample_time = st
        self.px4dir = px4dir
        self.autostart = autostart
        self.takeoff_at = takeoff_at
        self.transport = transport
        if transport != "sitl":
            raise NotImplementedError(
                f"transport={transport!r} 는 예약됨 — 현재는 'sitl' (Pixhawk HITL 은 2단계)")
        self._u = (0.0, 0.0, 0.0, 0.0)
        self._vel_prev = (0.0, 0.0, 0.0)
        self._rng = random.Random(0)
        self._conn = None
        self._gcs = None
        self._armed_sent = -1e9
        self._n_act = 0
        self._n_step = 0
        self._log_path = None
        self._last_log_check = 0.0

    def dinitial(self):
        self._rng = random.Random(0)
        self._vel_prev = (0.0, 0.0, 0.0)
        return (0.0,)

    # ---------------- 연결 ----------------
    def _connect(self):
        mavutil = _mavutil()
        if self.autostart:
            px4dir = self.px4dir or os.path.join(os.path.expanduser("~"), "PX4-Autopilot")
            self._log_path = os.path.join("/tmp", "loopsym_px4_sitl.log")
            _guard_and_launch_sitl(px4dir, self._log_path)
        # PX4 SITL 은 TCP 4560 에 클라이언트로 접속해 온다 → 우리는 서버
        self._conn = mavutil.mavlink_connection("tcpin:127.0.0.1:4560")
        t0 = time.time()
        while self._conn.recv_match(blocking=True, timeout=1.0) is None:
            if time.time() - t0 > 30:
                raise RuntimeError("PX4 가 30초 내에 TCP 4560 에 접속하지 않음"
                                   + (f" (로그: {self._log_path})" if self._log_path else ""))
        # 가상 GCS (arm/takeoff + STATUSTEXT) — PX4 mavlink udp 18570
        self._gcs = mavutil.mavlink_connection("udpout:127.0.0.1:18570",
                                               source_system=255, source_component=190)
        print(f"[MavlinkHil {self.name}] PX4 접속 — lockstep 시작")

    # ---------------- 매 샘플 ----------------
    def output(self, t, u, xd):
        return self._u

    def update(self, t, u, xd):
        if self._conn is None:
            self._connect()
        mav = self._conn.mav
        t_us = int(round(t * 1e6))
        q = u[0:4]; omega = u[4:7]; pos = u[7:10]; vel = u[10:13]

        s = synth_hil_sensor(q, omega, vel, self._vel_prev, pos[2],
                             self.st, 9.81, self._rng)
        self._vel_prev = vel
        mav.hil_sensor_send(t_us, *s["acc"], *s["gyro"], *s["mag"],
                            s["abs_pressure"], 0.0, s["pressure_alt"], 20.0,
                            0x1FFF)
        self._n_step += 1

        if self._n_step % 25 == 0:                       # HIL_GPS 10Hz
            lat = _LAT0 + (pos[0] / _R_EARTH) * 180 / math.pi
            lon = _LON0 + (pos[1] / (_R_EARTH * math.cos(math.radians(_LAT0)))) * 180 / math.pi
            alt_mm = int(round((-pos[2] + _ALT0) * 1000))
            vg = [int(round(v * 100)) for v in vel]
            mav.hil_gps_send(t_us, 3, int(lat * 1e7), int(lon * 1e7), alt_mm,
                             80, 120, int(math.hypot(vg[0], vg[1])),
                             vg[0], vg[1], vg[2], 0, 12)
        if self._n_step % 250 == 1:                      # HEARTBEAT 1Hz + GCS
            mav.heartbeat_send(18, 8, 0, 4, 3)           # onboard sim
            self._gcs.mav.heartbeat_send(6, 8, 0, 4, 3)  # type=GCS (datalink 헬스)
            self._drain_gcs()
            self._check_log_growth()

        if self._n_step % 250 == 0:                      # 1Hz(sim) 진행 표시 (콘솔 침묵 해소)
            alt = -pos[2]
            if self._armed_sent > 0:                     # 이륙 명령 후: 고도 로그 1s 간격
                print(f"[PX4] 비행 t={t:.0f}s 고도 {alt:.2f}m")
            elif self.takeoff_at and self._n_step % 1250 == 0:   # 정렬 대기: 5s 간격
                print(f"[PX4] EKF 정렬 대기 t={t:.0f}s / {self.takeoff_at:.0f}s")

        # lockstep: HIL_ACTUATOR_CONTROLS 대기 (0.2s 타임아웃)
        m = self._conn.recv_match(type="HIL_ACTUATOR_CONTROLS",
                                  blocking=True, timeout=0.2)
        if m is not None:
            self._u = tuple(min(max(float(c), 0.0), 1.0) for c in m.controls[0:4])
            self._n_act += 1

        # arm + takeoff (가상 GCS)
        if (self.takeoff_at and t >= self.takeoff_at and -pos[2] < 1.0
                and (t - self._armed_sent) > 3):
            cl = self._gcs.mav.command_long_send
            cl(1, 1, 400, 0, 1, 21196, 0, 0, 0, 0, 0)         # force arm
            cl(1, 1, 22, 0, 0, 0, 0, float("nan"),            # NAV_TAKEOFF
               float("nan"), float("nan"), float("nan"))
            self._armed_sent = t
            print(f"[MavlinkHil {self.name}] t={t:.1f}s arm+takeoff 전송")
        return xd

    def _drain_gcs(self):
        for _ in range(20):
            m = self._gcs.recv_match(blocking=False)
            if m is None:
                break
            if m.get_type() == "STATUSTEXT":
                print(f"[PX4] {m.text}")

    def _check_log_growth(self):
        """SITL 로그 폭주 감시 (38GB 사고 가드) — 1Hz 하트비트 시점마다."""
        if self._log_path and os.path.exists(self._log_path):
            mb = os.path.getsize(self._log_path) / 1e6
            if mb > 500:
                _teardown_sitl()
                raise RuntimeError(f"SITL 로그 {mb:.0f}MB 초과 — 폭주로 판단, 중단 "
                                   f"(SITL 은 종료함): {self._log_path}")

    @property
    def link_ratio(self):
        """actuator 수신률 (판정용) — 1.0 에 가까울수록 lockstep 건강."""
        return self._n_act / max(self._n_step, 1)
