#!/usr/bin/env bash
# Offline test of the Codeberg sync guards using throwaway local bare repos.
# "GitHub" and "Codeberg" are local bare repositories; gh is replaced by a stub.
# Run: scripts/codeberg-sync-test.sh        (needs git, jq, bash)
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$here/codeberg-sync-out.sh"
IN="$here/codeberg-sync-in.sh"

T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
export GIT_CONFIG_GLOBAL="$T/gitconfig" GIT_CONFIG_SYSTEM=/dev/null
git config --global user.name tester
git config --global user.email tester@example.invalid
git config --global init.defaultBranch main
git config --global protocol.file.allow always
export CODEBERG_SYNC_TEST_ALLOW_LOCAL_URL=1

pass=0; fail=0
ok()   { pass=$((pass+1)); printf 'PASS  %s\n' "$1"; }
bad()  { fail=$((fail+1)); printf 'FAIL  %s\n' "$1"; }
check() { local d="$1"; shift; if "$@"; then ok "$d"; else bad "$d"; fi; }
sha_of() { git --git-dir="$1" rev-parse --verify --quiet "$2" 2>/dev/null || echo none; }
show() { grep -E "$1" "$2" | sed 's/^/    /' | cut -c1-220 || true; }
commit_in() { # repo-worktree file content msg
  ( cd "$1" && printf '%s\n' "$3" >"$2" && git add "$2" && git commit -q -m "$4" ); }

new_world() { # creates $W/{gh.git,cb.git,work}
  W="$T/w$1"; mkdir -p "$W"
  git init -q --bare "$W/gh.git"; git init -q --bare "$W/cb.git"
  git clone -q "$W/gh.git" "$W/work" 2>/dev/null
  commit_in "$W/work" a.txt one "c1"
  commit_in "$W/work" a.txt two "c2"
  ( cd "$W/work" && git push -q origin main )
}
run_out() { # DRY_RUN
  ( cd "$W/work" && CODEBERG_URL="$W/cb.git" DRY_RUN="$1" CODEBERG_SYNC_SOURCE_REF=refs/heads/main "$OUT" ) >"$W/out.log" 2>&1
}

echo "=== static: forbidden flags must not appear in executable lines ==="
if grep -nE -- '--force|--mirror|--prune|--delete|push[^#]*[[:space:]]\+[^[:space:]]*:' "$OUT" "$IN" "$here/codeberg-sync-lib.sh" \
     | grep -vE '^[^:]+:[0-9]+:[[:space:]]*#'; then bad "forbidden flag found"; else ok "no --force/--mirror/--prune/--delete/+refspec in scripts"; fi

echo "=== URL validation ==="
url_ok=1
( unset CODEBERG_SYNC_TEST_ALLOW_LOCAL_URL
  cd "$T" && git init -q --bare v.git
  for u in "http://codeberg.org/a/b.git" "https://evil.example/a/b.git" "https://codeberg.org/a/b" "https://codeberg.org/a/../b.git" "file:///tmp/x.git"; do
    if CODEBERG_URL="$u" DRY_RUN=true "$OUT" >/dev/null 2>&1; then echo "ACCEPTED $u"; exit 1; fi
  done ) && url_ok=0
if [[ $url_ok -eq 0 ]]; then ok "rejects non-codeberg / non-https / malformed URLs"; else bad "URL validation"; fi

echo "=== OUT 1: bootstrap into empty Codeberg ==="
new_world 1
check "dry run on empty remote succeeds and changes nothing" run_out true
check "  remote still empty after dry run" test "$(sha_of "$W/cb.git" refs/heads/main)" = none
run_out true || true; show 'DRY RUN|bootstrap' "$W/out.log"
check "real push bootstraps main" run_out false
check "  Codeberg main == GitHub main" test "$(sha_of "$W/cb.git" refs/heads/main)" = "$(sha_of "$W/gh.git" refs/heads/main)"

echo "=== OUT 2: fast-forward succeeds ==="
commit_in "$W/work" b.txt x "c3"; ( cd "$W/work" && git push -q origin main )
check "fast-forward push succeeds" run_out false
show 'fast-forward' "$W/out.log"
check "  Codeberg main advanced to GitHub main" test "$(sha_of "$W/cb.git" refs/heads/main)" = "$(sha_of "$W/work/.git" refs/heads/main)"
check "re-run is a no-op success" run_out false
show 'Nothing to push|Already' "$W/out.log"

echo "=== OUT 3: Codeberg ahead (Codeberg-only commit) fails closed ==="
git clone -q "$W/cb.git" "$W/cbwork"; commit_in "$W/cbwork" cb-only.txt secret "codeberg-only"; ( cd "$W/cbwork" && git push -q origin main )
before="$(sha_of "$W/cb.git" refs/heads/main)"
if run_out false; then bad "should have failed"; else ok "refuses when Codeberg is ahead"; fi
show 'REFUSED|Nothing was pushed' "$W/out.log"
check "  Codeberg main untouched" test "$(sha_of "$W/cb.git" refs/heads/main)" = "$before"

echo "=== OUT 4: diverged histories fail closed (the non-fast-forward case) ==="
commit_in "$W/work" gh-only.txt y "github-only"; ( cd "$W/work" && git push -q origin main )
if run_out false; then bad "should have failed"; else ok "refuses diverged history with non-zero exit"; fi
show 'DIVERGED|Nothing was pushed' "$W/out.log"
check "  Codeberg main untouched (Codeberg-only commit survives)" test "$(sha_of "$W/cb.git" refs/heads/main)" = "$before"
if run_out true; then bad "dry run should also refuse"; else ok "  dry run also refuses"; fi

echo "=== OUT 5: tags are create-only ==="
new_world 5
( cd "$W/work" && git tag v1 && git tag -a v2 -m annotated && git push -q origin main --tags )
check "initial push with tags" run_out false
check "  tags present on Codeberg" test "$(sha_of "$W/cb.git" refs/tags/v1)" = "$(sha_of "$W/gh.git" refs/tags/v1)"
commit_in "$W/work" t.txt t "c3"; ( cd "$W/work" && git push -q origin main )
# retarget v1 locally to a different commit: must be an error, never an overwrite
( cd "$W/work" && git tag -f v1 HEAD >/dev/null )
old_v1="$(sha_of "$W/cb.git" refs/tags/v1)"
if run_out false; then bad "retargeted tag should fail"; else ok "refuses to overwrite a differing tag"; fi
show "REFUSED: tag" "$W/out.log"
check "  remote tag unchanged" test "$(sha_of "$W/cb.git" refs/tags/v1)" = "$old_v1"
check "  preflight is all-or-nothing: main not pushed either" test "$(sha_of "$W/cb.git" refs/heads/main)" != "$(sha_of "$W/work/.git" refs/heads/main)"
( cd "$W/work" && git tag -f v1 "$old_v1" >/dev/null )
# a tag on an unmerged side branch is skipped
( cd "$W/work" && git checkout -q -b side && printf s >side.txt && git add side.txt && git commit -q -m side && git tag side-tag && git checkout -q main )
run_out false || true
check "tag not reachable from main is skipped" test "$(sha_of "$W/cb.git" refs/tags/side-tag)" = none

echo "=== IN: stub gh, local GitHub/Codeberg ==="
STUB="$T/stub"; mkdir -p "$STUB"
cat >"$STUB/gh" <<'STUBEOF'
#!/usr/bin/env bash
# stub: GET pulls -> canned json; POST pulls (has -f) -> recorded
if [[ " $* " == *" -f "* ]]; then printf 'POST %s\n' "$*" >>"$STUB_DIR/calls.log"; echo '{}'; exit 0; fi
cat "$STUB_DIR/pulls.json"
STUBEOF
chmod +x "$STUB/gh"
run_in() { # DRY_RUN
  ( cd "$W/work" && CODEBERG_URL="$W/cb.git" DRY_RUN="$1" GITHUB_REPOSITORY=kolto-labs/holovec \
      CODEBERG_SYNC_GH="$STUB/gh" STUB_DIR="$STUB" CODEBERG_SYNC_GITHUB_MAIN_REF=refs/heads/main "$IN" ) >"$W/in.log" 2>&1
}
posts() { if [[ -f "$STUB/calls.log" ]]; then grep -c '^POST ' "$STUB/calls.log" || true; else echo 0; fi; }

new_world 6; rm -f "$STUB/calls.log"; echo '[]' >"$STUB/pulls.json"
git --git-dir="$W/gh.git" push -q "$W/cb.git" main:main
GH_MAIN="$(sha_of "$W/gh.git" refs/heads/main)"
check "IN: in sync -> no-op" run_in false
check "  no branch, no PR" test "$(sha_of "$W/gh.git" refs/heads/sync/from-codeberg)/$(posts)" = "none/0"

git clone -q "$W/cb.git" "$W/cbwork"; commit_in "$W/cbwork" c1.txt a "cb1"; commit_in "$W/cbwork" c2.txt b "cb2"; ( cd "$W/cbwork" && git push -q origin main )
C="$(sha_of "$W/cb.git" refs/heads/main)"
check "IN: dry run changes nothing" run_in true
check "  no branch created in dry run" test "$(sha_of "$W/gh.git" refs/heads/sync/from-codeberg)" = none
check "IN: Codeberg ahead -> branch pushed" run_in false
check "  sync/from-codeberg == Codeberg main" test "$(sha_of "$W/gh.git" refs/heads/sync/from-codeberg)" = "$C"
check "  GitHub main untouched" test "$(sha_of "$W/gh.git" refs/heads/main)" = "$GH_MAIN"
check "  exactly one PR opened" test "$(posts)" = 1
grep '^POST ' "$STUB/calls.log" | cut -c1-150 | sed 's/^/    /' || true

echo '[{"state":"open","merged_at":null,"head":{"sha":"'"$C"'"}}]' >"$STUB/pulls.json"
check "IN: re-run with open PR -> no duplicate PR" run_in false
check "  still exactly one PR" test "$(posts)" = 1

echo "--- loop guard: merge commit closes the loop"
( cd "$W/work" && git fetch -q "$W/cb.git" main && git merge -q --no-ff -m "Merge Codeberg" FETCH_HEAD && git push -q origin main )
echo '[]' >"$STUB/pulls.json"
check "IN after merge-commit merge -> in sync, no new PR" run_in false
check "  still exactly one PR total" test "$(posts)" = 1
check "OUT after merge-commit merge -> fast-forward Codeberg" run_out false
check "  Codeberg == GitHub main (no bounce, no loss)" test "$(sha_of "$W/cb.git" refs/heads/main)" = "$(sha_of "$W/gh.git" refs/heads/main)"

echo "--- loop guard: PR closed unmerged is not reopened"
new_world 7; rm -f "$STUB/calls.log"
git --git-dir="$W/gh.git" push -q "$W/cb.git" main:main
git clone -q "$W/cb.git" "$W/cbwork"; commit_in "$W/cbwork" r.txt r "cbr"; ( cd "$W/cbwork" && git push -q origin main )
C="$(sha_of "$W/cb.git" refs/heads/main)"
echo '[{"state":"closed","merged_at":null,"head":{"sha":"'"$C"'"}}]' >"$STUB/pulls.json"
check "IN: rejected PR at same sha -> not reopened" run_in false
check "  no PR POSTed" test "$(posts)" = 0

echo "--- loop guard: squash merge (identical trees, different history)"
new_world 8; rm -f "$STUB/calls.log"; echo '[]' >"$STUB/pulls.json"
git --git-dir="$W/gh.git" push -q "$W/cb.git" main:main
git clone -q "$W/cb.git" "$W/cbwork"; commit_in "$W/cbwork" sq.txt s "cb-squash-me"; ( cd "$W/cbwork" && git push -q origin main )
( cd "$W/work" && printf 's\n' >sq.txt && git add sq.txt && git commit -q -m "squashed copy" && git push -q origin main )
check "IN: identical trees -> warn, no branch, no PR" run_in false
check "  nothing created" test "$(sha_of "$W/gh.git" refs/heads/sync/from-codeberg)/$(posts)" = "none/0"
show 'identical content' "$W/in.log"
cb_before="$(sha_of "$W/cb.git" refs/heads/main)"
if run_out false; then bad "OUT must refuse after squash"; else ok "OUT refuses (diverged) after squash, Codeberg untouched"; fi
check "  Codeberg main unchanged" test "$(sha_of "$W/cb.git" refs/heads/main)" = "$cb_before"

echo "--- sync branch diverged: never force-updated"
new_world 9; rm -f "$STUB/calls.log"; echo '[]' >"$STUB/pulls.json"
git --git-dir="$W/gh.git" push -q "$W/cb.git" main:main
( cd "$W/work" && git checkout -q -b sync/from-codeberg && commit_in . human.txt h "human work" && git push -q origin sync/from-codeberg && git checkout -q main )
git clone -q "$W/cb.git" "$W/cbwork"; commit_in "$W/cbwork" n.txt n "cb-new"; ( cd "$W/cbwork" && git push -q origin main )
hb="$(sha_of "$W/gh.git" refs/heads/sync/from-codeberg)"
check "IN: diverged sync branch -> left alone, exit 0" run_in false
check "  branch not force-updated" test "$(sha_of "$W/gh.git" refs/heads/sync/from-codeberg)" = "$hb"

echo
echo "passed=$pass failed=$fail"
[[ $fail -eq 0 ]]
