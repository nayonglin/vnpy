# Stage004 新冻结运行时与账户标签smoke结果

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 当前模式：研究隔离/最小真实账户标签smoke
- 记录时间：2026-09-02 16:25 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：新研究数据库身份冻结、旧账户回放引擎适配、4任务A/A smoke
- 是否重要突破：否；只通过标签生产技术门
- 是否触发A/B：是；固定4任务smoke已完成，仅授权Stage005预注册

## 外部调研与判断

- XGBoost官方Learning to Rank要求同月候选拥有同口径、可比较的标签和`qid`；本阶段只验证标签生产机制：<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>。
- XGBoost官方仓库同样把可靠标签和组身份视为排序训练前提：<https://github.com/dmlc/xgboost/blob/master/doc/tutorials/learning_to_rank.rst>。
- 我的判断：4任务结果证明真引擎可以在严格PIT资格路径上生成确定、可辨识的账户边际标签；它没有证明XGBoost能提高收益或降低回撤。独立reviewer给出`ALLOW_STAGE005_PREREG_ONLY`，所以不能直接把270任务当成已授权批次。

## 本次变更

- 新增脚本：`runtime_smoke.py`、`stage004_runtime_smoke.py`。
- 修改脚本：无生产或正式策略脚本修改。
- 删除脚本：无。
- 新增参数：运行时`/private/tmp/vnpy-stage004-curve-account-runtime`、并行数`2`、单任务超时`600s`、固定4任务smoke。
- 修改参数：无策略、资金、成本、滑点、保证金、整数手或持仓上限参数修改。
- 删除参数：无。
- 新增测试：`test_runtime_smoke.py`；整线测试当前`17 passed`。

## 冻结运行时

- 生产源库与APFS clone均为`112,267,264`字节，SHA256=`5845010108e73661557e723556520d7a3ea42dc6bca4bbe5d50ca3bd419d4cad`，inode不同。
- SQLite `integrity_check=ok`，`dbbardata=1,020,397`行，最大时间`2026-09-01 00:00:00`。
- `vt_setting.json`为无换行2字节`{}`，SHA256=`44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a`；没有复制生产设置或CTP凭据。
- runtime receipt SHA256=`5a0ec07374276e890815bbe3722f46524e4482fca54865e0d39f9f8945deae8b`；源库和clone在运行前后SHA不变。

## 尝试与隔离记录

- 首次prepare在策略运行前因`{}`与`{}\n`文字/字节合同不一致被拦截并自动清理；预注册在读取标签值前纠正为2字节`{}`。
- `campaign_20260902T152555+0800_50243`在策略运行前被QMT runtime guard拦截，已标记`ABANDONED/reuse_forbidden`。
- `campaign_20260902T152724+0800_51724`中`20220128_R10`完成，A2在共享`.vntrader/log`目录创建时竞态失败；campaign已写`failure_receipt/reuse_forbidden`，该单任务结果未被成功campaign复用。
- 成功campaign为`campaign_20260902T153215+0800_55582`，contract SHA256=`a4a5a4278bfdb4131a790fd80696e00d3aa8b760ea40b44732f8bf36007f3bac`；4个worker均重新冷启动完成。
- 标准`--smoke`父进程因未继承QMT override，在worker完成后验证失败；随后只在同一campaign、同字节runner和原始输出上补跑validator，没有重跑或复用worker。独立reviewer将其定级P2，并要求Stage005用新orchestrator修复及持久化恢复回执。

## 回测/归因参数

- 数据区间：每任务账户路径从`2018-01-01`到对应`next_eval_date`；标签只取目标月后的一个账户区间。
- 账户规模：正式15万元。
- 成本口径：沿用旧Stage015，不修改滑点、手续费、保证金、整数手或最多4持仓。
- 样本过滤：固定`20220128_R10`、`20220128_R10_A2`、`20220228_R10`、`20220228_R11`，无结果后换样本。
- 策略/归因口径：前两任务验证A/A；后两任务只替换20220228的rank10候选，固定`fu.SHFE` rank11不变。

## 结果

- 期末权益：不发布组合全周期值；这是4个互斥反事实smoke，不能拼成一条策略曲线。标签期末权益分别为`4,740,258.8/4,740,258.8/5,383,438.8/5,504,348.8`。
- 总收益：不适用；四个未来标签收益分别为`15.187100%/15.187100%/13.568457%/16.119162%`。
- 最大回撤：不适用组合全周期口径；四个未来标签回撤分别为`-8.402345%/-8.402345%/-15.433911%/-14.041408%`。
- Sharpe：不适用，标签合同不发布单月Sharpe。
- 总滑点：不得跨互斥任务聚合；四个标签分别为`11,160/11,160/28,220/31,640`。
- 总交易次数：不得跨互斥任务聚合；四个标签分别为`8/8/14/16`。
- 胜率：不适用，标签合同未发布胜率。
- 其他关键指标：4个PID/TMPDIR/MPLCONFIGDIR均唯一；最大wall=`59.294921208s`；checkpoint/result reuse均为false；归一化runtime SHA256=`61665d29c46e86755df4102bc67d7f516648082ca1d9bbe62ba56c6fef9316ed`。
- A/A八类输出逐字节一致；20220228五项决策前payload SHA逐项一致，边界均为`14行/14个非空signal`。
- 20220228 R11相对R10：未来净利润和期末权益`+120,910`、收益`+2.5507046pp`、最大回撤改善`+1.3925030pp`、滑点`+3,420`、交易`+2`。
- 16/16 smoke门通过；sealed holdout标签、模型训练、CTP连接和订单API调用均为0。

## 独立复核

- reviewer：`01a06122-2d19-78f2-9c36-5b61e9c0c165`。
- 结论：`ALLOW_STAGE005_PREREG_ONLY`，置信度96%。
- 严重度：`P0=0/P1=0/P2=2/P3=1`。
- P2要求：修父进程环境与恢复留痕；持久化可独立重算的predecision原始证据，并把holdout/model/CTP-order零计数变成显式证据。
- P3要求：Stage005明确先按`1e-6`货币量化再做`<=1e-9`reconciliation；原始JSON浮点直接相减最大残差`1.3969838619e-9`。

## 输出文件

- runtime receipt：`artifacts/stage004_runtime_smoke/runtime_snapshot_receipt.json`。
- latest：`artifacts/stage004_runtime_smoke/LATEST.json`。
- 成功receipt：`artifacts/stage004_runtime_smoke/campaigns/campaign_20260902T153215+0800_55582/smoke_receipt.json`，SHA256=`89af0420628167796921621b47f9d893e01f675df36111b61c17a42f482a0671`。
- progress：同campaign下`progress.json`，SHA256=`7fbfbf0670e426e877a984537391579470a882eafa9f620ed772662734003f8e`。
- 独立复核：`reviews/20260902_stage004_independent_review.md`。

## 结论

- 本阶段结论：`stage004_runtime_smoke_pass_allow_development_label_batch_preregistration`。
- 是否进入下一步：是，但只进入Stage005预注册，不直接运行development batch。
- 下一步：新增Stage005 orchestrator和证据合同，关闭P2/P3后重新独立预运行评审；只有评审放行才运行266个main开发标签任务。

## 过拟合反思

- 运行前判断：否，但旧Stage073使整体方向先验风险偏高。
- 运行后判断：本阶段否。
- 原因：任务、样本、运行时、A/A、边界、差异门和失败即停规则都在标签值前冻结；失败后未换任务、品种、月份或策略参数。R11优于R10只是可辨识性证据，不能拿来选模型。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但仅限Stage005预注册和治理缺口修复。
- 原因：技术正确性已建立，生产完整开发标签仍是验证“新全曲线信息+账户目标”是否有alpha的必要输入；在模型OOS前不能声称收益提高或回撤下降。

## 合入建议

- 是否更新本线`LINE.md`：是。
- 是否更新`research/registry.md`：是。
- 是否追加根目录`memory.md/back_log.md`：追加`back_log.md`；不追加`memory.md`，因为尚无效果突破或正式候选。
