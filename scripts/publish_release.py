#!/usr/bin/env python3
"""Publish verified firmware using its embedded version and the release-time clock."""

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

import validate


HONK_FEED_URL = "https://github.com/kenzok8/openwrt-honk"


def verify_assets(artifacts):
    files = list(artifacts.iterdir())
    if not files or any(not path.is_file() or path.is_symlink() for path in files):
        raise ValueError("Firmware artifact must contain regular files only")
    expected = {}
    for line in (artifacts / "sha256sums").read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        if not match:
            raise ValueError("Invalid SHA256 manifest line")
        digest, name = match.groups()
        if name in expected or Path(name).name != name or name in (".", "..", "sha256sums"):
            raise ValueError("Invalid or duplicate SHA256 filename")
        expected[name] = digest
    if set(expected) != {path.name for path in files if path.name != "sha256sums"}:
        raise ValueError("SHA256 manifest does not cover all firmware assets")
    for name, expected_digest in expected.items():
        digest = hashlib.sha256()
        with (artifacts / name).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected_digest:
            raise ValueError(f"SHA256 mismatch: {name}")
    if len(list(artifacts.glob("*netcore_n60-pro*-sysupgrade.itb"))) != 1:
        raise ValueError("Expected one verified N60 Pro sysupgrade image")
    validate.check_release(artifacts / "openwrt_release", artifacts / "firmware-version.json")
    return sorted(path.name for path in files)


def read_honk_metadata(artifacts):
    manifests = list(artifacts.glob("*netcore_n60-pro*.manifest"))
    validate.require(len(manifests) == 1, "Expected exactly one N60 Pro firmware manifest")
    packages = validate.read_manifest(manifests[0])
    versions = {}
    for name in ("honk", "luci-app-honk"):
        version = packages.get(name)
        validate.require(version, f"Firmware manifest is missing version for {name}")
        versions[name] = version

    build_inputs = (artifacts / "build-inputs.txt").read_text()
    feeds = re.findall(r"^src-git[ \t]+honk[ \t]+(.+)$", build_inputs, re.M)
    validate.require(len(feeds) == 1, "Expected exactly one Honk feed in build-inputs.txt")
    pin = re.fullmatch(rf"{re.escape(HONK_FEED_URL)}(?:\.git)?\^([0-9a-f]{{40}})", feeds[0].strip())
    validate.require(pin is not None, "Honk feed in build-inputs.txt must include its resolved commit")
    return versions, pin[1]


def prepare_release(artifacts, repository, target, run_id, run_attempt, now=None):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid repository")
    if not re.fullmatch(r"[0-9a-f]{40}", target):
        raise ValueError("Release target must be the full build commit SHA")
    if not re.fullmatch(r"[1-9][0-9]*", str(run_id)) or not re.fullmatch(r"[1-9][0-9]*", str(run_attempt)):
        raise ValueError("Invalid source workflow run or attempt")
    assets = verify_assets(artifacts)
    honk_versions, honk_feed_commit = read_honk_metadata(artifacts)
    release_text = (artifacts / "openwrt_release").read_text()
    description = re.search(r"^DISTRIB_DESCRIPTION='([^']+)'$", release_text, re.M)[1]
    # Read the clock after asset verification, immediately before Release creation.
    if now is not None and now.tzinfo is None:
        raise ValueError("Release time must include a timezone")
    release_time = (now or datetime.now(ZoneInfo("Asia/Shanghai"))).astimezone(ZoneInfo("Asia/Shanghai"))
    safe_version = re.sub(r"[^a-z0-9]+", "-", description.lower()).strip("-")
    tag = f"firmware-{safe_version}-{release_time:%Y%m%d-%H%M}"
    return {
        "name": f"{description} {release_time:%H:%M}",
        "tag": tag,
        "repository": repository,
        "target": target,
        "created_at": release_time.isoformat(timespec="seconds"),
        "source_run_url": f"https://github.com/{repository}/actions/runs/{run_id}/attempts/{run_attempt}",
        "honk_versions": honk_versions,
        "honk_feed_commit": honk_feed_commit,
        "url": f"https://github.com/{repository}/releases/tag/{tag}",
        "assets": assets,
    }


def publish(metadata, artifacts, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "release.json").write_text(json.dumps(metadata, indent=2) + "\n")
    notes = output / "notes.md"
    package_notes = "\n".join(f"- `{name}` `{version}`" for name, version in metadata["honk_versions"].items())
    honk_commit = metadata["honk_feed_commit"]
    notes.write_text(
        f"固件版本：{metadata['name']}\n\n"
        f"设备：Netcore N60 Pro / ImmortalWrt 25.12 / Linux 6.12 / UBI-FIT。\n\n"
        f"**Honk 软件包版本**\n\n{package_notes}\n\n"
        f"openwrt-honk 提交：[`{honk_commit[:12]}`]({HONK_FEED_URL}/commit/{honk_commit})。\n\n"
        f"来源构建：[GitHub Actions]({metadata['source_run_url']})。\n\n"
        f"配置提交：`{metadata['target']}`。\n\n"
        f"Release 创建时间：{metadata['created_at']}（Asia/Shanghai）。\n\n"
        "产物已通过构建验收与 SHA256 校验；下载后可使用 sha256sums 核对文件。\n"
        "镜像布局说明见随附 DEVICE-LAYOUT.txt 和仓库 README。\n"
    )
    # Upload everything to a draft first so partially uploaded firmware is not published.
    subprocess.run([
        "gh", "release", "create", metadata["tag"],
        *[str((artifacts / name).resolve()) for name in metadata["assets"]],
        "--repo", metadata["repository"], "--target", metadata["target"],
        "--title", metadata["name"], "--notes-file", str(notes.resolve()), "--draft",
    ], check=True)
    subprocess.run([
        "gh", "release", "edit", metadata["tag"], "--repo", metadata["repository"],
        "--draft=false", "--latest",
    ], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true", help="Verify assets and preview metadata without publishing")
    args = parser.parse_args()
    try:
        metadata = prepare_release(args.artifacts, args.repository, args.target, args.run_id, args.run_attempt)
        if args.dry_run:
            print(json.dumps(metadata, indent=2))
            return 0
        publish(metadata, args.artifacts, args.output)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as summary:
                summary.write(f"### 固件 Release\n\n[{metadata['name']}]({metadata['url']})\n")
        print(metadata["url"])
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Release publication failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
