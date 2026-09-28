# Stage005 development账户边际标签批次预注册

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 当前模式：研究隔离/完整development标签生产前合同
- 记录时间：2026-09-02 16:35 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage004治理缺口修复、270任务完整冷进程批次、266条主标签发布
- 是否重要突破：否；只有完整标签通过且后续OOS同时改善收益与回撤才可能成为突破
- 是否触发A/B：是；本阶段只生产训练标签，不训练模型、不做策略A/B/C

## 外部调研与判断

- XGBoost官方Learning to Rank要求同一`qid`组内标签可比较；本线把每个`eval_date`视为一个组，任何跨候选账户路径或决策前状态不一致都会破坏排序目标：<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>。
- XGBoost官方仓库的ranking实现依赖可靠标签和组身份；模型复杂度不能弥补标签生产偏差：<https://github.com/dmlc/xgboost/blob/master/doc/tutorials/learning_to_rank.rst>。
- 我的判断：Stage004只证明4个固定任务可用，Stage005的价值是一次性取得严格PIT、同账户口径的完整开发标签。不得在看到标签分布后删月、删候选、改特征符号或换标签定义。

## 冻结上游身份

- Stage003 jobs SHA256=`7ee2062e9700d1c1e8800f42ce8dd0ba75470e4953e30c099c37741aed39b8f3`；资格审计SHA256=`9bb8bbe8749b69f9436ef6bbb1a9665b7c58eb332859f1468b2eb0c2ffc642ed`；summary SHA256=`b44e21dc5070675b23c03a26973cc76f4ad8c93d79c6add7be4fd480cd945c0a`。
- Stage004 runner SHA256=`8c8de4037e4bc64096b88a87a1a76a18a17033f2a9b16ce6c3aa3238fb1bc819`；runtime core SHA256=`c651cac7d515189edbed22b107899fef5464e5179179320b341e0e1f12a055e4`。
- Stage004 runtime receipt SHA256=`5a0ec07374276e890815bbe3722f46524e4482fca54865e0d39f9f8945deae8b`；成功smoke receipt SHA256=`89af0420628167796921621b47f9d893e01f675df36111b61c17a42f482a0671`。
- Stage004结果记录SHA256=`59c561058bb50394204e3c5012e0259559ea1f4c09e7f6d382c9d468a2e36eeb`；独立review SHA256=`60a4741da6a87c18f4c92c2f8ca078c6d1c2c7e32bceedfd7f9c8649258f4a46`，结论必须保持`ALLOW_STAGE005_PREREG_ONLY`、`P0/P1=0/0`。
- 正式身份继续为production HEAD `d492ee072aa5a9d71477235d79f17d2a5db59db3`、release `m0005_20260901T165450+0800_1961d98ccb2b`、策略`ai_top10_plus_fu_official_live_v1`；生产checkout必须clean。
- 数据库继续使用Stage004冻结APFS clone；源库和clone SHA256均必须为`5845010108e73661557e723556520d7a3ea42dc6bca4bbe5d50ca3bd419d4cad`，空setting SHA256=`44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a`。

## 新orchestrator合同

- 新增独立`stage005_development_label_batch.py`，不得修改Stage004 runner字节；Stage005 manifest同时绑定新orchestrator、Stage004 worker runner、预注册、review、result、smoke receipt、运行时receipt、Stage003源和全部266资格文件。
- parent在prepare、run、resume、validate、aggregate每个入口都必须显式建立同一QMT override、独立`TMPDIR`和`MPLCONFIGDIR`；不得依赖上一进程遗留环境。
- 每次运行或恢复写唯一attempt start/end receipt，记录campaign identity、已完成数、待运行数、结果和错误；恢复只允许同一campaign且输入身份逐字节不变，所有已有job必须重新验SHA。禁止跨campaign复制worker输出。
- worker继续是独立冷进程；每个实际运行job的PID、TMPDIR、MPLCONFIGDIR必须唯一，`checkpoint_reused=false`、`completed_result_reused=false`。同campaign恢复时可跳过已完成且重新验真的job，但必须在attempt receipt中显式记录。
- 并行数固定`2`，单job超时`600s`；不得根据耗时或结果调整并行数、任务顺序、超时或样本。

## 决策前原始证据合同

- 每个开发月的main rank10 worker额外持久化`curve/trades/entry_candidates/entry_risk/trade_events`五类、截至`eval_date`的canonical CSV原始payload，共固定`35月 x 5 = 175`个文件。
- 每个原始文件独立重算SHA必须等于该月rank10 receipt中的`predecision_sha256`；同月全部main和A2 receipt的对应SHA必须等于该原始文件SHA。
- 原始payload只按月保留一份，避免为每个候选复制同一历史；缺月、缺文件、SHA不等或同月候选不一致均失败停止，不发布标签。

## 任务、隔离与显式零计数

- 重新冷跑Stage003冻结的全部`270`任务：`266 main + 4 A2`；不复用Stage004四个成功worker，也不引用两个失败campaign。
- 35个开发月和266个main必须完整；12个`sealed_account_label_holdout`月、108行特征不得生成job、worker、label或输出目录。
- 发布前生成`execution_scope_audit.json`，由jobs、输出目录、attempt命令账本、模型文件扫描、空setting和运行日志机械计算：holdout job/output/label=`0`，model train/fit command和模型产物=`0`，CTP connect命令/日志事件=`0`，send/cancel/order命令/日志事件=`0`。
- 这些零计数不得在validator中直接写死为true；任何非零均失败停止。

## 会计量化与硬门

- 金额reconciliation统一先把每个输入操作数按`Decimal(str(float(value))).quantize(Decimal('0.000001'))`量化，再做加减；量化后绝对误差必须`<=1e-9`。
- 收益、回撤和计数不套金额量化；交易数、目标curve/combined/trades必须逐项一致。
- 4个A2必须与同月rank10的`label/curve/combined/trades/entry_candidates/entry_risk/trade_events`七类文件逐字节一致。
- 270个worker receipt、固定输出SHA、campaign/execution identity、shared builder、目标边界、runtime和wall time全部通过；PID/TMP/MPL对实际运行worker唯一。
- campaign输入在prepare、每次resume和publish前后必须一致；源库、clone和生产checkout不变。
- 只有全部门通过才发布`development_labels.csv`的266行main标签、`reconciliation.csv`和证据manifest；不得发布A2为训练样本。

## 运行与决策边界

- 新runner、测试、预注册和冻结输入先由独立reviewer做预运行评审；只有`ALLOW_STAGE005_BATCH`且`P0=0/P1=0`才允许启动worker。
- 通过决策固定为`stage005_development_account_labels_complete_allow_stage006_training_preregistration`；失败固定为`stage005_development_label_contract_failed_stop_no_training`。
- Stage005通过只允许Stage006训练合同预注册，不授权训练、读取sealed holdout、策略全周期A/B/C、修改正式版、连接CTP或调用订单API。
- Stage005产生真实回测标签后必须写中文结果记录、追加根目录`back_log.md`并拉独立运行后reviewer。

## 回测/归因参数

- 数据区间：每任务从`2018-01-01`到其`next_eval_date`；标签只取`eval_date`后的目标账户区间。
- 账户规模：正式15万元。
- 成本口径：与Stage004/旧Stage015一致；滑点、手续费、保证金、整数手、相关性和最多4持仓均不修改。
- 样本过滤：无；开发35月/266 main全部保留。
- 策略/归因口径：当前严格PIT逻辑回归A路径为rank10基线，每个挑战者只替换目标月第10席，固定`fu.SHFE` rank11及历史/未来资格不变。

## 结果

- 期末权益：待运行；266个互斥反事实不得聚合为策略曲线。
- 总收益：待运行；不发布伪组合总收益。
- 最大回撤：待运行；不发布伪组合最大回撤。
- Sharpe：待运行；标签合同不生成组合Sharpe。
- 总滑点：待运行；不得跨互斥任务求和当作策略成本。
- 总交易次数：待运行；不得跨互斥任务求和当作策略交易数。
- 胜率：待运行；标签合同不发布组合胜率。
- 其他关键指标：270任务完成度、A2一致性、35月predecision原始证据、量化reconciliation、显式零计数和身份隔离。

## 过拟合反思

- 运行前判断：本阶段本身否，但整个XGBoost研究序列已有较高先验选择风险。
- 运行后判断：待运行。
- 原因：Stage005不设计模型、不看标签分布、不筛月份或候选；标签合同已经冻结。若运行后根据标签好坏删样本、改全曲线特征符号或换目标，就会构成明确过拟合。

## 继续价值反思

- 运行前判断：是，但只在预运行review放行后。
- 运行后判断：待运行。
- 原因：完整账户边际标签是验证新信息源能否提高全周期收益并降低回撤的必要条件；它本身不是alpha结论。

## 合入建议

- 是否更新本线`LINE.md`：Stage005出结果后更新；预注册阶段只在当前状态中注明等待预运行review。
- 是否更新`research/registry.md`：Stage005出结果后更新。
- 是否追加根目录`memory.md/back_log.md`：预注册不追加；真实标签批次出结果后追加`back_log.md`，只有正式候选或路线关闭才考虑`memory.md`。
