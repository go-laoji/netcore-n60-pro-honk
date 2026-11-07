#!/usr/bin/env python3
"""Merge and verify plugin inputs without downloading or building OpenWrt."""

import argparse
from pathlib import Path
import re
import subprocess
import sys

import validate


OPTION = re.compile(r"(CONFIG_[A-Za-z0-9_-]+)=(.*)")
DISABLED = re.compile(r"# (CONFIG_[A-Za-z0-9_-]+) is not set")
EMPTY_CUSTOM_OPTIONS = "# No custom plugin options.\n"


def read_fragment(path):
    options = {}
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        disabled = DISABLED.fullmatch(line)
        if disabled:
            key, value = disabled[1], "n"
        elif not line or line.startswith("#"):
            continue
        else:
            match = OPTION.fullmatch(line)
            validate.require(match is not None, f"{path}:{number}: invalid Kconfig option")
            key, value = match.groups()
            validate.require(re.fullmatch(r'y|m|n|-?\d+|0x[0-9a-fA-F]+|"(?:[^"\\]|\\.)*"', value),
                             f"{path}:{number}: invalid Kconfig value for {key}")
        validate.require(key not in options, f"{path}:{number}: duplicate option {key}")
        options[key] = value
    return options


def render_options(options):
    return "".join(f"# {key} is not set\n" if value == "n" else f"{key}={value}\n"
                   for key, value in options.items())


def merge_config(base, custom, output, requests=None, seed=None):
    original = read_fragment(base)
    extra = read_fragment(custom)
    validate.require(original, f"Empty base configuration: {base}")
    combined = {**original, **extra}
    # Preserve seed comments, and replace existing keys rather than appending duplicates.
    lines = []
    for line in base.read_text().splitlines(keepends=True):
        match = OPTION.fullmatch(line.strip()) or DISABLED.fullmatch(line.strip())
        if match is None or match[1] not in extra:
            lines.append(line)
    text = "".join(lines)
    if extra:
        text = text.rstrip("\n") + "\n\n# User plugin selections\n" + render_options(extra)
    # Validate in memory before writing; existing firmware constraints remain in force.
    for key, expected in validate.REQUIRED_CONFIG.items():
        validate.require(combined.get(key, "n") == expected, f"Expected {key}={expected}")
    validate.check_proxy_packages(combined)
    if requests is not None:
        baseline = read_fragment(seed or base)
        requested = {key: value for key, value in combined.items()
                     if value != baseline.get(key, "n") or key in extra}
        requests.write_text(render_options(requested) or EMPTY_CUSTOM_OPTIONS)
    output.write_text(text)


def read_feeds(path):
    feeds = {}
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"src-git[ \t]+([A-Za-z0-9_]+)[ \t]+(https://[^\s;^]+);([^\s;^]+)", line)
        validate.require(match is not None,
                         f"{path}:{number}: expected src-git NAME https://URL;BRANCH")
        name, url, branch = match.groups()
        validate.require(name not in feeds, f"{path}:{number}: duplicate feed {name}")
        # The feed name is a directory. Branch rules match the existing source fetch policy.
        check = subprocess.run(["git", "check-ref-format", f"refs/heads/{branch}"],
                               capture_output=True, text=True)
        validate.require(check.returncode == 0, f"{path}:{number}: invalid branch {branch}")
        feeds[name] = (url, branch)
    return feeds


def merge_feeds(base, custom, output):
    original = read_feeds(base)
    extra = read_feeds(custom)
    duplicates = original.keys() & extra.keys()
    validate.require(not duplicates, f"Custom feeds duplicate existing names: {', '.join(sorted(duplicates))}")
    text = base.read_text()
    if extra:
        text = text.rstrip("\n") + "\n\n# User plugin feeds\n" + custom.read_text().rstrip("\n") + "\n"
    output.write_text(text)


def check_config(requests, config):
    actual = validate.read_config(config)
    for key, expected in read_fragment(requests).items():
        validate.require(actual.get(key, "n") == expected,
                         f"Custom option was changed or dropped: {key}={expected}; "
                         f"expanded value is {actual.get(key, 'n')}")


def check_manifest(requests, manifest, package_info):
    packages = validate.read_manifest(manifest)
    # PACKAGE_* also includes feature toggles; only real packages belong in a manifest.
    metadata = {}
    for match in re.finditer(r"^Package: (\S+)\n(.*?)(?=^Package: |\Z)",
                             package_info.read_text(), re.M | re.S):
        abi = re.search(r"^ABI-Version: (\S+)$", match[2], re.M)
        metadata[match[1]] = abi[1] if abi else ""
    validate.require(metadata, "Package metadata is empty")
    for key, value in read_fragment(requests).items():
        name = key.removeprefix("CONFIG_PACKAGE_")
        if not key.startswith("CONFIG_PACKAGE_") or name not in metadata or value != "y":
            continue
        # FormatABISuffix in upstream include/feeds.mk excludes kernel modules.
        abi = "" if name.startswith("kmod-") else metadata[name]
        runtime_name = name + ("-" if name[-1:].isdigit() and abi else "") + abi
        validate.require(runtime_name in packages,
                         f"Firmware is missing custom package: {runtime_name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("config", "feeds"):
        child = sub.add_parser(command)
        child.add_argument("base", type=Path)
        child.add_argument("custom", type=Path)
        child.add_argument("output", type=Path)
        if command == "config":
            child.add_argument("--requests", type=Path)
            child.add_argument("--seed", type=Path, help="Original seed, before DIY changes")
    child = sub.add_parser("check-feeds")
    child.add_argument("path", type=Path)
    for command in ("check-config", "check-manifest"):
        child = sub.add_parser(command)
        child.add_argument("requests", type=Path)
        child.add_argument("path", type=Path)
        if command == "check-manifest":
            child.add_argument("--package-info", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "config":
            merge_config(args.base, args.custom, args.output, args.requests, args.seed)
        elif args.command == "feeds":
            merge_feeds(args.base, args.custom, args.output)
        elif args.command == "check-feeds":
            read_feeds(args.path)
        elif args.command == "check-config":
            check_config(args.requests, args.path)
        else:
            check_manifest(args.requests, args.path, args.package_info)
    except (OSError, ValueError) as error:
        print(f"Customization failed: {error}", file=sys.stderr)
        return 1
    print(f"Validated customization: {args.command}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
