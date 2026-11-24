"""Pure helpers for the GitHub <-> Hugging Face dataset sync.

Nothing in this module talks to the network or runs a subprocess except
``git`` read-only plumbing in :func:`manifest_from_git`.  Everything that
comes from the Hub is treated as untrusted data: it is only ever hashed,
compared and written as bytes, never executed or interpolated into a shell.

See docs/sync-huggingface.md for the architecture and guarantees.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Mapping

import yaml

LFS_POINTER_HEADER = b"version https://git-lfs.github.com/spec/v1"
CARD_NAME = "README.md"
CATALOG_YAML = "catalog/dataset.yaml"
TAG_PREFIX = "gh-sync-"
TAG_RE = re.compile(r"^gh-sync-([0-9a-f]{12})$")

# Tracked paths that are never synced.  .gitattributes holds git-lfs rules that
# are meaningless on the Hub (it manages its own .gitattributes for Xet/LFS).
EXCLUDED_TOP = frozenset({".git", ".github", ".gitattributes", ".gitmodules", "staging", "__pycache__"})


class SyncError(Exception):
    """A condition under which the sync must stop without touching anything."""


@dataclass(frozen=True)
class Entry:
    size: int
    sha256: str | None = None  # content sha256 (LFS oid, or computed locally)
    blob1: str | None = None  # git blob sha1 (non-LFS files only)


Manifest = dict[str, Entry]


def same(a: Entry | None, b: Entry | None) -> bool:
    """Content equality across manifests built from different sources.

    Prefers sha256, falls back to git blob sha1.  If the two entries share no
    hash kind they are reported as different (the safe direction for every
    caller: outbound fails closed, inbound merely re-copies identical bytes,
    which git then sees as no change).
    """
    if a is None or b is None:
        return a is None and b is None
    if a.size != b.size:
        return False
    if a.sha256 is not None and b.sha256 is not None:
        return a.sha256 == b.sha256
    if a.blob1 is not None and b.blob1 is not None:
        return a.blob1 == b.blob1
    return False


# ---------------------------------------------------------------- path rules

def is_safe_rel_path(path: str) -> bool:
    if not path or path.startswith("/") or "\\" in path or "\x00" in path:
        return False
    parts = PurePosixPath(path).parts
    return all(p not in ("", ".", "..") for p in parts) and ".git" not in parts


def is_excluded(path: str) -> bool:
    top = PurePosixPath(path).parts[0]
    return top in EXCLUDED_TOP or "__pycache__" in PurePosixPath(path).parts


# --------------------------------------------------------------- dataset card

def split_card(text: str) -> tuple[str | None, str]:
    """Return (front_matter_yaml_or_None, body).  Inverse of :func:`build_card`."""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 3)
    if end == -1:
        return None, text
    front = text[4 : end + 1]
    body = text[end + 5 :]
    if body.startswith("\n"):
        body = body[1:]
    return front, body


def build_card(readme_text: str, dataset_yaml_text: str) -> str:
    """HF dataset card = YAML front matter from catalog/dataset.yaml + GitHub README body."""
    front, _ = split_card(readme_text)
    if front is not None:
        raise SyncError("README.md already has YAML front matter; refusing to stack a second one")
    meta = yaml.safe_load(dataset_yaml_text)
    if not isinstance(meta, dict) or not isinstance(meta.get("configs"), list) or not meta["configs"]:
        raise SyncError(f"{CATALOG_YAML} must be a mapping with a non-empty 'configs' list")
    meta = dict(meta)
    meta.setdefault("pretty_name", "HoloVec")
    dumped = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, default_flow_style=False, width=1000)
    return f"---\n{dumped}---\n\n{readme_text}"


def card_digest(text: str) -> Entry:
    """Manifest entry for a card/README with the generated front matter stripped."""
    _, body = split_card(text)
    data = body.encode("utf-8")
    return Entry(len(data), sha256=hashlib.sha256(data).hexdigest())


def is_trivial_card(text: str) -> bool:
    """A Hub-created default card with no body (safe to replace on first sync)."""
    return split_card(text)[1].strip() == ""


# ------------------------------------------------------------------ manifests

def _hash_file(path: Path) -> Entry:
    sha, blob = hashlib.sha256(), hashlib.sha1()
    size = path.stat().st_size
    blob.update(b"blob %d\x00" % size)
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            sha.update(chunk)
            blob.update(chunk)
    return Entry(size, sha.hexdigest(), blob.hexdigest())


def tracked_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--stage"], check=True, capture_output=True
    ).stdout
    files: list[str] = []
    for rec in out.split(b"\x00"):
        if not rec:
            continue
        meta, _, name = rec.partition(b"\t")
        mode = meta.split()[0].decode()
        path = name.decode("utf-8")
        if is_excluded(path):
            continue
        if mode in ("120000", "160000"):
            raise SyncError(f"{path}: symlinks and submodules are not synced")
        if not is_safe_rel_path(path):
            raise SyncError(f"unsafe tracked path: {path!r}")
        files.append(path)
    return files


def stage_tree(root: Path, out_dir: Path) -> Manifest:
    """Copy tracked files to ``out_dir`` and write the generated dataset card.

    Refuses on LFS pointer files (checkout without ``lfs: true``) and on an
    empty tree.  Returns the manifest of what was staged.
    """
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SyncError(f"staging dir {out_dir} is not empty")
    out_dir.mkdir(parents=True, exist_ok=True)
    files = tracked_files(root)
    if not files:
        raise SyncError("refusing to stage an empty tree")
    for rel in files:
        src = root / rel
        if not src.is_file() or src.is_symlink():
            raise SyncError(f"{rel}: tracked file missing or not a regular file")
        with src.open("rb") as fh:
            head = fh.read(len(LFS_POINTER_HEADER))
        if head == LFS_POINTER_HEADER:
            raise SyncError(f"{rel} is a Git LFS pointer; check out with lfs: true (git lfs pull)")
    if CARD_NAME not in files or CATALOG_YAML not in files:
        raise SyncError(f"{CARD_NAME} and {CATALOG_YAML} must both be tracked")
    for rel in files:
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if rel == CARD_NAME:
            card = build_card(
                (root / CARD_NAME).read_text(encoding="utf-8"),
                (root / CATALOG_YAML).read_text(encoding="utf-8"),
            )
            dst.write_text(card, encoding="utf-8")
        else:
            shutil.copy2(root / rel, dst)
    return manifest_from_dir(out_dir)


def manifest_from_dir(root: Path, *, normalize_card: bool = False) -> Manifest:
    m: Manifest = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            p = Path(dirpath) / name
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                raise SyncError(f"{rel}: symlink in tree")
            m[rel] = _hash_file(p)
    if normalize_card and CARD_NAME in m:
        m[CARD_NAME] = card_digest((root / CARD_NAME).read_text(encoding="utf-8"))
    return m


def manifest_from_git(root: Path, rev: str) -> Manifest:
    """Manifest of the (excluded-filtered) tree at ``rev`` without needing LFS content.

    LFS pointers contribute their oid as sha256; plain blobs contribute the git
    blob sha1.  README.md contributes the digest of its body.
    """
    out = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", "-l", "-z", "--full-tree", rev],
        check=True, capture_output=True,
    ).stdout
    m: Manifest = {}
    for rec in out.split(b"\x00"):
        if not rec:
            continue
        meta, _, name = rec.partition(b"\t")
        mode, typ, oid, size = meta.decode().split()
        path = name.decode("utf-8")
        if typ != "blob" or mode == "120000" or is_excluded(path) or not is_safe_rel_path(path):
            continue
        if path == CARD_NAME:
            data = subprocess.run(
                ["git", "-C", str(root), "cat-file", "blob", oid], check=True, capture_output=True
            ).stdout
            m[path] = card_digest(data.decode("utf-8"))
            continue
        sz = int(size)
        if sz < 300:
            data = subprocess.run(
                ["git", "-C", str(root), "cat-file", "blob", oid], check=True, capture_output=True
            ).stdout
            if data.startswith(LFS_POINTER_HEADER):
                mo = re.search(rb"^oid sha256:([0-9a-f]{64})$", data, re.M)
                ms = re.search(rb"^size (\d+)$", data, re.M)
                if mo and ms:
                    m[path] = Entry(int(ms.group(1)), sha256=mo.group(1).decode())
                    continue
        m[path] = Entry(sz, blob1=oid)
    return m


# ----------------------------------------------------------------- outbound plan

@dataclass
class OutboundPlan:
    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    remote_only: list[str] = field(default_factory=list)  # never touched

    @property
    def changes(self) -> bool:
        return bool(self.added or self.modified)


def plan_outbound(local: Mapping[str, Entry], remote: Mapping[str, Entry]) -> OutboundPlan:
    p = OutboundPlan()
    for path in sorted(local):
        if path not in remote:
            p.added.append(path)
        elif same(local[path], remote[path]):
            p.unchanged.append(path)
        else:
            p.modified.append(path)
    p.remote_only = sorted(set(remote) - set(local))
    return p


def check_guards(
    local: Mapping[str, Entry], remote: Mapping[str, Entry], *, max_drop_percent: float = 10.0
) -> None:
    """Raise SyncError if the push looks like it came from a broken checkout."""
    if not local:
        raise SyncError("guard: staged tree is empty")
    if sum(e.size for e in local.values()) == 0:
        raise SyncError("guard: staged tree has zero bytes")
    if not remote:
        return
    keep = 1.0 - max_drop_percent / 100.0
    lc, rc = len(local), len(remote)
    ls, rs = sum(e.size for e in local.values()), sum(e.size for e in remote.values())
    if lc < rc * keep:
        raise SyncError(
            f"guard: staged file count {lc} is more than {max_drop_percent:g}% below the remote's {rc}"
        )
    if ls < rs * keep:
        raise SyncError(
            f"guard: staged size {ls} B is more than {max_drop_percent:g}% below the remote's {rs} B"
        )


# ----------------------------------------------------------------- inbound plan

@dataclass
class InboundPlan:
    apply: list[str] = field(default_factory=list)  # HF-side add/modify to copy into GitHub
    delete: list[str] = field(default_factory=list)  # removed on HF, untouched on GitHub
    conflicts: list[str] = field(default_factory=list)  # changed on both sides; not applied
    already: list[str] = field(default_factory=list)  # HF change already present on GitHub


def plan_inbound(
    base: Mapping[str, Entry] | None, main: Mapping[str, Entry], remote: Mapping[str, Entry]
) -> InboundPlan:
    """Three-way compare.  ``base`` is the GitHub state last synced (None if unknown).

    Without a base nothing is assumed about who changed what: HF-only files are
    proposed, differing files are listed as conflicts, nothing is deleted.
    """
    p = InboundPlan()
    for path in sorted(set(main) | set(remote) | set(base or {})):
        m, r = main.get(path), remote.get(path)
        b = base.get(path) if base is not None else None
        if base is not None and same(b, r):
            continue  # HF did not change this file since the last sync
        if same(m, r):
            if m is not None and base is not None:
                p.already.append(path)
            continue
        if base is None:
            if r is None:
                continue  # GitHub-only file: outbound's job, never a deletion here
            (p.apply if m is None else p.conflicts).append(path)
        elif same(m, b):  # GitHub untouched since sync, HF changed
            (p.delete if r is None else p.apply).append(path)
        else:
            p.conflicts.append(path)
    return p


# ------------------------------------------------------------- hub state helpers

def pick_base(
    commit_ids_newest_first: Iterable[str], tags: Mapping[str, str]
) -> tuple[str | None, list[str]]:
    """Find the newest HF commit carrying a ``gh-sync-<sha12>`` tag.

    ``tags`` maps tag name -> HF commit id.  Returns (hf_commit, [sha12, ...]).
    """
    by_commit: dict[str, list[str]] = {}
    for name, commit in tags.items():
        mt = TAG_RE.match(name)
        if mt:
            by_commit.setdefault(commit, []).append(mt.group(1))
    for cid in commit_ids_newest_first:
        if cid in by_commit:
            return cid, sorted(by_commit[cid])
    return None, []


def resolve_sync_tags(
    listed: Mapping[str, str],
    commit_ids: Iterable[str],
    peel: Callable[[str], str | None],
) -> dict[str, str]:
    """Map each ``gh-sync-*`` tag to the commit it points at.

    ``listed`` maps tag name -> the id the Hub's refs listing reports.  For a lightweight
    tag that is the commit id; for an annotated tag (what ``create_tag(tag_message=...)``
    makes) it is the id of the tag *object*, which matches no commit.  Tags whose listed id
    is a known commit are used as-is; the rest are resolved with ``peel(tag_name)``, which
    returns the commit id or None.  A tag that cannot be resolved is dropped, so the caller
    sees no sync base and fails closed rather than guessing.  Non-sync tags are ignored.
    """
    known = set(commit_ids)
    out: dict[str, str] = {}
    for name, target in listed.items():
        if not TAG_RE.match(name):
            continue
        if target in known:
            out[name] = target
            continue
        commit = peel(name)
        if commit:
            out[name] = commit
    return out


def is_empty_remote(files: Iterable[str]) -> bool:
    """A freshly created Hub dataset only has the Hub-managed .gitattributes."""
    return set(files) <= {".gitattributes"}


def format_list(title: str, items: list[str], limit: int = 25) -> str:
    if not items:
        return f"{title}: none"
    shown = "\n".join(f"  {i}" for i in items[:limit])
    more = f"\n  ... and {len(items) - limit} more" if len(items) > limit else ""
    return f"{title} ({len(items)}):\n{shown}{more}"
