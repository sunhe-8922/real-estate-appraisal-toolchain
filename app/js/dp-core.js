/**
 * dp-core.js — 人工决策点（Decision Point）核心逻辑库
 *
 * 决策点管理放在编排层（appraisal-orchestrator skill + dp-console.html），
 * 本文件是共享纯逻辑：状态机转换、决策响应生成、驳回后自动建链、决策链校验与解析。
 *
 * 规范依据：
 * - 《决策点规格定义.md》1.3 人类决策动作语义 / 第四章 决策链模型（P2-2 决策）
 * - schema/appraisal-result.schema.json v1.4（decisionPoint 定义 + supersedes/attempt）
 * - scripts/validate_appraisal_json.py `_check_decision_chain()`（C1-C6 权威校验，
 *   本文件的 validateChain 是 JS 等价实现，用于前端即时校验与测试，不替代 Python 端）
 *
 * 双模：浏览器（window.DPCore）/ Node（module.exports）
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.DPCore = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const ACTIONS = ["approved", "modified", "rejected"];
  const STATUSES = ["pending", "approved", "modified", "rejected"];

  /** 终结状态：approved / modified（rejected 为非终结，触发新 DP） */
  function isTerminal(status) {
    return status === "approved" || status === "modified";
  }

  /**
   * 应用人类决策到决策点（状态机转换）。
   * @param {object} dp 决策点对象（将返回副本，不修改入参）
   * @param {string} action approved | modified | rejected
   * @param {object} opts { decidedBy, comment, modifications, timestamp }
   * @returns {{ok: boolean, dp?: object, error?: string}}
   */
  function applyDecision(dp, action, opts) {
    if (!dp || typeof dp !== "object") {
      return { ok: false, error: "dp 必须是对象" };
    }
    if (ACTIONS.indexOf(action) === -1) {
      return { ok: false, error: "action 必须是 approved / modified / rejected" };
    }
    if (dp.status !== "pending") {
      return { ok: false, error: `status=${dp.status} 非 pending，决策已定，不可重复决策` };
    }
    opts = opts || {};
    const humanDecision = {
      action: action,
      decidedBy: opts.decidedBy || "估价师",
      timestamp: opts.timestamp || new Date().toISOString(),
    };
    if (opts.comment !== undefined && opts.comment !== null && String(opts.comment).trim() !== "") {
      humanDecision.comment = String(opts.comment).trim();
    }
    if (action === "modified") {
      // 规格 1.3：调整必填 modifications（schema P0-2 约束）
      const mods = opts.modifications === undefined ? "" : String(opts.modifications).trim();
      if (mods === "") {
        return { ok: false, error: "action=modified 必须填写 modifications（schema P0-2）" };
      }
      humanDecision.modifications = mods;
    }
    if (action === "rejected") {
      // 编排协议强化：驳回必填 comment（否决原因是建链回应与 AI 学习信号）
      const cm = opts.comment === undefined ? "" : String(opts.comment).trim();
      if (cm === "") {
        return { ok: false, error: "action=rejected 必须填写 comment（否决原因，决策链模型 4.2 要求回应）" };
      }
    }
    const out = JSON.parse(JSON.stringify(dp));
    out.status = action; // status 与 action 一致（schema P0-6a/b/c）
    out.humanDecision = humanDecision;
    return { ok: true, dp: out };
  }

  /**
   * 提取决策链基础 id：去掉尾部 `-N` 序号（DP-comp-2 → DP-comp；DP1 → DP1）。
   */
  function baseIdOf(id) {
    return String(id).replace(/-\d+$/, "");
  }

  /**
   * 计算下一个尝试序号：被取代 DP 的 attempt（缺失或非法【非 number / <1】视作 1）+ 1（决策链模型 4.2 规则 4）。
   */
  function nextAttempt(dp) {
    const prev = dp && typeof dp.attempt === "number" && dp.attempt >= 1 ? dp.attempt : 1;
    return prev + 1;
  }

  /**
   * 驳回后自动建链：生成新 DP 骨架（决策链模型 4.2）。
   * 旧 DP（rejected）保留为不可变审计记录；新 DP 通过 supersedes 指向旧 DP、attempt 递增。
   *
   * 注意：本函数只生成"骨架"——status=pending、五段式字段从旧 DP 复制为占位。
   * 真正的内容（conclusion/evidence/reasoning/risks/comparison）必须由编排层 AI
   * 重写以回应否决原因（决策链模型 4.2 规则 5）。前端仅用于预览。
   *
   * @param {Array} chain 当前 decisionPoints 数组（含被驳回的 dp）
   * @param {object} dp 被驳回的决策点（status 应为 rejected）
   * @returns {{ok: boolean, successor?: object, error?: string}}
   */
  function buildSuccessorShell(chain, dp) {
    if (!Array.isArray(chain)) {
      return { ok: false, error: "chain 必须是数组" };
    }
    if (!dp || typeof dp !== "object" || typeof dp.id !== "string") {
      return { ok: false, error: "dp 必须含 id" };
    }
    if (dp.status !== "rejected") {
      return { ok: false, error: `仅 status=rejected 的 DP 可被取代（C3），当前 status=${dp.status}` };
    }
    const others = chain.filter(function (d) { return d && d.id !== dp.id; });
    // C4: 1:1 后继（防分叉）
    const forks = others.filter(function (d) { return d.supersedes === dp.id; });
    if (forks.length > 0) {
      return { ok: false, error: `DP ${dp.id} 已有后继 ${forks[0].id}，1:1 后继防分叉（C4）` };
    }
    // C5: 不得成环 — 新 DP supersedes 指向 dp，dp 沿其 supersedes 链不得回到自身
    let cursor = dp;
    const seen = {};
    while (cursor && cursor.supersedes) {
      if (cursor.supersedes === dp.id) {
        return { ok: false, error: `建链将成环（${dp.id} 沿 supersedes 链回到自身）（C5）` };
      }
      seen[cursor.supersedes] = true;
      cursor = chain.find(function (d) { return d && d.id === cursor.supersedes; });
    }
    const base = baseIdOf(dp.id);
    const attempt = nextAttempt(dp);
    const successor = {
      id: base + "-" + attempt,
      name: dp.name,
      phase: dp.phase,
      trigger: dp.trigger,
      riskLevel: dp.riskLevel,
      status: "pending",
      supersedes: dp.id,
      attempt: attempt,
      // 五段式占位：由编排层 AI 重写以回应否决原因（4.2 规则 5）
      conclusion: "", // TODO(AI): 更新结论，回应否决原因
      evidence: dp.evidence ? JSON.parse(JSON.stringify(dp.evidence)) : [],
      reasoning: "", // TODO(AI): 重新说明理由
      risks: dp.risks ? JSON.parse(JSON.stringify(dp.risks)) : [],
    };
    if (dp.method) { successor.method = dp.method; }
    if (Array.isArray(dp.comparison)) { successor.comparison = JSON.parse(JSON.stringify(dp.comparison)); }
    return { ok: true, successor: successor };
  }

  /**
   * 决策链校验（JS 版 C1-C6，与 validate_appraisal_json.py 语义一致）。
   * 内部以 {code, message} 结构生成：code 供机器比对（Round 6 / P1-1 ④，
   * 结构化导出后不再从消息文本解析码——含冒号的 key 不再有歧义），message 供人类阅读。
   * @returns {{code: string|null, message: string}[]}
   */
  function validateChainEntries(decisionPoints) {
    const entries = [];
    if (!Array.isArray(decisionPoints)) {
      return [{ code: null, message: "decisionPoints 必须是数组" }];
    }
    // 码层 key 哨兵（与 Python _code_key 同构，P1-1）：非字符串 id 统一 <no-id>
    const codeKey = function (id) { return typeof id === "string" ? id : "<no-id>"; };
    const byId = {};
    decisionPoints.forEach(function (d) { if (d && typeof d.id === "string") { byId[d.id] = d; } });
    const sups = decisionPoints.filter(function (d) { return d && typeof d.supersedes === "string"; });

    sups.forEach(function (d) {
      // C1: 存在性
      if (!byId[d.supersedes]) {
        entries.push({ code: `C1:key=${d.supersedes}`,
          message: `C1:key=${d.supersedes}: ${d.id} 的 supersedes 引用不存在的 id "${d.supersedes}"` });
        return;
      }
      // C2: 不自引用
      if (d.supersedes === d.id) {
        entries.push({ code: `C2:key=${codeKey(d.id)}`,
          message: `C2:key=${d.id}: ${d.id} 不得自引用 supersedes` });
        return;
      }
      // C3: 被取代者必须 rejected
      if (byId[d.supersedes].status !== "rejected") {
        entries.push({ code: `C3:key=${d.supersedes}`,
          message: `C3:key=${d.supersedes}: ${d.id} 取代的 ${d.supersedes} 状态为 ${byId[d.supersedes].status}，仅 rejected 可被取代` });
      }
    });
    // C4: 1:1 后继
    const counted = {};
    sups.forEach(function (d) {
      counted[d.supersedes] = (counted[d.supersedes] || 0) + 1;
    });
    Object.keys(counted).forEach(function (key) {
      // ghost key（指向不存在 id，C1 已报）不进 C4——与 Python 端对齐（Round 4 修复）
      if (counted[key] > 1 && byId[key]) {
        entries.push({ code: `C4:key=${key}`,
          message: `C4:key=${key}: ${key} 被 ${counted[key]} 个 DP 取代，决策链必须 1:1（防分叉）` });
      }
    });
    // C5: 无环
    decisionPoints.forEach(function (dp) {
      if (!dp || typeof dp.id !== "string") { return; }
      // C2 已报自引用：自引用即最短环，跳过以免重复归因（与 Python 端语义一致）
      if (typeof dp.supersedes === "string" && dp.supersedes === dp.id) { return; }
      let cursor = dp;
      const visited = {};
      while (cursor && typeof cursor.supersedes === "string") {
        if (cursor.supersedes === dp.id) {
          entries.push({ code: `C5:key=${dp.id}`,
            message: `C5:key=${dp.id}: 决策链成环（${dp.id} 沿 supersedes 链回到自身）` });
          break;
        }
        if (visited[cursor.supersedes]) { break; } // 已检测过，避免死循环
        visited[cursor.supersedes] = true;
        cursor = byId[cursor.supersedes];
        if (!cursor) { break; }
      }
    });
    // C6: attempt 一致性（若提供，须 = 前驱 attempt+1）
    sups.forEach(function (d) {
      // C2 已报自引用：自引用时 attempt 自推无意义，跳过（与 Python 端语义一致）
      if (d.supersedes === d.id) { return; }
      if (typeof d.attempt === "number" && byId[d.supersedes]) {
        const expect = nextAttempt(byId[d.supersedes]);
        if (d.attempt !== expect) {
          entries.push({ code: `C6:key=${codeKey(d.id)}`,
            message: `C6:key=${d.id}: ${d.id} attempt=${d.attempt}，前驱 ${d.supersedes} 应推导 ${expect}` });
        }
      }
    });
    return entries;
  }

  /**
   * 决策链校验（JS 版 C1-C6，与 validate_appraisal_json.py 语义一致）。
   * @returns {string[]} 违规描述数组（空 = 通过）
   */
  function validateChain(decisionPoints) {
    return validateChainEntries(decisionPoints).map(function (e) { return e.message; });
  }

  /**
   * 决策链校验——机器码视图（Round 6 / 假设池 #6 落地）。
   * @returns {string[]} 违规码数组，形如 "C4:key=DP-comp"（含冒号的 key 原样保留）
   */
  function validateChainCodes(decisionPoints) {
    return validateChainEntries(decisionPoints).map(function (e) { return e.code; });
  }

  /**
   * 解析决策链：按 supersedes 分组为链（前端决策链可视化用）。
   * @returns {{byId: object, roots: string[], chains: object[][]}}
   *   byId: id → DP；roots: 无 supersedes 的 DP id（链起点）；
   *   chains: 每条链从前驱到后继的有序数组（仅含 supersedes 链 ≥2 的链）
   */
  function resolveChain(decisionPoints) {
    const byId = {};
    const out = { byId: byId, roots: [], chains: [] };
    if (!Array.isArray(decisionPoints)) { return out; }
    decisionPoints.forEach(function (d) { if (d && typeof d.id === "string") { byId[d.id] = d; } });
    // roots = 链起点（无 supersedes 的最老 DP）；链方向：旧 → 新
    out.roots = Object.keys(byId).filter(function (id) { return !byId[id].supersedes; });
    // 从每个 root 沿"后继"（supersedes 指向它的 DP）方向走，收集链（长度 ≥2 才展示为链）
    out.roots.forEach(function (rootId) {
      const chain = [byId[rootId]];
      const seen = {};
      seen[rootId] = true;
      let cursor = byId[rootId];
      for (;;) {
        const next = decisionPoints.find(function (d) {
          return d && d.supersedes === cursor.id && !seen[d.id];
        });
        if (!next) { break; }
        chain.push(next);
        seen[next.id] = true;
        cursor = next;
      }
      if (chain.length >= 2) { out.chains.push(chain); }
    });
    return out;
  }

  return {
    ACTIONS: ACTIONS,
    STATUSES: STATUSES,
    isTerminal: isTerminal,
    applyDecision: applyDecision,
    baseIdOf: baseIdOf,
    nextAttempt: nextAttempt,
    buildSuccessorShell: buildSuccessorShell,
    validateChain: validateChain,
    validateChainCodes: validateChainCodes,
    resolveChain: resolveChain,
  };
});
