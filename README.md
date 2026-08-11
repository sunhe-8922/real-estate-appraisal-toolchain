# 房地产估价 AI 工具链

基于 **GB/T 50291-2015《房地产估价规范》** 的 WorkBuddy 技能体系。覆盖估价全流程：资料搜集→四大方法测算→报告生成。

> **数据声明**：本仓库所有示例、测试案例与 fixtures 中的人物姓名、证件号、电话、地址、机构名称均为**虚构测试数据**，不涉及任何真实个人或机构。

## 技能体系（7 技能 + 1 专家）

### 资料搜集

| 技能 | 职责 | 规范依据 |
|------|------|---------|
| `appraisal-data-collection` | 搜集估价所需资料，生成结构化资料清单 | 第 3.0.5 条 |
| `web-research-methodology` | 联网并行搜索方法论，T0/T1/T2 信源分级 | — |

### 四大方法测算

| 技能 | 职责 | 规范依据 | 输出 |
|------|------|---------|------|
| `comps-method` | 比较法测算，7 步流程 | 第 4.2 节 | `.xlsx`（公式驱动） |
| `income-method` | 收益法测算，报酬资本化/直接资本化 | 第 4.3 节 | `.xlsx`（公式驱动） |
| `cost-method` | 成本法测算，房地合估/分估 | 第 4.4 节 | `.xlsx`（公式驱动） |
| `hypothetical-dev-method` | 假设开发法测算，动/静态分析 | 第 4.5 节 | `.xlsx`（公式驱动） |

### 报告生成

| 技能 | 职责 | 规范依据 |
|------|------|---------|
| `appraisal-report` | 报告生成，6 步流程 | 第 7 章 |

### 专家

| 专家 | 职责 |
|------|------|
| `re-appraisal-expert` | 房地产估价全流程合规审查 |

## 约束红线

- 可比实例 ≥ 3、成交距价值时点 ≤ 2 年
- 单因素修正 ≤ 20%、综合 ≤ 30%
- 最高/最低价比 ≤ 1.2
- 至少采用两种估价方法
- 报告使用期限 ≤ 1 年

## 目录结构

```
├── skills/                        # 7 个技能
│   ├── appraisal-data-collection/
│   ├── web-research-methodology/
│   ├── comps-method/
│   ├── income-method/
│   ├── cost-method/
│   ├── hypothetical-dev-method/
│   └── appraisal-report/
├── experts/                       # 1 个专家
│   └── re-appraisal-expert/
├── outputs/                       # 示例输出
│   └── 武汉洪山住宅_抵押估价报告.md
├── schema/                        # JSON 数据契约
│   ├── appraisal-result.schema.json
│   └── example-武汉洪山住宅.json
├── install.ps1                    # Windows 安装脚本
├── install.sh                     # Unix/Git Bash 安装脚本
├── HANDOFF.md                     # 任务交接文档
├── CLAUDE.md                      # 项目上下文
└── README.md
```

## 安装

### 一键安装

```bash
# 克隆仓库
git clone https://github.com/sunhe-8922/real-estate-appraisal-toolchain.git
cd real-estate-appraisal-toolchain

# Windows (PowerShell)
.\install.ps1

# Unix / Git Bash
./install.sh
```

安装脚本会自动：
- 复制 7 个技能到项目级 `.workbuddy/skills/` 和用户级 `~/.workbuddy/skills/`
- 复制专家到 `~/.workbuddy/plugins/marketplaces/my-experts/plugins/`
- 复制 JSON Schema 到 `.workbuddy/schema/`
- 验证安装结果（7/7 技能 + 3/3 专家文件）

### 安装选项

| 命令 | 说明 |
|------|------|
| `install.ps1` / `./install.sh` | 全量安装 |
| `install.ps1 -SkillsOnly` / `./install.sh --skills-only` | 仅安装技能 |
| `install.ps1 -ExpertsOnly` / `./install.sh --experts-only` | 仅安装专家 |
| `install.ps1 -Check` / `./install.sh --check` | 检查安装状态 |
| `install.ps1 -Force` / `./install.sh --force` | 跳过确认提示 |

### 手动安装

1. 将 `skills/` 复制到 `[项目]/.workbuddy/skills/` 和 `~/.workbuddy/skills/`
2. 将 `experts/re-appraisal-expert/` 复制到 `~/.workbuddy/plugins/marketplaces/my-experts/plugins/`
3. 重启 WorkBuddy 使技能索引生效

## 测试报告

`outputs/武汉洪山住宅_抵押估价报告.md` — 以武汉洪山区 128.50m² 住宅为案例，比较法+收益法，18/18 项合规。可作为报告模板参考。

## License

MIT
