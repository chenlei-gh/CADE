#!/usr/bin/env python3
"""stdio encoding contract for the MCP server.

Regression guard for a real failure: under a GBK console (cp936, the Windows
default) the server read the JSON-RPC line with the wrong codec. A CJK request
was either rejected outright (``'gbk' codec can't decode byte ...``) or, worse,
silently decoded as mojibake — ``分析当前工作区`` became ``鍒嗘瀽褰撳墠宸ヤ綔鍖``
plus a lone surrogate — while ``json.loads`` still succeeded, so the Kernel ran
on a corrupted request. Responses were affected too: the ``ensure_ascii=False``
write raised ``'gbk' codec can't encode character`` for anything outside cp936
(an emoji in a diagnostic), killing the reply.

Existing tests call ``handle_tool()`` in-process and never exercise stdio, which
is exactly why this survived. These tests spawn the real server as a child on a
GBK code page and drive it over pipes.

The child gets no PYTHONIOENCODING, matching how an MCP host launches the
process (``setup_mcp.py`` emits ``{"command": "python", "args": [...]}`` with no
env block), so the fix must work on its own rather than relying on ambient env.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
SERVER = SKILL / "skills" / "mcp_server.py"

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))


def _child_env():
    """Environment as an MCP host would provide it: no encoding overrides."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    return env


def _spawn(requests, env):
    """Run the server over pipes, return (stdout, stderr) as decoded text."""
    payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in requests)
    proc = subprocess.run(
        [sys.executable, str(SERVER)],
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(SKILL),
        env=env,
        timeout=300,
    )
    return proc.stdout.decode("utf-8", errors="replace"), proc.stderr.decode("utf-8", errors="replace")


def _responses(stdout):
    out = []
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def main():
    ws = tempfile.mkdtemp(prefix="cade_stdio_enc_")
    try:
        req = {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "analyze",
                       "arguments": {"request": "分析当前工作区 CAAPartToAsm 模块", "workspace": ws}},
        }

        # ── 1: the reproduction that used to fail on a GBK console ───────
        stdout, stderr = _spawn([req], _child_env())
        res = _responses(stdout)

        check("server replies over stdio with CJK input", len(res) == 1,
              f"responses={len(res)} stderr={stderr.strip()[:200]}")
        if res:
            check("reply is not a JSON-RPC error", "error" not in res[0],
                  str(res[0].get("error"))[:200])
            check("reply carries tool content", "result" in res[0])

        check("no codec error leaked to stderr",
              "codec can't" not in stderr, stderr.strip()[:200])

        # ── 2: the request content must survive, not silently mojibake ───
        # A corrupted round trip still returns status ok, so asserting on the
        # response alone would miss it. Capture what the Kernel is handed.
        probe = tempfile.mkdtemp(prefix="cade_stdio_probe_")
        try:
            probe_script = Path(probe) / "probe.py"
            probe_script.write_text(
                "import json, sys\n"
                "sys.path.insert(0, r'%s')\n"
                "import mcp_server\n"
                "if hasattr(mcp_server, '_force_utf8_stdio'):\n"
                "    mcp_server._force_utf8_stdio()\n"
                "msg = json.loads(sys.stdin.readline())\n"
                "got = msg['params']['arguments']['request']\n"
                "sys.stderr.write(json.dumps({'stdin_encoding': sys.stdin.encoding, "
                "'got': got}, ensure_ascii=False))\n"
                % (SKILL / "skills")
            , encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(probe_script)],
                input=(json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8"),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=str(SKILL), env=_child_env(), timeout=120,
            )
            raw_err = proc.stderr.decode("utf-8", errors="replace").strip()
            try:
                seen = json.loads(raw_err)
                got = seen.get("got")
                enc = seen.get("stdin_encoding")
            except json.JSONDecodeError:
                # Pre-fix the child dies reading stdin, so nothing arrives.
                got, enc = None, f"crashed: {raw_err[:160]}"
            check("stdin is pinned to UTF-8",
                  enc == "utf-8", f"stdin encoding was {enc}")
            check("Kernel receives intact CJK, not mojibake",
                  got == req["params"]["arguments"]["request"],
                  repr(got)[:160])
        finally:
            shutil.rmtree(probe, ignore_errors=True)

        # ── 3: responses that cp936 cannot encode (emoji / arrows) ───────
        emoji_req = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "analyze",
                       "arguments": {"request": "分析 🎨 图标 → 完成", "workspace": ws}},
        }
        stdout, stderr = _spawn([emoji_req], _child_env())
        res = _responses(stdout)
        check("emoji-bearing request still answered", len(res) == 1,
              f"responses={len(res)} stderr={stderr.strip()[:200]}")
        check("emoji response not beaten by codec", "codec can't" not in stderr,
              stderr.strip()[:200])

        # ── 4: explicit cp936 pins must not break it either ──────────────
        # The failure was originally hit with PYTHONIOENCODING set to the
        # console page; the fix must override it rather than defer to it.
        cp936_env = dict(_child_env())
        cp936_env["PYTHONIOENCODING"] = "cp936"
        stdout, stderr = _spawn([req], cp936_env)
        res = _responses(stdout)
        check("survives an inherited cp936 PYTHONIOENCODING",
              len(res) == 1 and "error" not in res[0],
              f"responses={len(res)} err={str(res[0].get('error') if res else None)[:160]}")

        # ── 5: malformed bytes fail loudly, never as silent garbage ─────
        proc = subprocess.run(
            [sys.executable, str(SERVER)],
            input=b'{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"analyze","arguments":{"request":"\xff\xfe bad"}}}\n',
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(SKILL), env=_child_env(), timeout=300,
        )
        out = proc.stdout.decode("utf-8", errors="replace")
        check("invalid UTF-8 is reported, not silently decoded",
              "not valid UTF-8" in out, out.strip()[:200])

        # ── 6: stdio framing stays pure JSON-RPC ────────────────────────
        init = {"jsonrpc": "2.0", "id": 4, "method": "initialize"}
        stdout, _ = _spawn([init, {"jsonrpc": "2.0", "id": 5, "method": "tools/list"}], _child_env())
        lines = [ln for ln in stdout.splitlines() if ln.strip()]
        check("every stdout line is a JSON object",
              all(ln.lstrip().startswith("{") for ln in lines),
              f"lines={len(lines)}")
        res = _responses(stdout)
        check("initialize + tools/list both answered", len(res) == 2, f"responses={len(res)}")
    finally:
        shutil.rmtree(ws, ignore_errors=True)

    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
