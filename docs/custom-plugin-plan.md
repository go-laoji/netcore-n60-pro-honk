# 自定义插件入口实施计划

跟踪：[Issue #12](https://github.com/go-laoji/netcore-n60-pro-honk/issues/12)。分支：`feature/custom-plugin-config`。

## 范围与约定

- 保持当前 ImmortalWrt `openwrt-25.12` 单源及现有镜像、默认插件和发布流程。
- 参考本地 `netcore-n60-pro` 的 feeds 配置与 `diy-part1.sh` / `diy-part2.sh`，不克隆参考仓库。
- 新增 `custom.config`，通过配置片段选择插件；新增 `feeds.conf.custom`，追加插件源码 feed，默认均为空示例。
- 在 feeds 更新前和安装后执行两个 DIY 脚本。脚本在 OpenWrt 源码根目录执行，可通过 `PROJECT_DIR` 访问配置仓库。
- 合并配置时消除覆盖产生的重复选项；记录用户要求的选项，在云端 `make defconfig` 后确认它们未被丢弃，实际固件 manifest 检查新增的内置软件包。
- 沿用现有 Honk、设备、内核、代理及卸载约束；自定义入口用于增加插件，不改变已有固件的基本契约。
- 所有新增入口都纳入 Actions 的路径触发及输入检查；配置和 feed 的实际输入随日志/固件留存。
- 本地仅运行 CI、脚本、配置和临时样例校验。不运行 OpenWrt 配置展开、依赖下载、工具链或固件编译；不推送、不触发云端构建、不自动 finish。

## 阶段

1. [x] 核对当前脚本及本地参考流程，创建 Issue 和 Git Flow 分支。
2. [x] 增加默认空入口、配置/feeds 合并和校验工具、聚焦回归场景，验证并提交。
3. [x] 接入源码准备和 CI，在编译前后校验自定义配置与包，保存输入记录。
4. [x] 更新快速使用说明和本地检查命令，完成静态校验，分阶段提交，在 Issue 回填并关闭。

## 验收场景

- 空自定义输入保持现有配置和 feeds；已有 feed 中的插件只需增加一行 `CONFIG_PACKAGE_xxx=y`。
- 额外 feed 使用明确分支、唯一名称，保留 Honk feed 的现有优先级，并记录实际提交。
- DIY 两阶段的工作目录、执行顺序、失败中止与 `.config` 覆盖顺序正确。
- 无效或重复选项、重复 feed、缺少分支、配置展开丢失自定义选项、最终镜像缺少新增内置插件时明确失败。
- 已有配置、OpenClash、Release 和运行清理的回归检查继续通过。

## 完成与验证记录

2026-11-07 完成。本次新加的 17 个回归场景与原有 32 个检查共 49 个，全部通过。覆盖空输入不改变配置/feeds、去重覆盖、DIY 后的配置优先级、无效配置、重复 feed/非法分支、配置展开丢失、最终镜像缺包、ABI 软件包名称和模块/特性开关的区分。

准备流程测试只使用临时的极小源码样例和 `git` / feeds 命令替身，没有下载源码或执行 OpenWrt 构建。验证了两个 DIY 脚本的工作目录、环境、先后顺序、失败中止、最终 feed SHA/仓库校验，以及最后一行没有换行符的 feed 仍被记录。

额外在临时项目中填写 `CONFIG_PACKAGE_tcpdump=y` 和一个额外 feed，运行完整 `scripts/check-config.sh`，49 个场景仍全部通过。临时项目的两个真实 DIY 入口设置为 `exit 99`，确认本地检查不执行用户的 DIY 内容。

ShellCheck 0.11.0、actionlint 1.7.11（含 ShellCheck）、所有 Python 文件语法及 `git diff --check` 通过。新增文档/入口未包含本地用户目录。与 `develop` 比较，`build.env`、基础配置种子、内置 feeds、默认 UCI 脚本、版本生成、发布脚本及原有验收器保持一致。

实现分阶段提交在本地 `feature/custom-plugin-config`；未推送、未自动 finish、未触发远程 CI。本地没有运行真实 OpenWrt `make defconfig`、依赖下载或固件编译；新增插件的实际编译及运行兼容性由后续 Actions 和设备使用验证。
