/**
 * test_e2e_orchestrator.js — 编排层端到端闭环回归（第 7 项联调沉淀）
 * 运行：node --test tests/test_e2e_orchestrator.js
 *
 * 覆盖"调用编排层 skill → DP 暂停 → 生成决策包 → 人类决策 → AI 继续"的核心闭环：
 * 1. 4 个条件 DP pending fixture（comps/income/cost/hypoth）可加载，各含一个 pending 条件 DP
 * 2. 人类驳回（comment 必填）→ buildSuccessorShell 建链骨架
 * 3. 编排层 AI 重写 successor 五段式（回应否决原因）+ 同步 riskLevel = risks 最高级（schema P0-7）
 * 4. 批准 successor → 更新数组 → validateChain（C1-C6）通过
 * 5. successor 的 supersedes/attempt 正确（4.2 决策链模型）
 */
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const DPCore = require("../app/js/dp-core.js");

const FIXTURES_DIR = path.join(__dirname, "fixtures");

const FIXTURES = [
  { file: "orchestrator_pending_comps.json", dpId: "DP-comp", baseId: "DP-comp" },
  { file: "orchestrator_pending_income.json", dpId: "DP-income", baseId: "DP-income" },
  { file: "orchestrator_pending_cost.json", dpId: "DP-cost", baseId: "DP-cost" },
  { file: "orchestrator_pending_hypoth.json", dpId: "DP-hypoth", baseId: "DP-hypoth" },
];

/** 编排层 AI 重写 successor：回应否决原因 + 同步 riskLevel（P0-7 约束） */
function aiRewriteSuccessor(shell) {
  const s = JSON.parse(JSON.stringify(shell));
  // 模拟 AI 回应否决原因：更新 conclusion/reasoning，风险收敛为 P2
  s.conclusion = "已按否决原因重写结论：" + (shell.conclusion || "").slice(0, 20) + "…";
  s.reasoning = "已回应否决原因重新说明理由（4.2 规则 5）";
  s.risks = [{ description: "重写后残余风险", level: "P2", mitigation: "继续监控" }];
  // P0-7：riskLevel 必须 = risks 最高等级
  s.riskLevel = "P2";
  return s;
}

/** 执行一次完整闭环：驳回 → 建链 → AI 重写 → 批准 → 返回新决策点数组 */
function runClosedLoop(data, dpId) {
  const dps = data.decisionPoints;
  const dp = dps.find((d) => d.id === dpId);
  assert.ok(dp, `fixture 应含 ${dpId}`);
  assert.strictEqual(dp.status, "pending", `${dpId} 应为 pending`);

  // 1. 人类驳回（comment 必填）
  const rej = DPCore.applyDecision(dp, "rejected", { decidedBy: "sun", comment: "测试否决原因" });
  assert.ok(rej.ok, `驳回应成功: ${rej.error}`);
  assert.strictEqual(rej.dp.status, "rejected");
  assert.ok(rej.dp.humanDecision.comment, "驳回必须记录否决原因");

  // 2. 建链骨架
  const shell = DPCore.buildSuccessorShell(dps, rej.dp);
  assert.ok(shell.ok, `建链应成功: ${shell.error}`);
  assert.strictEqual(shell.successor.supersedes, dpId);
  assert.strictEqual(shell.successor.attempt, 2);
  assert.strictEqual(shell.successor.status, "pending");
  assert.strictEqual(shell.successor.id, shell.successor.id.replace(/-\d+$/, "") + "-2");

  // 3. AI 重写（编排层职责）+ 4. 批准
  const rewritten = aiRewriteSuccessor(shell.successor);
  const appr = DPCore.applyDecision(rewritten, "approved", { decidedBy: "sun" });
  assert.ok(appr.ok, `批准应成功: ${appr.error}`);
  assert.strictEqual(appr.dp.status, "approved");
  assert.strictEqual(appr.dp.riskLevel, "P2", "AI 重写后 riskLevel 必须 = risks 最高级（P0-7）");

  // 5. 更新数组 + C1-C6 校验
  const newDps = dps.map((d) => (d.id === dpId ? rej.dp : d));
  newDps.push(appr.dp);
  const chainErr = DPCore.validateChain(newDps);
  assert.deepStrictEqual(chainErr, [], `C1-C6 应通过: ${JSON.stringify(chainErr)}`);
  return newDps;
}

test("4 个条件 DP fixture 均可加载且含 pending 条件 DP", () => {
  for (const fx of FIXTURES) {
    const data = JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, fx.file), "utf-8"));
    assert.strictEqual(data.schemaVersion, "1.5", `${fx.file} 应为 v1.5`);
    const dp = data.decisionPoints.find((d) => d.id === fx.dpId);
    assert.ok(dp, `${fx.file} 应含 ${fx.dpId}`);
    assert.strictEqual(dp.status, "pending");
    assert.strictEqual(dp.phase, "inMethod");
    assert.ok(dp.trigger.startsWith("method:"), "条件 DP 应使用 method: 触发");
    assert.ok(dp.evidence.length >= 1 && dp.risks.length >= 1, "决策包五段式应完整");
  }
});

test("comps 条件 DP 完整闭环：驳回→建链→重写→批准→C1-C6", () => {
  const data = JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, "orchestrator_pending_comps.json"), "utf-8"));
  const newDps = runClosedLoop(data, "DP-comp");
  const succ = newDps.find((d) => d.id === "DP-comp-2");
  assert.ok(succ, "应生成 DP-comp-2");
  assert.strictEqual(succ.supersedes, "DP-comp");
  assert.strictEqual(succ.attempt, 2);
});

test("income 条件 DP 完整闭环", () => {
  const data = JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, "orchestrator_pending_income.json"), "utf-8"));
  const newDps = runClosedLoop(data, "DP-income");
  assert.ok(newDps.find((d) => d.id === "DP-income-2"), "应生成 DP-income-2");
});

test("cost 条件 DP 完整闭环", () => {
  const data = JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, "orchestrator_pending_cost.json"), "utf-8"));
  const newDps = runClosedLoop(data, "DP-cost");
  assert.ok(newDps.find((d) => d.id === "DP-cost-2"), "应生成 DP-cost-2");
});

test("hypoth 条件 DP 完整闭环", () => {
  const data = JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, "orchestrator_pending_hypoth.json"), "utf-8"));
  const newDps = runClosedLoop(data, "DP-hypoth");
  assert.ok(newDps.find((d) => d.id === "DP-hypoth-2"), "应生成 DP-hypoth-2");
});
