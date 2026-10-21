#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CADE Intent Gate acceptance tests
==================================

Exercises ``tools/check_intent.py`` against throwaway git repositories.

The load-bearing property under test is stated in AGENTS.md section 4: the
gate must not punish an author who never learned about the gate.  Every
"must not block" case below therefore asserts a *commit-shaped* outcome
(staged controlled asset + allowed verdict), not merely that the tool runs.

Run:  python tests/test_intent_gate.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TOOLS = SKILL_ROOT / "tools"
GATE = TOOLS / "check_intent.py"

sys.path.insert(0, str(SKILL_ROOT / "skills"))
sys.path.insert(0, str(TOOLS))

PASSED = 0
FAILED = 0


def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [ok]   {name}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name}" + (f"  -- {detail}" if detail else ""))


def run_gate(*args, expect=None):
    """Run the CLI and return (exit_code, parsed_json_or_None, stdout)."""
    proc = subprocess.run(
        [sys.executable, str(GATE), *args, "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload = None
    if proc.stdout.strip().startswith("{"):
        try:
            payload = json.loads(proc.stdout)
        except ValueError:
            payload = None
    if expect is not None:
        check(
            f"exit code {expect} for {' '.join(a for a in args if not a.startswith('--'))}",
            proc.returncode == expect,
            f"got {proc.returncode}; stderr={proc.stderr.strip()[:200]}",
        )
    return proc.returncode, payload, proc.stdout + proc.stderr


class TempRepo:
    """A disposable git repository with a couple of CAA-shaped modules."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="cade_intent_")
        self.root = Path(self._tmp.name).resolve()
        self._git("init", "-q")
        self._git("config", "user.email", "gate@test.local")
        self._git("config", "user.name", "Intent Gate Test")
        self._git("config", "commit.gpgsign", "false")
        # Mirror the production workspace: CRLF on disk, LF in the index.
        self._git("config", "core.autocrlf", "true")

        self.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() {}\n")
        self.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.h", "class FooCmd {};\n")
        self.write("CAAFoo.edu/CAAFoo.m/Imakefile.mk", "LINK_WITH=CATApplicationFrame\n")
        self.write("CAAFoo.edu/CAAFoo.m/IdentityCard.xml", "<IdentityCard/>\n")
        self.write("CAAFoo.edu/CAAFoo.m/CNext/resources/msgcatalog/Foo.CATNls", "a=1;\n")
        self.write("CAAFoo.edu/CAAFoo.m/CNext/resources/dictionary/Foo.dico", "# dico\n")
        self.write("docs/notes.md", "# notes\n")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "seed")

    # -- helpers ---------------------------------------------------
    def _git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def write(self, rel, content):
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\r\n")
        return target

    def stage(self, rel):
        self._git("add", "--", rel)

    def claim(self, name="c1.json", **fields):
        intent_dir = self.root / ".cade" / "intent"
        intent_dir.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 1, **fields}
        (intent_dir / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def merge_head(self):
        head = self._git("rev-parse", "HEAD").stdout.strip()
        (self.root / ".git" / "MERGE_HEAD").write_text(head + "\n", encoding="utf-8")

    def message_file(self, text):
        path = self.root / ".git" / "COMMIT_EDITMSG"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def cleanup(self):
        self._tmp.cleanup()


def main():
    print("=" * 70)
    print("  CADE Intent Gate Tests")
    print("=" * 70)

    # ── 1. Scope: non-controlled assets never gate ──────────────────
    print("\n[1] Scope — non-controlled staged files are out of scope")
    repo = TempRepo()
    try:
        repo.write("docs/notes.md", "# changed\n")
        repo.write("CAABar.edu/tool.py", "print('x')\n")
        repo.stage("docs/notes.md")
        repo.stage("CAABar.edu/tool.py")
        code, payload, _ = run_gate("--workspace", str(repo.root), expect=0)
        check("verdict PASS", payload and payload["gate"] == "PASS", str(payload))
        check("nothing classified as controlled", payload and payload["controlled"] == [])
    finally:
        repo.cleanup()

    # ── 2. Build output is not a controlled asset ──────────────────
    print("\n[2] Scope — build output and CADE metadata are excluded")
    repo = TempRepo()
    try:
        repo.write("win_b64/code/bin/Foo.dll", "binary\n")
        repo.write("CAAFoo.edu/CAAFoo.m/win_b64/Foo.obj", "obj\n")
        repo.write(".cade/intent/ignored.json", "{}\n")
        repo.stage("win_b64/code/bin/Foo.dll")
        repo.stage("CAAFoo.edu/CAAFoo.m/win_b64/Foo.obj")
        code, payload, _ = run_gate("--workspace", str(repo.root), expect=0)
        check("verdict PASS", payload and payload["gate"] == "PASS", str(payload))
    finally:
        repo.cleanup()

    # ── 3. Undeclared controlled asset BLOCKS ──────────────────────
    print("\n[3] Block — a controlled asset with no declaration")
    repo = TempRepo()
    try:
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() { int x = 1; }\n")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp")
        code, payload, _ = run_gate("--workspace", str(repo.root), expect=1)
        check("verdict BLOCK", payload and payload["gate"] == "BLOCK", str(payload))
        check(
            "the staged cpp is named",
            payload and payload["undeclared"] == ["CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp"],
            str(payload and payload["undeclared"]),
        )
        # The human-readable path must carry the remedy, not just the verdict.
        human = subprocess.run(
            [sys.executable, str(GATE), "--workspace", str(repo.root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        check("remedy is printed", "CADE-Intent" in human.stdout, human.stdout[-300:])
        check("escape hatch is documented in output", "--no-verify" in human.stdout)
    finally:
        repo.cleanup()

    # ── 4. The human affordance: one trailer line ──────────────────
    print("\n[4] Pass — a single commit-message trailer declares the change")
    repo = TempRepo()
    try:
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() { int x = 2; }\n")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp")
        msg = repo.message_file("Fix degenerate branch\n\nCADE-Intent: hand-tuned, no CADE capability\n")
        code, payload, _ = run_gate(
            "--workspace", str(repo.root), "--commit-msg-file", msg, expect=0
        )
        check("verdict PASS", payload and payload["gate"] == "PASS", str(payload))
        check("declaration source is the trailer", payload and payload["claims"][0]["source"] == "trailer")
        check("no undeclared files", payload and payload["undeclared"] == [])
    finally:
        repo.cleanup()

    # ── 5. Trailer that names other files does not cover this one ──
    print("\n[5] Block — a trailer scoped to other paths does not blanket-cover")
    repo = TempRepo()
    try:
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() { int x = 3; }\n")
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.h", "class FooCmd { int y; };\n")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.h")
        msg = repo.message_file(
            "Touch two files\n\n"
            "CADE-Intent: header only\n"
            "CADE-Intent-Files: CAAFoo.edu/CAAFoo.m/src/FooCmd.h\n"
        )
        code, payload, _ = run_gate(
            "--workspace", str(repo.root), "--commit-msg-file", msg, expect=1
        )
        check("verdict BLOCK", payload and payload["gate"] == "BLOCK", str(payload))
        check(
            "only the uncovered file blocks",
            payload and payload["undeclared"] == ["CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp"],
            str(payload and payload["undeclared"]),
        )
    finally:
        repo.cleanup()

    # ── 6. Structural claim file ───────────────────────────────────
    print("\n[6] Pass — a .cade/intent claim with an explicit file list")
    repo = TempRepo()
    try:
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() { int x = 4; }\n")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp")
        repo.claim(
            reason="algorithm rewrite CADE cannot generate",
            files=["CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp"],
        )
        code, payload, _ = run_gate("--workspace", str(repo.root), expect=0)
        check("verdict PASS", payload and payload["gate"] == "PASS", str(payload))
        check(
            "claim records kind=manual by default",
            payload and payload["claims"][0]["kind"] == "manual",
            str(payload and payload["claims"]),
        )
    finally:
        repo.cleanup()

    # ── 7. Unbounded claim is refused ──────────────────────────────
    print("\n[7] Block — a claim with neither files nor expiry is refused")
    repo = TempRepo()
    try:
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() { int x = 5; }\n")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp")
        repo.claim(reason="covers everything forever")
        code, payload, _ = run_gate("--workspace", str(repo.root), expect=1)
        check("verdict BLOCK", payload and payload["gate"] == "BLOCK", str(payload))
        check(
            "the refusal reason is reported",
            payload and payload["claim_problems"]
            and "forever" in " ".join(payload["claim_problems"][0]["problems"]),
            str(payload and payload["claim_problems"]),
        )
    finally:
        repo.cleanup()

    # ── 8. Expired claim is ignored ────────────────────────────────
    print("\n[8] Block — an expired claim no longer covers anything")
    repo = TempRepo()
    try:
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() { int x = 6; }\n")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp")
        repo.claim(
            reason="expired",
            files=["CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp"],
            expires_at="2020-01-01T00:00:00",
        )
        code, payload, _ = run_gate("--workspace", str(repo.root), expect=1)
        check("verdict BLOCK", payload and payload["gate"] == "BLOCK", str(payload))
        check(
            "expiry is reported",
            payload and payload["claim_problems"]
            and "expired" in " ".join(payload["claim_problems"][0]["problems"]),
            str(payload and payload["claim_problems"]),
        )
    finally:
        repo.cleanup()

    # ── 9. Future expiry + no file list is a valid time-boxed claim ─
    print("\n[9] Pass — a time-boxed unbounded claim is accepted")
    repo = TempRepo()
    try:
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() { int x = 7; }\n")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp")
        repo.claim(reason="migration window", expires_at="2999-01-01T00:00:00")
        code, payload, _ = run_gate("--workspace", str(repo.root), expect=0)
        check("verdict PASS", payload and payload["gate"] == "PASS", str(payload))
    finally:
        repo.cleanup()

    # ── 10. Wrong schema version is refused ────────────────────────
    print("\n[10] Block — a claim from an unknown schema is refused")
    repo = TempRepo()
    try:
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() { int x = 8; }\n")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp")
        repo.claim(
            schema_version=99,
            reason="from the future",
            files=["CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp"],
        )
        code, payload, _ = run_gate("--workspace", str(repo.root), expect=1)
        check("verdict BLOCK", payload and payload["gate"] == "BLOCK", str(payload))
    finally:
        repo.cleanup()

    # ── 11. --bless round-trip ─────────────────────────────────────
    print("\n[11] Pass — --bless writes a claim that then unblocks the commit")
    repo = TempRepo()
    try:
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() { int x = 9; }\n")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp")
        run_gate("--workspace", str(repo.root), expect=1)
        code, payload, _ = run_gate(
            "--workspace", str(repo.root), "--bless", "manual",
            "--reason", "hand edit, CADE has no capability", expect=0,
        )
        check("claim written", payload and payload["status"] == "written", str(payload))
        check("claim lists the staged asset", payload and payload["files"] == ["CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp"], str(payload))
        code, payload, _ = run_gate("--workspace", str(repo.root), expect=0)
        check("subsequent evaluation is PASS", payload and payload["gate"] == "PASS", str(payload))
    finally:
        repo.cleanup()

    # ── 12. --bless cade reads a rollback manifest ─────────────────
    print("\n[12] Pass — --bless cade derives the file list from a rollback manifest")
    repo = TempRepo()
    try:
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() { int x = 10; }\n")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp")
        backup = repo.root / ".caa_backups" / "20261021_120000_000000"
        backup.mkdir(parents=True)
        (backup / "manifest.json").write_text(
            json.dumps({
                "backup_id": "20261021_120000_000000",
                "action": "modify",
                "created": [],
                "modified": ["CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp"],
                "deleted": [],
            }),
            encoding="utf-8",
        )
        code, payload, _ = run_gate(
            "--workspace", str(repo.root), "--bless", "cade",
            "--reason", "generated by CADE", "--rollback-id", "20261021_120000_000000",
            expect=0,
        )
        check("claim written", payload and payload["status"] == "written", str(payload))
        check("claim carries the rollback id",
              payload and json.loads(Path(payload["claim_path"]).read_text(encoding="utf-8")).get("rollback_id") == "20261021_120000_000000",
              str(payload))
        code, payload, _ = run_gate("--workspace", str(repo.root), expect=0)
        check("evaluation is PASS", payload and payload["gate"] == "PASS", str(payload))
    finally:
        repo.cleanup()

    # ── 13. Merge resolutions are not blocked ──────────────────────
    print("\n[13] Pass (WARN) — a merge resolution is not gated")
    repo = TempRepo()
    try:
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() { int x = 11; }\n")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp")
        repo.merge_head()
        code, payload, _ = run_gate("--workspace", str(repo.root), expect=0)
        check("verdict WARN", payload and payload["gate"] == "WARN", str(payload))
    finally:
        repo.cleanup()

    # ── 14. Soft rollout --warn-only ───────────────────────────────
    print("\n[14] Pass (WARN) — --warn-only downgrades a would-be BLOCK")
    repo = TempRepo()
    try:
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() { int x = 12; }\n")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp")
        code, payload, _ = run_gate("--workspace", str(repo.root), "--warn-only", expect=0)
        check("verdict WARN", payload and payload["gate"] == "WARN", str(payload))
        check("undeclared files still reported", payload and len(payload["undeclared"]) == 1)
    finally:
        repo.cleanup()

    # ── 15. Fail-open on a non-git directory ───────────────────────
    print("\n[15] Pass (DEGRADED) — a non-git workspace cannot block a commit")
    tmp = tempfile.TemporaryDirectory(prefix="cade_nogit_")
    try:
        root = Path(tmp.name)
        (root / "a.cpp").write_text("void f(){}\n", encoding="utf-8")
        code, payload, _ = run_gate("--workspace", str(root), expect=0)
        check("verdict DEGRADED", payload and payload["gate"] == "DEGRADED", str(payload))
    finally:
        tmp.cleanup()

    # ── 16. Every controlled asset family is recognised ────────────
    print("\n[16] Recognise — all controlled asset families are gated")
    repo = TempRepo()
    try:
        families = [
            "CAAFoo.edu/CAAFoo.m/src/FooCmd.h",
            "CAAFoo.edu/CAAFoo.m/Imakefile.mk",
            "CAAFoo.edu/CAAFoo.m/IdentityCard.xml",
            "CAAFoo.edu/CAAFoo.m/CNext/resources/msgcatalog/Foo.CATNls",
            "CAAFoo.edu/CAAFoo.m/CNext/resources/dictionary/Foo.dico",
        ]
        for rel in families:
            repo.write(rel, "changed\n")
            repo.stage(rel)
        code, payload, _ = run_gate("--workspace", str(repo.root), expect=1)
        check(
            "all five families classified as controlled",
            payload and sorted(payload["controlled"]) == sorted(families),
            str(payload and payload["controlled"]),
        )
    finally:
        repo.cleanup()

    # ── 17. Classifier parity with the Provenance Guard ────────────
    print("\n[17] Parity — the gate uses the Provenance Guard's own rules")
    try:
        import provenance_guard as pg
        from check_intent import _provenance

        classifier, config = _provenance()
        probes = [
            ".cpp", ".cxx", ".c", ".cc", ".h", ".hpp", ".hxx", ".dico",
            ".catnls", ".catrsc", ".md", ".py", ".obj", ".dll", ".txt",
        ]
        mismatches = []
        for ext in probes:
            for rel in (f"m/src/x{ext}", f"win_b64/m/x{ext}", f".cade/x{ext}"):
                expected = pg.is_controlled_source_asset(
                    Path(rel), Path.cwd(), pg.DEFAULT_ASSET_CONFIG
                )
                actual = classifier(Path(rel), Path.cwd(), config)
                if expected != actual:
                    mismatches.append((rel, expected, actual))
        check("no classification drift vs provenance_guard", not mismatches, str(mismatches))
        check("config is the same object family", config is pg.DEFAULT_ASSET_CONFIG)
    except Exception as exc:  # pragma: no cover
        check("classifier parity harness runs", False, repr(exc))

    # ── 18. Deletion of a controlled asset is also a change ────────
    print("\n[18] Block — deleting a controlled asset counts as a change")
    repo = TempRepo()
    try:
        (repo.root / "CAAFoo.edu/CAAFoo.m/src/FooCmd.h").unlink()
        repo._git("add", "-A")
        code, payload, _ = run_gate("--workspace", str(repo.root), expect=1)
        check("verdict BLOCK", payload and payload["gate"] == "BLOCK", str(payload))
        check(
            "the deleted header is named",
            payload and payload["undeclared"] == ["CAAFoo.edu/CAAFoo.m/src/FooCmd.h"],
            str(payload and payload["undeclared"]),
        )
    finally:
        repo.cleanup()

    # ── 19. Rename is two paths, neither hidden ────────────────────
    print("\n[19] Block — a rename exposes both sides, hiding nothing")
    repo = TempRepo()
    try:
        repo._git("mv", "CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "CAAFoo.edu/CAAFoo.m/src/BarCmd.cpp")
        code, payload, _ = run_gate("--workspace", str(repo.root), expect=1)
        check(
            "new path is gated",
            payload and "CAAFoo.edu/CAAFoo.m/src/BarCmd.cpp" in payload["undeclared"],
            str(payload and payload["undeclared"]),
        )
    finally:
        repo.cleanup()

    # ── 20. Documented escape hatch still works at the git level ───
    print("\n[20] Escape — git commit --no-verify bypasses the hook entirely")
    repo = TempRepo()
    try:
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() { int x = 13; }\n")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp")
        proc = subprocess.run(
            ["git", "-C", str(repo.root), "commit", "-q", "--no-verify",
             "-m", "emergency fix"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        check("commit succeeds with --no-verify", proc.returncode == 0, proc.stderr[:200])
        head = repo._git("log", "-1", "--pretty=%s").stdout.strip()
        check("commit landed", head == "emergency fix", head)
    finally:
        repo.cleanup()

    # ── 21. Real hook installation, end to end ─────────────────────
    print("\n[21] Hook — a real 'git commit' is gated on a real repository")
    repo = TempRepo()
    try:
        proc = subprocess.run(
            [sys.executable, str(GATE), "--workspace", str(repo.root),
             "--install-hooks", "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        install = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {}
        check("installer succeeds", install.get("status") == "installed", proc.stdout + proc.stderr)
        hooks_dir = Path(install.get("hooks_dir", repo.root / ".git" / "hooks"))
        check("pre-commit hook exists", (hooks_dir / "pre-commit").exists())
        check("commit-msg hook exists", (hooks_dir / "commit-msg").exists())
        check(
            "hooks are LF-only (a CRLF shebang breaks sh)",
            b"\r\n" not in (hooks_dir / "commit-msg").read_bytes(),
        )

        # Undeclared controlled asset must be rejected by real git.
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() { int x = 20; }\n")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp")
        blocked = subprocess.run(
            ["git", "-C", str(repo.root), "commit", "-m", "undeclared edit"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        check("undeclared commit is rejected", blocked.returncode != 0, blocked.stdout[:300])
        head = repo._git("log", "-1", "--pretty=%s").stdout.strip()
        check("no commit was created", head == "seed", head)

        # Same change, now declared by trailer: must commit.
        declared = subprocess.run(
            ["git", "-C", str(repo.root), "commit", "-m", "declared edit",
             "-m", "CADE-Intent: hand-tuned branch, CADE has no capability"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        check("declared commit succeeds", declared.returncode == 0, declared.stdout + declared.stderr)
        head = repo._git("log", "-1", "--pretty=%s").stdout.strip()
        check("commit landed", head == "declared edit", head)

        # A human editing a non-controlled file is untouched by the gate.
        repo.write("docs/notes.md", "# human edit\n")
        repo.stage("docs/notes.md")
        docs = subprocess.run(
            ["git", "-C", str(repo.root), "commit", "-m", "update notes"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        check("non-controlled commit succeeds untouched", docs.returncode == 0, docs.stdout + docs.stderr)

        # Uninstall removes only what it created.
        un = subprocess.run(
            [sys.executable, str(GATE), "--workspace", str(repo.root),
             "--install-hooks", "--uninstall", "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        outcome = json.loads(un.stdout) if un.stdout.strip().startswith("{") else {}
        check("uninstall succeeds", outcome.get("status") == "uninstalled", un.stdout + un.stderr)
        check("hooks removed", not (hooks_dir / "commit-msg").exists())
    finally:
        repo.cleanup()

    # ── 22. Installer refuses to clobber a foreign hook ────────────
    print("\n[22] Hook — a pre-existing foreign hook is never overwritten")
    repo = TempRepo()
    try:
        hooks_dir = repo.root / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        foreign = hooks_dir / "commit-msg"
        foreign.write_text("#!/bin/sh\necho someone-elses-hook\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(GATE), "--workspace", str(repo.root),
             "--install-hooks", "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        outcome = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {}
        check("installer reports a conflict", outcome.get("status") == "conflict", proc.stdout + proc.stderr)
        check(
            "the foreign hook is intact",
            "someone-elses-hook" in foreign.read_text(encoding="utf-8"),
        )
    finally:
        repo.cleanup()

    # ── 23. Unreadable commit message must not accuse the author ───
    print("\n[23] Degraded — an unreadable commit message is missing evidence, not absent")
    repo = TempRepo()
    try:
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() { int x = 30; }\n")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp")
        code, payload, _ = run_gate(
            "--workspace", str(repo.root),
            "--commit-msg-file", str(repo.root / "no" / "such" / "msg"),
            expect=0,
        )
        check("verdict DEGRADED", payload and payload["gate"] == "DEGRADED", str(payload))
        check("reason names the message file",
              payload and "message" in payload["reason"],
              str(payload and payload["reason"]))
    finally:
        repo.cleanup()

    # ── 24. A stale hook must not lock the repository ──────────────
    print("\n[24] Hook — a missing gate makes the hook fail open, not closed")
    repo = TempRepo()
    try:
        hooks_dir = repo.root / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        # Mimic a clone whose CADE checkout has moved away.
        missing = repo.root / "gone" / "check_intent.py"
        body = (
            "#!/bin/sh\n# CADE-INTENT-GATE\n"
            f'if [ ! -f "{missing.as_posix()}" ]; then exit 0; fi\n'
            f'exec "{sys.executable}" "{missing.as_posix()}" --workspace "{repo.root.as_posix()}"\n'
        )
        (hooks_dir / "commit-msg").write_bytes(body.encode("utf-8"))
        repo.write("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp", "void Run() { int x = 31; }\n")
        repo.stage("CAAFoo.edu/CAAFoo.m/src/FooCmd.cpp")
        c = subprocess.run(
            ["git", "-C", str(repo.root), "commit", "-m", "stale hook"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        check("commit allowed when the gate is missing", c.returncode == 0, c.stdout + c.stderr)
    finally:
        repo.cleanup()

    # ── Summary ────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    total = PASSED + FAILED
    if FAILED:
        print(f"RESULT: {FAILED} of {total} checks FAILED")
        return 1
    print(f"RESULT: INTENT GATE OK — {PASSED}/{total} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
