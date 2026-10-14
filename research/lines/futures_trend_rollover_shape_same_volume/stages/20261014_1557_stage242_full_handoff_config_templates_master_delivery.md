# Stage242 完整交接包配置补齐与master附件交付

- line_id：`futures_trend_rollover_shape_same_volume`
- 时间：`2026-10-14 15:57`（Asia/Shanghai）
- 性质：工程迁移与资料交付，不是新增策略研究/回测。
- 是否重要突破：否；A/B：不触发。

## 用户要求与调研判断

- 删除字节/抖音相关Skill，补齐截图中的配置说明和模板，将整个交接包提交至master根目录，并提供接收agent提示词。
- GitHub官方大文件说明：普通Git单文件上限100MiB；TqSDK官方认证说明：行情认证和交易账户配置分离。判断：不把390MB单ZIP直接推送，也不依赖尚未验明的LFS远端；以5个最大90,000,000字节分卷交付，标准库工具核验并重组完整ZIP。
- 配置缺口为安全模板和字段说明，不是把原生产密码/授权码/签名私钥放入仓库。只有用户在目标机本地配置的账户才能证明实际权限。
- 参考： https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github ， https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.auth.html ；字段事实以本机正式源码、vendor及SOP为准。

## 本次变化

- 将Stage240完整数据、源码、Skill与Stage241资源恢复工具合成一份完整包，不依赖旧两个ZIP。
- 删除40个字节/抖音/飞书工作Skill；保留仓库6个期货Skill及futures-official-shadow、tushare-data、pdf、playwright四个外部Skill，共10个。
- 新增6份安全配置模板：vt_setting JSON、CTP live/test/SimNow、官方SMTP邮件、研究路径env；新增字段与新机安装说明。
- 新增分卷还原工具、7项测试、根目录README与接收agent提示词；修改交接包的README/00_AGENT_HANDOFF/03_SKILLS。
- 策略参数新增/修改/删除：均无。冻结策略源码HEAD仍为`77538e394167c290d5f2923f4d08931b9bbd7c4f`，m0008 release commit仍为`334d18f069de06df3aa7728203e942e3ecb94ce9`。
- 未读取实际*.local.env、真实vt_setting、私钥或生产私有状态；未连接CTP、SMTP，未下载行情、下单、发邮件或改生产调度。

## 验证

- 最终ZIP：`outputs/stage242_master_handoff_final/vnpy_handoff_20261014.zip`。
- 大小：`390,993,344` bytes；`12,591`成员；`12,590` payload SHA256全部通过；CRC通过。
- ZIP SHA256：`64258daf5d955e0a2e256c094bf7a428a96260c8a1bad268636d9a90e977f9bb`。
- `10,876`恢复资源与原包hash全部一致，包括日线数据库、raw CSV、映射、模型、分钟缓存和AI物料/参考源；没有为迁移修改历史数据。
- 分卷5片，全部实物hash和manifest检查通过；还原完整ZIP与原成品SHA256一致，CRC通过。已有不同ZIP不覆盖、缺失/破损分卷与路径逃逸拒绝。
- 离线测试：新分卷7项、既有资源恢复7项、分钟采集fake API5项，共19项通过；不是全仓库策略测试或新回测。
- 独立agent审核最终ZIP：P0=0/P1=0，模板路径错误已修复进入最终ZIP；冻结源码1,142项Git blob完全匹配77538e，missing/different均0。
- 真实私有配置文件、私钥、生产状态不在包中；env敏感字段空白，CTP smoke=0，邮件enabled=0/dry_run=1。
- 当前主工作区.git/index hash保持`b0c0e6388963765f2b748e746af20d0760a6df90a5a4a17340a9158cecaf2476`；生产HEAD保持77538e。所有Git提交在新建的隔离交接worktree进行，不包含原工作区既有暂存改动。

## master交付方式

- 根目录附件：5个`vnpy_handoff_20261014.zip.partNNN`、`vnpy_handoff_20261014.manifest.json`、`vnpy_handoff_20261014_restore.py`、`VNPY_HANDOFF_README.md`、`VNPY_HANDOFF_AGENT_PROMPT.md`。
- 只以非强制fast-forward推送隔离提交至远端master；任何远端推进/拒绝必须先检查，禁止force。发布commit及远端核验结果以最终交付回复为准。
- 不切换/重置主checkout，不升级或激活production，不改LINE/registry/根memory/back_log。

## 结果字段与限制

- 本阶段无新增回测。期末权益、收益、回撤、Sharpe、滑点、交易次数、胜率：不适用；Stage240固定窗口仅是原机参考，不能宣称目标机复算完成。
- 日线至2026-10-13，分钟仍是Stage861选定日期补丁，不是同期全市场连续分钟；数据覆盖限制保留。
- 目标电脑安装、固定窗口回测、Tq权限、CTP和SMTP均未在本机证明。Windows包内最长相对路径266字符，需系统/解压工具长路径支持，Git longpaths单独不足；根目录提示词已提醒。
- TODO：接收agent按root提示词和包内说明完成数据恢复、重建Python3.11、离线复算及独立review，再开展增量与月更研究；不安装生产任务。

## 反思

- 运行前/后是否过拟合：否；未修改alpha、风险或样本，未根据收益挑版本。
- 运行前/后继续价值：有；消除配置合同和完整包分散的交接歧义，让新机研究可复验。
