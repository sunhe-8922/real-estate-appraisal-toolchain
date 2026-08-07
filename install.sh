#!/usr/bin/env bash
# install.sh - 房地产估价 AI 工具链安装脚本 (Unix / Git Bash)
# 用法:
#   ./install.sh                # 全量安装（技能 + 专家）
#   ./install.sh --skills-only  # 仅安装技能
#   ./install.sh --experts-only # 仅安装专家
#   ./install.sh --check        # 仅检查已有安装状态，不复制
#   ./install.sh --force        # 跳过确认提示

set -euo pipefail

# ── 颜色 ─────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
DARKCYAN='\033[0;37m'
NC='\033[0m'

section() {
    echo ""
    echo -e "${DARKCYAN}============================================================${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${DARKCYAN}============================================================${NC}"
}

step()  { echo -e "  ${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "  ${YELLOW}[!]${NC}  $1"; }
err()   { echo -e "  ${RED}[X]${NC}  $1"; }

# ── 参数解析 ─────────────────────────────────────────────
INSTALL_SKILLS=true
INSTALL_EXPERTS=true
CHECK_ONLY=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skills-only)  INSTALL_EXPERTS=false; shift ;;
        --experts-only) INSTALL_SKILLS=false; shift ;;
        --check|-c)     CHECK_ONLY=true; shift ;;
        --force|-f)     FORCE=true; shift ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --skills-only    仅安装技能"
            echo "  --experts-only   仅安装专家"
            echo "  --check, -c      检查安装状态，不复制"
            echo "  --force, -f      跳过确认提示"
            echo "  --help, -h       显示帮助"
            exit 0
            ;;
        *)
            err "未知选项: $1"
            exit 1
            ;;
    esac
done

# ── 路径定位 ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"

SKILLS_SRC="$REPO_ROOT/skills"
EXPERT_SRC="$REPO_ROOT/experts/re-appraisal-expert"
SCHEMA_SRC="$REPO_ROOT/schema"

PROJECT_SKILLS="$REPO_ROOT/.workbuddy/skills"
USER_HOME="$(eval echo ~)"
USER_SKILLS="$USER_HOME/.workbuddy/skills"
USER_EXPERTS="$USER_HOME/.workbuddy/plugins/marketplaces/my-experts/plugins"

EXPECTED_SKILLS=(
    "appraisal-data-collection"
    "appraisal-report"
    "comps-method"
    "cost-method"
    "hypothetical-dev-method"
    "income-method"
    "web-research-methodology"
)

# ── 辅助函数 ─────────────────────────────────────────────

ensure_dir() {
    mkdir -p "$1"
}

copy_tree() {
    local src="$1"
    local dst="$2"
    ensure_dir "$dst"
    # 使用 rsync 如果可用，否则用 cp
    if command -v rsync &>/dev/null; then
        rsync -a --exclude='.DS_Store' "$src/" "$dst/"
    else
        # cp -a 保留权限和符号链接
        # 先删除目标中已有的同名目录再复制（确保干净覆盖）
        for item in "$src"/*; do
            [ -e "$item" ] || continue
            local name="$(basename "$item")"
            cp -a "$item" "$dst/"
        done
        # 复制隐藏文件/目录（.codebuddy-plugin 等）
        for item in "$src"/.*; do
            [ -e "$item" ] || continue
            local name="$(basename "$item")"
            [[ "$name" == "." || "$name" == ".." ]] && continue
            cp -a "$item" "$dst/"
        done
    fi
}

verify_skills() {
    local path="$1"
    local label="$2"
    local found=0
    for s in "${EXPECTED_SKILLS[@]}"; do
        local skill_file="$path/$s/SKILL.md"
        if [ -f "$skill_file" ]; then
            local lines=$(wc -l < "$skill_file" | tr -d ' ')
            echo -e "    $s : ${lines} lines"
            ((found++))
        else
            warn "$label 缺失: $s"
        fi
    done
    echo "$found"
}

verify_expert() {
    local path="$1"
    local found=0
    local checks=(
        "agents/re-appraisal-expert.md"
        "avatars/expert.png"
        ".codebuddy-plugin/plugin.json"
    )
    for c in "${checks[@]}"; do
        if [ -f "$path/$c" ]; then
            local size=""
            if command -v du &>/dev/null; then
                size="$(du -k "$path/$c" | cut -f1) KB"
            else
                local bytes=$(wc -c < "$path/$c" 2>/dev/null || echo "0")
                if [ "$bytes" -gt 0 ] 2>/dev/null; then
                    size="$(( (bytes + 1023) / 1024 )) KB"
                else
                    size="?"
                fi
            fi
            echo -e "    $c : ${size}"
            ((found++))
        else
            warn "专家缺失: $c"
        fi
    done
    echo "$found"
}

# ── 检查模式 ─────────────────────────────────────────────

if $CHECK_ONLY; then
    section "检查安装状态"
    echo ""
    echo -e "  项目级技能路径: $PROJECT_SKILLS"
    p_count=$(verify_skills "$PROJECT_SKILLS" "项目级")
    echo ""
    echo -e "  用户级技能路径: $USER_SKILLS"
    u_count=$(verify_skills "$USER_SKILLS" "用户级")
    echo ""
    expert_path="$USER_EXPERTS/re-appraisal-expert"
    echo -e "  专家路径: $expert_path"
    e_count=$(verify_expert "$expert_path")
    echo ""
    echo -e "  汇总: 项目级 ${p_count}/7, 用户级 ${u_count}/7, 专家 ${e_count}/3"
    exit 0
fi

# ── 前置检查 ─────────────────────────────────────────────

section "房地产估价 AI 工具链安装"
echo ""
echo -e "  仓库根目录: $REPO_ROOT"
SCOPE=""
$INSTALL_SKILLS  && SCOPE="技能 "
$INSTALL_EXPERTS && SCOPE="${SCOPE}专家"
echo -e "  安装范围:   $SCOPE"
echo ""

if $INSTALL_SKILLS && [ ! -d "$SKILLS_SRC" ]; then
    err "skills/ 目录不存在于 $REPO_ROOT"
    echo -e "  请在仓库根目录运行此脚本" >&2
    exit 1
fi
if $INSTALL_EXPERTS && [ ! -d "$EXPERT_SRC" ]; then
    err "experts/re-appraisal-expert/ 目录不存在于 $REPO_ROOT"
    exit 1
fi

# 确认
if ! $FORCE; then
    echo -e "  即将安装到以下路径：" >&2
    echo -e "    项目级技能: $PROJECT_SKILLS" >&2
    echo -e "    用户级技能: $USER_SKILLS" >&2
    echo -e "    专家:       $USER_EXPERTS/re-appraisal-expert" >&2
    echo ""
    read -p "  确认继续？(y/N) " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo -e "  已取消。"
        exit 0
    fi
fi

# ── 安装技能 ─────────────────────────────────────────────

if $INSTALL_SKILLS; then
    section "安装技能 (7 个)"

    # 项目级
    echo ""
    echo -e "  [1/2] 复制到项目级路径..."
    echo -e "  $PROJECT_SKILLS"
    copy_tree "$SKILLS_SRC" "$PROJECT_SKILLS"
    p_count=$(verify_skills "$PROJECT_SKILLS" "项目级")
    step "项目级 ${p_count}/7 技能已安装"

    # 用户级
    echo ""
    echo -e "  [2/2] 复制到用户级路径..."
    echo -e "  $USER_SKILLS"
    copy_tree "$SKILLS_SRC" "$USER_SKILLS"
    u_count=$(verify_skills "$USER_SKILLS" "用户级")
    step "用户级 ${u_count}/7 技能已安装"

    if [ "$p_count" -lt 7 ] || [ "$u_count" -lt 7 ]; then
        warn "部分技能未安装成功，请检查源目录完整性"
    fi
fi

# ── 安装专家 ─────────────────────────────────────────────

if $INSTALL_EXPERTS; then
    section "安装专家 (re-appraisal-expert)"

    expert_dst="$USER_EXPERTS/re-appraisal-expert"
    echo ""
    echo -e "  复制到用户级专家路径..."
    echo -e "  $expert_dst"
    copy_tree "$EXPERT_SRC" "$expert_dst"
    e_count=$(verify_expert "$expert_dst")
    step "专家 ${e_count}/3 文件已安装"

    if [ "$e_count" -lt 3 ]; then
        warn "部分专家文件未安装成功"
    fi
fi

# ── 复制 Schema ──────────────────────────────────────────

if $INSTALL_SKILLS && [ -d "$SCHEMA_SRC" ]; then
    section "复制 JSON Schema"
    schema_dst="$REPO_ROOT/.workbuddy/schema"
    ensure_dir "$schema_dst"
    cp -r "$SCHEMA_SRC"/* "$schema_dst/" 2>/dev/null || true
    step "Schema 已复制到项目级 .workbuddy/schema/"
    echo -e "  (Schema 仅供技能运行时参考，不影响 WorkBuddy 索引)"
fi

# ── 完成 ─────────────────────────────────────────────────

section "安装完成"
echo ""
echo -e "  技能清单:"
echo -e "    appraisal-data-collection   搜集估价所需资料 (GB/T 50291 3.0.5)"
echo -e "    web-research-methodology    联网信息收集方法论"
echo -e "    comps-method                 比较法测算 (4.2)"
echo -e "    income-method                收益法测算 (4.3)"
echo -e "    cost-method                  成本法测算 (4.4)"
echo -e "    hypothetical-dev-method      假设开发法测算 (4.5)"
echo -e "    appraisal-report             报告生成 (第7章)"
echo ""
echo -e "  专家:"
echo -e "    re-appraisal-expert          房地产估价合规审查专家"
echo ""
echo -e "  数据契约:"
echo -e "    schema/appraisal-result.schema.json  (JSON Schema draft 2020-12)"
echo -e "    schema/example-武汉洪山住宅.json       (完整示例)"
echo ""
echo -e "  ${YELLOW}*** 请重启 WorkBuddy 让新技能索引生效 ***${NC}"
echo ""
echo -e "  验证方式 (重启后):"
echo -e "    ./install.sh --check    # 检查安装状态"
echo -e "    在对话中调用 Skill 工具 (如 skill: 'comps-method')"
echo ""
