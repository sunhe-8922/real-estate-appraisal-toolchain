/**
 * chain_runner.js — Round 1 差分测试 Node 端执行器
 * 读 stdin: [{decisionPoints: [...]}, ...]
 * 写 stdout: [{violations: [类别...], errorCount: n}, ...]
 * 用法: node chain_runner.js < inputs.json
 */
"use strict";
const DPCore = require("../../app/js/dp-core.js");

let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (d) => { raw += d; });
process.stdin.on("end", () => {
  const inputs = JSON.parse(raw);
  const out = inputs.map((inp) => {
    const errs = DPCore.validateChain(inp.decisionPoints);
    const cats = new Set();
    errs.forEach((e) => {
      const m = String(e).match(/^C(\d):/);
      if (m) { cats.add("C" + m[1]); }
    });
    return { violations: Array.from(cats).sort(), errorCount: errs.length };
  });
  process.stdout.write(JSON.stringify(out));
});
