# Stage201：全域相邻月份价格弦线偏离一次纯X投影

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-19 18:56 CST。非重要突破，非正式A/B，不新增交易模型或回测。
- 工作区/分支：`/Users/mac/Desktop/fian` / `codex/ai-training-data-expansion`。完整全市场高质量做多目标active，未晋级/加注。

## 改动与一次执行

新增`tools/stage201_local_curve_projection.py`及4个固定几何/未知/身份/非冗余fixture，后者由实现agent新运行4/4通过。原fixture已在中断前写入，实现中断后接回；没有启动过旧actual，完整大表只由root本次唯一actual读取。没有修改旧策略、模型、风险、止损或历史结果。

200在18:42:03事前冻结，root18:53:26固定源码与fixture并启动；session22276最终exit0。terminal计时44.224015秒（至terminal写出，未包括其后的新文件哈希/manifest落盘），1 action CSV读＋1 mother CSV读，0旧大表再hash/fit/cash/selection/SQL/download。Source前后stat相同、原manifest小binding相同。

池仅同exact product/u、当日finite positive u_close、完整名义合约月首>u；query严格相邻两侧按月距插值log价格。没有按label、历史就绪、经济资格、K或未来是否闭合选quote。单位共同倍数不改变q；端点unknown不外推，缺失不填0。重复月闭合语义为observable positive/future pool；已接受129每exact product/u/canonical epoch唯一，因此202的一正一0同月诊断属于不可达原输入边界，保留披露，不为此改协议或重跑。

## 完整域与覆盖

1,552,456 action / 399,252 mother全部保留，98代码、95family、六所均在。action域97个有行情代码，全部存在source_ready；无行情DCE.S仍在完整mother域，不能因action coverage只有97行说全市场只有97代码。

| action状态 | 行数 |
| --- | ---: |
| no_lower_neighbor | 212,702 |
| no_upper_neighbor | 203,068 |
| nominal_month_not_after_u | 53,706 |
| source_ready | 1,082,980 |

source_ready 1,082,980/1,552,456=69.7591%；这些子合约行不是独立交易经验。mother中193,129有至少一个q，19,723有child但无q，186,400无child；在212,852有child母体中90.7339%可形成至少一个局部偏离。不能把无child当登记missing，也不据覆盖率认定可盈利。

| 年份 | action行数 | 可算q行数 |
| --- | ---: | ---: |
| 2010 | 46,804 | 33,985 |
| 2011 | 43,664 | 29,972 |
| 2012 | 43,230 | 28,148 |
| 2013 | 49,148 | 32,069 |
| 2014 | 57,549 | 35,903 |
| 2015 | 63,282 | 39,326 |
| 2016 | 65,773 | 42,193 |
| 2017 | 64,702 | 41,023 |
| 2018 | 69,884 | 44,194 |
| 2019 | 81,680 | 52,574 |
| 2020 | 108,099 | 75,093 |
| 2021 | 129,433 | 93,691 |
| 2022 | 129,102 | 93,457 |
| 2023 | 140,345 | 102,617 |
| 2024 | 152,962 | 112,448 |
| 2025 | 167,128 | 123,391 |
| 2026 | 139,671 | 102,896 |

2026仅至2026-10-16，不是完整年。2010—2019只表明可能训练输入覆盖，当前没有新增这些年份的资金回测。所有年份统计仅描述，不据此筛年、改邻居、加阈值或填端点。

## 产物与资格边界

输出全action身份/q/状态/邻月/gap（102,561,566B压缩）、全mother覆盖（19,803,147B压缩）、q_vector（9,963,099B）、小year/product/status覆盖、16个按source-ready身份均匀序号取的机械anchor，以及started/terminal/manifest。anchor选择未看价格、q正负或盈亏；有限抽定重算支持公式核对，不是全原报价重新认证。

模型未来可直接复用q_vector，不需要为同一X再读SQL、重建labels或重新计算源。大原始输入SHA沿已接受129/132/197继承，尺寸/stat guard不是重新hash审计。新输出由201一次记录hash，root不重复扫新大输出或旧行情。

外部调研复用[原论文](https://arxiv.org/pdf/2308.00383)、[RBA研究](https://www.rba.gov.au/publications/rdp/2017/2017-03.html)和[维护者GitHub](https://github.com/stefan-jansen/machine-learning-for-trading/blob/main/case_studies/cme_futures/03_financial_features.py)，细节见199；曲率成本负证据与short-leg依赖不抹除。判断为几何信息可非冗余，但月距不是精确到期、季节/非流动性可产生形状，PIT与做多可预测性仍未证明。

202独立关键源/新fixture/实际小summary与有限anchor审查完成后由root203决定是否接受；其范围不包含重读全投影或老价格，不能称第二次全行独审。source资格不是alpha、实际可成交或正式生产资格。

新增参数为q几何定义/缺失状态，修改/删除旧参数0；新增/修改/删除回测结果0。期末权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A。新增fit/cash=0/0，累计421/226；无正式/CTP/邮件/launchd/Git发布。

开始新增收益驱动过拟合：否，纯X、规则先定、未看盈亏；历史择题风险仍是。结束新增收益驱动过拟合：否，未据覆盖或anchor改规则；不能用新名称免除同史检验风险。开始/结束这次纯X检查有价值：是，现已完成并留下完整可复用特征；继续重复这同一投影无价值。完整全市场目标继续有价值，但要经过单独预声明的预测/资金证伪，不因覆盖好就宣称稳定优势或加注。
