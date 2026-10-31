# N60 Pro Honk 固件配置计划

跟踪 Issue：[go-laoji/netcore-n60-pro-honk#1](https://github.com/go-laoji/netcore-n60-pro-honk/issues/1)。

## 范围与已确认决策

- 参考 [go-laoji/netcore-n60-pro](https://github.com/go-laoji/netcore-n60-pro) 的配置和 Actions 流程，当前仓库从空仓库独立整理。
- 原计划使用 padavanonly 6.6；核对发现 Honk 的 `honk/files/control.sh` 要求 Linux >= 6.12，用户已确认改用满足要求的新源码。
- 使用 ImmortalWrt `openwrt-25.12`，Linux 6.12、`mediatek/filogic`、`netcore_n60-pro`、`aarch64_cortex-a53`。按 Issue #5 的调整，固件源码每次构建跟随该分支最新提交，记录实际 SHA；Honk 和其他依赖 feeds 继续独立固定版本。
- 主代理集成 `kenzok8/openwrt-honk` 的 `honk` 和 `luci-app-honk`；Doona、中文翻译由上游 LuCI 包提供。按 Issue #8 增加默认关闭的 OpenClash 备用管理组件，其 Mihomo 内核由运行时下载。GeoIP/GeoSite 是必要数据包，不属于额外代理服务。
- 保留路由、无线、LuCI、UPnP、ttyd 等基本功能；移除旧仓库的其他源码分支、更新检查器、聚合代理 feed、Go 覆盖和 daed 链路。OpenClash 使用现有固定 LuCI feed，不恢复聚合 feed 或核心预装流程。
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

## 家庭网络和构建标识调整（Issue #3）

跟踪：[Issue #3](https://github.com/go-laoji/netcore-n60-pro-honk/issues/3)。

- TurboACC 的流量卸载/SFE 主要优化转发路径，不能视为 Honk 代理加速；硬件卸载可能绕过主机处理，当前组合没有兼容性和吞吐实测。保持不引入 TurboACC、SFE 或硬件卸载，不替换防火墙依赖。
- 明确选择 `miniupnpd-nftables`、UPnP LuCI 和中文包；新安装固件默认在 LAN 开启 UPnP/NAT-PMP，启用安全模式并保留上游高端口允许规则和默认拒绝规则。UPnP 用于家庭游戏/P2P 自动映射，不提高带宽，也不能消除运营商 CGNAT。
- Actions 配置展开前，以 `Asia/Shanghai` 的日期生成显示标识 `go-laoji-MM/DD`，追加到上游 revision；保持上游版本号和软件源地址。镜像文件名使用 `go-laoji-MM-DD`，禁止带斜杠的 revision 进入文件名。
- 在展开配置和实际 rootfs 版本文件中检查标识，并将版本记录随固件和日志上传。
- 本地只用临时样例验证日期边界、重复执行、配置保留、错误标识和 UPnP 设置，不执行 OpenWrt 配置展开或固件编译。

进度：

1. [x] 创建 Issue，核对上游版本替换、TurboACC 和 miniupnpd 的实际配置。
2. [x] 修改 UPnP、版本生成及 Actions/验收脚本，分步提交。
3. [x] 更新 README，完成静态验证、隐私检查，并在 Issue 中回复结果后关闭。

本次验证：ShellCheck、actionlint、Bash/sh 和 Python 语法、配置种子、`git diff --check` 均通过。18 个临时版本/manifest/UCI 场景通过，覆盖北京时间跨日、跨年、闰日、重复生成、上游版本和源地址保留、实际版本描述缺失/日期错误、文件名斜杠保护、UPnP 缺包/错误后端和 TurboACC/SFE 泄漏。受版本管理文件和 Git 文本对象隐私检查通过。未本地构建、未推送；首次 Actions 和实机 UPnP/Honk 验收仍待后续完成。

## Argon 和 quickstart（Issue #4）

跟踪：[Issue #4](https://github.com/go-laoji/netcore-n60-pro-honk/issues/4)。

- Argon 和 argon-config 使用已固定的官方 LuCI feed；增加中文配置页，并在最后执行的 UCI defaults 脚本中明确选择 `/luci-static/argon` 为默认主题。
- quickstart 使用 LinkEase 官方已发布包定义；固定 `nas-packages`、`nas-packages-luci` 和 `istoreos/istore` 提交，补齐 quickstart 后端、上游要求的 iStore/taskd 组件及 Lua 兼容支持。不使用开发中的 `istoreos/quickstart` 仓库，不增加代理服务。
- 配置展开和固件 manifest 必须包含请求的主题/应用及关键依赖；编译后核对 Argon 静态资源、quickstart 后端与默认主题脚本。
- 保持本地仅做静态及临时样例验证，不展开 OpenWrt 配置或构建固件。

进度：

1. [x] 创建 Issue，核对固定 LuCI feed、quickstart 正式包及依赖。
2. [x] 增加固定 feeds、软件包选项、默认主题和 Actions 验收，分步提交。
3. [x] 更新 README，完成静态与隐私检查，在 Issue 回填结果并关闭。

本次验证：ShellCheck、actionlint、Bash/sh/Python 语法、配置种子和 `git diff --check` 通过。16 个临时配置/manifest/UI/feed 场景通过，覆盖请求包缺失、Argon CSS/quickstart 后端/控制器/默认脚本缺失、后端不可执行、默认主题设置和七个 feeds 的完整提交固定。受版本管理文件和 Git 文本对象隐私检查通过。未本地构建或推送，实际界面和服务运行留待首次 Actions 及实机验证。

## 源码跟随分支（Issue #5）

跟踪：[Issue #5](https://github.com/go-laoji/netcore-n60-pro-honk/issues/5)。

- 删除 `FIRMWARE_COMMIT`，每次 Actions 运行时拉取 `openwrt-25.12` 分支最新提交；显式使用 `refs/heads/`，保留实际构建 SHA 记录和现有验收。
- 本次只调整固件源码获取策略。feeds 版本独立固定；上游更新后通过下次推送构建或手动 Actions 获取，不增加定时构建。
- 本地以临时 Git 仓库验证分支前进后能拉到新提交、同名 tag 不干扰、输入记录是实际 SHA。只验证 Git 拉取逻辑，不运行 OpenWrt 构建命令。

进度：

1. [x] 核对现有固定提交逻辑，创建 Issue。
2. [x] 修改源码拉取、当前文档和 Actions 描述，完成验证并提交。
3. [x] 在 Issue 中回复结果并关闭。

本次验证：5 个临时 Git 仓库场景通过，验证分支头初次获取、上游分支前进后获取新提交、同名 tag 和无关分支不干扰、无效/不存在分支失败退出，以及实际 SHA 记录。Bash 语法、ShellCheck、actionlint、配置种子、`git diff --check` 和隐私检查通过。未下载固件源码或依赖，未执行 OpenWrt 配置展开、固件编译或推送。

## 修复首次 CI 配置展开（Issue #6）

跟踪：[Issue #6](https://github.com/go-laoji/netcore-n60-pro-honk/issues/6)。诊断依据为 run `41165282876` 第 2 次尝试的 job `124431733917` 及其配置/日志 artifact。

- 全量注册 feeds 后，未使用的 `luci-app-weechat` 在 Kconfig 中出现自依赖；在配置展开前注销该可选包，并拒绝包含 Kconfig error 的 defconfig 日志。
- 保存的 `.config` 显示 `IMAGEOPT=n`，`VERSIONOPT` 及版本/镜像名被清除。配置种子和日期标识脚本显式启用 `IMAGEOPT`，保留现有版本验收。
- firewall4 的实际包定义强制依赖 `kmod-nft-offload`。保留模块作为依赖，继续由 UCI defaults 关闭软件/硬件 flow offloading，不再以模块存在判断加速已开启。
- iStore/quickstart 管理页被丢弃时，`tar` 和 `libuci-lua` 未选中；第一次修复验证后，新增包 Kconfig artifact 显示 GNU tar 默认 XZ 支持还要求具体虚拟包提供者 `xz-utils`。显式加入这些依赖，并通过展开配置继续验收管理页和后端。
- 日志 artifact 增加生成的包 Kconfig 和 packageinfo，支持诊断后续依赖问题；本地只检查脚本、日志样例和配置，不运行 OpenWrt 构建。
- 第二次修复配置已保留所有必需包，但校验器将未启用 PassWall 的 `INCLUDE_Haproxy` 默认子选项误当成软件包。展开配置的代理扫描改为依据 `tmp/.packageinfo`，实际代理包和编译后的 manifest 检查保留。

进度：

1. [x] 读取实际失败日志与配置，核对上游包定义，创建修复分支和 Issue。
2. [x] 修复配置、feeds 处理与诊断，补充聚焦回归检查并提交。
3. [x] 推送修复分支，通过 GitHub Actions 验证原失败阶段，回填 Issue 结果。

本地验证：6 个标准库回归测试通过，覆盖 Kconfig 自依赖报错后仍写配置、非致命 warning 放行、版本生成补齐 IMAGEOPT、iStore 的 GNU tar/XZ 提供者选项，以及特性开关与真实代理包的区分。配置种子、ShellCheck、actionlint 和 `git diff --check` 通过。原失败日志由新日志验收直接识别；使用第 2 次修复 CI 保存的真实 `.config`、版本 JSON 和 packageinfo，完整展开配置检查已通过。

远程验证：[run 41167469654 / job 124438032022](https://github.com/go-laoji/netcore-n60-pro-honk/actions/runs/41167469654/job/124438032022)，修复提交 `0920cc5`。源码准备、配置展开、完整编译和固件验收均已成功，已生成固件 artifact。修复位于 `feature/fix-ci-defconfig`，未自动 finish 合入 develop。本地未执行固件构建。

## 固件 Release 发布（Issue #7）

跟踪：[Issue #7](https://github.com/go-laoji/netcore-n60-pro-honk/issues/7)。已核实 run `41167469654` 编译和验收全部成功，存在已校验固件 artifact。

- 默认构建成功并上传 artifact 后，由独立发布 job 下载同次产物；只有发布 job 获得 `contents: write` 和跨运行读取产物所需的 `actions: read`。
- 发布名使用最终 `openwrt_release` 中的版本描述，加实际创建 Release 时的北京时间 `HH:MM`。时间在编译完成后的发布步骤中取得，不取构建开始或配置日期。
- Git tag 使用合法化的固件版本和发布年月日时分；现有 tag/Release 不覆盖。校验产物 SHA256，完整上传后公开发布。
- 手动运行允许填写已有成功的构建 run ID，仅补发 Release、跳过重新编译；校验源运行成功、workflow 来源及最新尝试的固件 artifact，并将 tag 指向实际构建提交。
- 本次使用已有成功 run 的固件验证发布，不在本地或远程重复编译；文档不包含本地用户目录路径，不自动 finish 分支。

进度：

1. [x] 创建 Issue，确认成功运行、现有产物和官方下载 action 接口。
2. [x] 实现版本/校验和驱动的发布脚本及聚焦测试。
3. [x] 接入独立发布 job、手动补发入口和使用说明，静态验证并推送。
4. [x] 用已有成功产物实测发布，记录 Release 链接后回填并关闭 Issue。

本次验证：5 个发布回归测试和原有 6 个 CI 配置测试全部通过，覆盖北京时间跨日、保留固件内编译日期、发布时间命名、产物被修改/缺失时拒绝发布、草稿完整上传后公开及上传失败不公开。配置种子、Python 语法、actionlint（含 ShellCheck）、受版本管理文件的隐私路径检查和 `git diff --check` 通过。

远程验证：[发布 run 41174550410](https://github.com/go-laoji/netcore-n60-pro-honk/actions/runs/41174550410)，提交 `d47c1e4`，`build` 跳过、`publish` 成功。来源为成功构建 `41167469654` 的 artifact `13032370350`，没有重新编译。公开的 [Release](https://github.com/go-laoji/netcore-n60-pro-honk/releases/tag/firmware-immortalwrt-25-12-snapshot-r0-3682a14-go-laoji-10-31-20261031-1356) 名称为 `ImmortalWrt 25.12-SNAPSHOT r0-3682a14 go-laoji-10/31 13:56`，于北京时间 2026-10-31 13:56 发布，14 个资产均为已上传状态，tag 指向原固件构建提交 `0920cc5fe3943efc2b1eb06896e7c9f4de66e7ff`。代码位于 `feature/firmware-release`，未自动 finish。

## OpenClash 备用代理（Issue #8）

跟踪：[Issue #8](https://github.com/go-laoji/netcore-n60-pro-honk/issues/8)。分支：`feature/openclash-backup`。

- 参考 [原仓库](https://github.com/go-laoji/netcore-n60-pro) 的 `padavanonly-immortalwrt-mt798x-6.6.config` 中选择 `luci-app-openclash`、排除 `mihomo` 的方式，仅增加备用管理组件。
- 当前固定 LuCI feed 已含 OpenClash `0.48.002`；其 [Makefile](https://github.com/immortalwrt/luci/blob/c84adb975e207ae8b14982191838ec6218d632cd/applications/luci-app-openclash/Makefile) 的 `Build/Compile` 为空，不构建代理内核，不需要新增 feed。Honk 源码、Linux 6.12 和现有 Release 流程保持当前方案。
- 选择 OpenClash 所需的 `dnsmasq-full`、Ruby/YAML、bash、unzip、TUN、inet-diag 和 nftables TProxy；显式关闭普通 `dnsmasq`，启用 `dnsmasq_full_nftset`，沿用 firewall4 后端。
- 最后执行的 UCI defaults 明确设置 `openclash.config.enable=0`、ARM64 下载架构。服务保持上游注册方式，以便用户在 LuCI 启用后可正常开机启动；未启用时由上游启动检查直接退出，不自动下载内核。
- 不选择或预下载 Clash/Mihomo 代理内核，保留上游的运行时下载机制。保留工作区默认脚本中已有的 `small_flash_memory=1` 设置，运行时将内核和相关数据放在 `/tmp/etc/openclash`；重启后需重新下载，不宣称离线冷启动可用。
- 配置和 manifest 验收只精确放行 `luci-app-openclash`；继续拒绝其他代理核心和应用。rootfs 验收增加管理组件、运行时下载脚本、默认关闭状态及未预装内核的检查。
- 文档说明先停止当前代理，再启用另一代理，不实现自动故障切换。本地仅静态及临时样例验证，不执行 OpenWrt 配置展开或固件编译，不自动 finish。

进度：

1. [x] 创建 Issue、功能分支，核对参考配置与当前固定 feed 的实际包定义和运行时下载行为。
2. [x] 增加备用应用及依赖、默认设置和构建验收，完成聚焦测试后提交。
3. [x] 更新说明，完成静态与隐私检查，回填并关闭 Issue。

本次验证：新增 9 个 OpenClash 聚焦测试与原有 11 个测试全部通过，覆盖仅允许精确的备用应用、继续拒绝其他代理和核心、要求 dnsmasq-full/nftset 并排除普通 dnsmasq、管理组件及下载脚本缺失/不可执行、出厂配置误启用、闪存/内存目录中的预装核心或归档，以及实际执行默认脚本得到关闭状态、ARM64 和小闪存设置。使用固定 feed 的真实 OpenClash 配置进行 rootfs 配置解析检查通过。Bash/sh、Python 语法、ShellCheck、actionlint、配置种子、隐私路径和 `git diff --check` 均通过。

本地未执行 OpenWrt 配置展开、源码/内核下载或固件编译；固定 feed 的软件包定义、配置和运行脚本仅作只读检查。功能分支 `feature/openclash-backup` 未自动 finish；完整编译和实机验证由后续 Actions 与设备验收完成。

远程验证：[run 41177219836](https://github.com/go-laoji/netcore-n60-pro-honk/actions/runs/41177219836)，功能提交 `2fc88b7`、说明提交 `e78bda0`。分支已推送，Actions 的配置输入校验和全部回归测试已通过；云端环境准备与后续构建仍在进行，尚未声称新固件编译或实际代理切换成功。
