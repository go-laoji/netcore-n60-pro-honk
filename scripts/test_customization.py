#!/usr/bin/env python3
"""Plugin input regression checks using temporary files, without OpenWrt builds."""

from pathlib import Path
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
        self.assertEqual(self.requests.read_text(), "")
        validate.check_config(self.config, False)
        customize.check_config(self.requests, self.config)
        output = self.root / "feeds.conf"
        customize.merge_feeds(PROJECT / "feeds.conf.default", PROJECT / "feeds.conf.custom", output)
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


if __name__ == "__main__":
    unittest.main()
