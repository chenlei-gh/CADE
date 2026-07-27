#!/usr/bin/env sh
# sync_agents.sh — mirror .agents to the FSWorkspaces shadow copy.
#
# WHY THIS SCRIPT EXISTS (do not inline the robocopy command by hand):
#   This is a Windows native command run from an MSYS / Git-Bash style sh.
#   MSYS path conversion rewrites robocopy's `/E` switch into the path `E:/`,
#   so the command fails with:  无效参数 #3: "E:/".
#   Setting MSYS2_ARG_CONV_EXCL="*" disables that conversion for robocopy.
#   Any agent (Zed / Claude / CI) that syncs must use this script rather than
#   remembering the incantation — that knowledge should not live only in
#   someone's head.
#
# robocopy exit codes: 0 = nothing to do, 1 = files copied OK. Both are success.
# (>=8 is a real failure.)

set -u

SRC="D:\Vault\DevTools\CADE\.agents"
DST="D:\Vault\FSWorkspaces\.agents"

MSYS2_ARG_CONV_EXCL="*" robocopy "$SRC" "$DST" /E /XD .git /R:2 /W:2 /NP
code=$?

if [ "$code" -ge 8 ]; then
    echo "sync_agents: robocopy FAILED (exit $code)" >&2
    exit "$code"
fi

echo "sync_agents: OK (robocopy exit $code; 0=no change, 1=copied)"
exit 0
