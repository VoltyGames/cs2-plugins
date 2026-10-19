#!/usr/bin/env bash
# Runs inside the build container: FRAMEWORK=checkout|locked, RUN_TESTS=0|1.
set -euo pipefail

preset=linux-steamrt-release
cd /work

# The bind-mounted repositories belong to the Windows user.
git config --global --add safe.directory '*'

# The checkout's own CLI, so it matches the framework it builds.
uv venv --quiet --allow-existing --python 3.15 /cache/venv
uv pip install --quiet --python /cache/venv/bin/python --reinstall-package voltmod /work/voltmod
export PATH="/cache/venv/bin:$PATH"

conan profile detect --exist-ok >/dev/null 2>&1 || true
conan config install /work/voltmod -sf conan >/dev/null

# Locked revisions that exist only in the Windows Conan cache, saved by linux_build.py.
for seed in /work/build/linux-seed/*.tgz; do
    [ -e "$seed" ] && conan cache restore "$seed" >/dev/null
done

conan editable remove --refs='voltmod/*' >/dev/null 2>&1 || true
if [ "$FRAMEWORK" = checkout ]; then
    conan editable add /work/voltmod
fi

voltmod build -p "$preset"
if [ "$RUN_TESTS" = 1 ]; then
    voltmod test -p "$preset"
fi

uv run --quiet --locked --only-group deploy python -m deploy.cli package
# An editable framework keeps the host in its own build tree, which the packager does not read.
if [ "$FRAMEWORK" = checkout ]; then
    cmake --install "/work/voltmod/build/$preset" --component host --prefix /work/build/package/host
fi
