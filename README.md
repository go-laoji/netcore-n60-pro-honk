# Netcore N60 Pro · ImmortalWrt + Honk

只为 **Netcore N60 Pro** 生成固件的配置仓库。代理服务只安装 [kenzok8/openwrt-honk](https://github.com/kenzok8/openwrt-honk)：Honk 核心、LuCI 管理页和 Doona 界面。固件编译在 GitHub Actions 的 Linux runner 上完成。

本仓库参考 [go-laoji/netcore-n60-pro](https://github.com/go-laoji/netcore-n60-pro) 项目的配置和 Actions 流程。原项目的 `padavanonly-immortalwrt-mt798x-6.6` 使用 Linux 6.6，而当前 Honk 的启动检查要求 **Linux >= 6.12**，因此经确认改用 **ImmortalWrt `openwrt-25.12` / Linux 6.12**。未修改 Honk 的内核版本检查。

## 设备和镜像布局

| 项目 | 本仓库配置 |
| --- | --- |
| 源码 | `immortalwrt/immortalwrt`，每次构建使用 `openwrt-25.12` 分支最新提交 |
| 内核 | Linux 6.12 |
| Target / Subtarget | `mediatek / filogic` |
| 设备 profile | `netcore_n60-pro`，不包含 N60 或 512M 闪存硬改版 |
| 软件包架构 | `aarch64_cortex-a53` |
| 无线 | 上游 mt76 / mt7915e，配置由官方设备 profile 提供 |
| 主镜像 | `*netcore_n60-pro*-sysupgrade.itb`，UBI/FIT |
| 恢复镜像 | 上游生成的 `*netcore_n60-pro*-recovery.itb` |

**镜像布局与旧 padavanonly 6.6 固件不同。** 旧源码的设备树启用了 NMBM，产物为 `sysupgrade.bin`；此处上游设备树使用原生 NAND 上的 UBI `fit` 卷和匹配的 U-Boot。虽然机型和芯片相同，两个镜像不能仅凭文件名互换。刷入前必须核对实际设备的 bootloader、NMBM 状态及分区布局，并按匹配的上游迁移路径处理。本仓库不提供自动刷写或引导迁移脚本，也不将 bootloader 二进制放入固件下载包。

设备支持依据：[分支上的 N60 Pro profile](https://github.com/immortalwrt/immortalwrt/blob/openwrt-25.12/target/linux/mediatek/image/filogic.mk)、[N60 Pro 设备树](https://github.com/immortalwrt/immortalwrt/blob/openwrt-25.12/target/linux/mediatek/dts/mt7986a-netcore-n60-pro.dts)、[内核版本](https://github.com/immortalwrt/immortalwrt/blob/openwrt-25.12/target/linux/mediatek/Makefile)。每次构建都会重新验证源码和目标；当前尚未进行实机验证。

## 安装内容

- `honk`、`luci-app-honk`；Doona 静态资源和中文翻译由上游 LuCI 包提供。
- `v2ray-geoip`、`v2ray-geosite`：Honk 路由所需的数据包，不包含 V2Ray/Xray 代理核心。
- Honk 所需的 BTF、cgroup BPF、BPF events、网络命名空间，以及 `kmod-sched-core`、`kmod-sched-bpf`、`kmod-veth`、`kmod-nft-queue`。
- 正常路由/防火墙/无线、中文 LuCI、默认 Argon 主题、argon-config、QuickStart、UPnP、ttyd、htop、nano、SFTP 等管理功能。设备驱动依赖由官方 profile 补全。

不引入 small-package 聚合源，不安装 dae/daed/daede、OpenClash/Mihomo、Nikki、HomeProxy/Sing-box、PassWall、SSR Plus、VSSR、Xray、V2Ray 核心或其他代理。也不集成 AdGuardHome、MosDNS、SmartDNS。源码 feeds 中未选中的软件包不会因此进入固件。

默认关闭 `bridger` 和 nft flow offload 模块；首次启动的 UCI defaults 脚本关闭防火墙软件/硬件 flow offloading，使流量经过透明代理路径。旧固件配置不应直接恢复到新布局和新网络驱动上。Honk 保持上游未初始化、未启用的默认状态，不内置订阅、节点、密码或 API 密钥。

### Argon 与 QuickStart

默认主题为 **Argon**，同时安装 `luci-app-argon-config` 及中文翻译。`zz-honk-ui` 在主题包默认脚本之后执行，明确将 `luci.main.mediaurlbase` 设置为 `/luci-static/argon`，因此首次启动会使用 Argon。

`luci-app-quickstart` 使用 LinkEase 官方正式包，并安装中文翻译、`quickstart` 后端和 `luci-compat`。按其上游依赖，同时安装 iStore、taskd、xterm 库，以及后端所需的磁盘/系统管理工具。Argon 和 argon-config 使用当前固定的官方 LuCI feed；QuickStart、其 LuCI 页面和 iStore 组件分别来自固定提交的 [nas-packages](https://github.com/linkease/nas-packages/tree/aeb8ca964e437c06c507a171d38e0c7927c2384d/network/services/quickstart)、[nas-packages-luci](https://github.com/linkease/nas-packages-luci/tree/2a71fe50f64f57b85c190d34d7ffc0244b4ca794/luci/luci-app-quickstart)、[istore](https://github.com/istoreos/istore/tree/a97ace34f2da358a015b094d326bba2697697f2e)。这些 feeds 中的其他应用不会因加入 feed 而自动进入固件。

Actions 除检查软件包清单外，还会检查实际 rootfs 的 Argon 静态资源、QuickStart 可执行后端、LuCI controller 和默认主题脚本，防止只选中界面却遗漏运行组件。

### TurboACC 与 UPnP

当前不集成 TurboACC。它提供的是 Flow Offload、SFE、Full Cone NAT、BBR 等功能集合，不能直接视为 Honk 代理性能增强。硬件卸载/SFE 可能绕开主机上的代理处理；软件 flow offload 与 TC/eBPF 不能一概认定冲突，但当前固件组合没有兼容性和吞吐实测，因此继续保持禁用，不替换防火墙相关依赖。参考 [TurboACC 功能与安装说明](https://github.com/chenmozhijin/turboacc/blob/luci/README_EN.md)、[Honk 的 TC/eBPF 路径说明](https://github.com/Glassyiris/honk/blob/aebc0d78d567cac1cd74ee9c56674857c5441451/README.md) 和 [Linux flowtable 机制](https://docs.kernel.org/networking/nf_flowtable.html)。

UPnP 对家庭游戏主机、联机游戏、P2P 应用自动创建端口映射有帮助，作用是连接可达性，不提高带宽。本配置明确选择 `miniupnpd-nftables`、LuCI 管理页和中文翻译，新安装固件默认在 **LAN** 启用 UPnP/NAT-PMP，开启 `secure_mode`，保留上游的高端口允许规则和最后的默认拒绝规则。可在 LuCI「服务 → UPnP」查看映射或关闭服务。上级路由/运营商 CGNAT 下，单独启用本机 UPnP 无法保证公网入站可达。设置依据：[固定版本的 miniupnpd 配置](https://github.com/immortalwrt/packages/blob/2dba1dd2af3b447faf52f85c0850a6f9667cac17/net/miniupnpd/files/upnpd.config)。

### 自定义版本标识

Actions 准备配置时按 **Asia/Shanghai** 时区记录当次构建日期，系统版本描述追加 `go-laoji-MM/DD`。例如 10 月 31 日构建时显示 `ImmortalWrt 25.12-SNAPSHOT <上游 revision> go-laoji-10/31`，可在 LuCI 系统概览、`ubus call system board` 或 `/etc/openwrt_release` 的 `DISTRIB_DESCRIPTION` 中查看。

上游发行版本、源码 revision 和软件源地址继续保留。镜像文件名使用无斜杠的 `go-laoji-10-31`，版本代码不进入文件名；产物同时保存 `firmware-version.json` 和实际 rootfs 的 `openwrt_release`。标识生成和实际固件描述都经过 Actions 验收，日期取当次准备构建配置的时间，不固定为本文日期。

## 文件

| 文件 | 用途 |
| --- | --- |
| `build.env` | 固件源码仓库和需要跟随的分支，不固定提交 |
| `feeds.conf.default` | 固定版本的 Honk、官方 packages/LuCI/routing、QuickStart 和 iStore 依赖 feeds |
| `immortalwrt-netcore-n60-pro-honk.config` | 唯一的设备及软件包配置种子 |
| `scripts/prepare-source.sh` | Actions Linux runner 中拉取分支最新源码、记录实际 SHA、验证版本、安装 feeds、复制配置 |
| `scripts/stamp-version.py` | 以北京时间生成固件显示标识及文件名标识，保留上游发行版本和软件源 |
| `scripts/validate.py` | 只读检查配置、设备源码、目标内核配置及固件 manifest |
| `files/etc/uci-defaults/99-honk-routing` | 首次启动关闭防火墙 flow offloading，并配置 LAN UPnP 安全模式 |
| `files/etc/uci-defaults/zz-honk-ui` | 在主题包默认脚本后将 Argon 设为默认皮肤 |
| `.github/workflows/build-honk.yml` | 唯一的固件构建流程 |
| `docs/implementation-plan.md` | 实施范围、验证边界与完成状态 |

## 触发 GitHub Actions

远程仓库：[go-laoji/netcore-n60-pro-honk](https://github.com/go-laoji/netcore-n60-pro-honk)。

1. 推送本仓库到 GitHub。向 `main`、`develop` 或 `feature/**` 分支推送构建配置、feeds、脚本、`files/` 或 workflow 的改动时，会自动构建。仅修改 README/计划文档不会触发昂贵的固件编译。
2. 打开 **Actions → N60 Pro - ImmortalWrt 6.12 + Honk** 查看进度。
3. 手动重建可用 **Run workflow**。GitHub 要求 workflow 文件先存在于默认分支，按钮才会出现；首次推送功能分支时可先通过 `push` 事件构建。
4. 同一分支的新构建会取消该分支尚未完成的旧构建。不同分支互不影响。

功能通过 Git Flow 合入 `develop` 后，推送该分支即可触发构建：

```sh
git push -u origin develop
```

工作流只需默认的 `GITHUB_TOKEN` 只读仓库权限，无需添加 PAT、第三方上传 token 或订阅密钥；产物通过 Actions Artifacts 下载，不自动创建 Release，不清理历史 Release 或运行记录。

## 构建流程和产物

流程：静态检查 → 安装 Linux 构建依赖 → 拉取 `openwrt-25.12` 最新源码及固定版本 feeds → `make defconfig` → 检查配置 → `make download` → 编译 → 检查实际内核配置和软件包 manifest → 上传固件。

配置检查会确认只有 N60 Pro、Honk 和必需依赖均被选中、架构正确、Linux 6.12/BTF 未被配置展开丢弃，且无其他代理或 flow offload。编译后的检查还会验证实际内核的 BPF syscall/JIT、BTF、TC ingress/cls_bpf、veth、nft queue 和网络命名空间。多线程编译失败时，Actions 会用单线程 `V=s` 重试并保留日志。

成功后，在该次运行的 **Artifacts** 下载：

- `netcore-n60-pro-honk-go-laoji-MM-DD-<run_id>-<attempt>`：已通过检查的 N60 Pro 主镜像、可用的恢复镜像、manifest、镜像元数据、构建版本信息、展开配置、内核配置、版本标识记录、实际 rootfs 的版本文件、输入提交记录和 `sha256sums`。默认保存 30 天。
- `honk-build-logs-<run_id>-<attempt>`：准备/下载/编译日志、配置和输入记录。失败时也尝试上传已产生的诊断文件，默认保存 14 天。

本地没有执行配置展开、工具链构建或固件编译；编译是否成功由首次 Actions 运行验证，刷机和 Honk 实际路由行为仍需在布局匹配的设备上验收。

## Honk 首次使用

在设备满足镜像布局并正常启动后：

1. 登录 LuCI，进入 **服务 → Honk**。
2. 按上游管理页完成管理员初始化，填入节点/订阅并保存。
3. 运行系统检查，确认 Linux >= 6.12、`/sys/kernel/btf/vmlinux`、bpffs 和所需模块正常，再启用服务。
4. API 就绪后，从管理页打开 Doona。检查客户端代理路由、直连路由和 DNS 的实际行为。

管理入口和 API 应只用于可信 LAN。详情见 [Honk 固定版本的使用说明](https://github.com/kenzok8/openwrt-honk/blob/e1a68ffcced979a2b2c659010a22cd0281482947/README.md)。

## 更新版本与本地检查

`build.env` 只配置固件源码仓库及 `FIRMWARE_BRANCH=openwrt-25.12`，不配置固定 SHA。每次 Actions 运行时都会获取该分支当时的最新提交，并将实际 SHA 写入 `build-inputs.txt`，随固件和日志保存。上游有更新后，手动运行 Actions 或按上文推送构建配置即可使用新代码；上游提交本身不会自动触发本仓库构建。

`feeds.conf.default` 中的 Honk、官方软件包/LuCI/routing 和 QuickStart 依赖仍独立固定完整提交。更新依赖版本时复核内核、设备 profile、镜像布局、包依赖、Honk 核心/Doona 归档及校验值，再触发新构建。

Honk 的 [包定义](https://github.com/kenzok8/openwrt-honk/blob/e1a68ffcced979a2b2c659010a22cd0281482947/honk/Makefile) 会下载上游固定版本、带 SHA256 校验的 aarch64 核心；[LuCI 包](https://github.com/kenzok8/openwrt-honk/blob/e1a68ffcced979a2b2c659010a22cd0281482947/luci-app-honk/Makefile) 同样下载固定 Doona 归档。固件构建无需另行维护 Rust/Zig/Node 编译链，也不会在路由器启动后下载核心。

以下命令只做本地只读检查，不展开 OpenWrt 配置，也不构建固件：

```sh
bash -n scripts/prepare-source.sh
sh -n files/etc/uci-defaults/99-honk-routing
sh -n files/etc/uci-defaults/zz-honk-ui
python3 scripts/validate.py config immortalwrt-netcore-n60-pro-honk.config
git diff --check
```

如果本机已有 ShellCheck/actionlint，还可运行：

```sh
shellcheck -x -P SCRIPTDIR scripts/prepare-source.sh
shellcheck -s sh files/etc/uci-defaults/99-honk-routing
shellcheck -s sh files/etc/uci-defaults/zz-honk-ui
actionlint .github/workflows/build-honk.yml
```

开发跟踪：[Issue #1](https://github.com/go-laoji/netcore-n60-pro-honk/issues/1)、[家庭网络和版本标识 Issue #3](https://github.com/go-laoji/netcore-n60-pro-honk/issues/3)、[Argon 和 QuickStart Issue #4](https://github.com/go-laoji/netcore-n60-pro-honk/issues/4)、[源码跟随分支 Issue #5](https://github.com/go-laoji/netcore-n60-pro-honk/issues/5)。

## 许可与致谢

本配置仓库沿用 [P3TERX/Actions-OpenWrt](https://github.com/P3TERX/Actions-OpenWrt) 的 MIT 许可，参见 `LICENSE`。ImmortalWrt、Honk 核心、Doona 及各软件包保留各自的许可证和声明；Honk/Doona 的许可文件由上游包安装到 `/usr/share/licenses/`。
