/* viewer.html 스크립트를 node 에서 돌리기 위한 최소 DOM 스텁.
 * 파이썬↔JS 엔진 동기화 테스트(test_viewer_sync.py) 전용. */
function fakeEl(id) {
  const e = {
    id, children: [], style: {}, dataset: {}, value: "",
    className: "", textContent: "", placeholder: "", hidden: false, files: [],
    classList: { contains: () => false, add() {}, remove() {} },
    setAttribute() {}, removeAttribute() {},
    appendChild(c) { this.children.push(c); return c; },
    append() {}, remove() {}, closest() { return null; },
    addEventListener() {}, querySelector() { return fakeEl(); },
    showModal() {}, close() {}, click() {},
    _html: "",
  };
  Object.defineProperty(e, "innerHTML", {
    get() { return this._html; },
    set(v) { this._html = v; this.children = []; },
  });
  return e;
}
const byId = {};
globalThis.document = {
  getElementById(id) { if (!byId[id]) byId[id] = fakeEl(id); return byId[id]; },
  createElement: () => fakeEl(),
  createElementNS: () => fakeEl(),
  addEventListener() {},
  documentElement: fakeEl("root"),
};
globalThis.__byId = byId;
globalThis.MutationObserver = class { observe() {} };
globalThis.matchMedia = () => ({ addEventListener() {} });
globalThis.navigator = { clipboard: { writeText: async () => {} } };
globalThis.getComputedStyle = () => ({ getPropertyValue: () => "#000" });
globalThis.window = { devicePixelRatio: 1 };
globalThis.URL = { createObjectURL: () => "", revokeObjectURL() {} };
globalThis.Blob = class {};
