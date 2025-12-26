#!/usr/bin/env bash
set -euo pipefail

user_prompt="${*:?usage: vibe <prompt...>}"

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 127; }; }
need_cmd git
need_cmd codex
need_cmd llm
need_cmd gh

LLM_MODEL="gpt-5-mini"

root="$(git rev-parse --show-toplevel)"
mkdir -p "$root/.worktrees"

# Determine base branch from origin/HEAD (fallback to main)
base_branch="$(git symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || true)"
base_branch="${base_branch:-main}"

# Create a slug + unique branch name: feature/<slug>-<timestamp>
slug="$(
  printf "%s" "$user_prompt" | tr '[:upper:]' '[:lower:]' \
  | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' \
  | cut -c1-40
)"
ts="$(date +%Y%m%d-%H%M%S)"
branch="feature/${slug:-task}-${ts}"
wt_dir="$root/.worktrees/${branch//\//-}"

# Create worktree and branch
git -C "$root" worktree add -b "$branch" "$wt_dir"

cd "$wt_dir"

APPEND_PROMPT=$(
  cat <<'EOF'

Additional constraints and guidance are available in the AGENTS.md file.

Most changes should be accompanied with documentation in `docs`.  When asked to plan out a code integration, write the plan as a markdown file in `docs/planning`.  When doing more speculative work or developing something more novel, create a doc in `docs/research`

Do not ask follow-up questions.  You are in a scripted environment where your follow-ups will not be monitored.  The only thing that will be monitored is the eventual PR you create
EOF
)

# Run Codex
codex exec --full-auto "${user_prompt}${APPEND_PROMPT}"

# If nothing changed, exit cleanly
if git diff --quiet && git diff --cached --quiet; then
  echo "No changes to commit."
  echo "Worktree left at: $wt_dir"
  exit 0
fi

# Stage everything
git add -A

# Generate commit subject from staged diff
commit_subject="$(
  git diff --staged | llm --model "$LLM_MODEL" \
    "Write a concise git commit SUBJECT line for these changes.
Use Conventional Commits if reasonable (feat:, fix:, docs:, refactor:).
Output ONLY the subject line, no quotes, no trailing period."
)"

git commit -m "$commit_subject"

# Push branch
git push -u origin HEAD

# Generate PR title
pr_title="$(
  printf "Branch: %s\nBase: %s\nCommit: %s\n\n" "$branch" "$base_branch" "$commit_subject" | llm --model "$LLM_MODEL" \
    "Write a short, descriptive GitHub PR title for this change.
Output ONLY the title line."
)"

# Generate PR body (include context)
pr_body="$(
  {
    echo "Branch: $branch"
    echo "Base: $base_branch"
    echo "Commit: $commit_subject"
    echo
    echo "Recent commits:"
    git --no-pager log --oneline -n 20 "${base_branch}..HEAD" || true
    echo
    echo "Diff summary:"
    git --no-pager diff --stat "${base_branch}..HEAD" || true
    echo
    echo "Full diff:"
    git --no-pager diff "${base_branch}..HEAD" || true
  } | llm --model "$LLM_MODEL" \
    "Write a GitHub PR description (Markdown) for these changes.
Include:
- What changed (bullets)
- Why (brief)
- How to test (clear steps)
- Any risks/notes
Be concise but complete."
)"

# Open PR
gh pr create --base "$base_branch" --head "$branch" --title "$pr_title" --body "$pr_body"

echo "Done."
echo "Branch:   $branch"
echo "Worktree: $wt_dir"
