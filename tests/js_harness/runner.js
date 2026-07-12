/* stubs.js + (viewer.html 의 <script>) 뒤에 이어붙는 러너.
 * 환경변수 BS_MODEL(모델 JSON 경로), BS_TEND, BS_DT 를 읽어 runSim 을 돌리고
 * 각 Scope 의 마지막 값을 JSON 으로 stdout 에 낸다. */
drawScopes = (scopes) => { globalThis.__scopes = scopes; };
status = (m, c) => { globalThis.__status = [m, c || ""]; };

const fs = require("fs");
model = JSON.parse(fs.readFileSync(process.env.BS_MODEL, "utf-8"));
nextId = 0;
(function scan(m) { for (const b of m.blocks) { nextId = Math.max(nextId, b.id + 1); if (b.inner) scan(b.inner); } })(model);
path = [];
document.getElementById("inTend").value = process.env.BS_TEND || "10";
document.getElementById("inDt").value = process.env.BS_DT || "0.01";

runSim();

const out = {
  status: globalThis.__status,
  scopes: (globalThis.__scopes || []).map(s => ({
    disp: s.disp,
    t_last: s.t[s.t.length - 1],
    last: s.data.map(d => d[d.length - 1]),
  })),
};
process.stdout.write(JSON.stringify(out));
