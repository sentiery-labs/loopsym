// Pyodide 스모크 하니스 — node + pyodide(npm) 로 뷰어와 같은 경로를 헤드리스 실행.
// 뷰어의 initEngine() 과 동일하게: 엔진 소스를 FS 에 쓰고 run_simulation 을 부른다.
// 입력(환경변수): BS_SRC_DIR = blocksim/ 폴더, BS_CASES = 케이스 JSON 파일
//   케이스: [{ name, model, t_end, dt }, ...]
// 출력(stdout): [{ name, result }, ...]  (result = run_simulation 반환 객체)
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { loadPyodide } from "pyodide";

const srcDir = process.env.BS_SRC_DIR;
const cases = JSON.parse(readFileSync(process.env.BS_CASES, "utf-8"));

const py = await loadPyodide();
py.FS.mkdirTree("/app/blocksim");
for (const f of ["__init__.py", "core.py", "blocks.py", "sim.py", "viz.py", "webapi.py", "realtime.py", "ros2.py"])
  py.FS.writeFile("/app/blocksim/" + f, readFileSync(join(srcDir, f), "utf-8"));
py.runPython('import sys; sys.path.insert(0, "/app")');
const run = py.runPython("from blocksim.webapi import run_simulation; run_simulation");

const out = [];
for (const c of cases)
  out.push({ name: c.name, result: JSON.parse(run(JSON.stringify(c.model), c.t_end, c.dt)) });
console.log(JSON.stringify(out));
