#!/usr/bin/env bash
# Codeberg -> GitHub, inbound, review-only.
#
# Read-only fetch of Codeberg main over anonymous HTTPS. If Codeberg has commits
# that GitHub main lacks, publish them on the single branch sync/from-codeberg and
# open (or leave open) one pull request for a human to review. This script can
# never write to main or any other branch name: the target ref is a constant.
#
# Loop guard (see docs/sync-codeberg.md):
#   1. Codeberg main already an ancestor of GitHub main  -> no-op.
#   2. Trees identical but histories differ (squash/rebase merge) -> warn, no PR.
#   3. The branch is only fast-forwarded, never force-pushed.
#   4. A PR that was closed unmerged at the same Codeberg sha is not reopened.
#
# Env:
#   CODEBERG_URL          https://codeberg.org/<owner>/<repo>.git (required, public repo)
#   DRY_RUN               true|false (default true)
#   GITHUB_REPOSITORY     owner/repo of the GitHub repo (required unless DRY_RUN=true)
#   GH_TOKEN              token for the gh CLI (Actions provides it)
#   CODEBERG_SYNC_GH      gh binary override (tests only)
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/codeberg-sync-lib.sh
source "$here/codeberg-sync-lib.sh"

URL="${CODEBERG_URL:-}"
DRY_RUN="${DRY_RUN:-true}"
GH="${CODEBERG_SYNC_GH:-gh}"
readonly TARGET_BRANCH="sync/from-codeberg"
readonly TARGET_REF="refs/heads/${TARGET_BRANCH}"
readonly PRIV_MAIN="refs/codeberg-sync/main"
readonly GH_MAIN_REF="${CODEBERG_SYNC_GITHUB_MAIN_REF:-refs/remotes/origin/main}"

cs_validate_url "$URL"
cs_validate_dry_run
case "$GH_MAIN_REF" in refs/remotes/origin/main|refs/heads/main) ;; *) cs_die "unexpected GitHub main ref" ;; esac
# Hard assertion: this script never targets main or anything protected.
[[ "$TARGET_BRANCH" != "main" && "$TARGET_BRANCH" == sync/* ]] || cs_die "internal: unsafe target branch"

git rev-parse --git-dir >/dev/null 2>&1 || cs_die "not inside a git repository"
[[ "$(git rev-parse --is-shallow-repository)" == "false" ]] || cs_die "shallow clone: use fetch-depth: 0"
GHM="$(git rev-parse --verify --quiet "${GH_MAIN_REF}^{commit}")" || cs_die "GitHub main (${GH_MAIN_REF}) not found"

cs_ls_remote "$URL"
if [[ -z "${CS_REMOTE_REFS[refs/heads/main]:-}" ]]; then
  cs_log "Codeberg has no main branch yet. Nothing to import."; cs_summary "Codeberg has no main yet."; exit 0
fi
C="$(cs_fetch_private "$URL" main "$PRIV_MAIN")"
cs_log "GitHub main:   ${GHM}"
cs_log "Codeberg main: ${C}"

if git merge-base --is-ancestor "$C" "$GHM"; then
  cs_log "In sync: every Codeberg commit is already on GitHub main."; cs_summary "In sync (nothing to import)."; exit 0
fi

if [[ "$(git rev-parse "${C}^{tree}")" == "$(git rev-parse "${GHM}^{tree}")" ]]; then
  cs_warn "Codeberg main and GitHub main have identical content but different history (a squash/rebase merge of a sync PR?). No PR opened. Outbound sync will refuse until history is reconciled: see the recovery runbook in docs/sync-codeberg.md."
  cs_summary "Identical trees, different history: manual reconcile needed."
  exit 0
fi

N="$(git rev-list --count "${GHM}..${C}")"
cs_log "Codeberg has ${N} commit(s) GitHub main lacks."
cs_summary "### Inbound: ${N} Codeberg commit(s) not on GitHub (dry_run=${DRY_RUN})"

if [[ "$DRY_RUN" == "true" ]]; then
  cs_log "DRY RUN: would fast-forward-push ${C} to ${TARGET_REF} on origin and open/update one PR. Nothing changed."
  exit 0
fi

[[ "${GITHUB_REPOSITORY:-}" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]] || cs_die "GITHUB_REPOSITORY is missing or malformed"
OWNER="${GITHUB_REPOSITORY%%/*}"

# Existing sync branch state on GitHub.
B=""
if ls_out="$(git ls-remote --heads origin "$TARGET_REF")"; then
  B="${ls_out%%[[:space:]]*}"
  [[ -z "$B" || "$B" =~ $CS_SHA_RE ]] || cs_die "malformed ls-remote output from origin"
else
  cs_die "git ls-remote origin failed"
fi

push_branch=1
if [[ -n "$B" ]]; then
  if [[ "$B" == "$C" ]]; then
    push_branch=0
  else
    git update-ref -d refs/codeberg-sync/existing-branch 2>/dev/null || true
    git fetch --quiet --no-tags --no-recurse-submodules origin "${TARGET_REF}:refs/codeberg-sync/existing-branch" \
      || cs_die "cannot fetch existing ${TARGET_BRANCH}"
    if git merge-base --is-ancestor "$B" "$C"; then
      push_branch=1                                  # plain fast-forward
    elif git merge-base --is-ancestor "$C" "$B"; then
      cs_log "${TARGET_BRANCH} already contains ${C} (a human may have added commits). Leaving it alone."
      push_branch=0
    else
      cs_warn "${TARGET_BRANCH} (${B}) has diverged from Codeberg main (${C}). It is NOT force-updated. Merge or delete that branch by hand, then re-run."
      exit 0
    fi
  fi
fi

# GitHub-side LFS: only needed if the incoming diff touches LFS pointers.
if [[ $push_branch -eq 1 ]] && [[ -n "$(git diff --name-only -G'^version https://git-lfs\.github\.com/spec/v1' "$GHM" "$C" | head -n1)" ]]; then
  command -v git-lfs >/dev/null 2>&1 || cs_die "incoming commits touch Git LFS pointers but git-lfs is not installed"
  cs_log "incoming commits touch LFS pointers: mirroring LFS objects Codeberg -> GitHub"
  git remote remove codeberg-src 2>/dev/null || true
  git remote add codeberg-src "$URL"
  git lfs fetch codeberg-src "$C" || cs_die "could not fetch LFS objects from Codeberg; branch NOT pushed"
  git lfs push origin "$C" || cs_die "could not upload LFS objects to GitHub; branch NOT pushed"
fi

if [[ $push_branch -eq 1 ]]; then
  # Constant target ref, no '+', no --force. Rejected by git if it is not a fast-forward.
  git push --porcelain --no-verify origin "${C}:${TARGET_REF}" \
    || cs_die "push to ${TARGET_BRANCH} failed (note: GITHUB_TOKEN cannot push commits that modify .github/workflows; that is by design)"
fi

# ---- pull request (REST only) ----
pulls_json="$("$GH" api "repos/${GITHUB_REPOSITORY}/pulls?state=all&head=${OWNER}:${TARGET_BRANCH}&per_page=100")" \
  || cs_die "could not list pull requests"
open_n="$(jq -r '[.[] | select(.state=="open")] | length' <<<"$pulls_json")"
rejected_n="$(jq -r --arg sha "$C" '[.[] | select(.state=="closed" and .merged_at==null and .head.sha==$sha)] | length' <<<"$pulls_json")"

if [[ "$open_n" != "0" ]]; then
  cs_log "A sync PR is already open; the branch update refreshed it."; cs_summary "Existing sync PR updated."; exit 0
fi
if [[ "$rejected_n" != "0" ]]; then
  cs_warn "A sync PR for Codeberg commit ${C} was closed without merging. Not reopening (loop guard). Delete ${TARGET_BRANCH} or push a new Codeberg commit to get a new PR."
  exit 0
fi

codeberg_web="${URL%.git}"
title="Sync from Codeberg: ${N} new commit(s)"
body="$(cat <<EOF
Codeberg \`main\` has ${N} commit(s) that GitHub \`main\` does not.

- Codeberg head: \`${C}\` ([view](${codeberg_web}/commit/${C}))
- GitHub main: \`${GHM}\`

**Merge this PR with a MERGE COMMIT (not squash, not rebase).** That makes the Codeberg head an ancestor of GitHub \`main\`, which is what lets the outbound sync fast-forward Codeberg afterwards and stops this PR from being reopened.

Opened automatically by \`.github/workflows/sync-codeberg-in.yml\`. Commit contents come from an external host: review them like any other contribution. See \`docs/sync-codeberg.md\`.
EOF
)"
"$GH" api "repos/${GITHUB_REPOSITORY}/pulls" -f "title=${title}" -f "head=${TARGET_BRANCH}" -f "base=main" -f "body=${body}" >/dev/null \
  || cs_die "could not open the pull request"
cs_log "Opened sync PR."; cs_summary "Opened sync PR from ${TARGET_BRANCH}."
