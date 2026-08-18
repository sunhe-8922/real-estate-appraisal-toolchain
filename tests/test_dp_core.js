/**
 * test_dp_core.js — dp-core.js 单测（Node 内置 node:test）
 * 运行：node --test tests/test_dp_core.js
 * 覆盖：状态机转换、决策响应生成、驳回后自动建链、决策链校验 C1-C6、链解析
 */
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const DPCore = require("../app/js/dp-core.js");

/** 构造一个最小合法 pending 决策点 */
function makeDp(overrides) {
  const dp = {
    id: "DP-comp",
    name: "可比实例选取",
    phase: "inMethod",
    trigger: "method:comps",
    method: "comps",
    riskLevel: "P1",
    status: "pending",
    conclusion: "推荐选取实例 A/B/C",
    evidence: [{ item: "实例A 成交 25000 元/m²", source: "链家成交记录 (T1)" }],
    reasoning: "同小区、6 个月内成交",
    risks: [{ description: "实例 B 区位修正 18%", level: "P1", mitigation: "关注" }],
  };
  return Object.assign(dp, overrides || {});
}

// ── applyDecision: 状态机转换 ─────────────────────────────

test("applyDecision: approved 分支 → status=approved + humanDecision.action=approved", () => {
  const r = DPCore.applyDecision(makeDp(), "approved", { decidedBy: "sun", comment: "接受" });
  assert.ok(r.ok, r.error);
  assert.strictEqual(r.dp.status, "approved");
  assert.strictEqual(r.dp.humanDecision.action, "approved");
  assert.strictEqual(r.dp.humanDecision.decidedBy, "sun");
  assert.strictEqual(r.dp.humanDecision.comment, "接受");
  assert.ok(r.dp.humanDecision.timestamp);
});

test("applyDecision: modified 分支 → 必填 modifications（schema P0-2）", () => {
  const r = DPCore.applyDecision(makeDp(), "modified", { modifications: "实例 B 换为同小区 D" });
  assert.ok(r.ok, r.error);
  assert.strictEqual(r.dp.status, "modified");
  assert.strictEqual(r.dp.humanDecision.modifications, "实例 B 换为同小区 D");
});

test("applyDecision: modified 缺 modifications → 报错", () => {
  const r = DPCore.applyDecision(makeDp(), "modified", {});
  assert.strictEqual(r.ok, false);
  assert.ok(/modifications/.test(r.error));
});

test("applyDecision: modified 空白 modifications → 报错", () => {
  const r = DPCore.applyDecision(makeDp(), "modified", { modifications: "   " });
  assert.strictEqual(r.ok, false);
});

test("applyDecision: rejected 分支 → 必填 comment（否决原因）", () => {
  const r = DPCore.applyDecision(makeDp(), "rejected", { comment: "实例C信源T2不可靠" });
  assert.ok(r.ok, r.error);
  assert.strictEqual(r.dp.status, "rejected");
  assert.strictEqual(r.dp.humanDecision.action, "rejected");
});

test("applyDecision: rejected 缺 comment → 报错", () => {
  const r = DPCore.applyDecision(makeDp(), "rejected", {});
  assert.strictEqual(r.ok, false);
  assert.ok(/comment/.test(r.error));
});

test("applyDecision: 非 pending 状态不可重复决策", () => {
  const approved = Object.assign(makeDp(), { status: "approved" });
  const r = DPCore.applyDecision(approved, "rejected", { comment: "x" });
  assert.strictEqual(r.ok, false);
  assert.ok(/非 pending/.test(r.error));
});

test("applyDecision: 非法 action 报错", () => {
  const r = DPCore.applyDecision(makeDp(), "approve", {});
  assert.strictEqual(r.ok, false);
});

test("applyDecision: 不修改入参（返回副本）", () => {
  const dp = makeDp();
  const r = DPCore.applyDecision(dp, "approved", {});
  assert.strictEqual(dp.status, "pending"); // 入参不变
  assert.strictEqual(r.dp.status, "approved");
  assert.notStrictEqual(r.dp, dp);
});

// ── buildSuccessorShell: 驳回后自动建链 ───────────────────

test("buildSuccessorShell: rejected → 新 DP（supersedes + attempt=2 + status=pending）", () => {
  const chain = [makeDp({ id: "DP-comp", status: "rejected" })];
  const r = DPCore.buildSuccessorShell(chain, chain[0]);
  assert.ok(r.ok, r.error);
  const s = r.successor;
  assert.strictEqual(s.id, "DP-comp-2");
  assert.strictEqual(s.supersedes, "DP-comp");
  assert.strictEqual(s.attempt, 2);
  assert.strictEqual(s.status, "pending");
  assert.strictEqual(s.trigger, "method:comps");
  assert.strictEqual(s.method, "comps");
  assert.ok(!s.humanDecision, "新 DP 不应有人类决策记录");
});

test("buildSuccessorShell: 五段式占位复制（conclusion/reasoning 清空待 AI 重写）", () => {
  const chain = [makeDp({ id: "DP-comp", status: "rejected" })];
  const r = DPCore.buildSuccessorShell(chain, chain[0]);
  const s = r.successor;
  assert.strictEqual(s.conclusion, "", "conclusion 由 AI 重写回应否决原因（4.2 规则 5）");
  assert.strictEqual(s.reasoning, "");
  assert.strictEqual(s.evidence.length, 1, "evidence 占位复制");
  assert.strictEqual(s.risks.length, 1, "risks 占位复制");
});

test("buildSuccessorShell: 二次驳回 → DP-comp-3（attempt=3）", () => {
  const dp1 = makeDp({ id: "DP-comp", status: "rejected" });
  const dp2 = makeDp({ id: "DP-comp-2", status: "rejected", supersedes: "DP-comp", attempt: 2 });
  const chain = [dp1, dp2];
  const r = DPCore.buildSuccessorShell(chain, dp2);
  assert.ok(r.ok, r.error);
  assert.strictEqual(r.successor.id, "DP-comp-3");
  assert.strictEqual(r.successor.supersedes, "DP-comp-2");
  assert.strictEqual(r.successor.attempt, 3);
});

test("buildSuccessorShell: attempt 缺失视作 1（DP1 rejected → DP1-2）", () => {
  const dp1 = makeDp({ id: "DP1", name: "估价事项确认", phase: "preCalculation", trigger: "always", riskLevel: "P0", status: "rejected" });
  const r = DPCore.buildSuccessorShell([dp1], dp1);
  assert.ok(r.ok, r.error);
  assert.strictEqual(r.successor.id, "DP1-2");
  assert.strictEqual(r.successor.attempt, 2);
});

test("buildSuccessorShell: 仅 rejected 可被取代（C3）", () => {
  const dp = makeDp({ id: "DP-comp", status: "approved" });
  const r = DPCore.buildSuccessorShell([dp], dp);
  assert.strictEqual(r.ok, false);
  assert.ok(/仅 status=rejected/.test(r.error));
});

test("buildSuccessorShell: 防分叉（C4）", () => {
  const dp1 = makeDp({ id: "DP-comp", status: "rejected" });
  const dp2 = makeDp({ id: "DP-comp-2", status: "pending", supersedes: "DP-comp", attempt: 2 });
  const r = DPCore.buildSuccessorShell([dp1, dp2], dp1);
  assert.strictEqual(r.ok, false);
  assert.ok(/已有后继/.test(r.error));
});

test("buildSuccessorShell: 间接环场景由 C4 防分叉拦截（C5 独立验证见 validateChain）", () => {
  // a supersedes b + b supersedes a：对 a 建链时，b 已是 a 的直接后继 → C4 拦截。
  // 说明：环的最后一跳必然是"直接 supersedes 目标"的节点，故建链场景 C4 ⊃ C5；
  // C5 的独立验证由 validateChain（A↔B、A→B→C→A 两用例）覆盖。
  const a = makeDp({ id: "DP-a", status: "rejected", supersedes: "DP-b", attempt: 2 });
  const b = makeDp({ id: "DP-b", status: "rejected", supersedes: "DP-a", attempt: 2 });
  const r = DPCore.buildSuccessorShell([a, b], a);
  assert.strictEqual(r.ok, false);
  assert.ok(/已有后继/.test(r.error));
});

// ── validateChain: C1-C6 校验 ─────────────────────────────

test("validateChain: 合法链通过（示例数据 DP-comp → DP-comp-2）", () => {
  const dp1 = makeDp({ id: "DP-comp", status: "rejected" });
  const dp2 = makeDp({ id: "DP-comp-2", status: "approved", supersedes: "DP-comp", attempt: 2 });
  assert.deepStrictEqual(DPCore.validateChain([dp1, dp2]), []);
});

test("validateChain: C1 引用不存在的 id", () => {
  const dp = makeDp({ id: "DP-comp-2", status: "pending", supersedes: "DP-nonexist", attempt: 2 });
  const errors = DPCore.validateChain([dp]);
  assert.ok(errors.some((e) => /C1/.test(e)));
});

test("validateChain: C2 自引用", () => {
  const dp = makeDp({ id: "DP-comp", status: "pending", supersedes: "DP-comp" });
  const errors = DPCore.validateChain([dp]);
  assert.ok(errors.some((e) => /C2/.test(e)));
});

test("validateChain: C3 取代非 rejected 的 DP", () => {
  const dp1 = makeDp({ id: "DP-comp", status: "approved" });
  const dp2 = makeDp({ id: "DP-comp-2", status: "pending", supersedes: "DP-comp", attempt: 2 });
  const errors = DPCore.validateChain([dp1, dp2]);
  assert.ok(errors.some((e) => /C3/.test(e)));
});

test("validateChain: C4 分叉（同一 DP 被两个后继取代）", () => {
  const dp1 = makeDp({ id: "DP-comp", status: "rejected" });
  const dp2 = makeDp({ id: "DP-comp-2", status: "pending", supersedes: "DP-comp", attempt: 2 });
  const dp3 = makeDp({ id: "DP-comp-2b", status: "pending", supersedes: "DP-comp", attempt: 2 });
  const errors = DPCore.validateChain([dp1, dp2, dp3]);
  assert.ok(errors.some((e) => /C4/.test(e)));
});

test("validateChain: C5 成环（A→B→A）", () => {
  const a = makeDp({ id: "DP-a", status: "rejected", supersedes: "DP-b", attempt: 2 });
  const b = makeDp({ id: "DP-b", status: "rejected", supersedes: "DP-a", attempt: 2 });
  const errors = DPCore.validateChain([a, b]);
  assert.ok(errors.some((e) => /C5/.test(e)));
});

test("validateChain: C5 成环（三节点 A→B→C→A）", () => {
  const a = makeDp({ id: "DP-a", status: "rejected", supersedes: "DP-c", attempt: 2 });
  const b = makeDp({ id: "DP-b", status: "rejected", supersedes: "DP-a", attempt: 2 });
  const c = makeDp({ id: "DP-c", status: "rejected", supersedes: "DP-b", attempt: 2 });
  const errors = DPCore.validateChain([a, b, c]);
  assert.ok(errors.some((e) => /C5/.test(e)));
});

test("validateChain: C6 attempt 不一致", () => {
  const dp1 = makeDp({ id: "DP-comp", status: "rejected" });
  const dp2 = makeDp({ id: "DP-comp-2", status: "pending", supersedes: "DP-comp", attempt: 3 });
  const errors = DPCore.validateChain([dp1, dp2]);
  assert.ok(errors.some((e) => /C6/.test(e)));
});

test("validateChain: 独立多 DP + 无 supersedes → 通过", () => {
  const dps = [
    makeDp({ id: "DP1", phase: "preCalculation", trigger: "always", status: "approved" }),
    makeDp({ id: "DP-comp", status: "approved" }),
    makeDp({ id: "DP3", phase: "postMethod", trigger: "always", status: "pending" }),
  ];
  assert.deepStrictEqual(DPCore.validateChain(dps), []);
});

// ── resolveChain: 决策链解析 ──────────────────────────────

test("resolveChain: 按 supersedes 分组为链", () => {
  const dp1 = makeDp({ id: "DP-comp", status: "rejected" });
  const dp2 = makeDp({ id: "DP-comp-2", status: "approved", supersedes: "DP-comp", attempt: 2 });
  const dp3 = makeDp({ id: "DP-income", status: "approved" });
  const out = DPCore.resolveChain([dp1, dp2, dp3]);
  assert.deepStrictEqual(out.roots.sort(), ["DP-comp", "DP-income"]);
  assert.strictEqual(out.chains.length, 1, "仅 supersedes 链 ≥2 的链展示");
  assert.deepStrictEqual(out.chains[0].map((d) => d.id), ["DP-comp", "DP-comp-2"]);
});

// ── 端到端：真实示例数据决策链通过校验 ────────────────────

test("端到端: 示例数据 example-武汉洪山住宅.json 决策链通过 C1-C6", () => {
  const p = path.join(__dirname, "..", "schema", "example-武汉洪山住宅.json");
  const data = JSON.parse(fs.readFileSync(p, "utf-8"));
  assert.ok(Array.isArray(data.decisionPoints));
  assert.strictEqual(data.schemaVersion, "1.4");
  const errors = DPCore.validateChain(data.decisionPoints);
  assert.deepStrictEqual(errors, []);
  // 驳回链演示正确性：DP-comp rejected → DP-comp-2 approved（supersedes + attempt=2）
  const byId = {};
  data.decisionPoints.forEach((d) => (byId[d.id] = d));
  assert.strictEqual(byId["DP-comp"].status, "rejected");
  assert.strictEqual(byId["DP-comp-2"].supersedes, "DP-comp");
  assert.strictEqual(byId["DP-comp-2"].attempt, 2);
  assert.strictEqual(byId["DP-comp-2"].status, "approved");
});
