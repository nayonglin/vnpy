# Stage000 逐合约换月调整趋势质量标签预注册

- line_id：`futures_trend_xgboost_pit_roll_adjusted_trend_quality_labels`
- 当前模式：标签数据资格研究
- 记录时间：2026-09-05 02:52 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：读取标签值前的唯一合同冻结；不是模型实验、回测或上线。
- 是否重要突破：否，当前只有可证伪的新标签机制。
- 是否触发A/B：否；不改正式版本，也不运行策略效果。

## 外部调研与判断

- AQR `A Century of Evidence on Trend-Following Investing`（https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/AQR-JPM-Fall-2017.pdf）：基础时间序列动量以近期正收益做多、近期负收益做空，说明趋势机会本身具有双向性，不能把未来裸上涨当作唯一好标签。
- CME `Continuous Price Series`（https://www.cmegroup.com/market-data/cme-group-continuous-price-series.html）与`Improving Time-Series Momentum Strategies`（https://www.cmegroup.com/education/files/improving-time-series-momentum-strategies.pdf）：连续期货必须明确映射实际合约并消除换月价差造成的人工收益；CME示例采用ratio back-adjustment。
- Quantopian Zipline GitHub（https://github.com/quantopian/zipline/blob/master/zipline/api.pyi）：`continuous_future`同时定义volume/calendar roll和`mul/add/None`调整方式，开源实现同样把换月映射与价格调整作为两个独立问题。
- XGBoost官方LTR文档（https://xgboost.readthedocs.io/en/release_3.2.0/tutorials/learning_to_rank.html）：`XGBRanker`按qid内相关性等级学习，输出是相关性分数而非概率；标签应表达同一查询日候选间的相对质量。
- 我的判断：本地已有精确实际合约leg，因此无需构造一条会回写历史的连续价格；逐leg计算同合约log return并复合，等价地消除了跨合约跳空。对正式双向趋势策略，主标签应衡量未来净趋势幅度并扣除沿最终净方向观察到的路径最大回撤，而不是预测上涨方向。

## 冻结输入

- 到期安全路径：`expiry_safe_paths.csv.gz`，SHA256 `a3f2c1249085b872372f8f0aca2d1cbaf77ecb8a7bc04056f9118f077c16748e`。
- 到期安全legs：`expiry_safe_legs.csv.gz`，SHA256 `db2fcffc24053cbb5c540a699bc47f19149d54eeb66aa2b57057707f346a92da`。
- 上游summary/manifest：SHA256 `6f994dd88896781a7f1af9e9760890540445dc8539a6349ae416b82bcf37283f` / `9f768fc6de7ccd3eb240c29f0444249bd333356d756b137197dc78e4f5f44d76`。
- Stage002日线：`normalised_daily_bars.csv.gz`，SHA256 `f2cf98dbfde2e18031697d598c3147c0ee8f15d3feb6ab935b92bc44a919ece4`。
- 日线manifest/summary：SHA256 `e3894cd20114182e9b3a9e986ed5e0310fe264de06368b5efe1b5efb6903681a` / `67dcdb174bf7e253e100138eff1ec0b644c6a7cc68c0806f71aff10c66f00939`。
- 模型特征面板：`model_feature_panel.csv.gz`，SHA256 `1e4ebb1942dc066eb1164dc82e7e0412fe10d433e57aa5b8b8ab3b71822344ac`；只用于身份覆盖，不读取或改变特征值。
- 特征合同manifest：SHA256 `0ec63c32cf8fbe33a85bed16d20a94aaeb7d2ee9a5906670819e91d3671e702a`。
- V2无标签合同requalification manifest/summary：SHA256 `7428e753607ff44b39f0e3510e29493ec96b4163a35fa261791da7d819b27b79` / `a25817cbbd6da47dde8d711adf35ef70cc37422476060a2e652db37aaed7536d`。

## 冻结路径与标签公式

- 样本身份固定为上游全部`56,272`条路径、`1,046`个query-date qid、`1,125,440`个leg；每条路径精确20个leg，最小qid宽度至少30。
- 对leg `i`，只读取`selected_contract_vt`在`previous_date`和`return_date`的正有限close：
  - `r_i = log(close(return_date, selected_contract_vt) / close(previous_date, selected_contract_vt))`
  - 两个端点的合约身份必须相同；跨合约价格比较计数必须为0。
- 对每条20日路径：
  - `R = sum(r_i)`
  - `future_abs_log_return = abs(R)`
  - `future_trend_sign = sign(R)`，只用于标签审计，不得进入模型特征或决定交易方向。
  - `oriented_r_i = future_trend_sign * r_i`
  - 从0开始累计`oriented_r_i`，`future_oriented_max_drawdown = min(cumulative - cumulative_max)`，取值必须不大于0。
  - `future_abs_variation = sum(abs(r_i))`
  - `future_trend_efficiency = abs(R) / future_abs_variation`；若分母为0则固定为0。
  - 主标签`future_trend_capture_quality = future_abs_log_return + future_oriented_max_drawdown`。回撤为负，因此该式在相同净幅度下惩罚更反复的路径，不裁剪负值。
- qid内按主标签`rank(method='average', pct=True)`，再用`ceil(pct*5)-1`裁剪到`0..4`生成`trend_quality_relevance`；并列必须同级，不用产品代码拆散。

## Stage001硬门

1. 全部输入SHA、size、mtime在运行前后稳定，上游bundle和本阶段最终manifest可离线复验。
2. 路径/leg/qid精确为`56,272 / 1,125,440 / 1,046`，每路径20个连续leg，全部上游`path_valid/leg_valid=true`。
3. 标签路径身份全部被冻结特征面板一对一覆盖；不得新增、删除或回退候选。
4. 逻辑close读取精确`2,250,880`次；缺失、非正、非有限端点均为0；跨合约价格比较为0。
5. 每条路径公式逐值可复验：log return和、绝对变化、方向化最大回撤、效率及主标签误差均`<=1e-12`；效率在`[0,1]`、最大回撤`<=0`、主标签`<=abs(R)`。
6. 每个qid主标签至少5个唯一值且五个relevance等级齐全，最小qid宽度至少30；否则标签退化失败。
7. 标签读取、收益计算可大于0；XGBoost fit/predict、策略回测、true engine、sealed holdout、CTP、订单与生产写入均为0。

## 决策

- 全门通过：`stage001_roll_adjusted_trend_quality_labels_pass_allow_model_preregistration_only`。
- 任一门失败：`stage001_roll_adjusted_trend_quality_labels_fail_close_no_model`。
- 失败后禁止改主标签公式、改20日、删路径/品种/qid、放宽完整性或非退化门、按已见分布新增裁剪/权重后重跑。

## 回测记录占位

- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：不适用；Stage001不运行回测，`future_oriented_max_drawdown`只是单品种市场路径log-return代理，不是账户回撤。

## 过拟合反思

- 运行前判断：否，但后续风险高。
- 原因：20日窗口沿用既有合同，公式、全样本和门禁在首次读取未来close前冻结，没有参数或标签搜索；不过新假设是在多条失败线之后提出，后续模型必须唯一OOS并接受证伪。

## 继续价值反思

- 运行前判断：是。
- 原因：它直接修复旧标签只奖励上涨与固定合约跨到期失败的问题，同时不把市场路径代理冒充可成交PnL。
