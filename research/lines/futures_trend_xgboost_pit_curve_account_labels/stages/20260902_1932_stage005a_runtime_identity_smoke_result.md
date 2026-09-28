# Stage005A v2运行身份与固定4任务smoke结果

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 当前模式：研究隔离/运行身份修复/固定账户标签smoke
- 记录时间：2026-09-02 19:32 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：冻结v2数据库与市场输入、修复父/worker环境、第三个且最后一个固定4任务新campaign
- 是否重要突破：否；只关闭标签批次前的运行身份门
- 是否触发A/B：是；只授权Stage005迁移到v2并重新做批量前独立评审，不授权270任务

## 外部调研与判断

- XGBoost官方Learning to Rank要求按`qid`把同月候选分组，并在组内比较样本；因此账户标签、月份边界和同月可比性必须先于模型训练成立：<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>。
- 官方源码文档说明`XGBRanker`默认目标为`rank:ndcg`，但本阶段没有选择排序目标、训练树或评估模型：<https://github.com/dmlc/xgboost/blob/master/doc/tutorials/learning_to_rank.rst>。
- 我的判断：本次成功只证明当前正式数据快照下，标签生产在固定4任务上可重复、可隔离、可辨识；不能据此声称XGBoost提高收益或降低回撤。

## 本次变更

- 新增运行快照：`/private/tmp/vnpy-stage005-curve-account-runtime-v2`。
- 新增冻结输入：生产数据库源、运行数据库、主力映射、全量分钟数据和合约元数据。
- 新增/修改编排：父入口安装QMT/MPL/TMP环境；worker保留父进程注入的job级环境，并在锁和策略运行前验证`TMP_ROOT/<campaign>/<job>/<run>/tmp|mplconfig`。
- 新增参数：v2运行根目录、固定4任务smoke；并行数、单任务超时和任务集合沿用事前合同。
- 修改参数：无策略、资金、滑点、手续费、保证金、整数手、最多4持仓、日期、品种或rank参数修改。
- 删除参数：无。
- 新增回测结果：第三个新campaign固定4任务完整通过。
- 修改回测结果：无；前两个失败campaign保持`ABANDONED/reuse_forbidden`，不复用任何输出。
- 删除回测结果：无。

## 冻结身份

- 正式checkout：HEAD `d492ee072aa5a9d71477235d79f17d2a5db59db3`，clean。
- 正式数据库与冻结源/运行库SHA256：`db3342006f4220767f06e466bb40c046f372961cea41cef9a6d8bc1727fa0c4b`；大小`112,271,360`字节；SQLite `integrity_check=ok`，`dbbardata=1,020,420`，最大时间`2026-09-02 00:00:00`。
- 主力映射SHA256：`093d3bc767c09d9e0e4f4fbeb9846a091bf25c163cc31eddfd382cc1ff5490b7`。
- 全量分钟数据SHA256：`8e861633b08a82819a668c30c6799e2098d2beaa6863698351145018ea586784`。
- 合约元数据SHA256：`24a3573e847e024411b13a3a3b775791ded57563b0a68b717d1065078201635a`。
- runtime receipt SHA256：`f67186f8e1603c81afeb5800e3e742287228862e61e984aac6c843a1a69bf0c2`。

## 尝试与隔离记录

- `campaign_20260902T183807+0800_62957`在worker前因父环境缺失失败；0 worker、0输出，已废弃。
- `campaign_20260902T185715+0800_65899`只完成`20220128_R10/R10_A2`，因旧wrapper把job级TMP/MPL覆盖为orchestrator路径而失败；已写failure receipt与`ABANDONED.json`，不允许复用。
- 修复后成功campaign：`campaign_20260902T192840+0800_77391`；4个worker均为新进程，PID/TMP/MPL `4/4/4`唯一，checkpoint/result reuse均为false。
- run authorization SHA256：`d6a77d27b470b47da78379f1758e74916e3026bd72c662a0840f608ec0158926`；只授权这一个最后的新campaign固定4任务。

## 回测参数

- 账户路径：每任务从`2018-01-01`运行到对应`next_eval_date`；标签只读取目标月后的账户区间。
- 账户规模：正式15万元。
- 任务：`20220128_R10`、`20220128_R10_A2`、`20220228_R10`、`20220228_R11`。
- 策略和成本：沿用正式账户回放合同；未改滑点、手续费、保证金、整数手或最多4持仓。
- 隔离：冻结研究数据库与市场输入、空`vt_setting.json`、无CTP凭据；未访问sealed holdout。

## 回测结果

- 四个互斥标签期末权益：`4,740,258.80 / 4,740,258.80 / 5,383,438.80 / 5,504,348.80`。
- 四个未来收益：`15.187100% / 15.187100% / 13.568457% / 16.119162%`。
- 四个未来最大回撤：`-8.402345% / -8.402345% / -15.433911% / -14.041408%`。
- 四个未来滑点：`11,160 / 11,160 / 28,220 / 31,640`。
- 四个未来交易次数：`8 / 8 / 14 / 16`。
- 标签Sharpe与胜率：合同不发布，故不适用。
- Prefix R10/A2至2022-02-28：期末权益`4,740,258.80`，总收益`3060.172533%`，最大回撤`-39.914746%`，Sharpe `2.065862`，总滑点`184,620`，总交易`408`，非零日胜率`55.948553%`。
- Prefix 202202 R10至2022-03-31：期末权益`5,383,438.80`，总收益`3488.959200%`，最大回撤`-39.914746%`，Sharpe `2.083312`，总滑点`212,840`，总交易`422`，非零日胜率`56.025039%`。
- Prefix 202202 R11至2022-03-31：期末权益`5,504,348.80`，总收益`3569.565867%`，最大回撤`-39.914746%`，Sharpe `2.095059`，总滑点`216,260`，总交易`424`，非零日胜率`56.006240%`。
- 互斥反事实不得聚合为一条全周期策略曲线；因此不发布组合期末权益、组合总收益、组合最大回撤、组合Sharpe、组合总滑点、组合总交易或组合胜率。
- 202202 R11相对R10：未来净利润和期末权益`+120,910`、未来收益`+2.5507046pp`、未来最大回撤改善`+1.3925030pp`、滑点`+3,420`、交易`+2`。这只证明标签可辨识。

## 技术门与独立复核

- smoke `16/16`门通过；receipt SHA256=`d373a16588f2a2ce4125982ebe5bcbaa21534b25ba02c935d9376b818ef2e053`。
- execution scope audit SHA256=`a9ffbb58520f94c0c2bbb6af530afa0fd4eb12530c90f60e0fa575d8833de3bc`；holdout/model/CTP/order/unexpected artifact/unexpected command计数全部为0。
- `20220128_R10/R10_A2`八类输出逐字节一致；202202同月决策前payload与边界门通过。
- 修复后的三个相关测试文件已有独立fresh证据：`30 passed`；runner、核心和测试`py_compile`通过。
- post-run reviewer结论：`allow_stage005_migration_to_v2_and_batch_prereview_only`，`P0/P1/P2/P3=0/0/0/0`。
- review SHA256=`a97e9ca9a65bac290192f89f0a08cce192e1af1eaef492d20798c08c8cfe8511`；decision SHA256=`631d5e8842362e421c08cd0e1209beadeaa1b7e9e69d4da5fa0161c3c290bcf8`。

## 结论与TODO

- 本阶段决策：`stage005a_runtime_identity_smoke_pass_allow_stage005_batch_rereview_only`。
- 是否进入下一步：是，但只允许Stage005 runner迁移并完整绑定v2冻结输入、成功smoke与post-run review。
- TODO：测试先行完成Stage005 v2迁移；fresh测试和静态身份通过后再拉独立批量前review；在新的结构化`ALLOW_STAGE005_BATCH`与run authorization出现前，不创建或运行270任务campaign。
- 不训练模型、不读取sealed holdout、不连接CTP、不调用订单API、不修改生产。

## 过拟合反思

- 运行前判断：否；任务、日期、rank、运行身份和失败即停规则均事前冻结。
- 运行后判断：本阶段否；修复只涉及运行身份与环境隔离，未换样本、未改策略、未调模型或阈值。
- 风险边界：不得因202202 R11更优而挑特征方向、模型参数或候选规则。

## 继续价值反思

- 运行前判断：是；当前数据身份下必须重新证明标签生产可行。
- 运行后判断：是，但仅限Stage005 v2迁移与批量前复审。
- 原因：标签生产技术门已关闭，266个开发标签仍是检验全曲线信息是否存在样本外账户价值的必要前置；当前没有任何XGBoost收益/回撤结论。

## 合入建议

- 更新本线`LINE.md`和`research/registry.md`。
- 追加根目录`back_log.md`，因为本阶段产生真实回测数据。
- 不追加根目录`memory.md`，因为尚无模型效果突破或正式候选。
