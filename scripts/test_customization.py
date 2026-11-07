#!/usr/bin/env python3
"""Plugin input regression checks using temporary files, without OpenWrt builds."""

from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import customize
import validate


PROJECT = Path(__file__).resolve().parent.parent


class CustomPluginTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.seed = PROJECT / "immortalwrt-netcore-n60-pro-honk.config"
        self.custom = self.root / "custom.config"
        self.config = self.root / ".config"
        self.requests = self.root / "custom-options.config"
        self.custom.write_text("# No extra plugins\n")

    def merge(self, base=None):
        customize.merge_config(base or self.seed, self.custom, self.config,
                               self.requests, self.seed)

    def test_empty_inputs_preserve_defaults_byte_for_byte(self):
        self.merge()
        self.assertEqual(self.config.read_bytes(), self.seed.read_bytes())
        self.assertEqual(self.requests.read_text(), customize.EMPTY_CUSTOM_OPTIONS)
        self.assertEqual(customize.read_fragment(self.requests), {})
        validate.check_config(self.config, False)
        customize.check_config(self.requests, self.config)
        output = self.root / "feeds.conf"
        empty_feed = self.root / "feeds.conf.custom"
        empty_feed.write_text("# No extra feeds\n")
        customize.merge_feeds(PROJECT / "feeds.conf.default", empty_feed, output)
        self.assertEqual(output.read_bytes(), (PROJECT / "feeds.conf.default").read_bytes())

    def test_overrides_replace_disabled_options_without_duplicates(self):
        self.custom.write_text("CONFIG_PACKAGE_tcpdump=y\n# CONFIG_PACKAGE_nano is not set\n")
        self.merge()
        config = validate.read_config(self.config)
        self.assertEqual(config["CONFIG_PACKAGE_tcpdump"], "y")
        self.assertEqual(config["CONFIG_PACKAGE_nano"], "n")
        self.assertEqual(customize.read_fragment(self.requests), customize.read_fragment(self.custom))
        customize.check_config(self.requests, self.config)

    def test_custom_fragment_takes_precedence_over_diy_and_records_both(self):
        self.config.write_text(self.seed.read_text() + "CONFIG_PACKAGE_tcpdump=m\nCONFIG_PACKAGE_tree=y\n")
        self.custom.write_text("CONFIG_PACKAGE_tcpdump=y\n")
        self.merge(self.config)
        self.assertEqual(customize.read_fragment(self.requests), {
            "CONFIG_PACKAGE_tcpdump": "y", "CONFIG_PACKAGE_tree": "y",
        })
        self.assertEqual(validate.read_config(self.config)["CONFIG_PACKAGE_tcpdump"], "y")

    def test_duplicate_or_invalid_options_fail_before_writing(self):
        for text in ("CONFIG_PACKAGE_tcpdump=y\nCONFIG_PACKAGE_tcpdump=m\n",
                     "CONFIG_PACKAGE_tcpdump=yes\n", "CONFIG_PACKAGE_tcpdump=\n",
                     "PACKAGE_tcpdump=y\n", "CONFIG_BROKEN=\"unclosed\n"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "duplicate|invalid"):
                self.custom.write_text(text)
                self.merge()
            self.assertFalse(self.config.exists())

    def test_core_firmware_contract_cannot_be_disabled(self):
        for text in ("# CONFIG_PACKAGE_honk is not set\n", "CONFIG_PACKAGE_dnsmasq=y\n",
                     "CONFIG_KERNEL_DEBUG_INFO_BTF=n\n", "CONFIG_PACKAGE_mihomo=y\n"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "Expected|Unexpected proxy"):
                self.custom.write_text(text)
                self.merge()

    def test_lost_plugin_or_changed_feature_is_rejected_after_expansion(self):
        self.custom.write_text('CONFIG_PACKAGE_tcpdump=y\nCONFIG_FEATURE="requested"\n')
        self.merge()
        for before, after in (("CONFIG_PACKAGE_tcpdump=y", "# CONFIG_PACKAGE_tcpdump is not set"),
                              ('CONFIG_FEATURE="requested"', 'CONFIG_FEATURE="changed"')):
            with self.subTest(option=before):
                expanded = self.root / "expanded.config"
                expanded.write_text(self.config.read_text().replace(before, after))
                with self.assertRaisesRegex(ValueError, "changed or dropped"):
                    customize.check_config(self.requests, expanded)

    def test_extra_feeds_are_appended_with_base_precedence(self):
        extra = self.root / "feeds.conf.custom"
        extra.write_text("# my packages\nsrc-git\tmyplugins https://github.com/example/plugins.git;main\n")
        output = self.root / "feeds.conf"
        customize.merge_feeds(PROJECT / "feeds.conf.default", extra, output)
        feeds = customize.read_feeds(output)
        self.assertEqual(next(iter(feeds)), "honk")
        self.assertEqual(list(feeds)[-1], "myplugins")
        self.assertEqual(feeds["myplugins"], ("https://github.com/example/plugins.git", "main"))

    def test_invalid_or_duplicate_feeds_are_rejected(self):
        extra = self.root / "feeds.conf.custom"
        output = self.root / "feeds.conf"
        for text in (
            "src-git honk https://github.com/example/plugins.git;main\n",
            "src-git mine https://github.com/example/plugins.git\n",
            "src-git mine https://github.com/example/plugins.git;bad..branch\n",
            "src-link mine /tmp/plugins\n",
            "src-git mine https://github.com/example/plugins.git^" + "a" * 40 + "\n",
            "src-git mine https://github.com/example/plugins.git;main\n" * 2,
        ):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "duplicate|expected|invalid"):
                extra.write_text(text)
                customize.merge_feeds(PROJECT / "feeds.conf.default", extra, output)
            self.assertFalse(output.exists())

    def test_manifest_requires_built_in_plugins_but_ignores_modules_and_feature_flags(self):
        self.requests.write_text("CONFIG_PACKAGE_tcpdump=y\nCONFIG_PACKAGE_example_FEATURE=y\n"
                                 "CONFIG_PACKAGE_tree=m\n# CONFIG_PACKAGE_nano is not set\n")
        manifest = self.root / "firmware.manifest"
        manifest.write_text("tcpdump - 1\n")
        package_info = self.root / "packageinfo"
        package_info.write_text("Package: tcpdump\nVersion: 1\n@@\n"
                                "Package: tree\nVersion: 1\n@@\nPackage: nano\nVersion: 1\n@@\n")
        customize.check_manifest(self.requests, manifest, package_info)
        manifest.write_text("honk - 1\n")
        with self.assertRaisesRegex(ValueError, "missing custom package: tcpdump"):
            customize.check_manifest(self.requests, manifest, package_info)

    def test_manifest_uses_actual_abi_package_names(self):
        self.requests.write_text("CONFIG_PACKAGE_libexample=y\nCONFIG_PACKAGE_libexample2=y\n"
                                 "CONFIG_PACKAGE_kmod-example=y\n")
        package_info = self.root / "packageinfo"
        package_info.write_text("Package: libexample\nABI-Version: 20261107\n@@\n"
                                "Package: libexample2\nABI-Version: 1\n@@\n"
                                "Package: kmod-example\nABI-Version: 6.12\n@@\n")
        manifest = self.root / "firmware.manifest"
        manifest.write_text("libexample20261107 - 1\nlibexample2-1 - 1\nkmod-example - 1\n")
        customize.check_manifest(self.requests, manifest, package_info)
        manifest.write_text("libexample - 1\nlibexample2 - 1\n")
        with self.assertRaisesRegex(ValueError, "missing custom package"):
            customize.check_manifest(self.requests, manifest, package_info)


class PreparationHookTests(unittest.TestCase):
    """Run the preparation orchestration against fake sources and local command stubs."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        for name in ("build.env", "feeds.conf.default", "feeds.conf.custom", "custom.config",
                     "diy-part1.sh", "diy-part2.sh", "immortalwrt-netcore-n60-pro-honk.config"):
            shutil.copyfile(PROJECT / name, self.project / name)
        shutil.copytree(PROJECT / "scripts", self.project / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(PROJECT / "files", self.project / "files")
        self.source = self.root / "openwrt"
        self.template = self.root / "source-fixture"
        for name, content in {
            "target/linux/mediatek/Makefile": "KERNEL_PATCHVER:=6.12\n",
            "target/linux/mediatek/image/filogic.mk": "define Device/netcore_n60-pro\nendef\n",
            "target/linux/mediatek/dts/mt7986a-netcore-n60-pro.dts": '"netcore,n60-pro"; volname = "fit";\n',
            "scripts/getver.sh": "printf '%s\\n' r1-abcdef\n",
        }.items():
            path = self.template / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        self.tools = self.root / "tools"
        self.tools.mkdir()
        self.write_script(self.tools / "uname", "#!/bin/sh\necho Linux\n")
        # Never fetch network sources: git init copies the miniature fixture instead.
        self.write_script(self.tools / "git", f"#!{sys.executable}\n" + '''
import os, pathlib, shutil, sys
args = sys.argv[1:]
if args[0] == 'init':
    shutil.copytree(os.environ['CUSTOM_TEST_TEMPLATE'], args[1])
elif 'rev-parse' in args:
    mismatch = os.environ.get('CUSTOM_TEST_BAD_HEAD') and 'HEAD' in args and args[1].startswith('feeds/')
    print(('b' if mismatch else 'a') * 40)
elif 'get-url' in args:
    feed = pathlib.Path(args[1]).name
    for line in pathlib.Path('feeds.conf.default').read_text().splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[:2] == ['src-git', feed]:
            print('https://github.com/example/wrong.git' if os.environ.get('CUSTOM_TEST_BAD_ORIGIN')
                  else fields[2].split(';')[0])
''')
        # A fake feed tool creates package definitions for the existing presence checks.
        self.write_script(self.template / "scripts/feeds", f"#!{sys.executable}\n" + '''
import os, pathlib, sys
with open(os.environ['CUSTOM_TEST_EVENTS'], 'a') as log:
    log.write('feeds ' + ' '.join(sys.argv[1:]) + '\\n')
if sys.argv[1] == 'update':
    assert pathlib.Path('before-feeds.marker').is_file()
    packages = {
        'honk': ['honk', 'luci-app-honk'],
        'luci/themes': ['luci-theme-argon'],
        'luci/applications': ['luci-app-argon-config', 'luci-app-openclash'],
        'nas/network/services': ['quickstart'],
        'nas_luci/luci': ['luci-app-quickstart'],
        'istore/luci': ['luci-app-store', 'luci-lib-taskd', 'luci-lib-xterm', 'taskd'],
    }
    for directory, names in packages.items():
        for name in names:
            path = pathlib.Path('feeds') / directory / name / 'Makefile'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
''')
        self.events = self.root / "events.log"
        self.env = {**os.environ, "PATH": str(self.tools) + os.pathsep + os.environ["PATH"],
                    "GITHUB_ACTIONS": "true", "PYTHONDONTWRITEBYTECODE": "1",
                    "CUSTOM_TEST_TEMPLATE": str(self.template), "CUSTOM_TEST_EVENTS": str(self.events)}
        (self.project / "diy-part1.sh").write_text(
            '#!/bin/bash\nset -euo pipefail\n'
            'test "$PWD" = "$OPENWRT_DIR"\ntest -f "$PROJECT_DIR/custom.config"\n'
            'touch before-feeds.marker\necho before >> "$CUSTOM_TEST_EVENTS"\n'
        )
        (self.project / "diy-part2.sh").write_text(
            '#!/bin/bash\nset -euo pipefail\n'
            'test -f .config\ntest -f files/etc/uci-defaults/zz-honk-ui\n'
            'test -f feeds/honk/honk/Makefile\n'
            'echo after >> "$CUSTOM_TEST_EVENTS"\necho CONFIG_PACKAGE_tcpdump=m >> .config\n'
        )
        (self.project / "custom.config").write_text("CONFIG_PACKAGE_tcpdump=y\n")
        (self.project / "feeds.conf.custom").write_text(
            "src-git myplugins https://github.com/example/plugins.git;main\n"
        )

    @staticmethod
    def write_script(path, content):
        path.write_text(content)
        path.chmod(0o755)

    def run_prepare(self):
        return subprocess.run(["bash", str(self.project / "scripts/prepare-source.sh"), str(self.source)],
                              env=self.env, capture_output=True, text=True)

    def test_hooks_run_in_order_and_record_final_config_and_feed(self):
        result = self.run_prepare()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        events = self.events.read_text().splitlines()
        self.assertEqual(events[0], "before")
        self.assertEqual(events[1], "feeds update -a")
        self.assertEqual(events[-1], "after")
        self.assertEqual(validate.read_config(self.source / ".config")["CONFIG_PACKAGE_tcpdump"], "y")
        self.assertEqual(customize.read_fragment(self.source / "custom-options.config"),
                         {"CONFIG_PACKAGE_tcpdump": "y"})
        record = (self.source / "build-inputs.txt").read_text()
        self.assertIn("src-git myplugins https://github.com/example/plugins.git^" + "a" * 40, record)
        self.assertIn("Custom configuration requests:\nCONFIG_PACKAGE_tcpdump=y", record)

    def test_failing_first_hook_stops_before_feeds(self):
        (self.project / "diy-part1.sh").write_text("#!/bin/bash\nexit 23\n")
        result = self.run_prepare()
        self.assertEqual(result.returncode, 23, result.stdout + result.stderr)
        self.assertFalse(self.events.exists())

    def test_failing_second_hook_stops_before_stamping(self):
        (self.project / "diy-part2.sh").write_text("#!/bin/bash\nexit 24\n")
        result = self.run_prepare()
        self.assertEqual(result.returncode, 24, result.stdout + result.stderr)
        self.assertFalse((self.source / "firmware-version.json").exists())

    def test_invalid_feed_added_by_hook_is_rejected_before_update(self):
        with (self.project / "diy-part1.sh").open("a") as hook:
            hook.write("echo 'src-link invalid /tmp/packages' >> feeds.conf.default\n")
        result = self.run_prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected src-git", result.stderr)
        self.assertEqual(self.events.read_text(), "before\n")

    def test_feed_without_final_newline_is_still_recorded(self):
        with (self.project / "diy-part1.sh").open("a") as hook:
            hook.write("printf 'src-git last https://github.com/example/last.git;main' >> feeds.conf.default\n")
        result = self.run_prepare()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("src-git last https://github.com/example/last.git^" + "a" * 40,
                      (self.source / "build-inputs.txt").read_text())

    def test_changed_feed_head_is_rejected(self):
        self.env["CUSTOM_TEST_BAD_HEAD"] = "1"
        result = self.run_prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Feed revision mismatch", result.stderr)

    def test_changed_feed_repository_is_rejected(self):
        self.env["CUSTOM_TEST_BAD_ORIGIN"] = "1"
        result = self.run_prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Feed repository mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
