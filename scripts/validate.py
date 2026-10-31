#!/usr/bin/env python3
"""Read-only checks for the N60 Pro Honk configuration and CI build output."""

import argparse
import re
import sys
from pathlib import Path


DEVICE = "CONFIG_TARGET_mediatek_filogic_DEVICE_netcore_n60-pro"
REQUIRED_PACKAGES = (
    "honk", "luci-app-honk", "v2ray-geoip", "v2ray-geosite", "ca-bundle",
    "curl", "ip-full", "ubox", "ubus", "jsonfilter", "jshn", "sqlite3-cli", "libubox",
    "usign", "coreutils-stat", "rpcd", "cgi-io", "firewall4", "nftables-json",
    "kmod-sched-core", "kmod-sched-bpf", "kmod-veth", "kmod-nft-queue",
    "kmod-mt7915e", "kmod-mt7986-firmware", "mt7986-wo-firmware", "kmod-usb3",
    "wpad-openssl", "luci", "luci-base", "luci-app-upnp",
    "luci-i18n-upnp-zh-cn", "miniupnpd-nftables",
)
EXCLUDED_PACKAGES = (
    "bridger", "kmod-nft-offload", "luci-app-turboacc", "luci-app-turboacc-mtk",
    "kmod-shortcut-fe", "kmod-shortcut-fe-cm", "kmod-shortcut-fe-drv",
    "kmod-fast-classifier", "miniupnpd-iptables",
)
REQUIRED_CONFIG = {
    "CONFIG_TARGET_mediatek": "y",
    "CONFIG_TARGET_mediatek_filogic": "y",
    DEVICE: "y",
    "CONFIG_CCACHE": "y",
    "CONFIG_KERNEL_DEBUG_INFO": "y",
    "CONFIG_KERNEL_DEBUG_INFO_REDUCED": "n",
    "CONFIG_KERNEL_DEBUG_INFO_BTF": "y",
    "CONFIG_KERNEL_CGROUPS": "y",
    "CONFIG_KERNEL_CGROUP_BPF": "y",
    "CONFIG_KERNEL_BPF_EVENTS": "y",
    "CONFIG_KERNEL_BPF_STREAM_PARSER": "y",
    "CONFIG_KERNEL_NAMESPACES": "y",
    "CONFIG_KERNEL_NET_NS": "y",
    "CONFIG_KERNEL_XDP_SOCKETS": "y",
    "CONFIG_TARGET_MULTI_PROFILE": "n",
    "CONFIG_TARGET_ALL_PROFILES": "n",
    "CONFIG_VERSIONOPT": "y",
    "CONFIG_VERSION_CODE_FILENAMES": "n",
    **{f"CONFIG_PACKAGE_{name}": "n" for name in EXCLUDED_PACKAGES},
    **{f"CONFIG_PACKAGE_{name}": "y" for name in REQUIRED_PACKAGES},
}
# GeoIP/GeoSite are data, so v2ray-geoip and v2ray-geosite remain allowed.
OTHER_PROXY = re.compile(
    r"^(?:(?:luci-app|luci-i18n)-)?(?:"
    r"dae(?:d|de)?|openclash|clash(?:-meta)?|clashoo|mihomo|nikki|"
    r"passwall2?|ssr-plus|shadowsocks.*|simple-obfs|sing-box|homeproxy|"
    r"vssr|bypass|trojan.*|xray.*|v2ray-(?:core|plugin)|naiveproxy|"
    r"hysteria2?|tuic.*|mosdns|smartdns|adguardhome|chinadns-ng|"
    r"redsocks2?|ipt2socks|brook|overture|sagernet-core)(?:$|[-_])",
    re.IGNORECASE,
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_config(path):
    result = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        active = re.fullmatch(r"(CONFIG_[A-Za-z0-9_-]+)=(.*)", line)
        disabled = re.fullmatch(r"# (CONFIG_[A-Za-z0-9_-]+) is not set", line)
        if not active and not disabled:
            continue
        key, value = active.groups() if active else (disabled[1], "n")
        require(key not in result, f"{path}:{number}: duplicate option {key}")
        result[key] = value
    require(result, f"Empty or invalid configuration: {path}")
    return result


def check_config(path, expanded):
    config = read_config(path)
    for key, expected in REQUIRED_CONFIG.items():
        require(config.get(key, "n") == expected, f"Expected {key}={expected}")
    devices = [key for key, value in config.items()
               if re.fullmatch(r"CONFIG_TARGET_.*_DEVICE_.*", key) and value == "y"]
    require(devices == [DEVICE], f"Expected only N60 Pro; selected devices: {devices}")
    for key, value in config.items():
        if key.startswith("CONFIG_PACKAGE_") and value in ("y", "m"):
            name = key.removeprefix("CONFIG_PACKAGE_")
            require(not OTHER_PROXY.match(name), f"Unexpected proxy package: {name}={value}")
    if expanded:
        require(config.get("CONFIG_TARGET_ARCH_PACKAGES") == '"aarch64_cortex-a53"',
                "Unexpected target package architecture")
        require(config.get("CONFIG_LINUX_6_12") == "y", "Expected Linux 6.12 target")


def check_source(path):
    target = (path / "target/linux/mediatek/Makefile").read_text()
    version = re.search(r"^KERNEL_PATCHVER\s*:?=\s*(\d+)\.(\d+)\s*$", target, re.M)
    require(version is not None, "Cannot determine target kernel version")
    require(tuple(map(int, version.groups())) == (6, 12),
            "This configuration requires the pinned Linux 6.12 source")
    image = (path / "target/linux/mediatek/image/filogic.mk").read_text()
    require("define Device/netcore_n60-pro\n" in image, "N60 Pro profile is missing")
    dts = (path / "target/linux/mediatek/dts/mt7986a-netcore-n60-pro.dts").read_text()
    require('"netcore,n60-pro"' in dts and 'volname = "fit";' in dts,
            "Expected the N60 Pro UBI/FIT device tree")


def check_kernel(path):
    config = read_config(path)
    built_in = (
        "BPF", "BPF_SYSCALL", "BPF_JIT", "DEBUG_INFO_BTF", "CGROUP_BPF",
        "BPF_EVENTS", "NET_NS",
    )
    modules = ("NET_SCH_INGRESS", "NET_CLS_BPF", "VETH", "NFT_QUEUE")
    for name in built_in:
        require(config.get(f"CONFIG_{name}") == "y", f"Kernel requires CONFIG_{name}=y")
    for name in modules:
        require(config.get(f"CONFIG_{name}") in ("y", "m"),
                f"Kernel requires CONFIG_{name}=y/m")


def check_manifest(path):
    packages = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if parts:
            packages[parts[0]] = parts[2] if len(parts) >= 3 and parts[1] == "-" else ""
    for name in REQUIRED_PACKAGES:
        present = name in packages
        if name == "libubox":
            present = present or any(re.fullmatch(r"libubox\d+", pkg) for pkg in packages)
        require(present, f"Firmware is missing package: {name}")
    for name in packages:
        require(not OTHER_PROXY.match(name), f"Firmware contains another proxy: {name}")
    for name in EXCLUDED_PACKAGES:
        require(name not in packages, f"Firmware contains an excluded package: {name}")
    version = re.match(r"(\d+)\.(\d+)", packages.get("kernel", ""))
    require(version is not None, "Firmware kernel version is missing")
    require(tuple(map(int, version.groups())) >= (6, 12), "Honk requires Linux >= 6.12")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("config", "source", "kernel", "manifest"))
    parser.add_argument("path", type=Path)
    parser.add_argument("--expanded", action="store_true",
                        help="Also check generated target architecture and kernel symbols")
    args = parser.parse_args()
    try:
        if args.kind == "config":
            check_config(args.path, args.expanded)
        else:
            require(not args.expanded, "--expanded is only valid for config checks")
            {"source": check_source, "kernel": check_kernel,
             "manifest": check_manifest}[args.kind](args.path)
    except (ValueError, OSError) as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        return 1
    print(f"Validated {args.kind}: {args.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
