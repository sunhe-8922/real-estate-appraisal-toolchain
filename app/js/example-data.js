// 内嵌演示数据（决策包控制台默认示例）——源自 schema/example-武汉洪山住宅.json 决策链部分
window.EXAMPLE_DATA = {
 "schemaVersion": "1.4",
 "project": {
  "name": "武汉市洪山区珞狮路某小区3栋2单元1804室住宅房地产抵押估价",
  "purpose": "为确定抵押贷款额度提供参考依据而评估房地产抵押价值",
  "client": "××银行股份有限公司武汉分行",
  "agency": "××房地产土地资产评估有限公司",
  "appraiser": {
   "name": "张××",
   "registrationNumber": "××××××"
  },
  "coAppraiser": {
   "name": "李××",
   "registrationNumber": "××××××"
  },
  "reportDate": "2026-08-03",
  "reportNumber": "××房估字〔2026〕第0817号"
 },
 "property": {
  "area": 128.5,
  "usage": "住宅",
  "address": "武汉市洪山区珞狮路某小区3栋2单元1804室",
  "propertyType": "商品房",
  "completionYear": 2018,
  "remainingUsefulLife": 59.5,
  "landUseRightYears": 58.3,
  "floor": "18/33层",
  "orientation": "南向",
  "decoration": "精装修",
  "ownershipType": "出让"
 },
 "valuation": {
  "valueDate": "2026-08-01",
  "valueType": "抵押价值（等于市场价值）",
  "currency": "CNY"
 },
 "decisionPoints": [
  {
   "id": "DP1",
   "name": "估价事项确认",
   "phase": "preCalculation",
   "trigger": "always",
   "riskLevel": "P0",
   "status": "approved",
   "conclusion": "估价目的为抵押估价，价值类型为抵押价值（等于市场价值），价值时点 2026-08-01，估价对象为武汉市洪山区珞狮路某小区3栋2单元1804室住宅房地产",
   "evidence": [
    {
     "item": "委托合同明确估价目的：为确定抵押贷款额度提供参考依据而评估房地产抵押价值",
     "source": "委托合同 (T0)"
    },
    {
     "item": "产权证载明用途为住宅，建筑面积 128.50 m²",
     "source": "不动产权证 (T0)"
    },
    {
     "item": "估价对象为商品房，2018年竣工，剩余经济寿命 59.5 年",
     "source": "竣工验收备案表 (T0)"
    }
   ],
   "reasoning": "抵押估价要求评估市场价值，价值时点为估价作业期日。估价对象为住宅，交易活跃，适合比较法和收益法。",
   "risks": [
    {
     "description": "附属面积（阳台/飘窗）是否计入建筑面积需核实",
     "level": "P0",
     "mitigation": "以不动产权证记载为准"
    }
   ],
   "humanDecision": {
    "action": "approved",
    "decidedBy": "张××",
    "timestamp": "2026-08-01T09:30:00+08:00"
   }
  },
  {
   "id": "DP2",
   "name": "测算方案确认",
   "phase": "preCalculation",
   "trigger": "always",
   "riskLevel": "P1",
   "status": "approved",
   "conclusion": "采用比较法（权重60%）+ 收益法（权重40%）双方法测算，不采用成本法和假设开发法",
   "evidence": [
    {
     "item": "估价对象所在区域住宅交易活跃，可比实例成交时间均在2个月内",
     "source": "链家/贝壳成交数据 (T1)"
    },
    {
     "item": "估价对象存在租赁市场，可获取租金数据",
     "source": "区域租赁调研 (T1)"
    },
    {
     "item": "估价对象为已建成住宅，非待开发土地，不适用假设开发法",
     "source": "现场查勘 (T0)"
    }
   ],
   "reasoning": "住宅房地产交易活跃，比较法为首选方法。收益法作为辅助验证，采用直接资本化法。成本法对商品房适用性差（土地取得成本难以分离），假设开发法不适用。",
   "risks": [
    {
     "description": "收益法权重40%可能偏高，住宅市场租金回报率偏低时收益法结果偏离市场价",
     "level": "P1",
     "mitigation": "权重已设为40%作为辅助验证，最终以比较法为主导"
    }
   ],
   "humanDecision": {
    "action": "approved",
    "decidedBy": "张××",
    "timestamp": "2026-08-01T10:15:00+08:00"
   }
  },
  {
   "id": "DP-comp",
   "name": "可比实例选取",
   "phase": "inMethod",
   "trigger": "method:comps",
   "method": "comps",
   "riskLevel": "P1",
   "status": "rejected",
   "conclusion": "推荐选取实例 A/B/C，均为洪山区珞狮路同区域住宅，成交时间 2026-05 至 2026-06，与估价对象可比性良好",
   "evidence": [
    {
     "item": "实例 A：珞狮路1号小区，125.0 m²，成交 2026-05-15，单价 25000 元/m²",
     "source": "链家成交记录 (T1)"
    },
    {
     "item": "实例 B：珞狮路2号小区，130.0 m²，成交 2026-06-10，单价 26000 元/m²",
     "source": "贝壳成交记录 (T1)"
    },
    {
     "item": "实例 C：珞狮路3号小区，127.0 m²，成交 2026-06-20，单价 25500 元/m²",
     "source": "链家成交记录 (T1)"
    }
   ],
   "reasoning": "三个实例均在估价对象同一街区，成交时间距价值时点不超过77天，面积差异在5 m²以内，均为商品房住宅。单项修正幅度最大3.1%（实物状况），综合修正幅度最大3.1%，远低于20%/30%红线。最高价/最低价比 1.031，远低于1.2红线。",
   "risks": [
    {
     "description": "三个实例均来自线上平台，缺少线下实际成交核实",
     "level": "P1",
     "mitigation": "已交叉比对链家和贝壳数据，价格趋势一致"
    },
    {
     "description": "实例 B 面积 130 m² 比估价对象大 1.5 m²，建筑规模修正系数 102",
     "level": "P2",
     "mitigation": "已在实物状况修正中体现"
    }
   ],
   "comparison": [
    {
     "instance": "A",
     "differences": "不同小区（珞狮路1号小区 vs 估价对象所在小区），面积差 3.5 m²（125.0 vs 128.5，建筑规模修正指数 97），区位距重要场所距离优于估价对象（修正指数 102）"
    },
    {
     "instance": "B",
     "differences": "不同小区（珞狮路2号小区），面积差 1.5 m²（130.0 vs 128.5，建筑规模修正指数 102），区位距重要场所距离优于估价对象（修正指数 101）"
    },
    {
     "instance": "C",
     "differences": "不同小区（珞狮路3号小区），面积差 1.5 m²（127.0 vs 128.5，建筑规模修正指数 99），区位距重要场所距离逊于估价对象（修正指数 98）"
    }
   ],
   "humanDecision": {
    "action": "rejected",
    "decidedBy": "张××",
    "timestamp": "2026-08-01T14:05:00+08:00",
    "comment": "实例 C（珞狮路3号小区）区位距重要场所距离明显逊于估价对象，修正指数 98 超出可接受范围，可比性不足；请更换实例后重新提交。"
   }
  },
  {
   "id": "DP-income",
   "name": "收益率确定",
   "phase": "inMethod",
   "trigger": "method:income",
   "method": "income",
   "riskLevel": "P1",
   "status": "approved",
   "conclusion": "收益率（资本化率）取 1.5%，采用市场提取法，来源为同区域同类住宅租金回报率中位数",
   "evidence": [
    {
     "item": "洪山区珞狮路周边住宅租金回报率采样：1.2%-1.8%，中位数 1.5%",
     "source": "区域租赁市场调研 (T1)"
    },
    {
     "item": "采样样本 12 套，面积区间 110-140 m²，与估价对象可比",
     "source": "链家/自如租赁数据 (T1)"
    },
    {
     "item": "央行一年期 LPR 3.35%，住宅租金回报率低于无风险利率属市场常态",
     "source": "中国人民银行公告 (T0)"
    }
   ],
   "reasoning": "市场提取法直接反映估价对象所在区域的实际收益水平。1.5% 的资本化率虽然低于无风险利率，但住宅市场租金回报率偏低是武汉当前市场特征，非数据错误。报酬资本化法全剩余寿命模式（59.5年折现）测算结果约146万元，严重低估住宅资产价值，故采用直接资本化法。",
   "risks": [
    {
     "description": "1.5% 资本化率偏低，可能导致收益法结果偏离市场比较法",
     "level": "P1",
     "mitigation": "已设收益法权重40%作为辅助验证，两方法差异3.3%收敛良好"
    },
    {
     "description": "租金数据来自线上平台，实际成交租金可能有偏差",
     "level": "P2",
     "mitigation": "已对 3 套样本进行线下中介核实"
    }
   ],
   "humanDecision": {
    "action": "approved",
    "decidedBy": "张××",
    "timestamp": "2026-08-01T15:30:00+08:00"
   }
  },
  {
   "id": "DP3",
   "name": "测算结果审核",
   "phase": "postMethod",
   "trigger": "always",
   "riskLevel": "P1",
   "status": "approved",
   "conclusion": "最终评估总价 327万元（3271720元），单价 25461 元/m²。比较法331万、收益法321万，两方法差异3.3%，收敛良好",
   "evidence": [
    {
     "item": "比较法结果：总价 3314015 元，单价 25790 元/m²",
     "source": "测算表-比较法 (T0)"
    },
    {
     "item": "收益法结果：总价 3208267 元，单价 24967 元/m²",
     "source": "测算表-收益法 (T0)"
    },
    {
     "item": "两方法差异比 1.033，低于10%预警线",
     "source": "交叉验证 (T0)"
    },
    {
     "item": "全部红线检查通过：可比实例≥3、成交≤2年、单项修正≤20%、综合修正≤30%、最高/最低价比≤1.2",
     "source": "红线检查表 (T0)"
    }
   ],
   "reasoning": "两方法结果差异3.3%，在合理范围内。比较法权重60%反映了住宅交易活跃的市场特征。收益法略低是因为当前租金回报率偏低，资本化率取值保守。加权平均结果327万元合理反映了估价对象的市场价值。",
   "risks": [
    {
     "description": "最终单价 25461 元/m² 略低于可比实例成交单价区间 25000-26000 元/m²，需确认是否合理",
     "level": "P1",
     "mitigation": "修正后的比准单价区间 25490-26283 元/m²，加权后 25790 元/m²，收益法拉低了最终结果"
    }
   ],
   "humanDecision": {
    "action": "approved",
    "decidedBy": "张××",
    "timestamp": "2026-08-02T09:00:00+08:00"
   }
  },
  {
   "id": "DP4",
   "name": "报告签发",
   "phase": "postReport",
   "trigger": "always",
   "riskLevel": "P0",
   "status": "approved",
   "conclusion": "报告经审核合格，准予签发。报告编号 ××房估字〔2026〕第0817号",
   "evidence": [
    {
     "item": "报告全文已完成三级审核：估价师自审→复核人审核→技术负责人审批",
     "source": "审核记录 (T0)"
    },
    {
     "item": "所有红线检查通过，测算结果自洽",
     "source": "质量检查表 (T0)"
    },
    {
     "item": "报告日期 2026-08-03，在委托合同约定的交付期限内",
     "source": "委托合同 (T0)"
    }
   ],
   "reasoning": "报告内容完整，测算过程可追溯，结论合理。估价师和复核人均已在报告上签字。",
   "risks": [
    {
     "description": "抵押估价报告需附《房地产抵押估价风险提示》，确认已包含",
     "level": "P0",
     "mitigation": "报告第8章已包含风险提示及变现能力分析"
    }
   ],
   "humanDecision": {
    "action": "approved",
    "decidedBy": "张××",
    "timestamp": "2026-08-03T16:00:00+08:00"
   }
  },
  {
   "id": "DP-comp-2",
   "name": "可比实例选取",
   "phase": "inMethod",
   "trigger": "method:comps",
   "method": "comps",
   "riskLevel": "P1",
   "status": "approved",
   "supersedes": "DP-comp",
   "attempt": 2,
   "conclusion": "修正后推荐选取实例 A/B/D，均为洪山区珞狮路同区域住宅，成交时间 2026-05 至 2026-06，与估价对象可比性良好",
   "evidence": [
    {
     "item": "实例 A：珞狮路1号小区，125.0 m²，成交 2026-05-15，单价 25000 元/m²",
     "source": "链家成交记录 (T1)"
    },
    {
     "item": "实例 B：珞狮路2号小区，130.0 m²，成交 2026-06-10，单价 26000 元/m²",
     "source": "贝壳成交记录 (T1)"
    },
    {
     "item": "实例 D：珞狮路4号小区，128.0 m²，成交 2026-06-18，单价 25600 元/m²",
     "source": "链家成交记录 (T1)"
    }
   ],
   "reasoning": "按估价师驳回意见，剔除区位修正指数 98 的实例 C，更换为区位条件与估价对象基本一致的实例 D（修正指数 100）。三个实例均在估价对象同一街区，成交时间距价值时点不超过 77 天，面积差异在 3.5 m² 以内。单项修正幅度最大 3.1%，综合修正幅度最大 3.1%，远低于 20%/30% 红线。最高价/最低价比 1.04，远低于 1.2 红线。",
   "risks": [
    {
     "description": "三个实例均来自线上平台，缺少线下实际成交核实",
     "level": "P1",
     "mitigation": "已交叉比对链家和贝壳数据，价格趋势一致"
    },
    {
     "description": "实例 B 面积 130 m² 比估价对象大 1.5 m²，建筑规模修正系数 102",
     "level": "P2",
     "mitigation": "已在实物状况修正中体现"
    }
   ],
   "comparison": [
    {
     "instance": "A",
     "differences": "不同小区（珞狮路1号小区 vs 估价对象所在小区），面积差 3.5 m²（125.0 vs 128.5，建筑规模修正指数 97），区位距重要场所距离优于估价对象（修正指数 102）"
    },
    {
     "instance": "B",
     "differences": "不同小区（珞狮路2号小区），面积差 1.5 m²（130.0 vs 128.5，建筑规模修正指数 102），区位距重要场所距离优于估价对象（修正指数 101）"
    },
    {
     "instance": "D",
     "differences": "不同小区（珞狮路4号小区），面积差 0.5 m²（128.0 vs 128.5，建筑规模修正指数 100），区位条件与估价对象基本一致（修正指数 100）"
    }
   ],
   "humanDecision": {
    "action": "approved",
    "decidedBy": "张××",
    "timestamp": "2026-08-01T14:10:00+08:00"
   }
  }
 ]
};
