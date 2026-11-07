#!/usr/bin/env bash
set -euo pipefail

# Local/CI input checks only: no source preparation, downloads or OpenWrt make.
PROJECT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$PROJECT_DIR"
validation_dir=$(mktemp -d)
trap 'rm -rf -- "$validation_dir"' EXIT

for script in scripts/check-config.sh scripts/prepare-source.sh diy-part1.sh diy-part2.sh; do
    bash -n "$script"
done
for script in files/etc/uci-defaults/*; do
    sh -n "$script"
done
python3 -B scripts/customize.py config immortalwrt-netcore-n60-pro-honk.config custom.config \
    "$validation_dir/merged.config"
python3 -B scripts/validate.py config "$validation_dir/merged.config"
python3 -B scripts/customize.py feeds feeds.conf.default feeds.conf.custom "$validation_dir/feeds.conf"
python3 -B -m unittest discover -s scripts -p 'test_*.py'
