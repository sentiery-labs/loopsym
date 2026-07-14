"""커리큘럼 채점기 메타 테스트 [CLD-P22].

각 주차 채점기가 유효한지 두 방향으로 검증한다:
  1. 교사용 정답(course/solutions/)을 뼈대 자리에 넣으면 → 전부 PASS
  2. 뼈대(# TODO 상태) 그대로면 → FAIL (TODO 가 실제로 채점된다는 증거)
"""

import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COURSE = os.path.join(ROOT, "course")

# 주차 → {뼈대 파일: 정답 파일}
WEEKS = {
    "week01": {"signals.py": "week01_signals.py"},
    "week02": {"myblocks.py": "week02_myblocks.py"},
    "week03": {"myblocks.py": "week03_myblocks.py"},
    "week04": {"mydiagram.py": "week04_mydiagram.py"},
    "week05": {"mydiagram.py": "week05_mydiagram.py"},
    "week06": {"myblocks.py": "week06_myblocks.py", "mysim.py": "week06_mysim.py"},
    "week07": {"mymodel.py": "week07_mymodel.py"},
}


def _run_grader(week_dir):
    env = dict(os.environ, PYTHONPATH=ROOT)     # blocksim 오라클 임포트용
    return subprocess.run(
        [sys.executable, "-m", "pytest", f"test_{os.path.basename(week_dir)}.py",
         "-q", "-p", "no:cacheprovider"],
        cwd=week_dir, env=env, capture_output=True, text=True, timeout=300)


def _copy_week(week, tmp_path):
    dst = tmp_path / week
    shutil.copytree(os.path.join(COURSE, week), dst,
                    ignore=shutil.ignore_patterns("__pycache__"))
    return str(dst)


@pytest.mark.parametrize("week", sorted(WEEKS))
def test_solution_passes_grader(week, tmp_path):
    d = _copy_week(week, tmp_path)
    for skel, sol in WEEKS[week].items():
        shutil.copy(os.path.join(COURSE, "solutions", sol), os.path.join(d, skel))
    r = _run_grader(d)
    assert r.returncode == 0, f"{week} 정답이 채점기를 통과 못함:\n{r.stdout}\n{r.stderr}"


@pytest.mark.parametrize("week", sorted(WEEKS))
def test_skeleton_fails_grader(week, tmp_path):
    d = _copy_week(week, tmp_path)
    r = _run_grader(d)
    assert r.returncode != 0, f"{week} 뼈대(# TODO)가 채점기를 통과해 버림 — 채점기 무효"
