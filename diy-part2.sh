#!/usr/bin/env bash
set -euo pipefail

# Runs in the OpenWrt source root, AFTER feeds are installed and files/.config copied.
# Use custom.config for plugin selections; it is merged AFTER this script.
# When a custom feed intentionally replaces a package from another feed:
# ./scripts/feeds install -f -p myplugins luci-app-example
# You may also patch package sources or add defaults under files/ here.
