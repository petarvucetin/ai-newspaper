#!/usr/bin/env bash
# Claude Code status line script
# Shows: current directory, git branch, model name, context usage

input=$(cat)

# Current working directory
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
dir=$(basename "$cwd")

# Git branch (skip optional locks to avoid conflicts)
git_branch=""
if git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git_branch=$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null || git -C "$cwd" rev-parse --short HEAD 2>/dev/null)
fi

# Model display name
model=$(echo "$input" | jq -r '.model.display_name // .model.id // ""')

# Context usage (used percentage, pre-calculated)
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

# Build status line with ANSI colors
# Colors: cyan for dir, yellow for branch, green for model, magenta for context
printf "\033[0;36m%s\033[0m" "$dir"

if [ -n "$git_branch" ]; then
  printf " \033[0;33m(%s)\033[0m" "$git_branch"
fi

if [ -n "$model" ]; then
  printf " \033[0;32m%s\033[0m" "$model"
fi

if [ -n "$used_pct" ]; then
  printf " \033[0;35mctx:%s%%\033[0m" "$used_pct"
fi

echo ""
