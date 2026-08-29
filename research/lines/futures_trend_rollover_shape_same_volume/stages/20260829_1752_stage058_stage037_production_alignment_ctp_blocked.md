# Stage058：Stage037 生产身份对齐因正式 CTP 只读资格阻断

## 基本信息

- 研究线：`futures_trend_rollover_shape_same_volume`
- 记录时间：2026-08-29 17:52（Asia/Shanghai）
- 工作模式：日间研究模式（`work-type.txt=day`）
- 用户授权：同意先把稳定生产对齐到 Stage037 m0016，再运行 Stage056 Top14+fu 多周期
- 阶段性质：正式生产安装前置资格与身份治理；不新增 alpha、不运行回测

## 调研与判断

- 本阶段不新增策略资料调研。生产发布以仓库内 `freeze-official-strategy-materials`、`futures-live-execution-sop`、`futures-live-automation-startup`、远端 master、活动物料和私有生产收据为权威；网上或 GitHub 资料不能替代本机生产资格证据。
- 判断：不能把远端 master 已晋升等同于生产已安装。Stage948 准备前必须有精确提交上的独立生产审查、完整测试和两次正式 CTP 只读捕获。

## 身份预检

- 远端 `origin/master`：`a7d8599e9d895aa6fc7c73b25ef7f2e48d4e4c14`
- fresh clone：通过 `git clone --no-local` 获取并 detached 到上述精确提交；工作树干净，`git lfs fsck` 通过。
- fresh clone 活动物料：
  - strategy version：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
  - ruleset：`stage037_stage034_long_short_mirror_hard_block_v1`
  - source commit：`374df2d52e4f17220c5e2d4cae76f50d45bec47d`
  - material release：`m0016_20260829T034012+0800_374df2d52e4f`
  - release commit：`efef7217ee1b2194b064728257ff125035cec729`
  - manifest SHA256：`cc757212c8bef45617549630abf9b2dcf4f045bf8cb4af376cfd3e6a72da5cd4`
- 当前稳定生产 `/Users/bytedance/Desktop/person/vnpy_production_live`：
  - HEAD：`09aa96a03fb91124be90bd69861be3f834ab6299`
  - 活动物料：Stage021-Q m0015
  - 当前 7 个 production launchd label 均已加载，冲突为 0；旧生产健康证据截止 2026-08-28 为 healthy
  - 安装前保持不动

## 独立生产审查

- reviewer：`codex:/root/stage037_reviewer`
- 结论：PASS，`P0/P1=0/0`，`findings=[]`
- 聚焦安全回归：`96 passed, 40 subtests passed`
- 精确提交 tree fingerprint：`f80419c10c952aab402e05104f8296dfb9f81f3f0334ab61be1621995dbca4f7`
- raw review：`~/Library/Application Support/qmt-roll-stage179/production-live/stage037-promotion-20260829/raw-independent-production-review-a7d8599e.json`
- raw review SHA256：`ee46bef64be6f04a0cc8a5961679bb70e5ecbb813f0ab222eccbfb72d74c3649`
- review 文件为 canonical JSON、权限 `0600`；Stage048/049 硬失败和 operator override 保持原样，5 项 AI 资产 m0015→m0016 SHA 逐项不变。
- 边界：该审查仅允许进入资格 builder，不替代完整 37 套测试和两次正式 CTP 只读捕获。

## 正式运行时与只读资格

- Stage914 静态运行时预检：`production_readonly_preflight_passed`
  - 使用 `ctp_live.local.env`，权限 `0600`
  - 正式 `vnpy_ctp/api/libs` framework 优先
  - 静态预检未连接 CTP，订单 API `0/0/0`
- 第一次 Stage907 调用因 refresh env gate 与确认文本不匹配，在连接前 fail closed：`refresh_attempted=0`，订单 API `0/0/0`。该次不计资格捕获。
- 修正确认文本和 refresh env gate 后，执行一次真实正式只读探测：
  - source commit：`a7d8599e9d895aa6fc7c73b25ef7f2e48d4e4c14`
  - `refresh_attempted=1`
  - `readonly_status_after=readonly_logs_without_ctp_progress`
  - `broker_query_bundle.complete=false`
  - 账户、持仓、委托、成交查询均未形成完整快照
  - `send/cancel/order API=0/0/0`
- 结论：2026-08-29 周末时段无法取得正式资格要求的两次新鲜 CTP 只读捕获。没有构建可信 qualification bundle，没有执行 Stage948 prepare/activate。

## 生产与回测状态

- 稳定生产 HEAD：未修改，仍为 `09aa96a03fb91124be90bd69861be3f834ab6299`
- launchd：未重装、未 kickstart、未手工修改 plist
- CTP：只执行一次只读连接尝试；没有完整 broker 快照
- 发单/撤单/订单 API：`0/0/0`
- 多周期回测：未运行。正式 A 身份仍未与稳定生产一致，按多周期技能继续 fail closed
- 新增/修改/删除参数：无/无/无
- 新增/修改/删除回测结果：无/无/无
- 期末权益、收益、最大回撤、Sharpe、滑点、交易数、胜率：未运行
- 独立多周期 reviewer：未拉取；没有产生回测数据

## 过拟合与继续价值反思

- 开始前过拟合风险：中等，来自 Stage056 将 AI TopN 从 8 扩到 14 的离散选择；生产对齐治理本身不拟合参数。
- 结束后过拟合风险：未变化。本阶段没有运行回测或查看新增收益结果。
- 是否值得继续：是。只有稳定生产、远端 master 和活动物料成为同一身份，多周期 A 组才可信。
- 继续边界：在正式 CTP 可查询时段，对同一远端 master 精确提交重新构建两次只读资格；不得复用旧 m0015 捕获、不得绕过资格、不得扫描其他 TopN。

## 后续事项

1. 在下一个正式 CTP 可查询窗口，用相同 `a7d8599...` fresh clone 和正式 framework 运行可信资格 builder，取得两次完整只读捕获。
2. 资格全部通过后，仅用 Stage948 原子 prepare/activate 对齐生产，并核验 7/7 launchd、冲突 0、order/send/cancel `0/0/0`。
3. 生产六身份闭环后，重新执行 Stage056 固定全周期与 1/2/3 年、1 月/6 月冷启动多周期矩阵。
