#!/usr/bin/env bash
# GitHub -> Codeberg, outbound, additive and fast-forward only.
#
# Pushes: main (fast-forward only) and tags (create-only). Nothing else.
# Never uses: --force, --force-with-lease, --mirror, --prune, --delete, '+' refspecs.
# Everything is preflighted before the first byte is pushed; any problem exits
# non-zero with nothing changed on Codeberg.
#
# Env:
#   CODEBERG_URL      https://codeberg.org/<owner>/<repo>.git   (required)
#   DRY_RUN           true|false (default true)
#   CODEBERG_USER / CODEBERG_TOKEN   needed only when DRY_RUN=false
#   CODEBERG_SYNC_SOURCE_REF   refs/remotes/origin/main (default) or refs/heads/main
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/codeberg-sync-lib.sh
source "$here/codeberg-sync-lib.sh"

URL="${CODEBERG_URL:-}"
DRY_RUN="${DRY_RUN:-true}"
SRC_REF="${CODEBERG_SYNC_SOURCE_REF:-refs/remotes/origin/main}"
PRIV_MAIN="refs/codeberg-sync/main"

cs_validate_url "$URL"
cs_validate_dry_run
case "$SRC_REF" in
  refs/remotes/origin/main|refs/heads/main) ;;
  *) cs_die "CODEBERG_SYNC_SOURCE_REF must be refs/remotes/origin/main or refs/heads/main" ;;
esac

git rev-parse --git-dir >/dev/null 2>&1 || cs_die "not inside a git repository"
S="$(git rev-parse --verify --quiet "${SRC_REF}^{commit}")" || cs_die "source ref ${SRC_REF} not found (checkout with fetch-depth: 0)"
if [[ "$(git rev-parse --is-shallow-repository)" == "true" ]]; then
  cs_die "shallow clone: ancestry checks would be unreliable. Use fetch-depth: 0"
fi

if [[ "$DRY_RUN" == "false" && "$URL" == https://* ]]; then
  cs_enable_auth || cs_die "DRY_RUN=false requires CODEBERG_USER and CODEBERG_TOKEN (GitHub variable CODEBERG_USER, secret CODEBERG_TOKEN)"
fi

cs_log "source: ${SRC_REF} = ${S}"
cs_ls_remote "$URL"
R="${CS_REMOTE_REFS[refs/heads/main]:-}"

errors=()
push_main=0
main_count=0

# ---- main: classify -------------------------------------------------------
if [[ -z "$R" ]]; then
  if [[ ${#CS_REMOTE_REFS[@]} -eq 0 ]]; then
    cs_log "Codeberg repo is empty: bootstrap push of main (nothing to overwrite)."
  else
    cs_log "Codeberg has refs but no main: creating main (nothing to overwrite)."
  fi
  push_main=1
  main_count="$(git rev-list --count "$S")"
else
  RF="$(cs_fetch_private "$URL" main "$PRIV_MAIN")"
  if [[ "$RF" != "$R" ]]; then
    cs_log "note: Codeberg main moved during the run (${R} -> ${RF}); using the fetched value"
  fi
  R="$RF"
  if [[ "$R" == "$S" ]]; then
    cs_log "main: Codeberg is already at ${S}. Nothing to push."
  elif git merge-base --is-ancestor "$R" "$S"; then
    dropped="$(git rev-list --count "${S}..${R}")"
    [[ "$dropped" == "0" ]] || cs_die "internal check failed: fast-forward claimed but ${dropped} commits would be dropped"
    main_count="$(git rev-list --count "${R}..${S}")"
    cs_log "main: fast-forward ${R} -> ${S} (${main_count} new commits)"
    push_main=1
  elif git merge-base --is-ancestor "$S" "$R"; then
    errors+=("REFUSED: Codeberg main (${R}) is AHEAD of GitHub main (${S}). Pushing would drop Codeberg-only history. The scheduled inbound workflow (sync-codeberg-in) opens a PR on sync/from-codeberg; merge it with a MERGE COMMIT, then this workflow fast-forwards.")
  else
    errors+=("REFUSED: Codeberg main (${R}) and GitHub main (${S}) have DIVERGED (merge-base: $(git merge-base "$R" "$S" 2>/dev/null || echo none)). Nothing was pushed. See 'Recovery runbook' in docs/sync-codeberg.md.")
  fi
fi

# ---- tags: create-only ----------------------------------------------------
declare -a tag_refspecs=()
declare -a tag_names=()
while IFS=$'\t' read -r ref obj; do
  [[ -n "$ref" ]] || continue
  name="${ref#refs/tags/}"
  if [[ ! "$name" =~ ^[A-Za-z0-9._/-]+$ ]] || ! git check-ref-format "refs/tags/${name}"; then
    cs_warn "skipping tag with unsupported name"; continue
  fi
  if ! commit="$(git rev-parse --verify --quiet "${ref}^{commit}")"; then
    cs_warn "skipping tag '${name}': does not point at a commit"; continue
  fi
  if ! git merge-base --is-ancestor "$commit" "$S"; then
    cs_warn "skipping tag '${name}': its commit is not reachable from main (only main history is mirrored)"; continue
  fi
  remote_obj="${CS_REMOTE_REFS[$ref]:-}"
  if [[ -z "$remote_obj" ]]; then
    tag_refspecs+=("${obj}:${ref}"); tag_names+=("$name")
  elif [[ "$remote_obj" == "$obj" ]]; then
    :  # identical tag already on Codeberg
  else
    errors+=("REFUSED: tag '${name}' exists on Codeberg at ${remote_obj} but GitHub has ${obj}. Tags are never overwritten. Resolve by hand (see runbook).")
  fi
done < <(git for-each-ref --format='%(refname)%09%(objectname)' refs/tags)
cs_log "tags to create on Codeberg: ${#tag_names[@]}"
for n in "${tag_names[@]}"; do cs_log "  + ${n}"; done

# ---- verdict --------------------------------------------------------------
if [[ ${#errors[@]} -gt 0 ]]; then
  for e in "${errors[@]}"; do cs_err "$e"; cs_summary "- $e"; done
  cs_log "Nothing was pushed."
  CS_EXIT=3 cs_die "outbound sync refused (fail closed)"
fi

if [[ $push_main -eq 0 && ${#tag_refspecs[@]} -eq 0 ]]; then
  cs_log "Already in sync."; cs_summary "Codeberg already in sync with GitHub main."; exit 0
fi

cs_summary "### Outbound plan (dry_run=${DRY_RUN})"
cs_summary "- main: ${R:-none} -> ${S} (${main_count} commits)"
cs_summary "- new tags: ${#tag_names[@]}"

if [[ "$DRY_RUN" == "true" ]]; then
  [[ $push_main -eq 1 ]] && cs_log "DRY RUN: would run: git push <codeberg> ${S}:refs/heads/main  (plain fast-forward, no force)"
  for t in "${tag_refspecs[@]}"; do cs_log "DRY RUN: would run: git push <codeberg> ${t}"; done
  exit 0
fi

# ---- LFS objects first, so Codeberg never holds a pointer without its object ----
if command -v git-lfs >/dev/null 2>&1 && [[ -n "$(git lfs ls-files 2>/dev/null | head -n1)" ]]; then
  git remote remove codeberg-sync 2>/dev/null || true
  git remote add codeberg-sync "$URL"
  cs_log "uploading LFS objects to Codeberg (before refs)"
  git lfs fetch origin "$S" || cs_die "could not fetch LFS objects from GitHub"
  git lfs push codeberg-sync "$S" || cs_die "LFS upload to Codeberg failed; refs NOT pushed"
fi

# ---- refs: explicit refspecs, no '+', no --force ----
if [[ $push_main -eq 1 ]]; then
  git push --porcelain --no-verify --no-follow-tags "$URL" "${S}:refs/heads/main" \
    || cs_die "git push of main was rejected by Codeberg (non-fast-forward or permissions). Nothing was forced."
fi
if [[ ${#tag_refspecs[@]} -gt 0 ]]; then
  git push --porcelain --no-verify "$URL" "${tag_refspecs[@]}" \
    || cs_die "git push of tags was rejected by Codeberg. Nothing was forced."
fi
cs_log "outbound sync complete."
