# Stage236：真实账户普通全平授权链闭环

## 基本信息

- 时间：2026-09-08 20:42 CST
- 分支：`codex/live-broker-account-sizing`
- 起始提交：`4c27909a6ebb43b672625cda9159cc8a07054a8f`
- 是否重要突破版本：否；这是实盘安装前的执行安全补全，不改变策略 alpha、信号、止损阈值或重进场次数。
- 当前正式身份：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `stage037_stage034_long_short_mirror_hard_block_v1` / `ai_top10_plus_fu_official_live_v1`。

## 开始前反思

- 是否过拟合：否。改动针对真实券商账户手数、持仓归属和授权协议的一致性，不使用回测收益筛选参数。
- 是否仍有价值继续：是。普通全平此前缺少稳定 `intent_role` 和顶层持仓周期身份，无法通过 spool 与正式授权链，属于实盘部署硬阻断。

## 本次改动

- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 新增执行协议：普通 Stage901 全平使用唯一角色 `c9_full_position_close`。
- 真实持仓归属：所有非零券商全平数量都必须通过执行账本验证，不再只在券商手数与影子手数不一致时验证。
- 身份透传：归属验证返回并校验 `root_position_id`、`position_epoch_id`、`position_cycle_id`、`position_cycle_no`、`state_generation`；Stage905 将其写入普通全平顶层意图。
- 账户绑定：所有非零普通全平都绑定券商账户指纹，不再只绑定缩量全平。
- 授权范围：Stage930、正式授权记录和 Stage931 只把 `stage901_pending_order + c9_full_position_close` 识别为 `reduce_close_only`，不扩大开仓权限。
- 账本证据：Stage931 成交回调保留 `state_generation`，使后续全平归属可由已校验账本重建。

## 验证

- 定向单测：`15 passed, 245 deselected`。
- 普通全平授权 E2E：授权存在时从 spool 到 native 成交闭环；授权缺失和授权撤销均保持零 native 调用，`3 passed`。
- 相关启动、开仓封印与次日全平回归：`9 passed, 48 deselected`。
- 更大正式矩阵：待本提交固化后按发布 Skill 执行并回填。

## 回测结果

- 本阶段未运行回测，因此不新增、不修改、不删除期末权益、总收益、最大回撤、Sharpe、滑点、交易次数和胜率记录。

## 结束后反思

- 是否过拟合：否。修复的是跨 Stage905/930/931 的身份与授权不变量，测试同时覆盖成功和拒绝路径。
- 是否仍有价值继续：是。下一步应生成不可变正式物料、完成独立复审、正式测试矩阵和两次只读 CTP 资格检查；任何身份或券商只读门失败都保持 fail-closed。

## 后续规划

- 提交 Stage236 代码与测试。
- 生成绑定干净 source commit 的新不可变 release。
- 执行正式 production qualification、独立复审、master 晋升和 fresh clone 审计。
- 只准备 Stage948 安装包；不代为激活可自动真实下单的 launchd 任务。
