#!/usr/bin/env bash
set -euo pipefail

# This script prepares the build tree only on the GitHub Actions Linux runner.
[[ ${GITHUB_ACTIONS:-} == true && $(uname -s) == Linux ]] || {
    echo 'Run source preparation in GitHub Actions on Linux.' >&2
    exit 1
}

PROJECT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=../build.env
source "$PROJECT_DIR/build.env"
OPENWRT_DIR=${1:?Usage: prepare-source.sh /absolute/path/to/openwrt}
[[ $OPENWRT_DIR == /* && ! -e $OPENWRT_DIR ]] || {
    echo 'The source destination must be a new absolute path.' >&2
    exit 1
}
[[ $FIRMWARE_COMMIT =~ ^[0-9a-f]{40}$ ]] || exit 1

git init "$OPENWRT_DIR"
git -C "$OPENWRT_DIR" remote add origin "$FIRMWARE_REPOSITORY"
git -C "$OPENWRT_DIR" fetch --depth=1 origin "$FIRMWARE_COMMIT"
git -C "$OPENWRT_DIR" checkout --detach FETCH_HEAD
[[ $(git -C "$OPENWRT_DIR" rev-parse HEAD) == "$FIRMWARE_COMMIT" ]]

cd "$OPENWRT_DIR"
python3 "$PROJECT_DIR/scripts/validate.py" source .
cp "$PROJECT_DIR/feeds.conf.default" feeds.conf.default
./scripts/feeds update -a

# Verify that feeds honored every immutable revision in feeds.conf.default.
while read -r feed_type feed_name feed_url; do
    [[ $feed_type == src-git ]] || continue
    expected_commit=${feed_url##*^}
    [[ $expected_commit =~ ^[0-9a-f]{40}$ ]]
    [[ $(git -C "feeds/$feed_name" rev-parse HEAD) == "$expected_commit" ]] || {
        echo "Feed revision mismatch: $feed_name" >&2
        exit 1
    }
done < feeds.conf.default

test -f feeds/honk/honk/Makefile
test -f feeds/honk/luci-app-honk/Makefile
./scripts/feeds install -a
./scripts/feeds install -f -p honk honk luci-app-honk

cp "$PROJECT_DIR/$CONFIG_FILE" .config
mkdir -p files
cp -a "$PROJECT_DIR/files/." files/
chmod +x files/etc/uci-defaults/99-honk-routing

{
    printf 'Firmware repository: %s\nFirmware branch: %s\nFirmware commit: %s\n' \
        "$FIRMWARE_REPOSITORY" "$FIRMWARE_BRANCH" "$FIRMWARE_COMMIT"
    printf 'Configuration repository commit: %s\n' "$(git -C "$PROJECT_DIR" rev-parse HEAD)"
    printf '\nPinned feeds:\n'
    cat feeds.conf.default
} > build-inputs.txt
