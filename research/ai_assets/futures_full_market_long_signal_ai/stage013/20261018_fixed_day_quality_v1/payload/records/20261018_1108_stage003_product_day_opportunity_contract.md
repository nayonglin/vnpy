# Stage003：全市场品种日做多机会母体合同

line_id=`futures_full_market_long_signal_ai`；2026-10-18 11:08 CST。范围是现有 clean 数据读取流程上的一个有界新导出，不是交易策略或标签系统。沿用户已授权自主设计研究，本文在任何本线全市场机会表结果之前固定；Stage002只作输入盘点，两者不得按收益互相修改。

## 目的与非替代条件

每日对六所全部历史期货产品提供“可观察做多机会 / 数据状态”的记录。正式 AI 月池、fu 固定名额、C9 long_case、旧19池、未来盈利、未来是否有 D 行情，均不构成母体准入条件。此处 long 是待评价的方向，尚未决定交易。C9 原生适配暂不强制接入，因为用户允许独立规则和 AI 方向。

本次只新增一份纯读取选择器及有限针对性测试，复用 Stage266 规范库。真实源完整导出仅一次；随后独立 agent 一次同时审代码与实际数据范围。不得创建金融账户、假标签、特征寻优、分钟下载或正式 A/B 臂。

## 固定输入与覆盖

1. 数据：Stage266 `clean_daily.sqlite` 的 `contracts` 与 `daily_bars`，使用 SQLite `mode=ro` 和 `PRAGMA query_only=ON`；绑定 `dataset_manifest.json`、`contract.json`、单位合同、已有独立 qualification/receipt 和本次 Stage002（若已终态）。大库既有 SHA 为继承资格，本次记录实际 path/bytes/mtime/WAL 状态，不为换线重复全库 hash。若 size/WAL 或小绑定不符，先报告，不自动重建。
2. 六所范围为 SHFE/INE/DCE/CZCE/CFFEX/GFEX。产品目录取 `contracts` 的 `(exchange, product)` 全集合，保留普通及 DCE `_F` 月均价产品，保留无本目标区间清洗行的历史产品。不按首/末数据日删品种或把 metadata/首个 bar 当历史上市公告认证。`product_id=EXCHANGE.PRODUCT`，`contract_epoch_id=EXCHANGE.PRODUCT.YYYYMM`，CZCE跨十年不可拼成同一合约。
3. 目标区间为 2010-01-01 至清洗合同已完成上界 2026-10-16；从绑定 source calendar 取区间交易日。面板是产品目录×日历的完整积；上市前、退市后或资料缺失的空行一律只称 `no_accepted_observation`，没有历史证据时不拆成已认证上市/退市原因。
4. 不把 `train_eligible` 或 `legacy108_row_usable` 当新 AI 准入条件。它们仅旧 CSV 七列完整性；本线不依赖真实 opening OI，不能因其缺失删除2010—2019历史。原标记和缺失状态可保留，不补 opening OI。

## 每日代表合约：唯一、事前、无后视

- 在 u 收盘后，仅从 u 当日 `quality_status=accepted`、有限且合法的正价格 OHLC、`volume>0` 的真实合约中选择。当前 full clean 库预期均为此范围，选择器仍拒绝重复键/身份冲突并记录不合格行，而不默默修价。
- 固定按 **u 当日成交量降序 → 有限非负 close_oi 降序（缺失排最后）→ contract_epoch_id 字典序升序** 取每品种一个参考。成交量只在同一产品当日比较，不跨产品按名义张数排序。不搜索 OI/成交量权重或观察窗口。
- 所有比较值均止于 u。不能要求该合约 D 有行情或未来成熟，不能按未来主力/全生命周期成交量重选。这个规则是本线 research reference，不冒称交易所正式主力，也不等同可成交证明。
- 任一产品日有候选即 `observed_long_research_opportunity`；无合法候选则 `no_accepted_observation`。保留 candidate_count、reference_epoch、source_id、u OHLCV/close_oi及close_oi缺失状态、旧字段标记。无参考行的价格/成交量一律空，不 carry、不造0、不建虚拟持仓。
- `direction=long`；卖出平多将在未来执行合同处理，此表没有开空信号。事件 ID 为版本化的 `(product_id,u)` canonical hash，另保存参考 epoch；日后改变代表规则必须新版本，不能改旧 ID 绑定的参考。
- planned D 仅为显式 source calendar 中 u 的下一交易日（可以晚于数据上界）；D 不参与 u 的筛选、状态或排序。若 calendar 无后继，明确 `execution_day_unknown`。一切执行数据资格都为 `not_assessed`。
- cutoff 只声明 `after_u_daily_data_available_before_D_execution` 的历史信息集合同，不凭 u午夜造真实 feature_known_at。尚未证实供应商当年具体发布时间/修订，`publication_pit_certified=false`。

## 输出与边界

输出完整 product roster、压缩 product-day opportunity CSV、按产品年/所年计数、manifest/小绑定和实际 terminal。JSON无NaN，CSV缺失为空。总表统计必须满足产品×日历完整积、(product,u)唯一、参考只来自真实当日合格行、参考epoch归属一致、所有97/98等实际计数口径分别列出。`observed`、目录存在、可交易、特征就绪、成熟标签与独立统计经验不等价。

缺交易乘数/tick/保证金/历史费率/交易时段/限价及分钟资料不阻止**仅观察母体**导出，但必须在manifest写 `financial_ready=false,label_ready=false,model_ready=false`。后续小路径pilot遇缺停止该样本，不把它改选成有覆盖品种，更不能把无数据变成坏信号。

## 最小验证（先RED再GREEN；不跑旧suite）

固定三至四个测试方法，覆盖：①全产品/全日期含 `_F` 和无清洗行产品，不误用旧 train 标记；②代表排序确定、同名跨十年epoch分离、无量/非法OHLC/重复身份的明确行为；③前缀不变：追加未来价格、未来高量合约或删除D行，不改变早期u选择/观察状态，终端无后继另单列；④实际只读SQLite小样集与源文件未写。只对本次新增可错的行为验证，不跑数千旧交易测试或旧金融。

## 依据与反思

沿Stage001已读原始资料和GitHub实现。Stage269既有市场环境代码证明同合约历史和事前参考可计算，但本线不搬它的FORMAL19、普通合约 `_F` 排除、ER60阈值/age61或市场覆盖门。旧环境归因失败不反证整个全市场long目标，亦不授权重新扫描ER。

开始新增过拟合：否；代表规则仅表达流动性观测、在收益前固定，不是策略收益优化。继续价值：是；把用户的新范围落成真实可检查的数据母体。源读取/导出尚未运行，金融/训练/新下载0；全部绩效N/A，目标active、非正式候选。
