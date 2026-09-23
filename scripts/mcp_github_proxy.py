#!/usr/bin/env python3
"""
MCP Proxy for github-mcp-server.

Fixes ZED's "tool parameter root must be an object type
(root schema is an anyOf/one union branch)" error by stripping
root-level anyOf/oneOf from tool inputSchemas in tools/list responses.

The constraint info is appended to the tool description so the AI
still knows the mutual-exclusion rules. Real validation still
happens server-side in the Go binary.

Usage in Zed settings.json:
  "context_servers": {
    "mcp-server-github": { "enabled": false, ... },
    "github-mcp": {
      "command": "python",
      "args": ["<this-file-path>"],
      "env": {}
    }
  }

The PAT is read from settings.json (mcp-server-github.settings) so it
is never duplicated or hardcoded.
"""
import subprocess
import json
import os
import re
import sys
import threading

# --- Config ---
SETTINGS_PATH = os.path.join(
    os.environ.get("APPDATA", ""),
    "Zed", "settings.json",
)
# The Go binary is managed by the Zed extension; locate the latest version dir.
BINARY_DIR_TEMPLATE = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "Zed", "extensions", "work", "mcp-server-github",
)
BINARY_NAME = "github-mcp-server.exe"


def find_binary():
    """Find the latest github-mcp-server.exe under the extension work dir."""
    if not os.path.isdir(BINARY_DIR_TEMPLATE):
        return None
    versions = []
    for entry in os.scandir(BINARY_DIR_TEMPLATE):
        if entry.is_dir() and entry.name.startswith("github-mcp-server-v"):
            exe = os.path.join(entry.path, BINARY_NAME)
            if os.path.isfile(exe):
                versions.append((entry.name, exe))
    if not versions:
        return None
    # pick the highest version
    versions.sort(key=lambda v: v[0], reverse=True)
    return versions[0][1]


def load_pat():
    """Read PAT from Zed settings.json (JSONC). Never printed to stdout."""
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception as e:
        sys.stderr.write(f"[proxy] cannot read settings.json: {e}\n")
        return ""
    # strip JSONC line comments
    raw = re.sub(r"^\s*//.*$", "", raw, flags=re.M)
    raw = re.sub(r"^\s*/\*.*?\*/", "", raw, flags=re.M | re.S)
    try:
        s = json.loads(raw)
    except Exception as e:
        sys.stderr.write(f"[proxy] settings.json parse error: {e}\n")
        return ""
    pat = (
        s.get("context_servers", {})
        .get("mcp-server-github", {})
        .get("settings", {})
        .get("github_personal_access_token", "")
    )
    return pat


def clean_schema(schema):
    """Strip root-level anyOf/oneOf/dependentSchemas from an inputSchema.
    Appends the constraint info to the tool description so the AI still
    knows the rules. Returns True if the schema was modified."""
    if not isinstance(schema, dict):
        return False

    any_of = schema.pop("anyOf", None)
    one_of = schema.pop("oneOf", None)
    dep = schema.pop("dependentSchemas", None)

    if any_of is None and one_of is None and dep is None:
        return False

    # Build a human-readable constraint hint
    constraints = []
    if any_of is not None:
        constraints.append("anyOf: " + json.dumps(any_of, ensure_ascii=False))
    if one_of is not None:
        constraints.append("oneOf: " + json.dumps(one_of, ensure_ascii=False))
    if dep is not None:
        constraints.append("dependentSchemas: " + json.dumps(dep, ensure_ascii=False))
    hint = "\n\n[Schema constraint (stripped for client compatibility): " + "; ".join(constraints) + "]"
    return hint


def process_tools_list(result):
    """Process a tools/list result, cleaning all tool schemas in-place.
    Returns True if any tool schema was modified."""
    if not isinstance(result, dict):
        return False
    tools = result.get("tools", [])
    if not isinstance(tools, list):
        return False
    modified = False
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        schema = tool.get("inputSchema")
        if not isinstance(schema, dict):
            continue
        hint = clean_schema(schema)
        if hint:
            desc = tool.get("description", "") or ""
            tool["description"] = desc + hint
            modified = True
    return modified


def process_message(line):
    """Parse a JSON-RPC message line. If it's a tools/list response,
    clean the schemas. Returns the (possibly modified) JSON line, or None
    if the line should be passed through unchanged."""
    line = line.strip()
    if not line:
        return None
    try:
        msg = json.loads(line)
    except Exception:
        return None  # not JSON, pass through as-is

    if isinstance(msg, dict) and msg.get("id") is not None and "result" in msg:
        result = msg.get("result")
        if isinstance(result, dict) and isinstance(result.get("tools"), list):
            if process_tools_list(result):
                return json.dumps(msg, ensure_ascii=False) + "\n"

    return None


def main():
    binary = find_binary()
    if not binary:
        sys.stderr.write("[proxy] github-mcp-server.exe not found under " + BINARY_DIR_TEMPLATE + "\n")
        sys.exit(1)

    pat = load_pat()
    if not pat:
        sys.stderr.write("[proxy] PAT not found in settings.json\n")
        sys.exit(1)

    env = os.environ.copy()
    env["GITHUB_PERSONAL_ACCESS_TOKEN"] = pat

    sys.stderr.write(f"[proxy] starting {binary}\n")
    proc = subprocess.Popen(
        [binary, "stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,  # pass through server stderr directly
        env=env,
        bufsize=0,
    )

    # Thread: forward ZED stdin → server stdin (raw bytes)
    def forward_stdin():
        try:
            while True:
                data = sys.stdin.buffer.readline()
                if not data:
                    break
                proc.stdin.write(data)
                proc.stdin.flush()
        except Exception:
            pass
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass

    # Thread: read server stdout line by line, clean tools/list, forward to ZED
    def forward_stdout():
        try:
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace")
                replacement = process_message(decoded)
                if replacement:
                    sys.stdout.write(replacement)
                else:
                    sys.stdout.write(decoded)
                sys.stdout.flush()
        except Exception:
            pass

    t_in = threading.Thread(target=forward_stdin, daemon=True)
    t_out = threading.Thread(target=forward_stdout, daemon=True)
    t_in.start()
    t_out.start()

    # Wait for server to exit
    proc.wait()
    sys.stderr.write(f"[proxy] server exited with code {proc.returncode}\n")


if __name__ == "__main__":
    main()
