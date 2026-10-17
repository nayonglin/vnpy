# Stage031：实际身份与完整账户 checkpoint 增量独立复审

- line_id：`futures_trend_triple_screen`；2026-10-18 03:11 CST；审查者：`ordered_execution_review_independent`。
- 来源 HEAD：`4d120ef42f018ed1b672e4fd67b60fec5adeb62f`；最终 runner SHA256：`3af932bdbde9ae607c507ff8630dde0a0b03f190ca88be94fa43ce5910b0b860`。
- 结论：本次限定增量范围内剩余 P0/P1/P2=`0/0/0`，允许使用 Stage031 启动**唯一一次明确计数的 C_TS attempt2**，A0 复用。不是 promotion、金融结果验收或总目标完成。
- 是否重要突破：否，仅导出/持久化边界修复；新增/修改/删除策略参数均 0，不改 alpha、冻结 q/S、AI、成本或持仓语义。

## 对旧审查遗漏的更正

本人 Stage028 前置独立复审的 `0 P1` 漏掉了两个真实缺陷：新增 runner 强制要求 synthetic usage 提供真实 producer 没有承诺的 signal 字段，以及后处理前没有完整账户 durable checkpoint。旧组合 fixture 仅检查初始成交 signal 字段与 usage 行数，没有把 synthetic usage 送过 runner 新 guard；静态审查也没有追到完整失败持久化边界。这是审查遗漏，不能用“有限 scope”抹去。旧收据及失败目录保留，本新收据不将旧结论当作修复证据。

## 合同与静态核查

已读取 03:02 修复合同、Stage031 源码/测试/实现收据，沿前次已读的 827 实际 synthetic producer 与 022 capture 接口核对增量。外部研究沿既有合同的 Backtrader/GitHub 语义，本次按 root 分工不新增联网；判断以真实 producer 和失败证据为准，不按收益选择规则。

实际 `TradeData` 的 `signal_datetime`、`signal_order_id`、`intraday_episode_id` 在对象消失前独立采集，缺失不会被伪造。clock/usage/actual 三表 trade_id 必须唯一且一一对应；actual 的合约、方向、offset、价格、数量和执行日期时间须与 capture 相等。普通 usage 缺身份仍拒绝；usage 已有身份与 actual 冲突仍拒绝。synthetic 缺 usage signal 字段可以通过，但必须由实际 OPEN 母成交证明同合约、交易日、时间先后和相同母信号身份，原 usage 的 episode link 也必须一致。导出使用 actual 显式字段，不使用 synthetic 自身订单号或执行时间替代 signal。

`capture_ordered_engine` 在真实 calculate 返回并恢复 physical trades 后采集实际身份，与 prior capture 组合保留完整 usage/trades/equity。`_run_live_c9` 完整返回后、所有原后处理 guard 前保存 combined、全部 frames、完整 capture、actual identities、ordered、settings、params、spec/preflight、输入指纹与 run context。raw 文件 flush/fsync、原子 rename、目录 fsync 后写 manifest；它只是 raw 证据。全日期、零吞错、分钟完整、实际参数、输入未变等验证之后才签 seal。

seal/load 绑定自有固定路径、schema/arm/attempt/run_id、writer 快照、context/manifest/raw SHA 与长度；拒绝 symlink、外部路径和无 seal。全部验证先于对已验证原 bytes 的反序列化。`--export-only` 在数据栈/特征/AI/model/引擎调用前走早分支；失败后使用新的 `export_NNN`，保留原错误，已有成功拒覆盖。允许 runtime/package bootstrap 与 metrics 模块 import，不重载市场数据或引擎回放。

两项历史独立 receipt 各只允许一根精确 anchor、零 full-session 权利：cu2609 与 OI009。`_read_delivery` 后必须实际等于各自预声明单 key；追加 key 不进入 inherited full predicate。没有重下或重新资格整个原始数据集。Stage032 对冻结 Stage029 的差异独立断言恰为四行：docstring 和三处 output/request/protocol 常量，原 provider 行为不变；本次不执行 provider。

## 独立运行证据

命令：`.py311/bin/python -m unittest discover -s research/lines/futures_trend_triple_screen/tools -p 'test_stage031_ordered_checkpoint.py' -v`。

最终退出码 **0**，三项新测试均通过，报告测试时间 `0.080s`（不含 runtime 导入）：

1. 实际 827 mother+synthetic emitter 产生缺 signal 字段的 usage，实际 TradeData 身份接入通过，原 producer usage 不变。
2. usage 身份冲突、缺实际母成交、错交易日、缺 actual 身份和早于母成交的时间被拒绝。
3. 精确 DataFrame dtype/float.hex checkpoint、无 seal 拒绝、metrics 阶段模拟失败后从同一 sealed raw 在新目录重导出、原错误保留/raw SHA 不变、外部路径/原 bytes 篡改在 pickle 前拒绝、已有成功拒覆盖。

对 runner/新测试/Stage032 做 stdlib `compile()`，退出码 0；provider 四增四删行断言退出码 0。本次没有重复 26 个旧测试、FI 全流、全 DB hash、旧数据资格或金融回放。

## 判断与限制

对该增量的实际 producer/consumer 与 checkpoint/export 边界置信度为高。小型 fixture 没有测试全周期 checkpoint 的体积/速度或机器断电；seal 是本地完整性/来源证据，不是独立经济审查。所有真实金融接受仍须完整 terminal exit、sealed raw/导出账本及新的独立经济复审。后续源码变化需要重新绑定，不能沿用本 SHA 结论。

本次金融回测次数 `0`，联网 `0`，模型训练 `0`，broker/真实委托/撤单 API 均 `0`，`production_qualified=false`。新增/修改/删除金融结果：无。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、母信号胜率均 **N/A**。

开始与结束过拟合判断均为**否**：未读取新收益，没有参数扫描或收益后规则选择；历史研究选择偏差仍存在。开始与结束继续价值均为**是**：旧失败不能从部分审计恢复，修复后一次明确计数的真实账户对照仍有必要；组件测试不是收益结论。

后续 TODO：root 按最终 SHA 归档修复并唯一启动 attempt2；原 preflight/数据门仍保留；金融完成或失败后由独立经济审查按实际完整证据处理。新审查收据：`outputs/stage031_independent_review/review_receipt.json`。
