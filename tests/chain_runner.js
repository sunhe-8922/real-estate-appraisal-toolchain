/**
 * chain_runner.js — 双端决策链校验差分测试 Node 端执行器（唯一事实源）
 * 2026-08-30 自 rounds/1/chain_runner.js 迁入（审查 P2-2 解耦）。
 * 读 stdin: [{decisionPoints: [...]}, ...]
 * 写 stdout: [{violations: [类别...], errorCount: n}, ...]
 * 用法: node chain_runner.js < inputs.json
 */
"use strict";
const DPCore = require("../app/js/dp-core.js");

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
