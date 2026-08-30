/**
 * dp_chain_runner.js — resolveChain / buildSuccessorShell 的 Node 端执行器
 * 读 stdin: [{kind, dps, dpIndex, outsideDp?}, ...]
 * 写 stdout: [{kind, resolve: {...}, successor: {...}}, ...]
 *
 * 输出为规范形态（去 undefined、只留 id、错误归一为机器码），供 Python 参考实现
 * （tests/dp_chain_oracle.py）逐字段比对。用法: node dp_chain_runner.js < cases.json
 */
"use strict";
const DPCore = require("../app/js/dp-core.js");

function canonResolve(dps) {
  const r = DPCore.resolveChain(dps);
  return {
    byId: Object.keys(r.byId).sort(),
    roots: r.roots.slice(),
    chains: r.chains.map((chain) => chain.map((d) => (d && d.id !== undefined ? d.id : null))),
  };
}

function codeOf(err) {
  const s = String(err);
  if (s === "chain 必须是数组") { return "E_CHAIN_NOT_ARRAY"; }
  if (s === "dp 必须含 id") { return "E_DP_NO_ID"; }
  if (/（C3）/.test(s)) { return "C3"; }
  if (/（C4）/.test(s)) { return "C4"; }
  if (/（C5）/.test(s)) { return "C5"; }
  return "E_UNKNOWN:" + s;
}

function canonSuccessor(c) {
  const dp = Object.prototype.hasOwnProperty.call(c, "outsideDp") ? c.outsideDp : c.dps[c.dpIndex];
  const r = DPCore.buildSuccessorShell(c.dps, dp);
  if (!r.ok) { return { ok: false, code: codeOf(r.error), successor: null }; }
  return { ok: true, code: null, successor: JSON.parse(JSON.stringify(r.successor)) };
}

let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (d) => { raw += d; });
process.stdin.on("end", () => {
  const cases = JSON.parse(raw);
  const out = cases.map((c) => ({
    kind: c.kind,
    resolve: canonResolve(c.dps),
    successor: canonSuccessor(c),
  }));
  process.stdout.write(JSON.stringify(out));
});
