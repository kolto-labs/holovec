#!/usr/bin/env bash
# shellcheck disable=SC2034  # CS_REMOTE_REFS is read by the sourcing scripts
# Shared helpers for the GitHub <-> Codeberg sync scripts. Source it; do not execute.
# Safety stance: every value that comes from a remote (ref names, shas, URLs) is
# untrusted data. It is validated with a strict regex before use and always quoted.

cs_log()  { printf '%s\n' "$*"; }
cs_warn() { if [[ -n "${GITHUB_ACTIONS:-}" ]]; then printf '::warning::%s\n' "$*"; else printf 'WARNING: %s\n' "$*"; fi; }
cs_err()  { if [[ -n "${GITHUB_ACTIONS:-}" ]]; then printf '::error::%s\n' "$*" >&2; else printf 'ERROR: %s\n' "$*" >&2; fi; }
cs_die()  { cs_err "$*"; exit "${CS_EXIT:-1}"; }

cs_summary() { if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then printf '%s\n' "$*" >>"$GITHUB_STEP_SUMMARY"; fi; }

# Only a Codeberg repo over HTTPS is accepted, unless the test harness
# explicitly opts in to local bare repos.
CS_URL_RE='^https://codeberg\.org/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\.git$'
cs_validate_url() {
  local url="${1:-}"
  if [[ "${CODEBERG_SYNC_TEST_ALLOW_LOCAL_URL:-}" == "1" ]]; then
    [[ -n "$url" ]] || cs_die "CODEBERG_URL is empty"
    return 0
  fi
  [[ "$url" =~ $CS_URL_RE ]] || cs_die "CODEBERG_URL must match https://codeberg.org/<owner>/<repo>.git (the given value does not)"
  [[ "$url" != *..* ]] || cs_die "CODEBERG_URL contains '..'"
}

cs_validate_dry_run() {
  case "${DRY_RUN:-true}" in true|false) ;; *) cs_die "DRY_RUN must be exactly 'true' or 'false'" ;; esac
}

# Authenticated HTTPS without putting the secret in argv or on disk: git reads
# config from GIT_CONFIG_* env vars. The header is scoped to codeberg.org only,
# so it can never be sent to another host.
cs_enable_auth() {
  [[ -n "${CODEBERG_TOKEN:-}" && -n "${CODEBERG_USER:-}" ]] || return 1
  [[ "$CODEBERG_USER" =~ ^[A-Za-z0-9._-]+$ ]] || cs_die "CODEBERG_USER has unexpected characters"
  local b64
  b64="$(printf '%s:%s' "$CODEBERG_USER" "$CODEBERG_TOKEN" | base64 -w0)"
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then printf '::add-mask::%s\n' "$b64"; fi
  export GIT_CONFIG_COUNT=1
  export GIT_CONFIG_KEY_0="http.https://codeberg.org/.extraheader"
  export GIT_CONFIG_VALUE_0="Authorization: Basic ${b64}"
  return 0
}

export GIT_TERMINAL_PROMPT=0

CS_SHA_RE='^[0-9a-f]{40}([0-9a-f]{24})?$'

# cs_ls_remote URL -> fills associative array CS_REMOTE_REFS (ref -> sha).
# A failing ls-remote is a hard error: it must never be mistaken for "empty repo".
declare -A CS_REMOTE_REFS=()
cs_ls_remote() {
  local url="$1" out sha ref
  CS_REMOTE_REFS=()
  out="$(git ls-remote --refs "$url")" || cs_die "git ls-remote failed for the remote. Does the repo exist and is it reachable? (see docs/sync-codeberg.md)"
  while IFS=$'\t' read -r sha ref; do
    [[ -n "$sha" ]] || continue
    if [[ "$sha" =~ $CS_SHA_RE && "$ref" == refs/* ]]; then
      CS_REMOTE_REFS["$ref"]="$sha"
    else
      cs_warn "ignoring malformed ls-remote line"
    fi
  done <<<"$out"
}

# Fetch a remote branch into a private namespace, read-only, never checking out.
# The local ref is deleted first so the refspec needs no '+' (no forced update).
# Prints the fetched commit sha.
cs_fetch_private() {
  local url="$1" branch="$2" priv="$3"
  git update-ref -d "$priv" 2>/dev/null || true
  git fetch --quiet --no-tags --no-recurse-submodules "$url" "refs/heads/${branch}:${priv}" \
    || cs_die "failed to fetch ${branch} from the remote"
  git rev-parse --verify --quiet "${priv}^{commit}" || cs_die "fetched ref is not a commit"
}
