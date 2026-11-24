"""테스트 공용 설정."""

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolated_loopsym_home(tmp_path_factory):
    """서버 접속 키 파일을 실제 홈(~/.loopsym)이 아닌 임시 폴더에 둔다.

    테스트가 띄우는 서버 서브프로세스도 이 환경변수를 물려받아 같은 키를 쓴다."""
    old = os.environ.get("LOOPSYM_HOME")
    os.environ["LOOPSYM_HOME"] = str(tmp_path_factory.mktemp("loopsym_home"))
    yield
    if old is None:
        os.environ.pop("LOOPSYM_HOME", None)
    else:
        os.environ["LOOPSYM_HOME"] = old
