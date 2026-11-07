# 空附件与固件补发修复计划

跟踪：[Issue #13](https://github.com/go-laoji/netcore-n60-pro-honk/issues/13)。分支：`feature/fix-release-republish`。

## 问题与边界

运行 `42335938771` 的构建和全部固件验收已成功，固件 artifact 为 `13562523668`。发布失败是空的 `custom-options.config` 上传返回 HTTP 400。来源运行的整体结论为 failure，现有补发入口又只接受整体 success。

本次只修复元数据附件和发布流程，复用该次已编译固件，不进行新的本地或云端固件编译。所有推送提交使用 `[skip ci]` 跳过 push 构建，再通过 `workflow_dispatch` 指定 `publish_run_id` 只补发。保留 Git Flow 功能分支，不自动 finish。

## 阶段

1. [x] 创建 Issue、功能分支并记录计划。
2. [x] 空配置记录改为说明注释；兼容历史空附件，先验证源校验和，再在发布副本补注释并重新生成附件校验和。保留原始校验记录，固件镜像不修改。
3. [x] 补发入口验证来源仓库/workflow、最新 attempt 的成功 build 和固件验收、未过期且匹配该次构建的 artifact；不要求发布/清理成功。
4. [x] 增加回归场景，执行本地静态及临时样例检查，更新文档并分阶段提交。
5. [x] 安全推送修复分支，仅触发补发并跟踪至完成；核对 Release、tag 指向、全部附件和固件 SHA256，回填 Issue 并关闭。

## 验证重点

- 新生成记录非空，空选项语义不变。
- 旧空记录只在发布副本中处理，源 artifact 和固件字节不变；发布附件全部非空，校验和完整覆盖；源文件被篡改或出现其它空附件时，在创建草稿前失败。
- build 成功而 publish/cleanup 失败可以补发；build 失败/跳过、验收未成功、来源不匹配、旧 attempt、过期/重复 artifact 被拒绝；支持分页。
- 实际补发的 build job 必须 skipped，不得执行源码准备、下载或 Compile firmware。

## 本地校验

新增 15 个发布与来源回归场景，连同原有检查共 64 个全部通过。覆盖旧空记录发布副本及源文件保留、固件字节不变、发布校验和完整覆盖、其它空附件/源校验和不符时提前拒绝，以及失败运行补发、验收失败、分页、过期/重复/旧 attempt、来源不匹配和解析期间重跑。

ShellCheck、actionlint（含 ShellCheck）、全部 Python 文件语法和 `git diff --check` 通过。对真实运行执行新的只读来源解析，已得到 artifact `13562523668`、attempt `1` 和构建提交 `9dc8577b2b9812b5e1b8bf9170e491303350fbdf`。

## 实际产物与云端补发

下载源固件 artifact 后，原始 ZIP 的 SHA256 与 Actions 记录的 `ede154973be8f931a51678938b3c3212e833290b1197e8412941bbce793004d6` 一致，16 个源附件全部通过校验。仅在发布副本中给零字节 `custom-options.config` 增加注释、更新发布校验和，并额外保存 `source-sha256sums.txt`，得到 17 个非空发布附件。

修复分支以带 `[skip ci]` 的提交推送，没有产生 push 构建。GitHub CLI 手动触发 `workflow_dispatch`，明确指定 `publish_run_id=42335938771`、`cleanup_only=false`。

- [补发运行 42346264689](https://github.com/go-laoji/netcore-n60-pro-honk/actions/runs/42346264689)：整体 success；`build` skipped，`publish` 和 `cleanup` success。
- 补发执行的修复提交为 `7c7169dbad16cf10b30037b9c7d3ab469491b54e`，读取来源 artifact `13562523668` 和 attempt `1`，未执行源码准备、依赖下载或固件编译。
- [公开 Release](https://github.com/go-laoji/netcore-n60-pro-honk/releases/tag/firmware-immortalwrt-25-12-snapshot-r0-3682a14-go-laoji-11-07-20261107-1416)：`ImmortalWrt 25.12-SNAPSHOT r0-3682a14 go-laoji-11/07 14:16`，北京时间 2026-11-07 14:16 发布。
- 17 个附件均为 uploaded、非零字节；通过 GitHub 记录的每个附件 SHA256 与本地实际产物预检副本逐项比对，名称、大小和摘要全部匹配。Release 正文记录来源构建、原配置提交及空记录兼容说明。
- 发布 tag 实际指向原固件构建提交 `9dc8577b2b9812b5e1b8bf9170e491303350fbdf`，没有指向修复分支提交。

两份镜像保持源固件字节不变：

| 镜像 | SHA256 |
| --- | --- |
| sysupgrade.itb | `c3d02452f2478281cee3ec1c55d7a2b9d0a86d7d57d98119d3ba5b90a1d29d36` |
| initramfs-recovery.itb | `6800e3a3abffd4309a41c5487523150680f91a83ed699b0ac1fcca8ac26772be` |

原 13:41 失败草稿保留，未覆盖历史 Release。修复与验证记录保留在 `feature/fix-release-republish`，未自动 finish。
