# Stage237：正式矩阵夹具闭环

## 基本信息

- 时间：2026-09-08 21:54 CST
- 分支：`codex/live-broker-account-sizing`
- 起始提交：`57a6485af0ea4566171bc4aec0e26d049fa6acad`
- 是否重要突破版本：否；本阶段只修复 Stage236 安全协议升级后的测试夹具，不改变策略逻辑、风险参数或生产执行校验。
- 当前正式身份：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `stage037_stage034_long_short_mirror_hard_block_v1` / `ai_top10_plus_fu_official_live_v1`。

## 开始前反思

- 是否过拟合：否。问题来自测试夹具未同步新的持仓周期与状态代际字段，与历史收益或参数选择无关。
- 是否仍有价值继续：是。正式资格矩阵必须全绿，测试夹具也必须完整表达生产协议，不能靠放宽校验绕过。

## 本次改动

- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 普通全平夹具：补齐 `root_position_id`、`position_epoch_id`、`position_cycle_id`、`position_cycle_no`、`state_generation`，并同步到顶层意图、券商全平审计和订单请求。
- Stage905 夹具：把非法周期号断言移回普通全平测试，避免初始开仓测试引用不存在的全平审计变量。
- Stage931 授权夹具：把 `state_generation` 写入不可变订单 payload，使 payload 与 spool 行的状态代际一致。
- 生产代码：无改动；所有 fail-closed 校验保持不变。

## 验证

- 失败套件复验：`308 passed, 22 subtests passed`。
- 覆盖文件：`test_official_live_broker_position_ownership.py`、`test_stage931_trade_fill_accounting.py`、`test_stage931_broker_open_date_seal.py`。
- 更大正式矩阵：待本提交固化并生成新的不可变 release 后执行。

## 回测结果

- 本阶段未运行回测，因此不新增、不修改、不删除期末权益、总收益、最大回撤、Sharpe、滑点、交易次数和胜率记录。

## 结束后反思

- 是否过拟合：否。修复只对齐生产协议与测试证据，没有使用行情或绩效数据。
- 是否仍有价值继续：是。下一步发布新的不可变正式物料，完成独立复审、正式测试矩阵、两次只读 CTP 资格检查、master 晋升与 fresh clone 安装准备。

## 后续规划

- 提交 Stage237 测试夹具修复。
- 生成绑定新 source commit 的不可变 release，禁止修改既有 `m0006`。
- 完成正式 production qualification 与独立复审。
- 晋升并推送 `master`，在 fresh clone 中复验并准备 Stage948 安装包。
- 不代为激活可自动真实下单的 launchd 任务。
