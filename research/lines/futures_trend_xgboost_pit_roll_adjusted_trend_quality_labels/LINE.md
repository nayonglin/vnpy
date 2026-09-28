# PIT逐合约换月调整趋势质量标签线

- line_id：`futures_trend_xgboost_pit_roll_adjusted_trend_quality_labels`
- 创建时间：2026-09-05 02:52 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 资产/策略：商品期货趋势 / 线上逻辑回归主体与未来XGBoost一席挑战的独立标签研究线
- 当前状态：Stage003已完成无拟合证据恢复并明确效果失败；技术门全部通过，但全截面预测与A/C路径代理均为负，本标签/特征/XGBRanker/单槽selector形态关闭，不进入true engine。

## 核心假设

- 正式趋势策略的多空方向由每日均线、MACD、RSI及入场过滤器动态生成，不存在可合法冻结在月度查询日的单一方向。
- XGBoost不直接预测上涨，而预测未来20个交易日是否形成方向中性、幅度足够且路径回撤较小的趋势机会；正式策略继续独立决定多空方向。
- 每个收益leg只比较同一实际合约在相邻端点的close，换月处不比较旧合约与新合约价格，避免期限结构造成的伪收益。

## 冻结边界

- Stage001只生成和审计市场路径代理标签，不做XGBoost fit/predict、策略回测、true engine、holdout、CTP、订单或生产写入。
- 标签不是可成交PnL或账户回撤；低流动性路径不会因此被宣称可交易，后续selector和true-engine仍需独立成交资格门。
- Stage001通过只允许另立模型OOS预注册；失败则本线闭线，不改公式、20日窗口、样本或门槛救援。

## Stage001结果

- 决策：`stage001_roll_adjusted_trend_quality_labels_pass_allow_model_preregistration_only`。
- 56,272路径、1,046个qid、1,125,440个leg全部完成；qid宽度最小/中位/最大`49/53/61`。
- 逻辑close读取`2,250,880`次；跨合约价格比较`0`；27,970条路径包含换月。
- 每个qid目标唯一值至少49，五级relevance全部齐全；公式最大误差均为0。
- XGBoost fit/predict、策略回测、true engine、holdout、CTP、订单和生产写入均为0。

## Stage002/Stage003结果

- Stage002完成37折/74次固定浅树拟合，但因普通CSV末位浮点变化触发最终seal重放失败；失败bundle完整封存，不重跑。
- Stage003以`fit/load/predict=0/74/74`重建2,000条预测；原prediction/selection seal与lossless hex回读seal均为`37/37`，确认Stage002只是证据序列化技术失败。
- 全截面mean/median Rank IC为`-0.0232133/-0.0229765`，NDCG相对随机为`-0.0530824`；预测门除月份数外全部失败。
- C替换28月，但quality sum=`-0.5742274`、绝对趋势幅度sum=`-0.1511225`、路径回撤代理sum=`-0.4231049`，四个年度质量差均为负；效果门仅2项通过。
- Stage003决策：`stage003_lossless_evidence_recovery_effect_fail_stop_no_true_engine`；post-run独立复核P0/P1=`0/0`。
- 全程策略回测、sealed holdout、CTP、订单和生产写入均为0；没有收益或账户最大回撤结论。

## 当前下一步

- 本线关闭：禁止重跑、调参、改门、删月/年、符号反转、true-engine、holdout、shadow或正式接入。
- 继续总目标只能另立独立经济机制；优先勘察“当前可交易趋势方向下的未来净收益与下行风险”标签，并从无标签PIT覆盖合同重新开始。
