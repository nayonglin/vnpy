# Stage294：多日reopening贡献新增信息一次固定实验

- line_id=`futures_full_market_long_signal_ai`；2026-10-20 01:40 CST；当前分支codex/ai-training-data-expansion；金融前固定、非重要突破/正式晋级，不改官方/生产。
- 上轮289是progress：2新fit实际验证无动作增量并省去4重复cash，累计441/238。291/292分别否决以trailing stop释放原始风险和直接把conformal覆盖当均值质量门；未新增金融。本轮不重开WASDE，也不恢复290两NO-GO。

## 原始资料与判断

- [Lou/Polk/Skouras AEA原稿](https://www.aeaweb.org/conference/2018/preliminary/paper/ds4hZdf8)：收益在close→open与open→close的分解可能带有参与者差异。主体是股票，附有22股指期货VWAP证据；不是中国全部期货本政策的获利证明。
- [Rosa2022原论文摘要](https://onlinelibrary.wiley.com/doi/10.1002/fut.22375)：其intraday momentum样本外预报曾失效，是反对普适外推的重要证据。
- [中国商品1min原论文](https://www.sciencedirect.com/science/article/pii/S0378426626002086)：只提供高频信息扩散背景，其一分钟效应和期限衰减不授权本日线假说。
- [GitHub维护者notebook](https://github.com/paduckfst91/Systematic_trading/blob/master/overnight_returns.ipynb)：只参考分解定义，未复制或安装；其股票调整与美股时段不能机械移植。
- root判断：值得仅做一项有限信息检验。293构造旧COMMON26和旧20×4输入完全相同、历史Open不同而新量不同的例子，证明这里有未保留的观测自由度；它不是证明有alpha，也不是提高旧RFF容量。

## 唯一新增量及时间

`q = sum_{t=u-19..u}(O_t-C_(t-1))/(sqrt(20)*ATR20_TR_u)`，原129.own11的同一21个真实epoch连续源bar、rolling20TR均值归一化。只用完整u及以前；它是每日reopening贡献，不能称9am/夜盘或海外overnight收益。总20bar close变化已经在旧输入里；新增量区分该变化发生在reopen还是O→C。固定20继承既有观察尺度，不扫窗口。

295只一次129动作三身份字段流+一次接受132缓存，0SQL/下载/分钟/大hash，输出完整1552456动作对齐值；真实零保留，缺/无效历史z0沿原52，不删98产品/母域。不重做价格资格或标签。

## 固定实验与预算

- 原130六个scope/cutoff的52coef/intercept/scaler、成熟训练身份/原weights/原net_R_stress完全固定。只有一个训练内原权重标准化q，无新missing/ID/intercept；各fold独立解Ridge1残差scalar，共最多6fit。
- 全1933480 main/held分数只读一次；完整newscore重选D<K→positive argmax→普通/F/family，main161014/held并集161014母行保留。允许新增/取消交易，不只过滤旧4365。held沿原family分组训练排除，不借main系数；需要的原标签只一次minimal字段流，未知不同动作不填0。
- 候选最多4新cash（2020连续/2023空仓冷启×base/stress），157四本control只引用。100万、0.25N/原20low退出/K/anchor/容量/费用/风险.0025/.02/.25/1.1不变；两个stress各权益严格更高且DD严格更浅为名义主门，held均值不害必要，未知与PIT另限制，不因过门称目标完成。
- 全动作/执行输入相同则独立核等价后直接跳过cash；其他情形仅一次4cash、同旧070固定2000/block252 loggrowth诊断CI。失败关闭本q+20+linearoffset包，不改sign/normalizer/window/threshold/product/model/target/stop/risk救参。
- 已实现复用与新边界tiny可验证；实际须root最终源码/输入固定授权，不自动启动。298一次独立静态/actual总审；不重复旧基准模型/现金、大库hash、旧源资格流程。

当前新实际fit/cash=0/0，累计441/238；权益、收益、DD、Sharpe、滑点、交易数、胜率N/A；原参数/结果删除修改0。完整机器协议SHA `82a4e3f88c4c17c6319e298a2ad6c37ac1070f62fff6cd9eb5d25be857251016`，位于outputs/stage294_reopening_contribution_protocol/protocol.json。

开始新增按本轮收益调参过拟合：否；同一历史多次择题风险：是。继续这个有明确新观测自由度的有限证伪：有价值；继续扩大参数网格：无价值。完整全市场高质量long、更高收益更低DD、极小损失上界/加注仍未获证明，goal active。
