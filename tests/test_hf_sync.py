"""Tests for scripts/hf_sync*.py using a fake Hub (no network, no token)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hf_sync  # noqa: E402
import hf_sync_core as core  # noqa: E402
from hf_sync_core import Entry, SyncError  # noqa: E402

DATASET_YAML = "language:\n- en\nlicense: other\nconfigs:\n- config_name: all_text\n  default: true\n  data_files: data/a.jsonl\n"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def make_repo(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    files = {
        "README.md": "# Title\n\nbody\n",
        "catalog/dataset.yaml": DATASET_YAML,
        "data/a.jsonl": '{"a": 1}\n',
        "data/b.jsonl": '{"b": 2}\n',
        ".github/workflows/x.yml": "x: 1\n",
        ".gitattributes": "*.parquet filter=lfs\n",
        **(files or {}),
    }
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


def head(root: Path) -> str:
    return git(root, "rev-parse", "HEAD").strip()


class FakeHub:
    """In-memory Hub dataset repo with commit chain, tags and parent_commit semantics."""

    def __init__(self, exists=True, files=None):
        self._exists = exists
        self.commits: list[tuple[str, dict[str, bytes]]] = []  # oldest first
        self.tags: dict[str, str] = {}
        self.calls: list[str] = []
        if exists:
            self._commit({".gitattributes": b"*.bin filter=lfs\n", **{k: v for k, v in (files or {}).items()}})

    def _commit(self, files):
        cid = hashlib.sha1(repr((len(self.commits), sorted(files))).encode()).hexdigest()
        self.commits.append((cid, files))
        return cid

    @property
    def files(self):
        return self.commits[-1][1]

    def external_commit(self, changes: dict[str, bytes | None]):
        files = dict(self.files)
        for k, v in changes.items():
            if v is None:
                files.pop(k, None)
            else:
                files[k] = v
        return self._commit(files)

    # Hub protocol
    def state(self):
        if not self._exists:
            return hf_sync.RemoteState(False)
        ids = [c for c, _ in reversed(self.commits)]
        return hf_sync.RemoteState(True, ids[0], ids, dict(self.tags))

    def tree(self, rev):
        files = dict(self.commits)[rev]
        out = {}
        for p, data in files.items():
            out[p] = Entry(len(data), blob1=hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest())
        return out

    def read_text(self, path, rev):
        return dict(self.commits)[rev][path].decode()

    def download(self, path, rev, dest_dir):
        p = Path(dest_dir) / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(dict(self.commits)[rev][path])
        return p

    def create_repo(self, private):
        calls = self.calls + [f"create_repo private={private}"]
        self.__init__(True)
        self.calls = calls

    def upload(self, folder, parent, message, description):
        self.calls.append("upload")
        if parent != self.commits[-1][0]:
            raise RuntimeError("412 parent_commit mismatch")  # what the Hub does
        files = dict(self.files)  # add/update only, nothing removed
        for p in Path(folder).rglob("*"):
            if p.is_file():
                files[p.relative_to(folder).as_posix()] = p.read_bytes()
        return self._commit(files)

    def tag(self, name, rev, message):
        self.calls.append(f"tag {name}")
        self.tags[name] = rev


def outbound(hub, root, tmp_path, sha=None, **kw):
    stage = tmp_path / f"stage-{len(list(tmp_path.glob('stage-*')))}"
    args = dict(root=root, stage_dir=stage, github_sha=sha or head(root), github_repo="o/r", dry_run=False,
                private=True, create_if_missing=True, adopt_head=None, max_drop_percent=10.0)
    args.update(kw)
    return hf_sync.run_outbound(hub, **args)


# ---------------------------------------------------------------- card

def test_card_roundtrip_and_validity():
    card = core.build_card("# T\n\nbody\n", DATASET_YAML)
    front, body = core.split_card(card)
    assert body == "# T\n\nbody\n"
    assert "configs:" in front and "pretty_name: HoloVec" in front
    assert core.card_digest(card) == core.card_digest("# T\n\nbody\n")
    from huggingface_hub import DatasetCard

    DatasetCard(card)  # parses as valid YAML front matter


def test_card_is_deterministic_and_rejects_double_front_matter():
    a = core.build_card("x\n", DATASET_YAML)
    assert a == core.build_card("x\n", DATASET_YAML)
    with pytest.raises(SyncError):
        core.build_card(a, DATASET_YAML)
    with pytest.raises(SyncError):
        core.build_card("x\n", "language: [en]\n")


def test_path_rules():
    assert core.is_safe_rel_path("a/b.txt")
    for bad in ["", "/etc/passwd", "../x", "a/../b", "a/.git/c", "a\\b", ".git/config"]:
        assert not core.is_safe_rel_path(bad)
    assert core.is_excluded(".github/workflows/x.yml") and core.is_excluded(".gitattributes")
    assert not core.is_excluded("data/x")


# --------------------------------------------------------------- staging

def test_stage_excludes_and_generates_card(tmp_path):
    root = make_repo(tmp_path)
    m = core.stage_tree(root, tmp_path / "s")
    assert set(m) == {"README.md", "catalog/dataset.yaml", "data/a.jsonl", "data/b.jsonl"}
    assert (tmp_path / "s/README.md").read_text().startswith("---\n")
    assert (root / "README.md").read_text() == "# Title\n\nbody\n"  # GitHub README untouched


def test_stage_refuses_lfs_pointer(tmp_path):
    ptr = "version https://git-lfs.github.com/spec/v1\noid sha256:" + "0" * 64 + "\nsize 5\n"
    root = make_repo(tmp_path, {"data/big.parquet": ptr})
    with pytest.raises(SyncError, match="LFS pointer"):
        core.stage_tree(root, tmp_path / "s")


def test_stage_refuses_symlink_and_missing_catalog(tmp_path):
    root = make_repo(tmp_path)
    (root / "link").symlink_to("README.md")
    git(root, "add", "link")
    with pytest.raises(SyncError, match="symlink"):
        core.stage_tree(root, tmp_path / "s")
    root2 = tmp_path / "r2"
    root2.mkdir()
    git(root2, "init", "-q")
    (root2 / "x").write_text("x")
    git(root2, "add", "x")
    with pytest.raises(SyncError, match="must both be tracked"):
        core.stage_tree(root2, tmp_path / "s2")


# ----------------------------------------------------------- plans/guards

def E(n, s="a"):
    return Entry(n, sha256=s)


def test_plan_outbound_never_lists_deletions():
    p = core.plan_outbound({"a": E(1, "x"), "b": E(1, "y")}, {"a": E(1, "x"), "b": E(1, "z"), "c": E(1)})
    assert p.unchanged == ["a"] and p.modified == ["b"] and p.remote_only == ["c"] and p.added == []


def test_guards():
    big = {f"f{i}": E(100) for i in range(20)}
    core.check_guards(big, big)
    with pytest.raises(SyncError, match="empty"):
        core.check_guards({}, big)
    with pytest.raises(SyncError, match="file count"):
        core.check_guards({k: v for k, v in list(big.items())[:10]}, big)
    shrunk = {k: E(10) for k in big}
    with pytest.raises(SyncError, match="size"):
        core.check_guards(shrunk, big)
    with pytest.raises(SyncError, match="zero bytes"):
        core.check_guards({"a": E(0)}, {})


def test_plan_inbound_three_way():
    base = {"keep": E(1, "1"), "hfmod": E(1, "1"), "both": E(1, "1"), "hfdel": E(1, "1"), "gh": E(1, "1")}
    main = {"keep": E(1, "1"), "hfmod": E(1, "1"), "both": E(1, "m"), "hfdel": E(1, "1"), "gh": E(1, "g"),
            "applied": E(1, "n")}
    remote = {"keep": E(1, "1"), "hfmod": E(1, "2"), "both": E(1, "r"), "gh": E(1, "1"), "new": E(1, "n"),
              "applied": E(1, "n")}
    p = core.plan_inbound(base, main, remote)
    assert p.apply == ["hfmod", "new"] or sorted(p.apply) == ["hfmod", "new"]
    assert p.delete == ["hfdel"] and p.conflicts == ["both"]
    assert "applied" in p.already
    # GitHub-only change ("gh") is never reverted by inbound
    assert "gh" not in p.apply + p.delete + p.conflicts


def test_plan_inbound_without_base_never_deletes():
    main = {"a": E(1, "1"), "c": E(1, "3")}
    remote = {"a": E(1, "2"), "b": E(1, "2")}
    p = core.plan_inbound(None, main, remote)
    assert p.apply == ["b"] and p.conflicts == ["a"] and p.delete == []


def test_pick_base_newest_tagged():
    commits = ["c3", "c2", "c1"]
    assert core.pick_base(commits, {"gh-sync-aaaaaaaaaaaa": "c1", "gh-sync-bbbbbbbbbbbb": "c2", "junk": "c3",
                                    "gh-sync-../../x": "c3"}) == ("c2", ["bbbbbbbbbbbb"])
    assert core.pick_base(commits, {}) == (None, [])


# --------------------------------------------------------------- outbound

def test_outbound_bootstrap_into_missing_repo_then_incremental(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=False)
    assert outbound(hub, root, tmp_path) == 0
    assert hub.calls[0].startswith("create_repo private=True") and "upload" in hub.calls
    assert f"gh-sync-{head(root)[:12]}" in hub.tags
    assert hub.files["README.md"].decode().startswith("---\n")
    # next change on GitHub: incremental, fast-forward
    (root / "data/c.jsonl").write_text("{}\n")
    git(root, "add", "-A"), git(root, "commit", "-q", "-m", "c")
    assert outbound(hub, root, tmp_path) == 0
    assert "data/c.jsonl" in hub.files and len(hub.tags) == 2


def test_outbound_dry_run_touches_nothing(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=True)
    assert outbound(hub, root, tmp_path, dry_run=True) == 0
    assert hub.calls == [] and len(hub.commits) == 1 and not hub.tags
    hub2 = FakeHub(exists=False)
    outbound(hub2, root, tmp_path, dry_run=True)
    assert hub2.calls == []


def test_outbound_never_deletes_remote_only_files(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=True)
    outbound(hub, root, tmp_path)
    # a Hub-side file appears, inbound has not run: outbound must fail closed
    hub.external_commit({"hf_only.txt": b"keep me"})
    with pytest.raises(SyncError, match="Hub has commits that GitHub does not have"):
        outbound(hub, root, tmp_path)
    assert "hf_only.txt" in hub.files


def test_outbound_removed_github_file_is_not_deleted_on_hub(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=True)
    outbound(hub, root, tmp_path)
    git(root, "rm", "-q", "data/b.jsonl"), git(root, "commit", "-q", "-m", "rm")
    with pytest.raises(SyncError, match="guard"):  # default 10% guard trips on 1 of 4 files
        outbound(hub, root, tmp_path)
    outbound(hub, root, tmp_path, max_drop_percent=50.0)
    assert "data/b.jsonl" in hub.files  # never deleted; reported as Hub-only


def test_outbound_fails_closed_on_nonempty_unsynced_hub(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=True, files={"data/a.jsonl": b"DIFFERENT\n", "other.txt": b"x"})
    with pytest.raises(SyncError, match="never been synced"):
        outbound(hub, root, tmp_path)
    assert hub.files["data/a.jsonl"] == b"DIFFERENT\n" and not hub.tags


def test_outbound_adopt_head(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=True, files={"extra.txt": b"x"})
    with pytest.raises(SyncError):
        outbound(hub, root, tmp_path)  # no adopt
    with pytest.raises(SyncError):
        outbound(hub, root, tmp_path, adopt_head="0" * 40)  # wrong sha
    assert outbound(hub, root, tmp_path, adopt_head=hub.state().head) == 0
    assert "extra.txt" in hub.files and "data/a.jsonl" in hub.files


def test_outbound_adopt_refuses_when_files_would_be_overwritten(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=True, files={"data/a.jsonl": b"theirs\n"})
    with pytest.raises(SyncError, match="adopt_head refused"):
        outbound(hub, root, tmp_path, adopt_head=hub.state().head)
    assert hub.files["data/a.jsonl"] == b"theirs\n"


def test_outbound_trivial_hub_readme_is_replaceable(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=True, files={"README.md": b"---\nlicense: mit\n---\n"})
    assert outbound(hub, root, tmp_path) == 0
    assert b"Title" in hub.files["README.md"]


def test_outbound_size_guard(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=True)
    outbound(hub, root, tmp_path)
    for i in range(30):
        hub.external_commit({f"x{i}": b"1" * 50})
    sha = head(root)
    hub.tags[f"gh-sync-{sha[:12]}"] = hub.state().head  # pretend the hub head is the synced one
    with pytest.raises(SyncError, match="guard"):
        outbound(hub, root, tmp_path)


def test_outbound_requires_sha_from_head_atomicity(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=True)
    outbound(hub, root, tmp_path)
    (root / "data/c.jsonl").write_text("{}\n")
    git(root, "add", "-A"), git(root, "commit", "-q", "-m", "c")
    orig = hub.upload

    def racing(folder, parent, message, description):
        hub.external_commit({"race.txt": b"1"})  # Hub moves between check and upload
        return orig(folder, parent, message, description)

    hub.upload = racing
    with pytest.raises(RuntimeError, match="parent_commit mismatch"):
        outbound(hub, root, tmp_path)
    assert "data/c.jsonl" not in hub.files


def test_outbound_front_matter_edit_on_hub_fails_closed(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=True)
    outbound(hub, root, tmp_path)
    card = hub.files["README.md"].decode().replace("license: other", "license: mit")
    hub.external_commit({"README.md": card.encode()})
    with pytest.raises(SyncError, match="front matter was edited on the Hub"):
        outbound(hub, root, tmp_path)
    assert b"license: mit" in hub.files["README.md"]


# ---------------------------------------------------------------- inbound

def run_inbound(hub, root, tmp_path):
    rep, body = tmp_path / "rep.json", tmp_path / "body.md"
    assert hf_sync.run_inbound(hub, root=root, report_path=rep, body_path=body) == 0
    return json.loads(rep.read_text()), body


def test_inbound_noop_when_hub_head_is_synced(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=True)
    outbound(hub, root, tmp_path)
    rep, _ = run_inbound(hub, root, tmp_path)
    assert rep["changed"] is False and git(root, "status", "--porcelain") == ""


def test_inbound_proposes_hub_changes_and_loop_closes(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=True)
    outbound(hub, root, tmp_path)
    card = hub.files["README.md"].decode() + "\nHub edit\n"
    hub.external_commit({"data/new.jsonl": b'{"n": 1}\n', "data/b.jsonl": None, "README.md": card.encode(),
                         "../evil": b"x"})
    rep, body = run_inbound(hub, root, tmp_path)
    assert rep["changed"] and sorted(rep["apply"]) == ["README.md", "data/new.jsonl"] and rep["delete"] == ["data/b.jsonl"]
    assert rep["unsafe_paths"] == ["../evil"]
    assert (root / "data/new.jsonl").read_text() == '{"n": 1}\n'
    assert (root / "README.md").read_text() == "# Title\n\nbody\n\nHub edit\n"  # no front matter leaked
    assert not (root / "data/b.jsonl").exists() and not (tmp_path / "evil").exists()
    assert "Nothing was merged" in body.read_text()
    # human merges the PR
    git(root, "add", "-A"), git(root, "commit", "-q", "-m", "merge inbound")
    # loop guard 1: inbound again sees nothing to do
    rep2, _ = run_inbound(hub, root, tmp_path)
    assert rep2["changed"] is False and git(root, "status", "--porcelain") == ""
    # loop guard 2: outbound after the merge uploads nothing (content equal) and only tags
    n = len(hub.commits)
    assert outbound(hub, root, tmp_path) == 0
    # the Hub still lacks nothing; but the merged main has a different card body -> hub is in sync
    assert len(hub.commits) in (n, n + 1)
    rep3, _ = run_inbound(hub, root, tmp_path)
    assert rep3["changed"] is False


def test_inbound_outbound_after_merge_is_tag_only(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=True)
    outbound(hub, root, tmp_path)
    hub.external_commit({"data/new.jsonl": b"n\n"})
    run_inbound(hub, root, tmp_path)
    git(root, "add", "-A"), git(root, "commit", "-q", "-m", "merge inbound")
    n = len(hub.commits)
    hub.calls.clear()
    outbound(hub, root, tmp_path)
    assert len(hub.commits) == n and "upload" not in hub.calls and hub.calls[-1].startswith("tag gh-sync-")


def test_inbound_does_not_revert_github_only_changes(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=True)
    outbound(hub, root, tmp_path)
    (root / "data/gh.jsonl").write_text("{}\n")
    git(root, "add", "-A"), git(root, "commit", "-q", "-m", "gh only")
    hub.external_commit({"data/hf.jsonl": b"h\n"})
    rep, _ = run_inbound(hub, root, tmp_path)
    assert rep["apply"] == ["data/hf.jsonl"] and (root / "data/gh.jsonl").exists()


def test_inbound_conflict_is_reported_not_applied(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=True)
    outbound(hub, root, tmp_path)
    (root / "data/a.jsonl").write_text('{"gh": 1}\n')
    git(root, "add", "-A"), git(root, "commit", "-q", "-m", "gh edit")
    hub.external_commit({"data/a.jsonl": b'{"hf": 1}\n', "data/zzz.jsonl": b"z\n"})
    rep, _ = run_inbound(hub, root, tmp_path)
    assert rep["conflicts"] == ["data/a.jsonl"] and (root / "data/a.jsonl").read_text() == '{"gh": 1}\n'


def test_inbound_front_matter_only_change_is_ignored(tmp_path):
    root = make_repo(tmp_path)
    hub = FakeHub(exists=True)
    outbound(hub, root, tmp_path)
    card = hub.files["README.md"].decode().replace("license: other", "license: mit")
    hub.external_commit({"README.md": card.encode()})
    rep, _ = run_inbound(hub, root, tmp_path)
    assert rep["changed"] is False and rep["front_matter_drift"] is True
    assert git(root, "status", "--porcelain") == ""


def test_manifest_from_git_matches_dir_for_plain_files(tmp_path):
    root = make_repo(tmp_path)
    from_git = core.manifest_from_git(root, "HEAD")
    from_dir = core.manifest_from_dir(root, normalize_card=True)
    for p, e in from_git.items():
        assert core.same(e, from_dir[p]), p
    assert ".github/workflows/x.yml" not in from_git


def test_manifest_from_git_reads_lfs_pointer_oid(tmp_path):
    oid = "ab" * 32
    ptr = f"version https://git-lfs.github.com/spec/v1\noid sha256:{oid}\nsize 12345\n"
    root = make_repo(tmp_path, {"data/big.parquet": ptr})
    e = core.manifest_from_git(root, "HEAD")["data/big.parquet"]
    assert e.sha256 == oid and e.size == 12345


def test_no_shell_or_eval_in_scripts():
    for name in ("hf_sync.py", "hf_sync_core.py"):
        src = (Path(__file__).resolve().parents[1] / "scripts" / name).read_text()
        for bad in ("shell=True", "eval(", "exec(", "os.system", "delete_patterns=", "--force", "create_pr=True"):
            assert bad not in src, f"{name} contains {bad}"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", "true"),  # not configured at any level: private default
        ("   \n", "true"),
        ("true", "true"),
        ("True", "true"),
        (" TRUE\n", "true"),
        ("1", "true"),
        ("false", "false"),
        ("False", "false"),
        (" false\n", "false"),
        ("no", "false"),
        ("0", "false"),
    ],
)
def test_private_flag_normalises_org_and_repo_values(raw, expected):
    assert hf_sync.private_flag(raw) == expected


@pytest.mark.parametrize("raw", ["maybe", "public", "fals", "***", "true false"])
def test_private_flag_rejects_unrecognised_values(raw):
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        hf_sync.private_flag(raw)


def test_private_cli_flag_accepts_messy_value_and_fails_closed_on_junk(capsys):
    # Argument parsing only; no Hub access. Messy-but-valid values parse, junk exits non-zero.
    ns_args = ["outbound", "--repo-id", "o/r", "--stage-dir", "/tmp/x", "--github-sha", "0" * 40]
    with pytest.raises(SystemExit) as exc:
        hf_sync.main(ns_args + ["--private", "maybe"])
    assert exc.value.code == 2
    assert "HF_PRIVATE must be one of" in capsys.readouterr().err
