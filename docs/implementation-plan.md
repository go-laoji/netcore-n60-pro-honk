# N60 Pro Honk 固件配置计划

跟踪 Issue：[go-laoji/netcore-n60-pro-honk#1](https://github.com/go-laoji/netcore-n60-pro-honk/issues/1)。

## 范围与已确认决策

- 参考 [go-laoji/netcore-n60-pro](https://github.com/go-laoji/netcore-n60-pro) 的配置和 Actions 流程，当前仓库从空仓库独立整理。
- 原计划使用 padavanonly 6.6；核对发现 Honk 的 `honk/files/control.sh` 要求 Linux >= 6.12，用户已确认改用满足要求的新源码。
- 使用 ImmortalWrt `openwrt-25.12`，Linux 6.12、`mediatek/filogic`、`netcore_n60-pro`、`aarch64_cortex-a53`。源码和 Honk 均固定完整提交，避免分支更新改变首次构建输入。
- 代理仅集成 `kenzok8/openwrt-honk` 的 `honk` 和 `luci-app-honk`；Doona、中文翻译由上游 LuCI 包提供。GeoIP/GeoSite 是必要数据包，不属于额外代理服务。
- 保留路由、无线、LuCI、UPnP、ttyd 等基本功能；移除旧仓库的其他源码分支、更新检查器、聚合代理 feed、Go 覆盖、daed 和 OpenClash 链路。
- 新源码是 UBI/FIT 布局，旧 padavanonly 设备树使用 NMBM；新产物不能作为旧 `sysupgrade.bin` 的直接替代。提供构建配置，不操作设备或引导程序。
- 本地只进行静态校验和临时目录下的脚本检查；`make defconfig`、下载、编译、固件验收只在 GitHub Actions 运行。

## 交付步骤

1. [x] 检查仓库、Git Flow、参考配置和上游包定义，确认内核及设备支持。
2. [x] 创建 GitHub Issue，记录本计划并提交。
3. [x] 增加单设备 `.config`、固定源码版本配置、源码准备和配置/manifest 验收脚本。
4. [x] 增加单一 Actions：推送/手动触发、依赖安装、准备源码、配置展开、下载、编译、验收和产物上传。
5. [x] 编写中文 README，说明服务范围、运行初始化、构建触发、产物和引导布局限制。
6. [x] 本地静态验证，小步提交；在 Issue 中回复结果并关闭。不推送，不执行 `git flow feature finish`。

## 验证边界

- 本地：Bash 语法、ShellCheck、Actions 语法（actionlint）、配置重复项/目标/Honk/eBPF 依赖检查；用临时样例检查脚本拒绝代理泄漏与错误设备。
- Actions：`make defconfig` 后验证目标与必需配置未丢失；验证内核 >= 6.12；编译完成后验证 N60 Pro manifest 含 Honk 及必要数据、无其他代理。
- 实机：后续核对设备的 bootloader/分区布局，采用匹配的迁移路径；在 LuCI 中初始化并验证 Honk 的 BTF/模块/代理路由。当前不声称已完成实机或固件编译验证。

## 本次验证结果（2026-10-31）

- Bash/sh 语法检查通过；ShellCheck 0.11.0 检查源码准备脚本、UCI defaults 脚本及 workflow 内嵌 shell 通过。
- actionlint 1.7.12 检查唯一 workflow 通过，配置种子检查通过。
- 临时样例的 16 个配置/manifest/内核场景通过：覆盖重复配置、错选或多选设备、缺失 Honk/BTF、模块形式的额外代理、错误架构、旧内核、加速器泄漏和 libubox ABI 后缀。
- 读取固定提交 `3682a14dd5ec6382af65d7e72b5b415b5f3173a8` 的 MediaTek Makefile、N60 Pro profile 和设备树，在临时目录执行源码只读检查通过。
- 核实 Honk 固定提交 `e1a68ffcced979a2b2c659010a22cd0281482947` 的核心和 Doona 归档均出现在其 `source-41012758310` Release 中。下载与散列核验留给 Actions。
- 本地未执行 `make defconfig`、`make download`、工具链/固件编译，也未触发远程 Actions。首次 CI 编译及实机验证尚待后续完成。
