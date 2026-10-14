# 给新电脑agent的提示词

请从`git@github.com:nayonglin/vnpy.git`的master根目录读取`VNPY_HANDOFF_README.md`和本提示词，完成正式期货策略跨电脑研究环境交接。

这是策略开发/回测迁移，不是接管实盘。你可以执行本地研究环境安装、资源恢复与离线验收；不得连接CTP、提交/撤销订单、发送SMTP邮件、安装launchd或迁移生产activation/私钥。不要通过修改策略、模型或数据让指标凑近基准。

按顺序执行：

1. 保留已有脏工作区，使用新目录或隔离worktree。取得master根目录所有`vnpy_handoff_20261014.zip.part*`、manifest和restore工具，运行工具还原到checkout外的新路径。核验全部分卷、完整ZIP SHA256和CRC后解压。Windows核对系统/解压工具长路径支持并使用短根目录，单设Git longpaths不足；不能跳过文件。
2. 读取包内`00_AGENT_HANDOFF.md`、`SOURCE_IDENTITY.json`、`01_DATA_AND_DOWNLOAD.md`、`03_SKILLS.md`、`04_CONFIGURATION.md`，执行包内verify_bundle逐文件校验。
3. 创建冻结源码HEAD `77538e394167c290d5f2923f4d08931b9bbd7c4f`的研究checkout与codex/开发分支。fetch并验证AI m0008 release commit `334d18f069de06df3aa7728203e942e3ecb94ce9`。master附件提交不是策略升级，不能用它替代冻结基准。
4. 用包内restore_resources先plan-only，再恢复资源。不要只克隆Git而漏掉隐藏SQLite及被忽略的backtest_outputs；冲突先检查，不自动覆盖。原始CSV、映射、分钟、元数据、模型/summary及两份AI参考源都应正确绑定。
5. 按锁文件重建Python3.11环境，使用包内vendor，设置Asia/Shanghai系统/进程时区。按配置说明安装空模板：离线回测无需账号；联网行情需用户在目标机本地配置。不要显示、读取回报或提交真实密码/授权码；缺字段只报名字。CTP/邮件保持禁用。
6. 运行check-only和2026-07-23至2026-10-13冻结窗口回测，按VALIDATION.md与validation原始输出逐项对比。完成后请一个独立agent审核数据、逻辑、结果和bug，按仓库AGENTS写中文stage；任何不一致先定位，不静默升级依赖或改策略。
7. 固定窗口通过后才继续按数据说明做行情增量/月更AI研究。无行情权限时报告阻塞但不要影响已可完成的离线验收；新AI候选不覆盖当前不可变m0008，不发布正式策略。
8. 最终向我报告包校验、实际Git/物料身份、环境版本、日线及分钟真实覆盖、资源hash、固定窗口逐项比较、独立review、已完成与尚未验证步骤。配置仅报字段是否就绪，不回显值。明确不涉及过拟合、此次工程交接的后续价值，并说明订单/CTP/邮件/生产调度均未执行。

不要要求先前两个旧ZIP：本版是一份合并后的完整交接包。只安装与当前研究任务相关的Skill，字节/抖音/飞书工作Skill不在本包中。
