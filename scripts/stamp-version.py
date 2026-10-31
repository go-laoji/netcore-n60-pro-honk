#!/usr/bin/env python3
"""Stamp a prepared OpenWrt config with a dated display label and filename tag."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
from zoneinfo import ZoneInfo


def stamp_version(source, build_time=None):
    config_path = source / ".config"
    config = config_path.read_text()
    if build_time is not None and build_time.tzinfo is None:
        raise ValueError("Build time must include a timezone")
    build_day = (build_time or datetime.now(ZoneInfo("Asia/Shanghai"))).astimezone(
        ZoneInfo("Asia/Shanghai")
    ).date()
    revision = subprocess.check_output(
        ["bash", "scripts/getver.sh"], cwd=source, text=True
    ).strip()
    if not re.fullmatch(r"[A-Za-z0-9._+-]+", revision):
        raise ValueError("Unexpected upstream revision format")

    label = f"go-laoji-{build_day:%m/%d}"
    filename_tag = f"go-laoji-{build_day:%m-%d}"
    version_code = f"{revision} {label}"
    values = {
        "CONFIG_VERSIONOPT": "y",
        "CONFIG_VERSION_CODE": json.dumps(version_code),
        "CONFIG_EXTRA_IMAGE_NAME": json.dumps(filename_tag),
        "CONFIG_VERSION_CODE_FILENAMES": "n",
    }
    # Replace all occurrences of our options so stamping is safe to repeat.
    # VERSION_NUMBER, VERSION_REPO and VERSION_DIST retain their upstream values.
    options = "|".join(map(re.escape, values))
    pattern = re.compile(rf"^(?:(?:{options})=|# (?:{options}) is not set$)")
    lines = [line for line in config.splitlines() if not pattern.match(line)]
    for key, value in values.items():
        lines.append(f"# {key} is not set" if value == "n" else f"{key}={value}")
    config_path.write_text("\n".join(lines) + "\n")

    info = {
        "build_date": build_day.isoformat(),
        "timezone": "Asia/Shanghai",
        "display_label": label,
        "filename_tag": filename_tag,
        "source_revision": revision,
        "version_code": version_code,
    }
    (source / "firmware-version.json").write_text(json.dumps(info, indent=2) + "\n")
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Prepared OpenWrt source directory")
    args = parser.parse_args()
    try:
        info = stamp_version(args.source)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Version stamping failed: {error}", file=sys.stderr)
        return 1
    print(f"Firmware version code: {info['version_code']}")
    print(f"Image filename tag: {info['filename_tag']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
