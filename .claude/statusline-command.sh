#!/usr/bin/env bash
# Claude Code status line script
# Format: Model | [bar] pct% | used/total | branch* | repo | 5h:pct%

input=$(cat)

# --- Colors (ANSI 256) ---
RESET='\033[0m'
BOLD='\033[1m'

C_MODEL='\033[38;5;213m'      # magenta/pink  — model name
C_BAR='\033[38;5;82m'         # bright green  — bar fill
C_BAR_EMPTY='\033[38;5;238m'  # dark gray     — bar empty
C_BAR_PCT='\033[38;5;227m'    # yellow        — percentage
C_TOKENS='\033[38;5;117m'     # light blue    — token counts
C_BRANCH='\033[38;5;208m'     # orange        — git branch
C_REPO='\033[38;5;159m'       # pale cyan     — repo name
C_RATE='\033[38;5;203m'       # red/salmon    — rate limit
C_SEP='\033[38;5;240m'        # gray          — separators

SEP="${C_SEP}|${RESET}"

# 1. Model name
model_name=$(echo "$input" | jq -r '.model.display_name // .model.id // "Claude"')
model_short=$(echo "$model_name" | sed 's/^[Cc]laude //I')
seg_model="${C_MODEL}${BOLD}${model_short}${RESET}"

# 2. Context usage bar + percentage
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
if [ -n "$used_pct" ]; then
    used_int=$(printf '%.0f' "$used_pct")
    filled=$(( used_int * 20 / 100 ))
    empty=$(( 20 - filled ))
    bar_fill=$(python3 -c "print('=' * $filled)" 2>/dev/null || printf '%*s' "$filled" '' | tr ' ' '=')
    bar_empty=$(python3 -c "print('-' * $empty)" 2>/dev/null || printf '%*s' "$empty" '' | tr ' ' '-')
    seg_bar="${C_BAR_EMPTY}[${C_BAR}${bar_fill}${C_BAR_EMPTY}${bar_empty}]${RESET} ${C_BAR_PCT}${used_int}%${RESET}"
else
    seg_bar="${C_BAR_EMPTY}[--------------------]${RESET} ${C_BAR_PCT}--%${RESET}"
fi

# 3. Token counts  (current context input / window size)
current_input=$(echo "$input" | jq -r '.context_window.current_usage.input_tokens // 0')
ctx_size=$(echo "$input" | jq -r '.context_window.context_window_size // 200000')

fmt_k() {
    local n=$1
    if [ "$n" -ge 1000 ]; then
        printf '%dk' $(( n / 1000 ))
    else
        printf '%d' "$n"
    fi
}

used_k=$(fmt_k "$current_input")
total_k=$(fmt_k "$ctx_size")
seg_tokens="${C_TOKENS}${used_k}/${total_k}${RESET}"

# 4. Git branch with dirty indicator
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
if [ -n "$cwd" ]; then
    branch=$(git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null)
    if [ -n "$branch" ]; then
        dirty=$(git -C "$cwd" status --porcelain 2>/dev/null | head -1)
        [ -n "$dirty" ] && branch="${branch}*"
        seg_branch="${C_BRANCH}${branch}${RESET}"
    else
        seg_branch="${C_BRANCH}-${RESET}"
    fi
else
    seg_branch="${C_BRANCH}-${RESET}"
fi

# 5. Project/repo name
proj_dir=$(echo "$input" | jq -r '.workspace.project_dir // .workspace.current_dir // .cwd // empty')
repo_name=$([ -n "$proj_dir" ] && basename "$proj_dir" || echo "-")
seg_repo="${C_REPO}${repo_name}${RESET}"

# 6. 5-hour rate limit usage
five_pct=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
if [ -n "$five_pct" ]; then
    five_int=$(printf '%.0f' "$five_pct")
    seg_rate="${C_RATE}5h:${five_int}%${RESET}"
else
    seg_rate=""
fi

# Assemble
line="${seg_model} ${SEP} ${seg_bar} ${SEP} ${seg_tokens} ${SEP} ${seg_branch} ${SEP} ${seg_repo}"
[ -n "$seg_rate" ] && line="${line} ${SEP} ${seg_rate}"

printf "%b" "$line"
