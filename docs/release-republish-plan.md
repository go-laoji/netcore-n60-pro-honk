# 空附件与固件补发修复计划

跟踪：[Issue #13](https://github.com/go-laoji/netcore-n60-pro-honk/issues/13)。分支：`feature/fix-release-republish`。

## 问题与边界

运行 `42335938771` 的构建和全部固件验收已成功，固件 artifact 为 `13562523668`。发布失败是空的 `custom-options.config` 上传返回 HTTP 400。来源运行的整体结论为 failure，现有补发入口又只接受整体 success。

本次只修复元数据附件和发布流程，复用该次已编译固件，不进行新的本地或云端固件编译。所有推送提交使用 `[skip ci]` 跳过 push 构建，再通过 `workflow_dispatch` 指定 `publish_run_id` 只补发。保留 Git Flow 功能分支，不自动 finish。

## 阶段

1. [x] 创建 Issue、功能分支并记录计划。
2. [ ] 空配置记录改为说明注释；兼容历史空附件，先验证源校验和，再在发布副本补注释并重新生成附件校验和。保留原始校验记录，固件镜像不修改。
3. [ ] 补发入口验证来源仓库/workflow、最新 attempt 的成功 build 和固件验收、未过期且匹配该次构建的 artifact；不要求发布/清理成功。
4. [ ] 增加回归场景，执行本地静态及临时样例检查，更新文档并分阶段提交。
5. [ ] 安全推送修复分支，仅触发补发并跟踪至完成；核对 Release、tag 指向、全部附件和固件 SHA256，回填 Issue 并关闭。

## 验证重点

- 新生成记录非空，空选项语义不变。
- 旧空记录只在发布副本中处理，源 artifact 和固件字节不变；发布附件全部非空，校验和完整覆盖；源文件被篡改或出现其它空附件时，在创建草稿前失败。
- build 成功而 publish/cleanup 失败可以补发；build 失败/跳过、验收未成功、来源不匹配、旧 attempt、过期/重复 artifact 被拒绝；支持分页。
- 实际补发的 build job 必须 skipped，不得执行源码准备、下载或 Compile firmware。
