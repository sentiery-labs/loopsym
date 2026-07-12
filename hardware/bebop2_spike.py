"""[CLD-P41] Bebop 2 스파이크 — 이륙→호버 5초→착륙 + 텔레메트리 수신 확인.

⚠ 실행 전 hardware/BEBOP2_SAFETY.md 체크리스트를 반드시 통과할 것.
⚠ 이 스크립트는 사람이 현장에서 실행한다 (기체·WiFi 필요). --dry-run 은 어디서든 OK.

준비:
  pip install pyparrot
  Bebop 2 전원 → PC 를 드론 WiFi(Bebop2-xxxxxx)에 연결

실행:
  python3 hardware/bebop2_spike.py --dry-run   # 연결 없이 시퀀스 점검
  python3 hardware/bebop2_spike.py             # 실제 비행 (프로펠러 가드 필수)
"""

import argparse
import sys
import time

HOVER_SECONDS = 5


def telemetry_cb(args_):
    """상태 수신 콜백 — BebopState 블록([CLD-P43])의 원형."""
    bebop = args_[0]
    s = bebop.sensors.sensors_dict
    alt = s.get("AltitudeChanged_altitude", float("nan"))
    bat = s.get("BatteryStateChanged_percent", -1)
    print(f"  [telemetry] alt={alt:.2f}m battery={bat}%")


def main(dry_run):
    print("=== Bebop 2 스파이크: 연결 → 이륙 → 호버 5s → 착륙 ===")
    if dry_run:
        print("[dry-run] pyparrot 시퀀스 점검만 수행 (기체 미접속)")
        print("  1) Bebop(drone_type='Bebop2') 생성")
        print("  2) connect(num_retries=3)")
        print("  3) set_user_sensor_callback(telemetry_cb)")
        print("  4) safe_takeoff(10) → smart_sleep(5) → safe_land(10)")
        print("  5) disconnect")
        print("[dry-run] OK — 실기체 실행은 안전 체크리스트 통과 후")
        return 0

    try:
        from pyparrot.Bebop import Bebop
    except ImportError:
        print("pyparrot 미설치: pip install pyparrot", file=sys.stderr)
        return 1

    bebop = Bebop(drone_type="Bebop2")
    print("연결 중... (Bebop2 WiFi 에 접속되어 있어야 함)")
    if not bebop.connect(num_retries=3):
        print("연결 실패 — WiFi 연결과 기체 전원을 확인", file=sys.stderr)
        return 1
    print("연결됨. 배터리:", bebop.sensors.battery, "%")
    if bebop.sensors.battery < 30:
        print("배터리 30% 미만 — 비행 중단 (안전수칙)", file=sys.stderr)
        bebop.disconnect()
        return 1

    bebop.set_user_sensor_callback(telemetry_cb, (bebop,))
    try:
        print("이륙...")
        bebop.safe_takeoff(10)
        print(f"호버 {HOVER_SECONDS}s (E-stop: Ctrl+C = 즉시 착륙)")
        bebop.smart_sleep(HOVER_SECONDS)
    except KeyboardInterrupt:
        print("\nE-stop! 착륙합니다.")
    finally:
        print("착륙...")
        bebop.safe_land(10)
        bebop.disconnect()
        print("완료. 텔레메트리가 위에 찍혔으면 [CLD-P41] 완료조건 충족.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="기체 없이 시퀀스 점검")
    sys.exit(main(ap.parse_args().dry_run))
