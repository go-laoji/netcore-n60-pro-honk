#!/usr/bin/env python3
"""Release naming, Honk metadata, asset integrity, and draft publication tests."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import publish_release


class FirmwareReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        self.image = self.artifacts / "immortalwrt-go-laoji-10-31-netcore_n60-pro-sysupgrade.itb"
        self.image.write_bytes(b"firmware fixture")
        self.manifest = self.artifacts / "immortalwrt-netcore_n60-pro.manifest"
        self.manifest.write_text("honk - 2026.10.24-r2\nluci-app-honk - 2026.10.30-r1\n")
        self.build_inputs = self.artifacts / "build-inputs.txt"
        self.feed_commit = "b" * 40
        self.build_inputs.write_text(
            f"Configuration repository commit: {'a' * 40}\n\n"
            "Pinned feeds:\n"
            f"src-git honk https://github.com/kenzok8/openwrt-honk.git^{self.feed_commit}\n"
        )
        (self.artifacts / "firmware-version.json").write_text(json.dumps({
            "build_date": "2026-10-31", "timezone": "Asia/Shanghai",
            "display_label": "go-laoji-10/31", "filename_tag": "go-laoji-10-31",
            "source_revision": "r1-abcdef", "version_code": "r1-abcdef go-laoji-10/31",
        }))
        (self.artifacts / "openwrt_release").write_text(
            "DISTRIB_ID='ImmortalWrt'\nDISTRIB_RELEASE='25.12-SNAPSHOT'\n"
            "DISTRIB_REVISION='r1-abcdef'\nDISTRIB_TARGET='mediatek/filogic'\n"
            "DISTRIB_ARCH='aarch64_cortex-a53'\n"
            "DISTRIB_DESCRIPTION='ImmortalWrt 25.12-SNAPSHOT r1-abcdef go-laoji-10/31'\n"
        )
        self.write_checksums()

    def write_checksums(self):
        (self.artifacts / "sha256sums").write_text("".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
            for path in sorted(self.artifacts.iterdir())
            if path.name != "sha256sums"
        ))

    def metadata(self, now=None):
        return publish_release.prepare_release(
            self.artifacts, "owner/repo", "a" * 40, "123", "1",
            now or datetime(2026, 10, 31, 16, 42, tzinfo=timezone.utc),
        )

    def test_name_uses_release_time_and_preserves_embedded_version(self):
        metadata = self.metadata()
        self.assertEqual(metadata["name"], "ImmortalWrt 25.12-SNAPSHOT r1-abcdef go-laoji-10/31 00:42")
        self.assertTrue(metadata["tag"].endswith("20261101-0042"))
        self.assertRegex(metadata["tag"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        later = self.metadata(datetime(2026, 10, 31, 16, 43, tzinfo=timezone.utc))
        self.assertNotEqual(metadata["name"], later["name"])
        self.assertNotEqual(metadata["tag"], later["tag"])

    def test_modified_firmware_is_rejected(self):
        self.image.write_bytes(b"changed after checksum generation")
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            self.metadata()

    def test_missing_asset_is_rejected(self):
        self.image.unlink()
        with self.assertRaisesRegex(ValueError, "does not cover"):
            self.metadata()

    def test_missing_honk_version_is_rejected(self):
        self.manifest.write_text("honk - 2026.10.24-r2\nluci-app-honk -\nluci-app-honk-extra - 1\n")
        self.write_checksums()
        with self.assertRaisesRegex(ValueError, "missing version for luci-app-honk"):
            self.metadata()

    def test_duplicate_honk_version_is_rejected(self):
        with self.manifest.open("a") as manifest:
            manifest.write("honk - 2026.11.05-r2\n")
        self.write_checksums()
        with self.assertRaisesRegex(ValueError, "Duplicate package in firmware manifest: honk"):
            self.metadata()

    def test_branch_without_resolved_commit_is_rejected(self):
        self.build_inputs.write_text("src-git honk https://github.com/kenzok8/openwrt-honk.git;main\n")
        self.write_checksums()
        with self.assertRaisesRegex(ValueError, "must include its resolved commit"):
            self.metadata()

    def test_assets_upload_as_draft_before_publication(self):
        metadata = self.metadata()
        output = self.root / "metadata"
        with patch("publish_release.subprocess.run") as run:
            publish_release.publish(metadata, self.artifacts, output)
        create, publish = [call.args[0] for call in run.call_args_list]
        self.assertEqual(create[:3], ["gh", "release", "create"])
        self.assertIn("--draft", create)
        self.assertIn(str(self.image.resolve()), create)
        self.assertEqual(create[create.index("--target") + 1], "a" * 40)
        self.assertEqual(publish[:3], ["gh", "release", "edit"])
        self.assertIn("--draft=false", publish)
        self.assertNotIn(str(self.artifacts), (output / "release.json").read_text())
        notes = Path(create[create.index("--notes-file") + 1]).read_text()
        self.assertIn("- `honk` `2026.10.24-r2`", notes)
        self.assertIn("- `luci-app-honk` `2026.10.30-r1`", notes)
        self.assertIn(f"https://github.com/kenzok8/openwrt-honk/commit/{self.feed_commit}", notes)
        self.assertIn(f"配置提交：`{'a' * 40}`", notes)

    def test_failed_upload_does_not_publish_draft(self):
        with patch("publish_release.subprocess.run", side_effect=subprocess.CalledProcessError(1, ["gh"])) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                publish_release.publish(self.metadata(), self.artifacts, self.root / "metadata")
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
