# Stage050 Stage037 正式晋升与生产安装

- line_id：`futures_trend_rollover_shape_same_volume`
- 记录时间：2026-08-29 03:30 CST
- 阶段性质：正式版本晋升治理，不新增回测
- 是否重要突破：是，变更当前正式 alpha ruleset
- 用户授权：明确要求将 Stage037 晋升正式版，并确认按 `freeze-official-strategy-materials` Skill 完成 master 与生产闭环

## 外部调研与判断

- 本阶段不新增 alpha 研究；Stage047-049 已完成固定全周期、多周期与蒙特卡洛验证。发布治理以仓库 publisher、active material resolver、远端 master、Stage948 和生产私有回执为权威，不引入新的参数或外部策略资料。
- 我的判断：Stage037 不是自然门禁通过的候选。Stage048 决策为 `stage037_multicycle_has_hard_fail_keep_research`，Stage049 决策为 `stage049_mc_does_not_support_stable_stage037_path_advantage_keep_research`。本次晋升只能记录为用户明确承担稳健性风险的 operator override，不能改写历史结论。

## 正式规则合同

- 策略版本保持：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- 新规则集：`stage037_stage034_long_short_mirror_hard_block_v1`。
- 继承 C9/15w 执行栈、Stage021-Q 换月续开、量能风险缩放、ATR5 逆向冲击过滤、AI 池、资金口径、日内止损、broker 与订单闸门。
- Stage037 相对旧正式 Q 的差异严格为13项：新主力自身历史、换月延迟5交易日，以及多空初始入口的10日区间扩张+3日滞涨或有序峰谷4ATR镜像硬拦截。
- AI 决策资产保持 m0015 的5个文件字节不变；任何后续 AI 池变化必须生成新的不可变 material release，不能覆盖本次 release。

## 已有回测证据

- Stage047 Stage037：期末权益 `16,862,237.30`，总收益 `11141.4915%`，最大回撤 `-39.9147%`，Sharpe `1.539584`，总滑点 `1,671,655`，总交易 `734`，胜率 `53.1502%`。
- Stage048：多周期硬失败，保留原始 decision 和产物，不因人工晋升改成通过。
- Stage049：蒙特卡洛不支持稳定路径优势，保留原始 decision 和产物，不因人工晋升改成通过。

## 晋升执行状态

- 正式源码提交：待冻结；Stage027-049/正式规则联合回归 `83 passed, 14 subtests passed`，物料/manifest/identity/Stage948 联合回归 `58 passed, 3 subtests passed`，三项运行 Skill quick validator 全部 `Skill is valid!`。
- 独立评审：PASS，`P0/P1/P2/P3=0/0/0/1`，允许生成 source commit/material release；评审聚焦回归 `73 passed, 39 subtests passed`。唯一 P3 是过渡期 Skill 文案已写 Stage037、而 CURRENT/生产在安装前仍为 Q；Skill 本身要求以 CURRENT/稳定生产为权威且身份不一致 fail closed，因此不阻断，但闭环完成前不得声称 Stage037 已在线。
- material release/manifest：`m0016_20260829T034012+0800_374df2d52e4f`，244文件，release commit `efef7217ee1b2194b064728257ff125035cec729`，manifest SHA256 `cc757212c8bef45617549630abf9b2dcf4f045bf8cb4af376cfd3e6a72da5cd4`。
- 独立评审与资格：待完成。
- activation/CURRENT：分支内已激活，activation commit `a1aff7bf9f7d0d5c2b7e0b4e9d452a58f400c41b`；CURRENT 已解析 Stage037 ruleset 与来源提交 `374df2d52e4f17220c5e2d4cae76f50d45bec47d`。
- 远端 master：待完成。
- fresh clone：待完成。
- Stage948 生产安装：待完成。
- 六身份与 order/send/cancel：待完成。

## 过拟合反思

- 运行前判断：是。Stage037 来自连续后验研究，且多周期与蒙特卡洛稳健性门明确失败；人工晋升不能消除选择偏差。
- 晋升治理本身：否。规则字节已经冻结，本阶段不扫参数、不重跑相邻阈值，只做身份和生产闭环。

## 继续价值反思

- 运行前判断：是。用户已决定把 Stage037 作为新的正式基线，只有完成不可变物料、master、fresh clone 和生产六身份，后续“基于实盘优化”才不会继续误用 Q。
- 后续研究边界：不继续围绕已失败窗口、ATR倍数、回看期或方向补丁救参；只接受新的自然 forward 证据或结构不同的研究假设。
