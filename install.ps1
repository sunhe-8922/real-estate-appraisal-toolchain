# install.ps1 - 房地产估价 AI 工具链安装脚本 (Windows)
# 用法:
#   .\install.ps1              # 全量安装（技能 + 专家）
#   .\install.ps1 -SkillsOnly # 仅安装技能
#   .\install.ps1 -ExpertsOnly# 仅安装专家
#   .\install.ps1 -Check      # 仅检查已有安装状态，不复制

[CmdletBinding()]
param(
    [switch]$SkillsOnly,
    [switch]$ExpertsOnly,
    [switch]$Check,
    [switch]$Force  # 跳过确认提示
)

$ErrorActionPreference = "Stop"

# ── 路径定位 ─────────────────────────────────────────────
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $RepoRoot) { $RepoRoot = $PSScriptRoot }
if (-not $RepoRoot) { $RepoRoot = Get-Location }

$SkillsSrc     = Join-Path $RepoRoot "skills"
$ExpertSrc     = Join-Path $RepoRoot "experts\re-appraisal-expert"
$SchemaSrc     = Join-Path $RepoRoot "schema"

$ProjectSkills = Join-Path $RepoRoot ".workbuddy\skills"
$UserHome       = $env:USERPROFILE
$UserSkills     = Join-Path $UserHome ".workbuddy\skills"
$UserExperts    = Join-Path $UserHome ".workbuddy\plugins\marketplaces\my-experts\plugins"

# 安装范围
$InstallSkills  = -not $ExpertsOnly
$InstallExperts = -not $SkillsOnly

# ── 辅助函数 ─────────────────────────────────────────────

function Write-Section($title) {
    Write-Host ""
    Write-Host "=" * 60 -ForegroundColor DarkCyan
    Write-Host "  $title" -ForegroundColor Cyan
    Write-Host "=" * 60 -ForegroundColor DarkCyan
}

function Write-Step($msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "  [!]  $msg" -ForegroundColor Yellow
}

function Write-Err($msg) {
    Write-Host "  [X]  $msg" -ForegroundColor Red
}

function Ensure-Dir($path) {
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
}

function Copy-Tree($src, $dst) {
    Ensure-Dir $dst
    # 递归复制，覆盖已存在文件
    Get-ChildItem -Path $src -Directory | ForEach-Object {
        $target = Join-Path $dst $_.Name
        Copy-Item -Path $_.FullName -Destination $target -Recurse -Force
    }
    # 复制文件
    Get-ChildItem -Path $src -File | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $dst -Force
    }
    # 处理隐藏目录（.codebuddy-plugin 等）
    Get-ChildItem -Path $src -Hidden -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $target = Join-Path $dst $_.Name
        Copy-Item -Path $_.FullName -Destination $target -Recurse -Force
    }
    Get-ChildItem -Path $src -Hidden -File -ErrorAction SilentlyContinue | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $dst -Force
    }
}

function Verify-Skills($path, $label) {
    $expected = @(
        "appraisal-data-collection",
        "appraisal-report",
        "comps-method",
        "cost-method",
        "hypothetical-dev-method",
        "income-method",
        "web-research-methodology"
    )
    $found = 0
    foreach ($s in $expected) {
        $skillFile = Join-Path $path "$s\SKILL.md"
        if (Test-Path $skillFile) {
            $lines = (Get-Content $skillFile | Measure-Object -Line).Lines
            Write-Host "    $s : ${lines} lines" -ForegroundColor DarkGray
            $found++
        } else {
            Write-Warn "$label 缺失: $s"
        }
    }
    return $found
}

function Verify-Expert($path) {
    $checks = @(
        @{ Path = Join-Path $path "agents\re-appraisal-expert.md";  Label = "agents/re-appraisal-expert.md" },
        @{ Path = Join-Path $path "avatars\expert.png";             Label = "avatars/expert.png" },
        @{ Path = Join-Path $path ".codebuddy-plugin\plugin.json";  Label = ".codebuddy-plugin/plugin.json" }
    )
    $found = 0
    foreach ($c in $checks) {
        if (Test-Path $c.Path) {
            $size = (Get-Item $c.Path).Length
            $sizeKB = [math]::Round($size / 1024, 1)
            Write-Host "    $($c.Label) : ${sizeKB} KB" -ForegroundColor DarkGray
            $found++
        } else {
            Write-Warn "专家缺失: $($c.Label)"
        }
    }
    return $found
}

# ── 检查模式 ─────────────────────────────────────────────

if ($Check) {
    Write-Section "检查安装状态"
    Write-Host ""
    Write-Host "  项目级技能路径: $ProjectSkills" -ForegroundColor DarkGray
    $pCount = Verify-Skills $ProjectSkills "项目级"
    Write-Host ""
    Write-Host "  用户级技能路径: $UserSkills" -ForegroundColor DarkGray
    $uCount = Verify-Skills $UserSkills "用户级"
    Write-Host ""
    $expertPath = Join-Path $UserExperts "re-appraisal-expert"
    Write-Host "  专家路径: $expertPath" -ForegroundColor DarkGray
    $eCount = Verify-Expert $expertPath
    Write-Host ""
    Write-Host "  汇总: 项目级 ${pCount}/7, 用户级 ${uCount}/7, 专家 ${eCount}/3" -ForegroundColor Cyan
    exit 0
}

# ── 前置检查 ─────────────────────────────────────────────

Write-Section "房地产估价 AI 工具链安装"
Write-Host ""
Write-Host "  仓库根目录: $RepoRoot" -ForegroundColor DarkGray
Write-Host "  安装范围:   $(if ($InstallSkills) {'技能 '})$(if ($InstallExperts) {'专家'})" -ForegroundColor DarkGray
Write-Host ""

if (-not (Test-Path $SkillsSrc) -and $InstallSkills) {
    Write-Err "skills/ 目录不存在于 $RepoRoot"
    Write-Host "  请在仓库根目录运行此脚本" -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path $ExpertSrc) -and $InstallExperts) {
    Write-Err "experts/re-appraisal-expert/ 目录不存在于 $RepoRoot"
    exit 1
}

# 确认
if (-not $Force) {
    $title = "即将安装到以下路径："
    $msg  = "`n  项目级技能: $ProjectSkills`n  用户级技能: $UserSkills`n  专家:       $UserExperts\re-appraisal-expert`n`n确认继续？(Y/N)"
    Write-Host $title -ForegroundColor Cyan
    Write-Host $msg
    $confirm = Read-Host
    if ($confirm -ne 'Y' -and $confirm -ne 'y') {
        Write-Host "  已取消。" -ForegroundColor Yellow
        exit 0
    }
}

# ── 安装技能 ─────────────────────────────────────────────

if ($InstallSkills) {
    Write-Section "安装技能 (7 个)"

    # 项目级
    Write-Host "`n  [1/2] 复制到项目级路径..." -ForegroundColor Cyan
    Write-Host "  $ProjectSkills" -ForegroundColor DarkGray
    Copy-Tree $SkillsSrc $ProjectSkills
    $pCount = Verify-Skills $ProjectSkills "项目级"
    Write-Step "项目级 ${pCount}/7 技能已安装"

    # 用户级
    Write-Host "`n  [2/2] 复制到用户级路径..." -ForegroundColor Cyan
    Write-Host "  $UserSkills" -ForegroundColor DarkGray
    Copy-Tree $SkillsSrc $UserSkills
    $uCount = Verify-Skills $UserSkills "用户级"
    Write-Step "用户级 ${uCount}/7 技能已安装"

    if ($pCount -lt 7 -or $uCount -lt 7) {
        Write-Warn "部分技能未安装成功，请检查源目录完整性"
    }
}

# ── 安装专家 ─────────────────────────────────────────────

if ($InstallExperts) {
    Write-Section "安装专家 (re-appraisal-expert)"

    $expertDst = Join-Path $UserExperts "re-appraisal-expert"
    Write-Host "`n  复制到用户级专家路径..." -ForegroundColor Cyan
    Write-Host "  $expertDst" -ForegroundColor DarkGray
    Copy-Tree $ExpertSrc $expertDst
    $eCount = Verify-Expert $expertDst
    Write-Step "专家 ${eCount}/3 文件已安装"

    if ($eCount -lt 3) {
        Write-Warn "部分专家文件未安装成功"
    }
}

# ── 复制 Schema ──────────────────────────────────────────

if ($InstallSkills -and (Test-Path $SchemaSrc)) {
    Write-Section "复制 JSON Schema"
    $schemaDstProject = Join-Path $RepoRoot ".workbuddy\schema"
    $schemaDstUser    = Join-Path $UserSkills "..\schema"
    Ensure-Dir $schemaDstProject
    Copy-Item -Path "$SchemaSrc\*" -Destination $schemaDstProject -Recurse -Force
    Write-Step "Schema 已复制到项目级 .workbuddy/schema/"
    Write-Host "  (Schema 仅供技能运行时参考，不影响 WorkBuddy 索引)" -ForegroundColor DarkGray
}

# ── 完成 ─────────────────────────────────────────────────

Write-Section "安装完成"
Write-Host ""
Write-Host "  技能清单:" -ForegroundColor Cyan
Write-Host "    appraisal-data-collection   搜集估价所需资料 (GB/T 50291 3.0.5)"
Write-Host "    web-research-methodology    联网信息收集方法论"
Write-Host "    comps-method                 比较法测算 (4.2)"
Write-Host "    income-method                收益法测算 (4.3)"
Write-Host "    cost-method                  成本法测算 (4.4)"
Write-Host "    hypothetical-dev-method      假设开发法测算 (4.5)"
Write-Host "    appraisal-report             报告生成 (第7章)"
Write-Host ""
Write-Host "  专家:" -ForegroundColor Cyan
Write-Host "    re-appraisal-expert          房地产估价合规审查专家"
Write-Host ""
Write-Host "  数据契约:" -ForegroundColor Cyan
Write-Host "    schema/appraisal-result.schema.json  (JSON Schema draft 2020-12)"
Write-Host "    schema/example-武汉洪山住宅.json       (完整示例)"
Write-Host ""
Write-Host "  *** 请重启 WorkBuddy 让新技能索引生效 ***" -ForegroundColor Yellow
Write-Host ""
Write-Host "  验证方式 (重启后):" -ForegroundColor DarkGray
Write-Host "    .\install.ps1 -Check    # 检查安装状态" -ForegroundColor DarkGray
Write-Host "    在对话中调用 Skill 工具 (如 skill: 'comps-method')" -ForegroundColor DarkGray
Write-Host ""
