#!/usr/bin/env python3
"""GitHub <-> Hugging Face dataset sync driver (see docs/sync-huggingface.md).

Subcommands
  stage     build the staging tree + generated dataset card, print a report
  outbound  GitHub -> Hub: add/update only, atomic via ``parent_commit``, fails closed
  inbound   Hub -> GitHub working tree: applies Hub-side changes for a PR, never pushes

Uses ``huggingface_hub.HfApi`` (upload_folder with ``parent_commit`` and *no*
``delete_patterns``).  The token is read from the HF_TOKEN environment variable
only; it is never accepted on the command line and never printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hf_sync_core import (  # noqa: E402
    CARD_NAME,
    CATALOG_YAML,
    TAG_PREFIX,
    Entry,
    Manifest,
    SyncError,
    build_card,
    card_digest,
    check_guards,
    format_list,
    is_empty_remote,
    is_excluded,
    is_safe_rel_path,
    is_trivial_card,
    manifest_from_git,
    pick_base,
    plan_inbound,
    plan_outbound,
    split_card,
    stage_tree,
)

# Hub limits worth flagging (https://huggingface.co/docs/hub/repositories-recommendations):
# unverified from this sandbox, used only for warnings, never to loosen a guard.
WARN_FILE_BYTES = 20 * 1024**3
WARN_DIR_FILES = 10_000
WARN_REPO_FILES = 100_000


@dataclass
class RemoteState:
    exists: bool
    head: str | None = None
    commits: list[str] | None = None  # newest first
    tags: dict[str, str] | None = None  # tag name -> commit id


class Hub(Protocol):
    def state(self) -> RemoteState: ...
    def tree(self, rev: str) -> Manifest: ...  # raw entries (README.md = raw text digest)
    def read_text(self, path: str, rev: str) -> str: ...
    def download(self, path: str, rev: str, dest_dir: Path) -> Path: ...
    def create_repo(self, private: bool) -> None: ...
    def upload(self, folder: Path, parent: str, message: str, description: str) -> str: ...
    def tag(self, name: str, rev: str, message: str) -> None: ...


class HfHub:
    """Thin adapter over huggingface_hub.HfApi for a single dataset repo."""

    def __init__(self, repo_id: str, token: str | None):
        from huggingface_hub import HfApi

        self.api = HfApi(token=token)
        self.repo_id = repo_id
        self.token = token

    def state(self) -> RemoteState:
        from huggingface_hub.errors import RepositoryNotFoundError

        try:
            commits = [c.commit_id for c in self.api.list_repo_commits(self.repo_id, repo_type="dataset")]
            refs = self.api.list_repo_refs(self.repo_id, repo_type="dataset")
        except RepositoryNotFoundError:
            return RemoteState(False)
        tags = {t.name: t.target_commit for t in refs.tags}
        return RemoteState(True, commits[0] if commits else None, commits, tags)

    def tree(self, rev: str) -> Manifest:
        m: Manifest = {}
        for item in self.api.list_repo_tree(self.repo_id, repo_type="dataset", revision=rev, recursive=True):
            if not hasattr(item, "size"):  # RepoFolder
                continue
            lfs = getattr(item, "lfs", None)
            sha = getattr(lfs, "sha256", None) if lfs else None
            m[item.path] = Entry(item.size, sha256=sha, blob1=None if sha else item.blob_id)
        return m

    def read_text(self, path: str, rev: str) -> str:
        with tempfile.TemporaryDirectory() as td:
            return self.download(path, rev, Path(td)).read_text(encoding="utf-8")

    def download(self, path: str, rev: str, dest_dir: Path) -> Path:
        from huggingface_hub import hf_hub_download

        return Path(
            hf_hub_download(
                self.repo_id, path, repo_type="dataset", revision=rev, local_dir=str(dest_dir), token=self.token
            )
        )

    def create_repo(self, private: bool) -> None:
        self.api.create_repo(self.repo_id, repo_type="dataset", private=private, exist_ok=False)

    def upload(self, folder: Path, parent: str, message: str, description: str) -> str:
        # No delete_patterns, no create_pr: add/update only, rejected by the Hub if
        # main moved away from `parent` (optimistic concurrency).
        info = self.api.upload_folder(
            repo_id=self.repo_id,
            repo_type="dataset",
            folder_path=str(folder),
            parent_commit=parent,
            commit_message=message,
            commit_description=description,
        )
        return info.oid

    def tag(self, name: str, rev: str, message: str) -> None:
        self.api.create_tag(self.repo_id, tag=name, tag_message=message, revision=rev, repo_type="dataset", exist_ok=True)


# ------------------------------------------------------------------ helpers

def out(msg: str = "") -> None:
    print(msg, flush=True)


def summary(md: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(md + "\n")


def remote_manifest(hub: Hub, rev: str, *, normalize_card: bool) -> tuple[Manifest, list[str]]:
    """Hub tree at ``rev`` with unsafe paths dropped; optionally README.md reduced to its body digest."""
    raw = hub.tree(rev)
    safe: Manifest = {}
    unsafe: list[str] = []
    for path, entry in raw.items():
        if is_safe_rel_path(path) and is_excluded(path):
            continue  # Hub-managed (.gitattributes) or non-synced paths: never compared, never touched
        if is_safe_rel_path(path):
            safe[path] = entry
        else:
            unsafe.append(path)
    if CARD_NAME in safe:
        text = hub.read_text(CARD_NAME, rev)
        if normalize_card:
            safe[CARD_NAME] = card_digest(text)
        else:
            data = text.encode("utf-8")
            safe[CARD_NAME] = Entry(len(data), sha256=hashlib.sha256(data).hexdigest())
    return safe, unsafe


def size_warnings(m: Manifest) -> list[str]:
    warns = [f"{p}: {e.size} B exceeds {WARN_FILE_BYTES} B" for p, e in m.items() if e.size > WARN_FILE_BYTES]
    dirs: dict[str, int] = {}
    for p in m:
        d = p.rpartition("/")[0]
        dirs[d] = dirs.get(d, 0) + 1
    warns += [f"{d or '.'}: {n} files in one directory" for d, n in dirs.items() if n > WARN_DIR_FILES]
    if len(m) > WARN_REPO_FILES:
        warns.append(f"{len(m)} files exceeds the recommended {WARN_REPO_FILES}")
    return warns


def token_from_env() -> str | None:
    tok = os.environ.get("HF_TOKEN", "").strip()
    return tok or None


# ------------------------------------------------------------------ outbound

def run_outbound(
    hub: Hub,
    *,
    root: Path,
    stage_dir: Path,
    github_sha: str,
    github_repo: str,
    dry_run: bool,
    private: bool,
    create_if_missing: bool,
    adopt_head: str | None,
    max_drop_percent: float,
) -> int:
    local = stage_tree(root, stage_dir)
    out(f"staged {len(local)} files, {sum(e.size for e in local.values())} bytes")
    for w in size_warnings(local):
        out(f"::warning::{w}")

    state = hub.state()
    if not state.exists:
        if not create_if_missing:
            raise SyncError("Hub dataset repo does not exist and create_if_missing is false (or no access)")
        if dry_run:
            out(f"DRY RUN: would create {'private' if private else 'public'} dataset repo and upload {len(local)} files")
            return 0
        out(f"creating {'private' if private else 'public'} dataset repo (exist_ok=False)")
        hub.create_repo(private)
        state = hub.state()
    if not state.head:
        raise SyncError("could not determine Hub head commit")

    remote, unsafe = remote_manifest(hub, state.head, normalize_card=False)
    if unsafe:
        out(f"::warning::ignoring {len(unsafe)} Hub paths with unsafe names (never touched)")
    base_commit, prefixes = pick_base(state.commits or [], state.tags or {})
    plan = plan_outbound(local, remote)

    remote_readme = hub.read_text(CARD_NAME, state.head) if CARD_NAME in remote else None
    effective = [p for p in remote if p != ".gitattributes" and not (p == CARD_NAME and remote_readme and is_trivial_card(remote_readme))]
    empty = is_empty_remote(effective)

    if empty:
        mode = "bootstrap-empty"
    elif base_commit == state.head:
        mode = "incremental"
    elif not plan.added and not plan.modified and not plan.remote_only:
        mode = "already-in-sync"
    elif plan.modified == [CARD_NAME] and not plan.added and not plan.remote_only and remote_readme is not None \
            and card_digest(remote_readme) == card_digest(build_card((root / CARD_NAME).read_text(encoding="utf-8"), (root / CATALOG_YAML).read_text(encoding="utf-8"))):
        raise SyncError(
            "the dataset card front matter was edited on the Hub. It is generated from "
            f"{CATALOG_YAML}; port the change there (or revert it on the Hub), then re-run. Nothing was changed."
        )
    elif adopt_head and adopt_head == state.head:
        bad = [p for p in plan.modified if not (p == CARD_NAME and remote_readme and is_trivial_card(remote_readme))]
        if bad:
            raise SyncError("adopt_head refused: these files differ between GitHub and the Hub:\n" + format_list("modified", bad))
        mode = "bootstrap-adopt"
    else:
        why = (
            "the Hub repo is not empty and has never been synced from GitHub (no gh-sync-* tag)"
            if not base_commit
            else "the Hub has commits that GitHub does not have (head is past the last synced commit)"
        )
        raise SyncError(
            f"refusing to push: {why}.\n"
            f"  hub head: {state.head}\n  last synced: {base_commit or 'never'}\n"
            + format_list("differences, would be added", plan.added, 10) + "\n"
            + format_list("differences, would overwrite", plan.modified, 10) + "\n"
            + format_list("differences, Hub-only", plan.remote_only, 10) + "\n"
            "Nothing was changed. Run the inbound sync, review and merge its PR, then re-run; see "
            "docs/sync-huggingface.md (recovery runbook)."
        )

    out(f"mode: {mode}; hub head {state.head[:12]}; last synced hub commit {base_commit or 'none'} {prefixes}")
    out(format_list("add", plan.added))
    out(format_list("update", plan.modified))
    out(f"unchanged: {len(plan.unchanged)}")
    out(format_list("Hub-only (left untouched, never deleted)", plan.remote_only))

    if mode != "already-in-sync":
        check_guards(local, remote, max_drop_percent=max_drop_percent)

    summary(
        f"### Outbound sync ({mode})\n- add: {len(plan.added)}\n- update: {len(plan.modified)}\n"
        f"- unchanged: {len(plan.unchanged)}\n- Hub-only, untouched: {len(plan.remote_only)}\n- dry run: {dry_run}"
    )
    if dry_run:
        out("DRY RUN: nothing uploaded or tagged")
        return 0

    tag = f"{TAG_PREFIX}{github_sha[:12]}"
    msg = f"GitHub-Sha: {github_sha}"
    target = state.head
    if mode != "already-in-sync" and plan.changes:
        description = f"{msg}\nSource: https://github.com/{github_repo}/commit/{github_sha}\nGenerated by scripts/hf_sync.py"
        target = hub.upload(stage_dir, state.head, f"Sync from GitHub {github_sha[:12]}", description)
        out(f"uploaded as Hub commit {target}")
    else:
        out("no content changes to upload")
    hub.tag(tag, target, msg)
    out(f"tagged {target[:12]} as {tag}")
    return 0


# ------------------------------------------------------------------- inbound

def _resolve_base(root: Path, prefixes: list[str]) -> str | None:
    best: tuple[int, str] | None = None
    for p in prefixes:
        r = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "--quiet", f"{p}^{{commit}}"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            continue
        sha = r.stdout.strip()
        ct = int(subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%ct", sha], check=True, capture_output=True, text=True).stdout)
        if best is None or ct > best[0]:
            best = (ct, sha)
    return best[1] if best else None


def run_inbound(hub: Hub, *, root: Path, report_path: Path, body_path: Path) -> int:
    report: dict = {"changed": False}
    state = hub.state()
    if not state.exists or not state.head:
        out("Hub repo not found or empty: nothing to pull")
        report_path.write_text(json.dumps(report))
        return 0
    base_commit, prefixes = pick_base(state.commits or [], state.tags or {})
    report.update(hub_head=state.head, base_hub_commit=base_commit)
    if base_commit == state.head:
        out("Hub head is the commit GitHub last pushed (gh-sync tag): nothing to pull")
        report_path.write_text(json.dumps(report))
        return 0

    remote, unsafe = remote_manifest(hub, state.head, normalize_card=True)
    remote = {p: e for p, e in remote.items() if not is_excluded(p)}
    # GitHub side is read from git objects (LFS pointers carry the sha256), so the
    # daily run does not need to download any LFS content.
    main = manifest_from_git(root, "HEAD")
    base_rev = _resolve_base(root, prefixes)
    base = manifest_from_git(root, base_rev) if base_rev else None
    warnings = []
    if prefixes and base_rev is None:
        warnings.append("synced GitHub commit from the Hub tag is not in this clone; treating as unknown base")
    if not prefixes:
        warnings.append("Hub has never been synced from GitHub (no gh-sync tag); only Hub-only files are proposed")
    plan = plan_inbound(base, main, remote)

    # Front matter drift (informational: the card front matter is GitHub-owned).
    fm_drift = False
    if CARD_NAME in remote:
        gen = build_card((root / CARD_NAME).read_text(encoding="utf-8"), (root / CATALOG_YAML).read_text(encoding="utf-8"))
        fm_drift = split_card(hub.read_text(CARD_NAME, state.head))[0] != split_card(gen)[0]

    report.update(
        base_github_commit=base_rev, apply=plan.apply, delete=plan.delete, conflicts=plan.conflicts,
        already=plan.already, unsafe_paths=unsafe, front_matter_drift=fm_drift, warnings=warnings,
    )
    if not plan.apply and not plan.delete:
        out(format_list("conflicts (not applied)", plan.conflicts))
        out("no Hub-side changes to apply")
        report_path.write_text(json.dumps(report))
        return 0

    with tempfile.TemporaryDirectory() as td:
        for path in plan.apply:
            if not is_safe_rel_path(path) or is_excluded(path):
                raise SyncError(f"refusing unsafe path from Hub: {path!r}")
            dest = root / path
            if path == CARD_NAME:
                _, body = split_card(hub.read_text(CARD_NAME, state.head))
                dest.write_text(body, encoding="utf-8")
                continue
            got = hub.download(path, state.head, Path(td))
            if got.stat().st_size != remote[path].size:
                raise SyncError(f"{path}: downloaded size does not match the Hub tree listing")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(got, dest)
    for path in plan.delete:
        if is_safe_rel_path(path) and not is_excluded(path) and (root / path).is_file():
            (root / path).unlink()

    report["changed"] = True
    report_path.write_text(json.dumps(report, indent=1))
    body_path.write_text(_pr_body(report, state.head))
    out(format_list("applied from Hub", plan.apply) + "\n" + format_list("deleted (removed on Hub)", plan.delete))
    out(format_list("conflicts (not applied)", plan.conflicts))
    return 0


def _pr_body(rep: dict, head: str) -> str:
    def block(title: str, items: list[str]) -> str:
        if not items:
            return ""
        body = "\n".join(f"- `{i}`" for i in items[:50])
        more = f"\n- ... and {len(items) - 50} more" if len(items) > 50 else ""
        return f"\n**{title} ({len(items)})**\n{body}{more}\n"

    notes = "".join(f"\n> {w}" for w in rep.get("warnings", []))
    fm = "\n> The dataset card front matter on the Hub differs from the generated one. It is GitHub-owned and was not imported; edit `catalog/dataset.yaml` instead." if rep.get("front_matter_drift") else ""
    return (
        f"Automated proposal from the Hugging Face dataset, Hub revision `{head}`.\n"
        "Review the diff like any other contribution. Nothing was merged or pushed to `main`.\n"
        f"{notes}{fm}\n"
        f"{block('Added or changed on the Hub', rep['apply'])}"
        f"{block('Removed on the Hub', rep['delete'])}"
        f"{block('Conflicts, changed on both sides and NOT applied', rep['conflicts'])}"
        f"{block('Hub paths ignored as unsafe', rep['unsafe_paths'])}"
        "\nAfter merging, the outbound workflow sees the trees match and only records the sync marker; it does not push again.\n"
    )


# ----------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("stage", "outbound", "inbound"):
        p = sub.add_parser(name)
        p.add_argument("--root", type=Path, default=Path("."))
        if name != "inbound":
            p.add_argument("--stage-dir", type=Path, required=True)
        if name != "stage":
            p.add_argument("--repo-id", required=True)
    sub.choices["outbound"].add_argument("--github-sha", required=True)
    sub.choices["outbound"].add_argument("--github-repo", default="")
    sub.choices["outbound"].add_argument("--dry-run", action="store_true")
    sub.choices["outbound"].add_argument("--private", choices=["true", "false"], default="true")
    sub.choices["outbound"].add_argument("--create-if-missing", action="store_true")
    sub.choices["outbound"].add_argument("--adopt-head", default="")
    sub.choices["outbound"].add_argument("--max-drop-percent", type=float, default=10.0)
    sub.choices["inbound"].add_argument("--report", type=Path, required=True)
    sub.choices["inbound"].add_argument("--pr-body", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "stage":
            m = stage_tree(a.root, a.stage_dir)
            out(f"staged {len(m)} files, {sum(e.size for e in m.values())} bytes -> {a.stage_dir}")
            for w in size_warnings(m):
                out(f"WARNING {w}")
            return 0
        hub = HfHub(a.repo_id, token_from_env())
        if a.cmd == "outbound":
            if not a.dry_run and not token_from_env():
                raise SyncError("HF_TOKEN is not set")
            if len(a.github_sha) != 40 or any(c not in "0123456789abcdef" for c in a.github_sha):
                raise SyncError("--github-sha must be a full 40-char lowercase hex sha")
            if a.adopt_head and (len(a.adopt_head) != 40 or any(c not in "0123456789abcdef" for c in a.adopt_head)):
                raise SyncError("--adopt-head must be a full 40-char lowercase hex Hub commit sha")
            return run_outbound(
                hub, root=a.root, stage_dir=a.stage_dir, github_sha=a.github_sha, github_repo=a.github_repo,
                dry_run=a.dry_run, private=a.private == "true", create_if_missing=a.create_if_missing,
                adopt_head=a.adopt_head or None, max_drop_percent=a.max_drop_percent,
            )
        return run_inbound(hub, root=a.root, report_path=a.report, body_path=a.pr_body)
    except SyncError as exc:
        print(f"::error::{exc}")
        summary(f"### Sync stopped (fail closed)\n```\n{exc}\n```")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
