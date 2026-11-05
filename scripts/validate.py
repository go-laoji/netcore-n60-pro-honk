#!/usr/bin/env python3
"""Read-only checks for the N60 Pro Honk configuration and CI build output."""

import argparse
from datetime import date
import json
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
    "luci-theme-argon", "luci-app-argon-config", "luci-i18n-argon-config-zh-cn",
    "luci-app-quickstart", "luci-i18n-quickstart-zh-cn", "quickstart", "luci-compat",
    "luci-app-store", "luci-lib-taskd", "luci-lib-xterm", "taskd", "tar", "xz-utils", "libuci-lua",
    "kmod-nft-offload",
    "luci-app-openclash", "dnsmasq-full", "bash", "ruby", "ruby-yaml", "unzip",
    "kmod-inet-diag", "kmod-nft-tproxy", "kmod-tun",
)
EXCLUDED_PACKAGES = (
    "bridger", "luci-app-turboacc", "luci-app-turboacc-mtk", "luci-app-weechat",
    "kmod-shortcut-fe", "kmod-shortcut-fe-cm", "kmod-shortcut-fe-drv",
    "kmod-fast-classifier", "miniupnpd-iptables", "dnsmasq",
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
    "CONFIG_IMAGEOPT": "y",
    "CONFIG_VERSIONOPT": "y",
    "CONFIG_VERSION_CODE_FILENAMES": "n",
    "CONFIG_PACKAGE_dnsmasq_full_nftset": "y",
    **{f"CONFIG_PACKAGE_{name}": "n" for name in EXCLUDED_PACKAGES},
    **{f"CONFIG_PACKAGE_{name}": "y" for name in REQUIRED_PACKAGES},
}
# Only this exact OpenClash package is allowed as a backup; its core is excluded.
ALLOWED_PROXY_PACKAGES = {"honk", "luci-app-honk", "luci-app-openclash"}
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


def read_version(path):
    info = json.loads(path.read_text())
    build_day = date.fromisoformat(info["build_date"])
    require(info["timezone"] == "Asia/Shanghai", "Unexpected build timezone")
    require(info["display_label"] == f"go-laoji-{build_day:%m/%d}",
            "Incorrect display date label")
    require(info["filename_tag"] == f"go-laoji-{build_day:%m-%d}",
            "Incorrect image filename tag")
    require(re.fullmatch(r"[A-Za-z0-9._+-]+", info["source_revision"]),
            "Unexpected source revision format")
    require(info["version_code"] == f"{info['source_revision']} {info['display_label']}",
            "Custom label must be appended to the source revision")
    return info


def check_proxy_packages(config, package_names=None):
    for key, value in config.items():
        if key.startswith("CONFIG_PACKAGE_") and value in ("y", "m"):
            name = key.removeprefix("CONFIG_PACKAGE_")
            # Kconfig also uses PACKAGE_* for feature toggles such as
            # luci-app-passwall_INCLUDE_Haproxy, even when the app is disabled.
            if package_names is not None and name not in package_names:
                continue
            require(name in ALLOWED_PROXY_PACKAGES or not OTHER_PROXY.match(name),
                    f"Unexpected proxy package: {name}={value}")


def check_config(path, expanded, version_file=None, package_info=None):
    config = read_config(path)
    for key, expected in REQUIRED_CONFIG.items():
        require(config.get(key, "n") == expected, f"Expected {key}={expected}")
    devices = [key for key, value in config.items()
               if re.fullmatch(r"CONFIG_TARGET_.*_DEVICE_.*", key) and value == "y"]
    require(devices == [DEVICE], f"Expected only N60 Pro; selected devices: {devices}")
    package_names = None
    if package_info is not None:
        package_names = set(re.findall(r"^Package: (\S+)$", package_info.read_text(), re.M))
        require(package_names, "Package metadata is empty")
    check_proxy_packages(config, package_names)
    if expanded:
        require(config.get("CONFIG_TARGET_ARCH_PACKAGES") == '"aarch64_cortex-a53"',
                "Unexpected target package architecture")
        require(config.get("CONFIG_LINUX_6_12") == "y", "Expected Linux 6.12 target")
        require(version_file is not None, "Expanded config check needs --version-file")
        require(package_info is not None, "Expanded config check needs --package-info")
    if version_file is not None:
        info = read_version(version_file)
        require(config.get("CONFIG_VERSION_CODE") == json.dumps(info["version_code"]),
                "Firmware version code was lost during config expansion")
        require(config.get("CONFIG_EXTRA_IMAGE_NAME") == json.dumps(info["filename_tag"]),
                "Image filename tag was lost during config expansion")


def check_source(path):
    target = (path / "target/linux/mediatek/Makefile").read_text()
    version = re.search(r"^KERNEL_PATCHVER\s*:?=\s*(\d+)\.(\d+)\s*$", target, re.M)
    require(version is not None, "Cannot determine target kernel version")
    require(tuple(map(int, version.groups())) == (6, 12),
            "Expected Linux 6.12 on the openwrt-25.12 branch")
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
    modules = ("NET_SCH_INGRESS", "NET_CLS_BPF", "VETH", "NFT_QUEUE",
               "INET_DIAG", "NFT_TPROXY", "TUN")
    for name in built_in:
        require(config.get(f"CONFIG_{name}") == "y", f"Kernel requires CONFIG_{name}=y")
    for name in modules:
        require(config.get(f"CONFIG_{name}") in ("y", "m"),
                f"Kernel requires CONFIG_{name}=y/m")


def read_manifest(path):
    packages = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if parts:
            name = parts[0]
            require(name not in packages, f"Duplicate package in firmware manifest: {name}")
            packages[name] = parts[2] if len(parts) == 3 and parts[1] == "-" else ""
    return packages


def check_manifest(path):
    packages = read_manifest(path)
    for name in REQUIRED_PACKAGES:
        present = name in packages
        if name == "libubox":
            present = present or any(re.fullmatch(r"libubox\d+", pkg) for pkg in packages)
        require(present, f"Firmware is missing package: {name}")
    for name in packages:
        require(name in ALLOWED_PROXY_PACKAGES or not OTHER_PROXY.match(name),
                f"Firmware contains another proxy: {name}")
    for name in EXCLUDED_PACKAGES:
        require(name not in packages, f"Firmware contains an excluded package: {name}")
    version = re.match(r"(\d+)\.(\d+)", packages.get("kernel", ""))
    require(version is not None, "Firmware kernel version is missing")
    require(tuple(map(int, version.groups())) >= (6, 12), "Honk requires Linux >= 6.12")


def check_release(path, version_file):
    require(version_file is not None, "Release check needs --version-file")
    info = read_version(version_file)
    fields = dict(re.findall(r"^([A-Z_]+)='([^']*)'$", path.read_text(), re.M))
    require(fields.get("DISTRIB_ID") == "ImmortalWrt", "Unexpected distribution name")
    require(fields.get("DISTRIB_TARGET") == "mediatek/filogic", "Unexpected release target")
    require(fields.get("DISTRIB_ARCH") == "aarch64_cortex-a53", "Unexpected release architecture")
    require(fields.get("DISTRIB_REVISION") == info["source_revision"],
            "Upstream source revision changed")
    require(fields.get("DISTRIB_DESCRIPTION", "").endswith(" " + info["version_code"]),
            "Custom version label is missing from the built firmware description")
    require(re.fullmatch(r"25\.12(?:\.[0-9]+)?(?:-SNAPSHOT)?", fields.get("DISTRIB_RELEASE", "")),
            "Expected upstream release number without custom date suffix")


def check_ui(path):
    assets = path / "www/luci-static/argon"
    require(assets.is_dir() and any(assets.rglob("*.css")), "Argon theme assets are missing")
    backend = path / "usr/sbin/quickstart"
    require(backend.is_file() and backend.stat().st_mode & 0o111,
            "Quickstart executable backend is missing")
    require((path / "usr/lib/lua/luci/controller/quickstart.lua").is_file(),
            "Quickstart LuCI controller is missing")
    require((path / "etc/uci-defaults/zz-honk-ui").is_file(),
            "Default Argon theme setup is missing")
    check_openclash(path)


def check_openclash(path):
    for name in ("usr/lib/lua/luci/controller/openclash.lua",
                 "usr/lib/lua/luci/model/cbi/openclash/settings.lua"):
        require((path / name).is_file(), f"OpenClash management component is missing: {name}")
    for name in ("etc/init.d/openclash", "usr/share/openclash/openclash_core.sh",
                 "etc/uci-defaults/zz-openclash-backup"):
        script = path / name
        require(script.is_file() and script.stat().st_mode & 0o111,
                f"OpenClash runtime script is missing or not executable: {name}")
    config = (path / "etc/config/openclash").read_text()
    section = re.search(r"^config openclash 'config'\s*\n(.*?)(?=^config |\Z)",
                        config, re.M | re.S)
    require(section is not None, "OpenClash default configuration is missing")
    options = dict(re.findall(r"^\s*option (\w+) '([^']*)'\s*$", section[1], re.M))
    require(options.get("enable") == "0", "OpenClash must be disabled by default")
    for name in ("etc/openclash/core", "tmp/etc/openclash/core"):
        core = path / name
        require(not core.is_symlink() and (not core.exists() or
                (core.is_dir() and not any(core.iterdir()))),
                "OpenClash core must be downloaded at runtime, not bundled")
    for name in ("etc/openclash/clash", "usr/bin/clash", "usr/bin/clash_meta", "usr/bin/mihomo"):
        core = path / name
        require(not core.exists() and not core.is_symlink(),
                f"Unexpected bundled proxy core: {name}")


def check_defconfig_log(path):
    # Some Kconfig diagnostics still leave make defconfig with exit status 0.
    errors = [line for line in path.read_text().splitlines()
              if "recursive dependency detected" in line.lower()
              or re.search(r"(?:^|:\d+:)\s*(?:fatal\s+)?error:", line, re.I)]
    require(not errors, "Kconfig reported errors:\n" + "\n".join(errors[:10]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("config", "source", "kernel", "manifest", "release", "ui", "defconfig-log"))
    parser.add_argument("path", type=Path)
    parser.add_argument("--expanded", action="store_true",
                        help="Also check generated target architecture and kernel symbols")
    parser.add_argument("--version-file", type=Path,
                        help="firmware-version.json generated during source preparation")
    parser.add_argument("--package-info", type=Path,
                        help="tmp/.packageinfo lists real packages, excluding Kconfig feature toggles")
    args = parser.parse_args()
    try:
        if args.kind == "config":
            check_config(args.path, args.expanded, args.version_file, args.package_info)
        elif args.kind == "release":
            require(not args.expanded, "--expanded is only valid for config checks")
            require(args.package_info is None, "--package-info is only valid for config checks")
            check_release(args.path, args.version_file)
        else:
            require(not args.expanded, "--expanded is only valid for config checks")
            require(args.version_file is None, "--version-file needs config or release")
            require(args.package_info is None, "--package-info is only valid for config checks")
            {"source": check_source, "kernel": check_kernel,
             "manifest": check_manifest, "ui": check_ui,
             "defconfig-log": check_defconfig_log}[args.kind](args.path)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        return 1
    print(f"Validated {args.kind}: {args.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
