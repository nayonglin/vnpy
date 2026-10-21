# Stage227：完整 action 固定 K 时钟支持工具实施（尚未 actual）

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-19 20:47 CST。不是重要突破版本；累计仍为 433 fit / 234 cash。
- 开始前已读 `research/registry.md`、本线 `LINE.md`、Stage226 协议及阶段记录、Stage129 状态/clock 写出逻辑、Stage156 纯日历 helper 与 Stage214 一次授权/stat 模式。该任务只实施既定 226 有界设计，无新增 alpha 假说；调研和判断承接 225/226 已核的原论文/作者 GitHub，未重复外网取数或扩大研究问题。
- 使用 brainstorming 的既定 bounded 设计衔接、TDD 和 verification-before-completion；root 明确授权自主实施且 226 已冻结设计，不另请求确认。

## 版本变更

- 新增工具 `tools/stage227_K_clock_support.py`，30 个 action metadata 列及 7 个 mother 身份列 allowlist，原数值 Y/X 一律不选取、不解析。源通过 156 `calendar_boundary` 原函数取得 K，日历门顺序固定 beforecalendar → D 哨兵 → aftercalendar 日期比较 → 严格 D<K；原 u 资格独立，不继承 score>0 门。
- 原始 30 列全部原样输出；path_state 保留原 label_state，timing_state 独立分为 13 类。原退出 τ==K 强制单列 `closed_on_K_priority_reprice`，不能复制旧 Y。unknown 首 clock 缺失保持 `unknown_unclassified`；aftercalendar K 不夹到末日。
- 只 nonparticipation/notready/intent 三类无需比较 K，保留同名 timing；closed/unknown/open 在 beforecalendar 归 `K_before_calendar_unavailable`。entry_execution_unknown 原状态仍在 path_state，时钟按 before/on/after/unclassified 分列。
- 一次 action 迭代、列式 mother 身份及 int32 child counts；不缓存 155 万 Python dict。calendar membership 预建 set；全母体和 nochild 保留，空母 anchor 是合法状态，只对非空母 anchor 核产品前缀。
- 输出完整 action/mother metadata 投影、all/2020onward 及固定 year/family/product 守恒分区、至多 16 个均匀原 sequence anchors、解释 gate、source_read_receipt、terminal 和 manifest。大原输入 SHA 继承 accepted129，只做前后 stat；所有源/协议/小依赖精确绑定。
- CLI 只允许精确 root source/input 授权及全新 `outputs/stage227_K_clock_support/actual_run1`；失败留 terminal，不自动重跑。既无 fit/cash，也没有模型、SQL、价格、cache、下载或新标签入口。

## 新参数及结果变更

- 新参数仅工具 CLI：`--actual`、`--authorization`、`--authorization-sha256`、`--output`，不是策略参数。修改/删除策略参数 0；新增/修改/删除回测结果 0。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均 N/A（没有回测或现金运行）。

## 四个 tiny fixture 及修正证据

- 初版仅接口 scaffold 时，四个既定测试方法先 RED，10 个预期行为断言失败，退出 1；随后实施时钟、日历门、完整母子/固定分区守恒和坏身份/坏时钟拒绝。
- 独立 228 预审发现合法 nochild 母 anchor 可为空。只把已有第 3 个 fixture 的 nochild anchor 改空，修前 RED：`mother_product_family_epoch_mismatch`，1 error，退出 1；随后仅修母前缀的非空条件，不增加测试方法。
- 最终 `.py311/bin/python -m unittest tools/test_stage227_K_clock_support.py`（完整绝对路径由 fixture terminal 保存）：4/4 GREEN，unittest 内耗时 0.006 秒，子进程实墙 0.295563500 秒，退出 0。旧 suite 0；fixture fit 0。
- 最终源码 29989B SHA `377f9e56e4881d89d7ee16f72d3d3f0abaa4e71635f0dd58cff195da65a692c1`；测试 7637B SHA `bcb0a95914fd0d87f2c4361ebe8d93652318f5252909fb9f8420cbe3898e2169`。纯 calendar 依赖 156 原 SHA 不变；完整精确源束见 `outputs/stage227_K_clock_support/source_bundle.json`，测试收据见 `author_fixture_terminal.json`。
- 作者未读 accepted 大 actions/mothers/calendar，未启动 actual；未改 LINE、registry、旧工具、其他研究线、生产或 Git。

## 判断和下一步

- 开始/结束反思：本步新增按收益调参的过拟合否，因为只处理 metadata，不看数值 Y，不训练、不回测；历史适应性择题风险是，当前盘点不能清除。继续此唯一有界支持检查有价值，因为它能以较低成本证伪对象差异是否有时钟支持；它不证明价格可用、Y_K 差异、成熟更早、可预测性或 alpha。
- 下一步由 228 完成独立固定规则/预审，由 root 精确授权并唯一运行 actual，再按 226 决策。作者不能启动或重跑 actual。任何身份/时钟/分区错误停止；潜在或未知支持不会自动授权 Y_K、模型、现金、正式生产或加注。


## Root 唯一 actual 完成快照（2026-10-19 20:51 CST）

- 上文“尚未 actual”为 20:47 实施冻结时的历史状态。此后 root 唯一启动 Stage227，exec session `1459`，终态 `completed / exit 0`，实耗 `95.312050208` 秒，没有自动重试。此追加仅新读小 summary/terminal/gate/manifest；作者没有读全投影，也没有重跑原数据。
- 已核小 manifest `10,299B` SHA `92000eb83e8c1bb9717f3b7f1701382849a4c17e49b7c67e04a5ed021a4ed098`。actions/mothers 各一次完成 stream，calendar 一次；数值 Y/X、价格/native cache、旧 score/selection、旧训练 cache、旧大输入 hash、SQL、下载、新标签、fit、cash 全部 0。累计仍为 `433 fit / 234 cash`。

| 固定范围 | 全 action | 全 mother | nochild mother | primary action | 潜在时钟/重定价支持 | 未决遮蔽 | 确定 K 前闭合/不参与 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 全期 | 1,552,456 | 399,252 | 186,400 | 706,910 | 14,254（2.0163812%） | 2,710 | 689,946 |
| 2020onward | 966,740 | 161,014 | 44,788 | 483,648 | 9,760（2.0179966%） | 2,545 | 471,343 |

- 全期 primary 的潜在支持 `14,254 = closed_after_K 11,607 + closed_on_K_priority_reprice 1,903 + unknown_after_K 682 + open_K_reached 62`，涉及 `13,044` 个母。2020onward 为 `9,760 = 7,771 + 1,298 + 629 + 62`，涉及 `8,701` 个母。子动作、母体及状态计数不可混作独立样本量。
- 2020onward 的未决遮蔽 `2,545 = unknown_before_K 1,695 + unknown_on_K 8 + intent_right_censored 348 + open_K_pending 494`；全期 `2,710 = 1,851 + 17 + 348 + 494`。两范围 unknown_unclassified 为 0；该事实仅描述现存 metadata，不提升未知路径、价格或首发 PIT 资格。
- 三分守恒：全期 `689,946 + 14,254 + 2,710 = 706,910`；2020onward `471,343 + 9,760 + 2,545 = 483,648`。calendar unknown u-eligible 为 0。raw 原始七类 label 状态完整保留，固定 year/family/product 输出未按结果挑选。
- 解释门状态 `potential_or_unresolved_support_only`：`all_primary_paths_resolved_before_K=false`、`no_effect_necessary_condition_met=false`。本次不能用“所有可行动路径都在 K 前结束”关闭目标时钟问题；接受范围仍仅是潜在/未知支持。它不表示 Y_K 与旧 Y 有数值差异，不表示收益反序、成熟更早、可预测、盈利或旧标签 bug。
- `automatic_Y_K_authorized=false`、`fit_authorized=false`、`cash_authorized=false`。新增/修改/删除金融回测结果仍为 0，期末权益/收益/回撤/Sharpe/滑点/交易次数/胜率仍 N/A；没有正式/生产/加注资格。
- 独立 Stage228 已由 root 唯一启动 session `84673`，本次追加时仍 live，仅登记 pending 历史快照；不能提前称独审接受。root Stage229 再作最终裁决，不由作者启动下一轮或重新运行本 probe。
- 结束反思：本次按数值 reward 追参的过拟合否（0 Y 数值、0 fit/cash），历史适应性择题风险仍是；重复此盘点无继续价值，一次盘点的必要条件价值已经实现。后续是否建设新标签只能由独立审查和新事前协议决定，不能由这约 2% 的潜在支持自动推出；完整全市场目标仍 active，未完成。
