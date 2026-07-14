"""주차별 '제공 코드' 파일 생성기 — 정본은 week07/mybs.py 하나.

각 주차 뼈대의 "지난주 완성본(제공)" 부분과 교사용 정답 일부를 mybs.py 에서
슬라이스해 만든다. mybs.py 를 고치면 이 스크립트를 다시 돌려 전파한다.
(드리프트 방지 — tests/test_course_graders.py 가 정답으로 채점기 통과를 검증)

    python course/tools/gen_given.py
"""

import ast
import os

HERE = os.path.dirname(os.path.abspath(__file__))
COURSE = os.path.dirname(HERE)
MYBS = os.path.join(COURSE, "week07", "mybs.py")

src = open(MYBS, encoding="utf-8").read()
lines = src.splitlines(keepends=True)
tree = ast.parse(src)

seg = {}          # 최상위 정의 이름 -> 소스 조각
for node in tree.body:
    if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
        seg[node.name] = "".join(lines[node.lineno - 1:node.end_lineno])

HEAD = '''import math

# PyFunction 식에서 쓸 수 있는 안전한 이름들
_MATH_ENV = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
for _f in (abs, min, max):
    _MATH_ENV[_f.__name__] = _f


'''

STATESTUB = '''

class StateStub(Block):
    """5주차용 '상태 블록 흉내' — 출력이 현재 입력에 의존하지 않는다는 것만 중요.

    진짜 적분기는 6주차에 만든다. 이번 주는 feedthrough=False 가
    실행 순서(대수 루프)에 미치는 효과만 본다."""

    n_in = 1
    feedthrough = False

    def output(self, t, u, x):
        return (0.0,)
'''


def emit(path, doc, names, extra=""):
    body = "".join(seg[n] + "\n\n" for n in names).rstrip() + "\n"
    out = f'"""{doc}"""\n\n' + HEAD + body + extra
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)
    print("wrote", os.path.relpath(path, COURSE))


BLOCKS_W3 = ["Block", "Constant", "Step", "Gain", "Saturation", "Offset",
             "Sum", "Product", "PyFunction", "Scope"]

# ---- 주차별 '제공' 파일 ----
emit(os.path.join(COURSE, "week04", "myblocks.py"),
     "4주차 제공 — 1~3주차에 완성한 블록들 (이번 주는 연결과 실행 순서).",
     BLOCKS_W3)
emit(os.path.join(COURSE, "week05", "myblocks.py"),
     "5주차 제공 — 완성 블록들 + StateStub (feedthrough=False 체험용).",
     BLOCKS_W3, STATESTUB)
emit(os.path.join(COURSE, "week06", "mydiagram.py"),
     "6주차 제공 — 5주차에 완성한 Diagram (대수 루프 검출 포함). "
     "(이번 주는 솔버가 주인공 — 다이어그램은 완성본 제공)",
     ["AlgebraicLoopError", "Diagram"])

# ---- 교사용 정답 (뼈대 파일을 그대로 대체하는 드롭인) ----
SOL = os.path.join(COURSE, "solutions")
emit(os.path.join(SOL, "week02_myblocks.py"),
     "2주차 정답 — myblocks.py 대체용.",
     ["Block", "Constant", "Step", "Gain", "Saturation", "Offset"])
emit(os.path.join(SOL, "week03_myblocks.py"),
     "3주차 정답 — myblocks.py 대체용.", BLOCKS_W3)
emit(os.path.join(SOL, "week04_mydiagram.py"),
     "4주차 정답 — mydiagram.py 대체용 (5주차 것과 동일 — 미리 완성형).",
     ["AlgebraicLoopError", "Diagram"])
emit(os.path.join(SOL, "week05_mydiagram.py"),
     "5주차 정답 — mydiagram.py 대체용.",
     ["AlgebraicLoopError", "Diagram"])
emit(os.path.join(SOL, "week06_myblocks.py"),
     "6주차 정답 — myblocks.py 대체용 (Integrator 포함).",
     BLOCKS_W3 + ["Integrator"])
print("done")
