#!/usr/bin/env bash
# Builds the viewer and runs the real-window Hyprland E2E (scripts/e2e_hyprland.py).
#   scripts/e2e.sh test-server            # against the isolated test server (started and stopped here)
#   scripts/e2e.sh runtime cuda [--exercise]   # against the running Render Bridge
set -euo pipefail
cd "$(dirname "$0")/.."
mode="${1:?usage: e2e.sh test-server | runtime BACKEND [--exercise]}"
cargo build --offline --release -p blobin-showcase -p blob-frame-testserver
target="$(cargo metadata --offline --format-version 1 --no-deps | python3 -c 'import json,sys; print(json.load(sys.stdin)["target_directory"])')"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
case "$mode" in
  test-server)
    "$target/release/blob-frame-testserver" --delay-ms 40 >"evidence/logs/testserver-$stamp.log" 2>&1 &
    server=$!
    trap 'kill "$server" 2>/dev/null || true' EXIT
    sleep 0.5
    python3 -I scripts/e2e_hyprland.py --viewer "$target/release/blobin-showcase" --test-server \
      --backend cpu --out "evidence/runs/e2e-test-server-$stamp" "${@:2}"
    ;;
  runtime)
    backend="${2:?backend: cpu | cuda | vulkan}"
    python3 -I scripts/e2e_hyprland.py --viewer "$target/release/blobin-showcase" \
      --socket "$XDG_RUNTIME_DIR/blobin-showcase/render.sock" --backend "$backend" \
      --out "evidence/runs/e2e-runtime-$backend-$stamp" "${@:3}"
    ;;
  *) echo "unknown mode $mode" >&2; exit 2 ;;
esac
