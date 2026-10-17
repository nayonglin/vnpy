# Stage267 pairwise19 接入依赖独立只读审查

时间：2026-10-17 19:48 CST。line_id：futures_trend_rollover_shape_same_volume。开始前已重读 research/registry.md，范围仅当前仓库默认 pairwise v2 原19列，不变更正式入口、模型、清洗库或单位合同。开始过拟合判断：否，查数据依赖与时钟，无收益反馈；继续价值：是，避免把无关的openOI缺项错当模型阻塞，同时阻止用回退填造数据。

## 结论

**原19特征不需要真实openOI。clean的OHLC、单边volume、真实同日close_oi，配合候选上下文，足以在不填造OI的前提下计算原19列。旧通用函数不能原样当作严格clean适配器。** 它机械读取open_oi、在空文件回退中用前closeOI构造openOI，并对未成熟滚动值填0；这些不是模型19列的必要语义。

实际默认模型是 StandardScaler + LogisticRegression，model_tag为`selection_pairwise_v2_risk_weighted`。不是根据文件名猜19列：本轮用pickletools只读解析物理joblib的字符串/opcode，取得其中`feature_names_in_`的19个有序名字，与summary的model_metadata.feature_columns完全相等，未joblib.load/pickle.load、未执行模型反序列化、预测或训练。

- 模型2865字节，SHA `ba982708a476be74e30ed966883d1eae8ef52010bf8df3763a83d6fc5c719d66`。
- summary SHA `c399a5787577c1cb55276766ed28b0cad8385c063de5b492076dfa8e0619ee86`。
- compact JSON `stage267_pairwise_dependency_review.json` SHA `53da06a66527a835dcb51b37f2c48a727cc93abfbdaa4aede6a2bcc8a724aed7`；包含完整19列、依赖矩阵、代码/模型SHA和P1位置。

网上核对了scikit-learn官方StandardScaler文档与官方GitHub实现，其`feature_names_in_`表示拟合时见过的字段名；本报告最终模型身份依据本地物理产物和实际调用，不拿其他框架文档套用。[官方文档](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html)、[官方源码](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/preprocessing/_data.py)

## 19列的真实依赖

列顺序就是物理模型和summary的顺序。表中“至少原始bar数”指非退化、分母非零、没有缺日时滚动值首次有限的最低量，不保证达到数量就一定成熟。

| 模型输入 | 真实依赖 | 至少原始bar数 |
|---|---|---:|
| feature_pair_same_direction | 候选direction | 0 |
| feature_pair_same_signal | 候选signal | 0 |
| feature_pair_same_risk_mode | 候选risk_mode | 0 |
| delta_risk_ratio | 候选风险比例 | 0 |
| delta_remaining_position_slots | 候选可用仓位槽 | 0 |
| delta_feature_ret_signed_5d | close、direction | 6 |
| delta_feature_trend_ma20_gap_pct | close | 20 |
| delta_feature_atr14_pct_zscore_120 | high、low、close | 133 |
| delta_feature_lower_wick_pct | open、low、close | 1 |
| delta_feature_volume_ratio_2v2 | volume | 4 |
| delta_feature_margin_per_contract_to_equity | 候选每手保证金、权益 | 0 |
| delta_feature_oi_delta_1d_pct | close_oi | 2 |
| delta_feature_oi_delta_1d_pct_zscore_120 | close_oi | 121 |
| delta_feature_close_position_60d | high、low、close | 60 |
| delta_feature_ret_20d_zscore_120 | close | 140 |
| delta_feature_range_pct_zscore_120 | high、low、close | 120 |
| delta_feature_trend_ma20_gap_pct_cs_rank_centered_1d | close、同日候选截面 | 20 |
| delta_feature_ma20_ma40_gap_pct_cs_zscore_1d | close、同日候选截面 | 40 |
| delta_feature_close_position_60d_cs_zscore_1d | high、low、close、同日候选截面 | 60 |

直接证据：`build_qmt_roll_ai_position_training_samples.extract_market_features`第182行用close_oi.diff(1)/close_oi.shift(1).abs()，第260、262行输出两个实际OI特征。open_oi仅在164、196行被读取，并在256行输出`feature_open_oi`；该列不在19列中，也不被任何上述列间接引用。`build_pair_row`第171–174行只取两个closeOI变化特征；v2第32–37、61–72行新增四列亦无openOI。

因此不需要把RQ缺失openOI填成0、前收、ffill或别的代理。适配器应直接构造模型实际需要的列；如果沿用宽函数接口，也必须保留openOI缺失状态且丢弃不被模型使用的装饰列，不能把其_safe_float产出的0当作真实观测。clean不包含候选direction/signal/risk_mode、账户风险比例/槽位/保证金权益及候选全集，这些必须由真实候选事件提供，不能用行情文件臆造。

## 三项P1接入风险

### 1. 旧loader和fallback仍有机械openOI依赖

`load_contract_bars`第94–117行只读旧DATA_ROOT CSV，并强制转换open_oi/close_oi，不会自动读clean；全局BAR_CACHE只按旧vt_symbol缓存。缺少open_oi列会KeyError，证明“模型不需要”不等于“旧函数不读取”。

`build_runtime_feature_row`第61–71行在契约CSV缺失或截断后为空时，改用history，并以freq=D重新分配日期，把open_interest当closeOI，再shift一日构造openOI，缺失填0。这是待替换的兼容回退，不是clean可接受的OI证据。严格接入必须保持完整YYYYMM epoch和源SHA，数据不可用就记录unavailable，不进入此回退。

### 2. candidate_date不等于真实信息可见时点

runtime第53、58–59行按日期规范化后取`date<=candidate日`，包括当日最终close和closeOI；只有候选确实在该完整日线发布后才能安全使用。应明确记录feature_asof和候选event_asof：若候选在当日收盘前，只能取此前已完成日，而不能因日期相同就获得全日数据。本轮没有证明当前所有调用发生在什么信息时点，不把这种风险写成已经发生的泄漏。

`_locate_entry_index`第120–131行在指定日缺失时静默取前一条；runtime又以bars_df最后一日提特征，最后将candidate_date写成请求日。这样“特征来自旧日”可能被隐藏。严格适配应要求精确的已完成源日或明确披露last_observed_feature_date，不能给陈旧数据重新贴当前日标签。fallback的人工日历也必须禁止。

`qmt_roll_portfolio_strategy._apply_selection_pairwise_scores`第4245行用第一个候选target_bar的日期给全部候选，`score_candidate_pool`做截面后又对输入全体成对；需断言候选池只有一个asof/交易日和一致的可用性范围，避免混日或缺候选改变截面含义。

### 3. 120条并不等于原19列全部成熟，旧代码会把不足历史变0

helper第156行只要求entry_index>=40，即41条；第72–76行rolling默认要求完整窗口，随后_safe_float把NaN/Inf变0。runtime第133–135行又对模型矩阵fillna(0)。

原19列的最长链是close.pct_change(20)再rolling_zscore(...,120)，至少140条有效原始bar；ATR14再120z至少133条，OI日变化再120z至少121条。用纯正数序列按同一pandas滚动公式做索引验算，首次有限位置分别为第140、133、121条，未运行行情回放。**Stage266的120源日历可用门不能直接作为pairwise19全成熟证明。** 至少140条仍不充分：OI前值为0、滚动方差为0、真实日历缺日或源日尚未发布都可能让某列不可用。

策略第4261、4274行对空feature row静默跳过，少于两个就不打分，候选保留原生0默认值/未启用状态。严格研究必须记录未评分原因和候选全集的退出规则，不能把这种状态当作模型打分0或悄悄切回原生排序。若从历史41条+补0改为140完整门，会改变历史样本资格，须公开标为严格新数据合同，不能声称原评分完全复刻。

## 接入建议与审查边界

最小严格输入为clean真实epoch、已完成日OHLC/单边V/closeOI，加真实候选上下文；openOI继续null。单列140日成熟门、逐字段有限性、真源日历缺日门、精确asof截断及单日截面门；保持模型19列名称和顺序，不扩列，不混训练标签进入预测。原build_pair_row会计算标签装饰信息，但模型只选择固定19列；适配时仍应保持feature/label边界。

依赖审查P0=0、P1=3。结论为`clean_close_only_semantically_sufficient_for_original_pairwise19_but_needs_strict_adapter_not_legacy_fallback`，并不批准直接把旧runtime挂到clean后运行。本轮未重审月度108，按root已确认结论处理；没有加载/修改生产或正式模型，没有金融回放、训练、预测、下载或DB写入。

结束过拟合判断：否，结论取自固定字段依赖和滚动公式，没有结果调参；继续价值：是，可以做隔离的严格研究适配器，不能以无openOI为由放弃close-only可用信息，也不能用旧fallback掩盖PIT/成熟度不足。本报告及compact JSON是本轮唯一新文件，不改LINE/registry/其他源码。
