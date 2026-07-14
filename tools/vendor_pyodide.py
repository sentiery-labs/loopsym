"""Pyodide 로컬 vendored 사본 설치 — 인터넷 없는 교실 대비.

    python tools/vendor_pyodide.py

blocksim/pyodide/ 에 Pyodide 코어 런타임(~10MB 다운로드)을 풀어 놓는다.
뷰어는 이 사본을 CDN 보다 먼저 찾으므로, 설치해 두면 완전 오프라인으로
동작한다 (blocksim 은 순수 파이썬이라 추가 패키지 다운로드도 없음).

주의: 이 폴더는 .gitignore 대상 — 배포 기계마다 이 스크립트로 설치한다.
버전은 뷰어(viewer.html 의 PYODIDE_VERSION)와 반드시 같아야 한다.
"""

import io
import os
import sys
import tarfile
import urllib.request

VERSION = "0.26.4"          # viewer.html 의 PYODIDE_VERSION 과 동일해야 함
URL = (f"https://github.com/pyodide/pyodide/releases/download/"
       f"{VERSION}/pyodide-core-{VERSION}.tar.bz2")
DEST = os.path.join(os.path.dirname(__file__), "..", "blocksim", "pyodide")


def main():
    dest = os.path.abspath(DEST)
    if os.path.exists(os.path.join(dest, "pyodide.js")):
        print(f"이미 설치됨: {dest} (다시 받으려면 폴더를 지우세요)")
        return 0
    print(f"다운로드: {URL}")
    data = urllib.request.urlopen(URL, timeout=120).read()
    print(f"{len(data) / 1e6:.1f} MB — 압축 해제 중…")
    os.makedirs(dest, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:bz2") as tar:
        for m in tar.getmembers():
            # 아카이브 최상위 "pyodide/" 를 벗겨 dest 바로 아래에 푼다
            parts = m.name.split("/", 1)
            if len(parts) < 2 or not m.isfile():
                continue
            rel = parts[1]
            if ".." in rel:          # 경로 탈출 방지
                continue
            out = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as f:
                f.write(tar.extractfile(m).read())
    print(f"완료: {dest}")
    print("이제 뷰어가 CDN 없이(오프라인) 동작합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
