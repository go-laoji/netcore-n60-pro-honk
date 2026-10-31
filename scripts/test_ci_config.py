#!/usr/bin/env python3
"""Regression checks for the configuration failures in Actions run 41165282876."""

import importlib.util
from pathlib import Path
import tempfile
import unittest

import validate


class ConfigurationRegressionTests(unittest.TestCase):
    def test_kconfig_cycle_is_rejected_despite_written_configuration(self):
        # This diagnostic was followed by a successful make exit in the real run.
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "defconfig.log"
            log.write_text(
                "tmp/.config-package.in:68803:error: recursive dependency detected!\n"
                "tmp/.config-package.in:68803: symbol PACKAGE_luci-app-weechat "
                "depends on PACKAGE_luci-app-weechat\n"
                "# configuration written to .config\n"
            )
            with self.assertRaisesRegex(ValueError, "Kconfig reported errors"):
                validate.check_defconfig_log(log)

    def test_warnings_do_not_hide_successful_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "defconfig.log"
            log.write_text(
                "WARNING: optional package has a dependency which does not exist\n"
                "# configuration written to .config\n"
            )
            validate.check_defconfig_log(log)

    def test_version_stamping_enables_image_options(self):
        spec = importlib.util.spec_from_file_location(
            "stamp_version", Path(__file__).with_name("stamp-version.py")
        )
        stamp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stamp)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "scripts").mkdir()
            (source / "scripts/getver.sh").write_text("printf '%s\\n' r1-abcdef\n")
            (source / ".config").write_text(
                "# CONFIG_IMAGEOPT is not set\nCONFIG_VERSIONOPT=y\n"
            )
            stamp.stamp_version(source)
            config = validate.read_config(source / ".config")
            self.assertEqual(config["CONFIG_IMAGEOPT"], "y")
            self.assertEqual(config["CONFIG_VERSIONOPT"], "y")


if __name__ == "__main__":
    unittest.main()
