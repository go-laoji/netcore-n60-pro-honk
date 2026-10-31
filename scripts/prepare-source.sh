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
git check-ref-format "refs/heads/$FIRMWARE_BRANCH"

git init "$OPENWRT_DIR"
git -C "$OPENWRT_DIR" remote add origin "$FIRMWARE_REPOSITORY"
git -C "$OPENWRT_DIR" fetch --depth=1 --no-tags origin "refs/heads/$FIRMWARE_BRANCH"
git -C "$OPENWRT_DIR" checkout --detach FETCH_HEAD
FIRMWARE_RESOLVED_COMMIT=$(git -C "$OPENWRT_DIR" rev-parse HEAD)

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
test -f feeds/luci/themes/luci-theme-argon/Makefile
test -f feeds/luci/applications/luci-app-argon-config/Makefile
test -f feeds/luci/applications/luci-app-openclash/Makefile
test -f feeds/nas/network/services/quickstart/Makefile
test -f feeds/nas_luci/luci/luci-app-quickstart/Makefile
test -f feeds/istore/luci/luci-app-store/Makefile
test -f feeds/istore/luci/luci-lib-taskd/Makefile
test -f feeds/istore/luci/luci-lib-xterm/Makefile
test -f feeds/istore/luci/taskd/Makefile
./scripts/feeds install -a
# The fixed feed's optional WeeChat UI triggers a Kconfig self-dependency.
# Unregister it before defconfig; this firmware does not use WeeChat.
./scripts/feeds uninstall luci-app-weechat
./scripts/feeds install -f -p honk honk luci-app-honk
./scripts/feeds install -f -p luci luci-theme-argon luci-app-argon-config luci-compat luci-app-openclash
./scripts/feeds install -f -p nas quickstart
./scripts/feeds install -f -p nas_luci luci-app-quickstart
./scripts/feeds install -f -p istore luci-app-store luci-lib-taskd luci-lib-xterm taskd
test ! -e package/feeds/luci/luci-app-weechat

cp "$PROJECT_DIR/$CONFIG_FILE" .config
python3 "$PROJECT_DIR/scripts/stamp-version.py" .
mkdir -p files
cp -a "$PROJECT_DIR/files/." files/
chmod +x files/etc/uci-defaults/99-honk-routing files/etc/uci-defaults/zz-honk-ui \
    files/etc/uci-defaults/zz-openclash-backup

{
    printf 'Firmware repository: %s\nFirmware branch: %s\nFirmware commit: %s\n' \
        "$FIRMWARE_REPOSITORY" "$FIRMWARE_BRANCH" "$FIRMWARE_RESOLVED_COMMIT"
    printf 'Configuration repository commit: %s\n' "$(git -C "$PROJECT_DIR" rev-parse HEAD)"
    printf '\nPinned feeds:\n'
    cat feeds.conf.default
    printf '\nFirmware version:\n'
    cat firmware-version.json
} > build-inputs.txt
