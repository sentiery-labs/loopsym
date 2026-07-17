"""loopsym.viz — 다이어그램 구조를 눈으로 보기.

export_json(bd)        : 블록/와이어/자동배치 좌표를 dict 로
render_html(bd, path)  : viewer.html 템플릿에 모델을 심어 단독 HTML 생성.
                         브라우저에서 블록을 드래그하고, 와이어를 다시 잇고,
                         파라미터를 고치고, 그 자리에서 재시뮬레이션할 수 있다.
"""

import json
import os

from .core import Port

# 뷰어/직렬화에 내보낼 파라미터 이름 (블록 타입별)
_PARAMS = {
    "Constant": ["value"],
    "Step": ["t_on", "height"],
    "Sine": ["amp", "freq_hz", "phase"],
    "Gain": ["k"],
    "Sum": ["signs"],
    "Product": ["ops"],
    "Saturation": ["lo", "hi"],
    "PyFunction": ["expr", "n_in", "n_out"],
    "Integrator": ["x0"],
    "TransferFunction": ["num", "den"],
    "Scope": ["n_in", "labels"],
    "Inport": ["index"],
    "Outport": ["index"],
    "Subsystem": [],           # params 자리에는 mask 를 내보낸다 (아래 특례)
    "UnitDelay": ["st", "x0"],
    "DiscreteIntegrator": ["st", "x0"],
    "DiscreteTransferFunction": ["num", "den", "st"],
    "Mux": ["n_in"],
    "Demux": ["n_out"],
    "Ros2Subscribe": ["topic", "msg_type", "fields", "st", "defaults"],
    "Ros2Publish": ["topic", "msg_type", "fields"],
    # 드론 팔레트 (drone.py, CLD-P65)
    "QuadPlant": ["m", "g", "ixx", "iyy", "izz", "arm", "c_m",
                  "roll0", "pitch0", "yaw0", "z0"],
    "PID": ["kp", "ki", "kd", "st", "lim"],
    "AttitudeController": ["roll_p", "pitch_p", "yaw_p", "yaw_w"],
    "RateController": ["st"],
    "PositionController": ["st"],
    "QuadXMixer": [],
}


def _auto_layout(bd):
    """왼쪽에서 오른쪽으로 층(layer)을 나눠 좌표를 정한다.

    compile() 이 준 실행 순서를 기준으로, '앞선 블록 -> 뒤 블록' 와이어만
    층 계산에 쓰고 피드백 와이어는 무시한다 (그림에서 되돌아가는 선이 된다).
    """
    order = bd.compile()
    rank = {b: i for i, b in enumerate(order)}
    layer = {b: 0 for b in bd.blocks}
    for b in order:
        for i in range(b.n_in):
            src = bd.wires[Port(b, i)].block
            if rank[src] < rank[b]:
                layer[b] = max(layer[b], layer[src] + 1)
    cols = {}
    pos = {}
    for b in order:
        if getattr(b, "_pos", None):        # load_json 등으로 좌표가 지정된 블록은 존중
            pos[b] = b._pos
            continue
        row = cols.get(layer[b], 0)
        cols[layer[b]] = row + 1
        pos[b] = (60 + layer[b] * 190, 60 + row * 120)
    return pos


def export_json(bd):
    pos = _auto_layout(bd)
    idx = {b: i for i, b in enumerate(bd.blocks)}
    blocks = []
    for b in bd.blocks:
        cls = type(b).__name__
        params = {}
        for p in _PARAMS.get(cls, []):
            v = getattr(b, p, None)
            params[p] = v
        if cls == "PyFunction" and b.expr is None:
            params["expr"] = None   # callable 은 뷰어에서 실행 불가 표시
        if cls == "Subsystem":
            params = dict(b.mask)   # 마스크 파라미터가 뷰어의 편집 대상
        entry = {
            "id": idx[b], "type": cls, "name": b.name,
            "n_in": b.n_in, "n_out": b.n_out,
            "params": params,
            "x": pos[b][0], "y": pos[b][1],
        }
        if cls == "Subsystem":
            entry["inner"] = export_json(b.inner)   # 재귀 — 내부 다이어그램
        blocks.append(entry)
    meta = getattr(bd, "_wire_meta", {})     # 뷰어의 수동 배선 꼭짓점 (load_json 이 채움)
    wires = []
    for d, s in bd.wires.items():
        w = {"src": [idx[s.block], s.index], "dst": [idx[d.block], d.index]}
        if d in meta:
            w["pts"] = meta[d]
        wires.append(w)
    return {"blocks": blocks, "wires": wires}


def save_json(bd, path):
    """모델을 JSON 파일로 저장 (뷰어의 '열기'와 호환)."""
    path = os.path.abspath(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(export_json(bd), f, ensure_ascii=False, indent=1)
    return path


def load_json(src):
    """JSON(경로/dict) → Diagram. export_json / 뷰어 '저장'의 역방향.

    주의: 파이썬에서 마스크는 생성 시점 치환이므로, JSON 의 "$이름" 문자열은
    Subsystem 생성 때 params 로 채워진다.
    """
    from . import blocks as _blocks
    from .core import Diagram

    if isinstance(src, str):
        with open(src, encoding="utf-8") as f:
            src = json.load(f)

    def build(j):
        d = Diagram()
        byid = {}
        for bj in j["blocks"]:
            cls_name, params = bj["type"], dict(bj.get("params") or {})
            if cls_name == "Subsystem":
                inner = build(bj["inner"])
                b = _blocks.Subsystem(inner, params=params or None, name=bj["name"])
            elif cls_name == "Inport":
                b = _blocks.Inport(params.get("index", 0), name=bj["name"])
            elif cls_name == "Outport":
                b = _blocks.Outport(params.get("index", 0), name=bj["name"])
            else:
                cls = getattr(_blocks, cls_name, None)
                if cls is None and cls_name.startswith("Ros2"):
                    from . import ros2 as _ros2
                    cls = getattr(_ros2, cls_name, None)
                if cls is None:
                    from . import drone as _drone
                    from .core import Block as _Block
                    cls = getattr(_drone, cls_name, None)
                    if not (isinstance(cls, type) and issubclass(cls, _Block)):
                        cls = None
                if cls is None:
                    raise ValueError(f"알 수 없는 블록 타입: {cls_name}")
                if cls_name == "PyFunction" and params.get("expr") is None:
                    raise ValueError(
                        f"'{bj['name']}': callable PyFunction 은 JSON 으로 복원 불가 — expr 문자열 사용")
                b = cls(name=bj["name"], **params)
            b._pos = (bj.get("x", 0), bj.get("y", 0))   # 뷰어 좌표 보존
            byid[bj["id"]] = d.add(b)
        d._wire_meta = {}                    # 수동 배선 좌표 보존 (엔진 의미론과 무관)
        for w in j["wires"]:
            s, ds = w["src"], w["dst"]
            d.connect(byid[s[0]][s[1]], byid[ds[0]][ds[1]])
            if w.get("pts"):
                d._wire_meta[Port(byid[ds[0]], ds[1])] = [list(p) for p in w["pts"]]
        return d

    return build(src)


# 뷰어에 심는 엔진 소스 — 뷰어의 Pyodide 가 이 파일들을 그대로 임포트해서 돌린다.
# (JS 시뮬 엔진 복제본은 2026-07 에 폐기: 실행은 파이썬 한 곳뿐, README 참조)
_ENGINE_FILES = ["__init__.py", "core.py", "blocks.py", "sim.py", "viz.py", "webapi.py",
                 "realtime.py", "ros2.py", "drone.py"]


def _engine_sources():
    here = os.path.dirname(__file__)
    out = {}
    for fname in _ENGINE_FILES:
        with open(os.path.join(here, fname), encoding="utf-8") as f:
            out[fname] = f.read()
    return out


def render_html(bd, path, title="loopsym viewer"):
    """모델을 심은 단독 HTML 파일을 만든다. 반환: 절대 경로."""
    template = os.path.join(os.path.dirname(__file__), "viewer.html")
    with open(template, encoding="utf-8") as f:
        html = f.read()
    model = json.dumps(export_json(bd), ensure_ascii=False)
    html = html.replace("/*__MODEL_JSON__*/null", model)
    # 엔진 소스 주입. "</" 는 "<\/" 로 — 소스 안의 문자열이 </script> 로 오인되는 것 방지
    sources = json.dumps(_engine_sources(), ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("/*__BLOCKSIM_SRC__*/null", sources)
    html = html.replace("__TITLE__", title)
    html = (
        "<!doctype html>\n<html lang=\"ko\">\n<head>\n"
        f"<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{title}</title>\n</head>\n<body>\n" + html + "\n</body>\n</html>\n"
    )
    path = os.path.abspath(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
