"""뷰어 배선 (직교 라우팅 + 수동 조정 pts) 테스트.

1. viewer.html 의 ROUTING-BEGIN/END 순수 함수 구간을 node 로 실행해
   자동 배선의 직교성/블록 회피/heal·tidy 를 검증.
2. 수동 배선 꼭짓점(wire.pts)이 파이썬 load_json → export_json
   라운드트립에서 보존되는지 검증 (뷰어 저장 ↔ 파이썬 왕복 경로).
"""

import json
import os
import re
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blocksim import Diagram, Gain, Scope, Step, export_json, load_json  # noqa: E402

HERE = os.path.dirname(__file__)
VIEWER = os.path.join(HERE, "..", "blocksim", "viewer.html")

node = shutil.which("node")

JS_CHECKS = r"""
function ok(cond, msg) { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } }
function orthogonal(poly) {
  for (let i = 0; i < poly.length - 1; i++)
    if (poly[i][0] !== poly[i+1][0] && poly[i][1] !== poly[i+1][1]) return false;
  return true;
}
const rects = [[100, 50, 80, 60]];   // (100,50)-(180,110) 블록

// 1) 전진 연결이 일직선 경로를 막는 블록을 우회
const p1 = autoRoute(0, 80, 300, 80, rects);
ok(orthogonal(p1), "전진 경로 직교성");
ok(!polyHits(p1, rects), "전진 경로 블록 회피");
ok(p1[0][0] === 0 && p1[0][1] === 80 && p1[p1.length-1][0] === 300 && p1[p1.length-1][1] === 80, "끝점 보존");

// 2) 피드백(역방향) 경로
const p2 = autoRoute(300, 80, 0, 200, rects);
ok(orthogonal(p2), "피드백 경로 직교성");
ok(!polyHits(p2, rects), "피드백 경로 블록 회피");

// 3) heal: 블록 이동으로 어긋난 endpoint 에 코너 삽입
const h = healPoly([0, 0], [[50, 40]], [120, 90]);
ok(orthogonal(h), "heal 직교성");
ok(h[0][0] === 0 && h[h.length-1][0] === 120 && h[h.length-1][1] === 90, "heal 끝점");

// 4) tidy: 일직선 꼭짓점 병합
const t = tidyPoly([[0,0],[50,0],[80,0],[80,60],[80,60],[120,60]]);
ok(JSON.stringify(t) === JSON.stringify([[0,0],[80,0],[80,60],[120,60]]), "tidy 병합: " + JSON.stringify(t));

console.log("ok");
"""


@pytest.mark.skipif(node is None, reason="node 없음")
def test_js_routing_functions(tmp_path):
    src = open(VIEWER, encoding="utf-8").read()
    m = re.search(r"/\*ROUTING-BEGIN\*/(.*?)/\*ROUTING-END\*/", src, re.S)
    assert m, "viewer.html 에 ROUTING 마커가 없음"
    js = tmp_path / "routing.js"
    js.write_text(m.group(1) + JS_CHECKS, encoding="utf-8")
    out = subprocess.run([node, str(js)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0 and out.stdout.strip() == "ok", out.stderr or out.stdout


def test_wire_pts_roundtrip_python():
    """뷰어 수동 배선 pts 가 load_json → export_json 을 통과해도 남는다."""
    bd = Diagram()
    a = bd.add(Step(name="a")); g = bd.add(Gain(2.0, name="g")); sc = bd.add(Scope(name="sc"))
    bd.connect(a, g); bd.connect(g, sc)
    j = export_json(bd)
    j["wires"][0]["pts"] = [[300, 60], [300, 200]]      # 뷰어가 저장했다고 가정

    bd2 = load_json(json.loads(json.dumps(j)))
    j2 = export_json(bd2)
    w = [w for w in j2["wires"] if "pts" in w]
    assert len(w) == 1 and w[0]["pts"] == [[300, 60], [300, 200]]
    # pts 없는 와이어는 그대로 없음
    assert sum("pts" not in w_ for w_ in j2["wires"]) == 1
