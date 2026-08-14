# Excel 模板 ↔ JSON Schema 字段映射分析

> 生成日期：2026-08-14
> 分析对象：`outputs/房地产评估明细表-计算模板.xlsx`（11 sheet, 1582 公式）↔ `schema/appraisal-result.schema.json`（v1.1）
> 目标：验证字段映射关系，确保数据可互导

---

## 一、映射总览

| 维度 | 完全匹配 | 间接匹配 | Excel 有 Schema 无 | Schema 有 Excel 无 |
|------|---------|---------|-------------------|-------------------|
| project | 3 | 1 | 3 | 4 |
| property | 5 | 3 | 3 | 1 |
| valuation | 1 | 1 | 0 | 2 |
| methods.comps | 6 | 4 | 2 | 3 |
| methods.income | 4 | 3 | 8 | 3 |
| methods.cost | — | — | — | 全部（Excel 无此方法） |
| methods.hypotheticalDev | — | — | — | 全部（Excel 无此方法） |
| result | 2 | 1 | 2 | 5 |
| crossMethodConsistency | — | — | — | 全部 |
| **合计** | **21** | **13** | **18** | **18+** |

**结论**：核心测算字段（比较法 + 收益法）可互导，但存在 3 类结构性差异需处理。

---

## 二、逐字段映射表

### 2.1 project — 估价项目基本信息

| JSON 路径 | Excel Sheet!Cell | 匹配类型 | 说明 |
|-----------|-----------------|---------|------|
| `project.client` | `评估明细表!B3` → "委托人：XX投资有限公司" | ✅ 完全 | 需解析前缀"委托人：" |
| `project.agency` | `评估明细表!B9` → "评估机构：XX评估有限公司" | ✅ 完全 | 需解析前缀"评估机构：" |
| `project.appraiser.name` | `评估明细表!J9` → "评估人员：评估师A、评估师B" | ⚠️ 间接 | 需解析前缀 + 分割多人 |
| `project.reportDate` | `评估明细表!B10` → "日期：2028年08月11日" | ⚠️ 间接 | 需解析中文日期 → YYYY-MM-DD |
| `project.purpose` | — | ❌ 缺失 | Excel 无"估价目的"字段 |
| `project.name` | — | ❌ 缺失 | Excel 无"项目名称"字段 |
| `project.reportNumber` | — | ❌ 缺失 | Excel 无"报告编号"字段 |
| `project.appraiser.registrationNumber` | — | ❌ 缺失 | Excel 无"注册号"字段 |
| `project.coAppraiser` | — | ❌ 缺失 | Excel 无第二估价师字段 |

### 2.2 property — 估价对象基本信息

| JSON 路径 | Excel Sheet!Cell | 匹配类型 | 说明 |
|-----------|-----------------|---------|------|
| `property.area` | `评估明细表!M6` → 580 | ✅ 完全 | 建筑面积 |
| `property.usage` | `评估明细表!F6` → "成套住宅" | ✅ 完全 | |
| `property.address` | `评估明细表!D6` → "XX市XX区XX路XX号XX小区XX栋XX房" | ✅ 完全 | |
| `property.completionYear` | `评估明细表!K6` → 2011-07-01 (datetime) | ⚠️ 间接 | 需提取年份 2011 |
| `property.floor` | `评估明细表!I6`+`J6` → "钢混5层"+"第1-5层" | ⚠️ 间接 | 需合并为 "1-5/5层" 格式 |
| `property.orientation` | `住宅-实物状况!L4` → "南" | ✅ 完全 | |
| `property.decoration` | `评估明细表!G6` → "精致" | ✅ 完全 | |
| `property.remainingUsefulLife` | `住宅-收益法测算!J11` → =J8-J10 (公式) | ⚠️ 间接 | 需读取计算值 |
| `property.landUseRightYears` | `住宅-收益法测算!J6` → =(J5-J4)/365 (公式) | ⚠️ 间接 | 需读取计算值 |
| `property.propertyType` | — | ❌ 缺失 | Excel 无"房地产类型"字段（可从权属证号推断"商品房"） |
| `property.ownershipType` | — | ❌ 缺失 | Excel 无"权属类型"字段（可从土地到期日推断"出让"） |
| — | `评估明细表!C6` → "《商品房买卖合同》" | Excel 独有 | 权属证号 |
| — | `评估明细表!L6` → 540 | Excel 独有 | 套内建筑面积 |
| — | `评估明细表!H6` → 2068-07-24 | Excel 独有 | 土地到期日（可推导 landUseRightYears） |

### 2.3 valuation — 估价参数

| JSON 路径 | Excel Sheet!Cell | 匹配类型 | 说明 |
|-----------|-----------------|---------|------|
| `valuation.valueDate` | `评估明细表!J2` → 42879 (Excel serial date) | ⚠️ 间接 | 需转换 Excel 序列号 → YYYY-MM-DD |
| `valuation.currency` | `评估明细表!P3` → "金额单位：人民币元" | ✅ 完全 | 映射为 "CNY" |
| `valuation.valueType` | — | ❌ 缺失 | Excel 无"价值类型"字段 |
| `valuation.estimatedDate` | — | ❌ 缺失 | Excel 无"预计成交日期"字段 |

### 2.4 methods.comps — 比较法

| JSON 路径 | Excel Sheet!Cell | 匹配类型 | 说明 |
|-----------|-----------------|---------|------|
| `comps.applicable` | (隐式：sheet 存在 = true) | ✅ 完全 | |
| `comps.comparableInstances[].name` | `市场价比较法!E1/F1/G1` → "可比实例1/2/3" | ✅ 完全 | |
| `comps.comparableInstances[].location` | `市场价比较法!E2/F2/G2` | ✅ 完全 | |
| `comps.comparableInstances[].area` | `市场价比较法!E24/F24/G24` | ✅ 完全 | 建筑规模 |
| `comps.comparableInstances[].unitPrice` | `市场价比较法!E4/F4/G4` → 31000/30000/28000 | ✅ 完全 | 成交单价 |
| `comps.comparableInstances[].transactionPrice` | unitPrice × area | ⚠️ 间接 | 需计算 |
| `comps.comparableInstances[].transactionDate` | `市场价比较法!E6/F6/G6` → 42821 (serial) | ⚠️ 间接 | 需转换日期 |
| `comps.comparableInstances[].adjustments.transactionSituation` | `市场价比较法!M5/O5` → 100/85 | ⚠️ **结构差异** | Excel 用 100 基准，Schema 用小数 1.0。需 ÷100 |
| `comps.comparableInstances[].adjustments.marketCondition` | `市场价比较法!M6/N6/O6` → 100/100/100 | ⚠️ **结构差异** | 同上 |
| `comps.comparableInstances[].adjustments.location` | 多个子项乘积 | ⚠️ **结构差异** | Excel 拆为 7+子项各 100 分，Schema 是单一系数。需合并计算 |
| `comps.comparableInstances[].adjustments.physical` | 多个子项乘积 | ⚠️ **结构差异** | Excel 拆为 8+子项各 100 分，Schema 是单一系数 |
| `comps.comparableInstances[].adjustments.interest` | 多个子项乘积 | ⚠️ **结构差异** | Excel 拆为 5 子项各 100 分，Schema 是单一系数 |
| `comps.comparableInstances[].adjustedUnitPrice` | `市场价比较法!T32/W32/Z32` (公式) | ⚠️ 间接 | 需读取计算值 |
| `comps.comparableInstances[].sourceGrade` | — | ❌ 缺失 | Excel 无信源等级标注 |
| `comps.finalValue.unit` | `市场价比较法!T34` (加权后公式) | ⚠️ 间接 | |
| `comps.finalValue.total` | T34 × area | ⚠️ 间接 | 需计算 |
| `comps.weight` | `住宅-收益法测算!I28` → 1 (市场法权重) | ⚠️ 间接 | 收益法 sheet 中 I28=1 表示全用市场法 |
| `comps.weightRationale` | — | ❌ 缺失 | Excel 无权重理由文字 |
| `comps.redLineChecks[]` | — | ❌ 缺失 | Excel 无红线检查记录 |
| — | `市场价比较法!D7-G31` | Excel 独有 | 区位/交通/配套/环境/权益/实物的文字描述（定性分析） |
| — | `市场价比较法!AD33` | Excel 独有 | 最高/最低价比值（=MIN/MAX-1） |

### 2.5 methods.income — 收益法

| JSON 路径 | Excel Sheet!Cell | 匹配类型 | 说明 |
|-----------|-----------------|---------|------|
| `income.applicable` | (隐式：sheet 存在 = true) | ✅ 完全 | |
| `income.calculationMode` | (公式结构推断：fullRemainingLife) | ⚠️ 间接 | G27 公式含 n1+n2 分段 → 全剩余寿命模式 |
| `income.incomeType` | (隐式：rentalIncome) | ✅ 完全 | |
| `income.netOperatingIncome.effectiveGrossIncome` | `住宅-收益法测算!G5` (公式) | ⚠️ 间接 | 需读取计算值 |
| `income.netOperatingIncome.operatingExpenses` | `住宅-收益法测算!G11` (公式=SUM) | ⚠️ 间接 | 需读取计算值 |
| `income.netOperatingIncome.annualAmount` | `住宅-收益法测算!G4` (公式=G5-G11) | ⚠️ 间接 | 需读取计算值 |
| `income.netOperatingIncome.growthRate` | `住宅-收益法测算!G25` → 0.015 | ✅ 完全 | |
| `income.netOperatingIncome.historicalDataYears` | — | ❌ 缺失 | Excel 无历史数据调查年数记录 |
| `income.rate.type` | (隐式：yieldRate — G24 引用报酬率) | ✅ 完全 | |
| `income.rate.value` | `住宅-收益率!O14` (公式=ROUND(...)) | ⚠️ 间接 | 需读取计算值 |
| `income.rate.determinationMethod` | (从 sheet 结构推断："累加法") | ⚠️ 间接 | |
| `income.finalValue.unit` | `住宅-收益法测算!G27` (公式) | ⚠️ 间接 | 需读取计算值 |
| `income.finalValue.total` | G27 × area | ⚠️ 间接 | 需计算 |
| `income.weight` | `住宅-收益法测算!I27` (公式=1-I28) | ⚠️ 间接 | |
| `income.weightRationale` | — | ❌ 缺失 | Excel 无权重理由 |
| `income.redLineChecks[]` | — | ❌ 缺失 | Excel 无红线检查 |
| — | `住宅-收益法测算!G7` → 42.59 | Excel 独有 | 月租金单价（元/㎡/月） |
| — | `住宅-收益法测算!G9` → =1/12 | Excel 独有 | 空置率 |
| — | `住宅-收益法测算!G12-G20` | Excel 独有 | 8 项运营费用明细（房产税/增值税/城建税/教育附加/...） |
| — | `住宅-收益法测算!G21-G23` | Excel 独有 | 收益期分段（n1 递增年限 + n2 固定年限） |
| — | `住宅-收益率!B4-L12` | Excel 独有 | 风险补偿率评分矩阵（7 项风险因素×权重×分值） |
| — | `住宅-收益率!B19-L23` | Excel 独有 | 管理负担补偿评分矩阵（4 项×权重×分值） |
| — | `住宅-收益率!O5/O9/O11/O12` | Excel 独有 | 安全利率/存款利率/流动性补偿/投资优惠率 |

### 2.6 result — 估价结果汇总

| JSON 路径 | Excel Sheet!Cell | 匹配类型 | 说明 |
|-----------|-----------------|---------|------|
| `result.finalUnitValue` | `评估明细表!N6` → 38000 | ✅ 完全 | 评估单价 |
| `result.finalTotalValue` | `评估明细表!O6` → =ROUND(M6*N6,0) | ✅ 完全 | 评估总价（公式） |
| `result.determinationMethod` | — | ❌ 缺失 | Excel 无"结果确定方式"描述文字 |
| `result.weightAllocation` | `住宅-收益法!I27/I28` | ⚠️ 间接 | 需从收益法 sheet 推断权重分配 |
| `result.weightSum` | (隐式：I27+I28=1) | ⚠️ 间接 | |
| `result.finalTotalValueInWords` | — | ❌ 缺失 | Excel 无大写金额 |
| `result.crossMethodDifference` | — | ❌ 缺失 | Excel 无差异分析文字 |
| `result.calculationMode` | — | ❌ 缺失 | Excel 无计算模式 enum |
| — | `评估明细表!W4-W6` | Excel 独有 | 原购买价/购买单价/购买总价 |
| — | `评估明细表!Y6/Z6/AA6` | Excel 独有 | 增减值/增减率/单价增值 |

### 2.7 crossMethodConsistency & crossMethodNotes

| JSON 路径 | Excel Sheet!Cell | 匹配类型 | 说明 |
|-----------|-----------------|---------|------|
| `crossMethodConsistency[]` | — | ❌ 全缺 | Excel 无跨方法一致性检查记录 |
| `crossMethodNotes` | — | ❌ 缺失 | Excel 无跨方法讨论笔记 |

### 2.8 Excel 独有 Sheet（Schema 无对应）

| Excel Sheet | 用途 | Schema 对应 |
|-------------|------|------------|
| `单价修正明细表-住宅` | 逐户单价修正（楼层/朝向/面积/装修） | ❌ 无 — Schema 只记录可比实例级修正，不记录估价对象内部逐户修正 |
| `二手房案例` | 二手房成交案例数据库 | ❌ 无 — Schema 不存储原始案例数据库 |
| `租金案例` | 租金案例数据库 | ❌ 无 — 同上 |
| `租金单价` | 租金挂牌价数据库 | ❌ 无 — 同上 |
| `可比案例` | 可比实例详细数据（面积/总价/单价） | ⚠️ 部分对应 `comparableInstances`，但 Excel 存的是原始数据库不是测算用的实例 |
| `住宅-实物状况` | 估价对象 + 可比实例实物状况文字描述 | ⚠️ 部分对应 `comparableInstances` 的定性描述，但 Excel 更详细 |

---

## 三、结构性差异分析

### 差异 1：修正系数基准不同（P0 — 影响数据互导准确性）

**Excel**：修正系数以 **100 为基准**（100=无差异，85=下调15%，103=上调3%）
**Schema**：修正系数用 **小数**（1.0=无差异，0.85=下调15%，1.03=上调3%）

**互导规则**：`Schema 值 = Excel 值 / 100`

**影响范围**：`comparableInstances[].adjustments.*` 全部 5 个字段

### 差异 2：区位/实物/权益状况拆分粒度不同（P0 — 影响映射完整性）

**Excel**：区位状况拆为 7+ 子项（距离/临街/朝向/楼层/道路/公交/停车/交通管理），实物状况拆为 8+ 子项（规模/外观/结构/设施/装修/性能/布局/新旧），权益状况拆为 5 子项。每个子项独立打分。

**Schema**：每个维度只有一个汇总系数（`location` / `physical` / `interest`）

**互导规则**：
- Excel → Schema：将各子项系数连乘后归一化为单一系数
  - `adjustments.location = ∏(子项系数_i) / 100^(n-1)`（n 为子项数）
- Schema → Excel：无法逆推（单一系数无法拆分为多子项）

**影响**：Excel → Schema 方向可行但损失精度；Schema → Excel 方向不可逆

### 差异 3：收益法费用结构粒度不同（P1 — 影响数据完整性）

**Excel**：运营费用拆为 8 项明细（房产税12%/增值税5%/城建税7%/教育附加3%/地方教育2%/印花税/维修费/管理费/保险费），每项有独立公式

**Schema**：只有 `operatingExpenses` 一个总数

**互导规则**：
- Excel → Schema：读取 `G11 = SUM(G12:G20)` 计算值
- Schema → Excel：无法拆分到明细项

### 差异 4：权重管理位置不同（P1 — 影响数据查找路径）

**Excel**：权重分散在两个位置
- `市场价比较法!T33/W33/Z33` — 可比实例间权重（0.5/0.3/0.2）
- `住宅-收益法!I27/I28` — 方法间权重（市场法 vs 收益法）

**Schema**：
- `methods.comps.weight` — 比较法整体权重
- `result.weightAllocation` — 统一权重分配表

### 差异 5：Excel 不含成本法/假设开发法（P2 — 住宅模板限制）

**原因**：当前 Excel 模板从住宅评估案例模糊化生成，住宅通常不使用成本法和假设开发法。

**影响**：Schema 中的 `methods.cost` 和 `methods.hypotheticalDev` 在 Excel 模板中无对应。如需支持非住宅估价，需新增对应 sheet 模板。

---

## 四、互导可行性评估

| 方向 | 可行性 | 说明 |
|------|--------|------|
| **Excel → JSON** | ✅ 可行（需处理） | 核心字段可映射；需转换日期格式、修正系数基准、合并子项系数；缺失字段需手动补充 |
| **JSON → Excel** | ⚠️ 部分可行 | 数值字段可写入；但 Excel 公式链无法从 JSON 重建；多子项修正系数无法拆分 |
| **双向同步** | ❌ 不可行 | 结构差异导致信息不对称（Excel > Schema 信息量），无法无损双向同步 |

### Excel → JSON 互导数据流

```
评估明细表!B3     → project.client          (解析前缀)
评估明细表!D6     → property.address        (直传)
评估明细表!F6     → property.usage          (直传)
评估明细表!G6     → property.decoration     (直传)
评估明细表!J2     → valuation.valueDate     (serial → date)
评估明细表!K6     → property.completionYear (datetime → year)
评估明细表!M6     → property.area           (直传)
评估明细表!N6     → result.finalUnitValue   (直传)
评估明细表!O6     → result.finalTotalValue  (直传或公式重算)
市场价比较法!E4/F4/G4  → comps.comparableInstances[].unitPrice  (直传)
市场价比较法!E6/F6/G6  → comps.comparableInstances[].transactionDate (serial → date)
市场价比较法!M5/O5     → comps.comparableInstances[].adjustments.transactionSituation (÷100)
市场价比较法!T32/W32/Z32 → comps.comparableInstances[].adjustedUnitPrice (直传)
住宅-收益法测算!G4  → income.netOperatingIncome.annualAmount (直传)
住宅-收益法测算!G5  → income.netOperatingIncome.effectiveGrossIncome (直传)
住宅-收益法测算!G11 → income.netOperatingIncome.operatingExpenses (直传)
住宅-收益法测算!G24 → income.rate.value (直传)
住宅-收益法测算!G27 → income.finalValue.unit (直传)
住宅-收益率!O14    → income.rate.value (直传, 同 G24)
```

---

## 五、建议

### 5.1 短期（可立即实施）

1. **编写 `excel_to_json.py` 互导脚本**：实现上述映射表，处理日期转换、系数基准转换、子项合并
2. **在 Excel 模板新增"元数据"sheet**：补充 `project.purpose`、`project.name`、`project.reportNumber`、`valuation.valueType` 等 Schema 必填字段
3. **在 Excel 模板标注"信源等级"列**：在可比实例/租金案例 sheet 新增 `sourceGrade` 列（T0/T1/T2）

### 5.2 中期

4. **Schema 新增 Excel 独有字段（v1.2）**：
   - `property.internalArea`（套内建筑面积）
   - `property.landUseRightExpiryDate`（土地到期日）
   - `property.ownershipDoc`（权属证号）
   - `result.originalPurchasePrice`（原购买价）
   - `methods.comps.comparableInstances[].qualitativeFactors`（文字描述）
5. **修正系数多子项支持（v1.2）**：在 `adjustments` 下新增 `locationDetails` / `physicalDetails` / `interestDetails` 对象，保留 Excel 子项粒度

### 5.3 长期

6. **成本法/假设开发法 Excel 模板**：为非住宅估价场景新增对应 sheet 模板
7. **Excel 公式 → JSON 计算链**：将 Excel 公式逻辑提取为 JSON 中的 `calculationChain` 字段，实现 Schema → Excel 公式重建
