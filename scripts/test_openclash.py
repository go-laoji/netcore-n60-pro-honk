#!/usr/bin/env python3
"""Backup-only OpenClash checks: runtime core download and exact package allowance."""

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

import validate


PROJECT = Path(__file__).resolve().parent.parent
DEFAULTS = PROJECT / "files/etc/uci-defaults/zz-openclash-backup"


class OpenClashBackupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.rootfs = self.root / "rootfs"
        for name in ("usr/lib/lua/luci/controller/openclash.lua",
                     "usr/lib/lua/luci/model/cbi/openclash/settings.lua",
                     "etc/init.d/openclash", "usr/share/openclash/openclash_core.sh"):
            path = self.rootfs / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("#!/bin/sh\n")
            path.chmod(0o755)
        defaults = self.rootfs / "etc/uci-defaults/zz-openclash-backup"
        defaults.parent.mkdir(parents=True)
        shutil.copyfile(DEFAULTS, defaults)
        defaults.chmod(0o755)
        self.config = self.rootfs / "etc/config/openclash"
        self.config.parent.mkdir(parents=True)
        self.config.write_text(
            "config openclash 'config'\n"
            "\toption enable '0'\n\toption small_flash_memory '0'\n"
            "\nconfig config_overwrite\n\toption enable '1'\n"
        )
        self.manifest = self.root / "firmware.manifest"

    def write_manifest(self, added=(), removed=()):
        packages = (set(validate.REQUIRED_PACKAGES) | set(added)) - set(removed)
        self.manifest.write_text("kernel - 6.12.1\n" + "".join(
            f"{name} - 1\n" for name in sorted(packages)
        ))

    def test_only_requested_backup_ui_is_allowed(self):
        validate.check_proxy_packages({"CONFIG_PACKAGE_luci-app-openclash": "y"})
        for name in ("mihomo", "clash", "clash-meta", "luci-app-openclash-extra",
                     "luci-app-nikki", "luci-app-passwall", "sing-box"):
            for value in ("y", "m"):
                with self.subTest(name=name, value=value), self.assertRaisesRegex(
                    ValueError, "Unexpected proxy package"
                ):
                    validate.check_proxy_packages({f"CONFIG_PACKAGE_{name}": value}, {name})

    def test_manifest_requires_backup_ui_and_rejects_bundled_cores(self):
        self.write_manifest()
        validate.check_manifest(self.manifest)
        self.write_manifest(removed={"luci-app-openclash"})
        with self.assertRaisesRegex(ValueError, "missing package: luci-app-openclash"):
            validate.check_manifest(self.manifest)
        self.write_manifest(added={"mihomo"})
        with self.assertRaisesRegex(ValueError, "contains another proxy: mihomo"):
            validate.check_manifest(self.manifest)

    def test_dnsmasq_full_nftset_is_required_and_plain_dnsmasq_is_excluded(self):
        seed = (PROJECT / "immortalwrt-netcore-n60-pro-honk.config").read_text()
        config = self.root / "firmware.config"
        for before, after, error in (
            ("CONFIG_PACKAGE_dnsmasq_full_nftset=y", "# CONFIG_PACKAGE_dnsmasq_full_nftset is not set",
             "Expected CONFIG_PACKAGE_dnsmasq_full_nftset=y"),
            ("# CONFIG_PACKAGE_dnsmasq is not set", "CONFIG_PACKAGE_dnsmasq=y",
             "Expected CONFIG_PACKAGE_dnsmasq=n"),
        ):
            with self.subTest(option=before):
                self.assertIn(before, seed)
                config.write_text(seed.replace(before, after))
                with self.assertRaisesRegex(ValueError, error):
                    validate.check_config(config, False)

    def test_management_files_without_core_pass_rootfs_checks(self):
        validate.check_openclash(self.rootfs)

    def test_nonexecutable_downloader_is_rejected(self):
        script = self.rootfs / "usr/share/openclash/openclash_core.sh"
        script.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "not executable"):
            validate.check_openclash(self.rootfs)

    def test_missing_controller_is_rejected(self):
        (self.rootfs / "usr/lib/lua/luci/controller/openclash.lua").unlink()
        with self.assertRaisesRegex(ValueError, "management component is missing"):
            validate.check_openclash(self.rootfs)

    def test_enabled_backup_in_factory_config_is_rejected(self):
        self.config.write_text(self.config.read_text().replace("option enable '0'", "option enable '1'"))
        with self.assertRaisesRegex(ValueError, "disabled by default"):
            validate.check_openclash(self.rootfs)

    def test_bundled_core_or_archive_in_flash_or_ram_is_rejected(self):
        for name in ("etc/openclash/core/clash_meta", "etc/openclash/core/core.tar.gz",
                     "tmp/etc/openclash/core/clash_meta", "usr/bin/mihomo", "etc/openclash/clash"):
            with self.subTest(path=name):
                path = self.rootfs / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"unexpected preinstalled core")
                try:
                    with self.assertRaisesRegex(ValueError, "runtime, not bundled|bundled proxy core"):
                        validate.check_openclash(self.rootfs)
                finally:
                    path.unlink()

    def test_defaults_disable_backup_and_choose_arm64_core_in_ram(self):
        tools = self.root / "tools"
        tools.mkdir()
        log = self.root / "uci.log"
        uci = tools / "uci"
        uci.write_text('#!/bin/sh\n/bin/cat > "$OPENCLASH_TEST_UCI_LOG"\n')
        uci.chmod(0o755)
        env = {**os.environ, "PATH": str(tools), "OPENCLASH_TEST_UCI_LOG": str(log)}
        result = subprocess.run(["/bin/sh", str(DEFAULTS)], env=env, check=True, capture_output=True, text=True)
        self.assertEqual(result.stderr, "")
        settings = {}
        for line in log.read_text().splitlines():
            command = shlex.split(line)
            if command[0] == "set":
                key, value = command[1].split("=", 1)
                settings[key] = value
        self.assertEqual(settings["openclash.config.enable"], "0")
        self.assertEqual(settings["openclash.config.core_version"], "linux-arm64")
        self.assertEqual(settings["openclash.config.small_flash_memory"], "1")
        self.assertIn("commit openclash", log.read_text())


if __name__ == "__main__":
    unittest.main()
