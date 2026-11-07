#!/usr/bin/env bash
set -euo pipefail

# Runs in the OpenWrt source root, BEFORE ./scripts/feeds update -a.
# Prefer feeds.conf.custom for extra feeds. PROJECT_DIR is the config repository.
# For a standalone package repository, you can add a clone here, for example:
# git clone --depth=1 --branch main https://github.com/your-name/luci-app-example.git \
#     package/custom/luci-app-example
