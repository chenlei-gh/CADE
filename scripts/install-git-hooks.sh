#!/bin/sh
# Install the versioned pre-push hook into this clone's .git/hooks.
# .git/hooks is not part of the repository, so each clone must run this once.
set -eu

root=$(git rev-parse --show-toplevel)
src="$root/scripts/git-hooks/pre-push"
dst="$root/.git/hooks/pre-push"

if [ ! -f "$src" ]; then
    echo "install-git-hooks: missing $src" >&2
    exit 1
fi

cp "$src" "$dst"
chmod +x "$dst"
echo "installed $dst"
echo "it runs: python scripts/static_audit.py"
echo "bypass once: git push --no-verify"
