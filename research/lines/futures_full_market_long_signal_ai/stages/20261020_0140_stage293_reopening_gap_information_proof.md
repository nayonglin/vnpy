# Stage293：20bar reopening contribution 确有新增历史信息，有限检验 GO

- 时间：2026-10-20 01:40 CST；line_id `futures_full_market_long_signal_ai`。唯一新增本记录，不写pipeline或金融协议，不改LINE/registry/旧源码。
- 结论：**GO，仅限一次预先固定的新增q信息检验。** 下述反例证明q不是旧COMMON26或旧023 ordered20×4的函数；这只是信息可识别性，不是alpha、经济优势或样本外资格。旧ordered/RFF、20bar标签、模型与失败包仍关闭。
- 本轮0实际行情/大数据读取、0network/SQL/native cache/labels、0fit/cash；仅静读registry、LINE、129/023及023依赖的009纯特征片段，再执行一次合成算术。累计441fit/238cash。

## 公式与被遗漏的自由度

固定唯一候选（同一实际epoch、21个连续源bar，最后bar为u）：

`q = sum[t=u−19..u](O_t − C_(t−1)) / (sqrt(20) × rolling20_TR_ATR_u)`。

129 `own11`第88—114行明确用21bar计算20个TR的算术均值。其OWN11为r1/r5/r20、当前body/range/close_location/gap、TR压缩、成交量比、突破与ATR比例；历史open不进入这些数值，当前body/gap只用O_u。`maturity13`依赖同u/前u的peer close、tenor及own WilderN；成本/low20两项在当前价格、HLC历史、N和经济参数相同时也相同。WilderN不是本q分母。

023 `window_representation`第55—80行的四通道是delta_close/ATR、range/ATR、close_location、log_relative_volume；其历史open只影响OHLC有效性判定，不进入任何通道。它保存的是HLC/V序列信息，不包含每根旧open。

价格点数的逐bar恒等式给出：

`C_u − C_(u−20) = sum(O_t−C_(t−1)) + sum(C_t−O_t)`。

因此129现有`r20_atr = q + intrabar_body_contribution`（后二者使用同一sqrt20×ATR分母）。r20已知并不能唯一决定两项；只新增q即可刻画这一个自由度，不再同时加互为残差的第二列。它不是论文中对数隔夜收益的直接照抄。

## 两段完整21bar反例

索引i=0..20，对应u−20..u；epoch、21个连续源索引、成交量、所有非本合约上下文相同：

| 历史 | 每bar H/L/C/V | O_i | 当前O_20 |
| --- | --- | --- | ---: |
| A | 102 / 98 / 100 / 100 | 全部100 | 100 |
| B | 102 / 98 / 100 / 100 | 仅i=5改为101，其余100 | 100 |

这完整指定两段21bar，不需任何未说明的中间价格。两段均满足`L <= min(O,C) <= max(O,C) <= H`、价格及volume正数；i=5即u−15，明确不是当前bar。各20个TR均为`max(4,2,2)=4`，rolling ATR均4。若用到WilderN，给两段同一常数HLC前史即可同时保持N_u=4；所有peer/tenor/economic上下文固定。共同缩放正成交量也不改变旧成交量比或本证明。

| 量 | A | B |
| --- | ---: | ---: |
| 当前gap / 当前body | 0 / 0 | 0 / 0 |
| 20bar close变化 | 0 | 0 |
| 20bar reopening点数和 | 0 | 1 |
| 20bar O→C点数和 | 0 | −1 |
| q | 0 | `1/(4 sqrt20)` = 0.05590169943749474 |

两者旧OWN11精确同为`[0,0,0,0,1,0.5,0,1,0,−0.5,0.04]`；旧20×4每行均为`[0,1,0.5,0]`。其余15项保持同一实现可行上下文：相同peer池和N、当前close/open、low20、费用/滑点/乘数。旧输入及不变跨月派生因而都无法区分A/B，但q可以。保持旧80个通道仍不能恢复历史open；这不是对旧有序表示换名。

合成核验使用AST仅抽取已静读源码的纯`129.own11/maturity13`、`009.valid_prices/valid_history_bar/own_features`、`023.window_representation`，不import旧CLI或读取实际数据。采用同一三peer池、N=4、共同成本项0.05、共同low20距离0.25；终端exit0（chunk5761a5），`array_equal(COMMON26_A,B)=True`、`array_equal(20×4_A,B)=True`，两ATR=4、所有OHLC/volume有效，q差如上。没有构建实际特征表或拟合模型。

## 经济依据的支持与反证

本阶段按0network边界，以下是root已完成原文/GitHub调研的继承结论，本agent没有再联网复核，也不冒称文献已经测试本q：

- [Lou/Polk/Skouras AEA原稿](https://www.aeaweb.org/conference/2018/preliminary/paper/ds4hZdf8)：把收益按交易时段分解具有经济动机，但主证为股票；22股指期货VWAP附表不等于中国真实合约、本执行或这个ATR点数q的证据。
- [Rosa 2022原文](https://onlinelibrary.wiley.com/doi/10.1002/fut.22375)：样本外预测失效是实质负证据，应降低先验，不能把分时分解当普适alpha。
- [中国商品期货日内可预测性原文](https://www.sciencedirect.com/science/article/pii/S0378426626002086)：题为 Intraday predictability in commodity futures: New evidence from China’s retail-dominated market，使用36合约2018—2024的1分钟滞后横截面预测；仅作中国商品信息扩散背景，不能支持本日线q。
- [维护者 overnight_returns notebook](https://github.com/paduckfst91/Systematic_trading/blob/master/overnight_returns.ipynb)：仅供定义参考，不copy/install，不视作alpha或PIT证明。

可检验机制仅为：相同close→close路径可能来自不同的开市重新定价与连续交易段变化，参与者/信息和流动性所处时段可能不同。由此不能直接断言q越大越值得做多；跳变也可能意味着不可承受的窄损尾部风险。当前支持一次有界新增信息检验，不支持设符号、扫窗口/阈值、换label或复杂模型救参。441fit后的长期同史选题风险仍在，不称盲测。

## 来源时钟和最省数据复用

1. **准确命名为reopening contribution。** `O_t`只指现有供应商/交易日定义下的该真实epoch daily open。带夜盘品种可能在前一民用日21:00开始；不把它称9am、海外overnight、纯闭市信息或分钟分解。夜盘制度/交易时段变化也是解释限制。
2. **q只能在u完整源bar收盘后可计算。** 分母依赖u的H/L/close；沿原u收盘选择→后续真实D执行，不能因为最后gap的open已知就把完整q提前到u open。不得读D行、未来主力或未来成功路径。
3. **资格完全复用own11的21bar支撑。** 同actual epoch、源索引严格连续、21bar valid且ATR>0；缺口、停牌/缺bar、epoch边界、无量/坏价保持unavailable/null，不能补0或拼前后合约。数值q=0本身是有效分解，须与unknown分开。完整98产品、母体与动作身份保留。
4. **无需新SQL/download。** 后续如另获授权，优先在129已加载的`series.values/days/valid`上同一21bar窗口取O/H/L/C；若需独立生成，复用已接受132 `native_store_cache.npz`，只需epochs/offsets/days/values/valid成员和既有calendar/身份索引。一次成员加载后按epoch单遍滚动20项，不调用旧restore流程额外大hash、不重复源扫描；本293没有打开该NPZ或任何实际价格。
5. q在每个action实际epoch/u计算，不能错用mother reference epoch或连续复权主力。后续最小输出只需原action身份、q/available及既有支撑状态；不在此建立观察/恢复系统，也不先读取收益挑样本或参数。

## 裁决边界与反思

GO理由是有明确不可恢复的历史open自由度、来源已在本机接受日线中、严格收盘时钟和同epoch21bar支撑可沿用。其余经济证据有限且有样本外反证，因此GO只对一次固定新增q test；实际密度、决策变化、收益/回撤和尾部风险仍完全未验证。若后续只能重复旧信息或必须改窗口、符号、模型、标签才能继续，则NO-GO。

新增策略参数/回测结果：无；本阶段只提出题设唯一20项q，不批准金融或流水线。权益/收益/回撤/Sharpe/滑点/交易次数/胜率/费用N/A。开始/结束新增按成绩过拟合否；历史适应性风险是。继续有限新增信息检验有价值，复活旧orderRFF/20barlabel/model无价值。原完整目标未完成，下一actual仍须root另行冻结授权。
