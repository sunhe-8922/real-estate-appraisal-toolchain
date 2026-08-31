/**
 * dp_action_runner.js — applyDecision / isTerminal 的 Node 端执行器（Round 7）
 * 读 stdin: [{kind, dp, action, status, opts?}, ...]
 * 写 stdout: [{kind, terminal: bool, apply: {ok, code, dp}}, ...]
 *
 * 规范化：① 错误归一为机器码 ② 缺 opts.timestamp 时删掉自动时间戳（不可复现）
 * 用法: node dp_action_runner.js < cases.json
 */
"use strict";
const DPCore = require("../app/js/dp-core.js");

function codeOf(err) {
  const s = String(err);
  if (s === "dp 必须是对象") { return "E_DP_NOT_OBJECT"; }
  if (/action 必须是/.test(s)) { return "E_BAD_ACTION"; }
  if (/不可重复决策/.test(s)) { return "E_NOT_PENDING"; }
  if (/必须填写 modifications/.test(s)) { return "E_MODIFIED_REQUIRES_MODIFICATIONS"; }
  if (/必须填写 comment/.test(s)) { return "E_REJECTED_REQUIRES_COMMENT"; }
  return "E_UNKNOWN:" + s;
}

let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (d) => { raw += d; });
process.stdin.on("end", () => {
  const cases = JSON.parse(raw);
  const out = cases.map((c) => {
    const hasOpts = Object.prototype.hasOwnProperty.call(c, "opts");
    const opts = hasOpts ? c.opts : undefined;
    const hasTs = !!(opts && Object.prototype.hasOwnProperty.call(opts, "timestamp"));
    const r = DPCore.applyDecision(c.dp, c.action, opts);
    const apply = { ok: r.ok, code: r.ok ? null : codeOf(r.error), dp: null };
    if (r.ok) {
      const dp = JSON.parse(JSON.stringify(r.dp));
      if (!hasTs && dp.humanDecision) { delete dp.humanDecision.timestamp; }
      apply.dp = dp;
    }
    return { kind: c.kind, terminal: DPCore.isTerminal(c.status), apply: apply };
  });
  process.stdout.write(JSON.stringify(out));
});
