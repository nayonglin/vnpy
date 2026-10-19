# Stage023 量仓分歧、价格一致的独立执行专用行情

- line_id：`futures_trend_full_market_noai_one_lot`；时间：2026-10-18。
- 重要突破：否；执行数据合同修复，非alpha收益突破。
- 来源：Stage021确认AL2110/2021-09-24三源四价一致，只有量仓分歧，原quantity隔离连带阻断已有仓位平单。用户已授权修复到期卡死，root明确授权本通用overlay实现。
- 本agent金融回测0、模型拟合0、下载0、CTP/订单API0。旧clean、inputs、expiry overlay与已失败run保持不动。

## 冻结资格规则

只接受当前冻结4,328个epoch、2014-01-01—2026-10-16、已知maturity且quote日期不晚于maturity的数量整键隔离记录；不接受任何价格隔离键。每键必须唯一RQ+至少官方真实原行，并要求**所有在场源**OHLC逐字段完全相同、正有限、几何合法；各源按已经冻结的单位规则转换后的V均>=1。所有源身份/日期/原行和指纹必须能核实。

这里不要求V或OI相等，不把它们认证为真量仓。输出V取各源规范化V最小值，只作一手执行报价资格；closeOI取确定官方quote-only值。输出`execution_only=True`、`allow_new_open=False`、`quantity_certified=False`、`quote_class=quantity_conflict_price_consensus_execution_only`，必须只供已有仓位成交/估值；不得进入signal、主力选择、AM预热、新开仓或训练数据。

通用覆盖所有同结构记录，不点名AL或生命周期截止日，不看PNL。与已有accepted/expiry key重复时拒绝；未知官方数量制度拒绝。价格分歧全部拒绝，不靠多数投票抹掉第三源。

## 实现与来源绑定

新增本线`tools/stage023_quantity_price_overlay.py`及专属test。新输出独立目录`outputs/stage023_quantity_price_overlay/`，不改原source manifest。

- RQ：核已锁futures.h5 SHA、完整product+YYMM/F精确key、row与交易日期、native OHLCV/OI，避免CZCE同名跨epoch。
- 官方：核已锁normalized gz SHA及准确CSV物理行；核原archive/member字节SHA和原sheet/原行。XLS/XLSX复用主工作区Stage265既有纯reader，不调用其中下载/normalize入口。合约列空白时按原报表同段向下承接，日期与原source_symbol必须相同。
- TQ：核已锁CSV SHA、native、准确CSV物理行和日期，量仓取原值并按冻结单位转换。
- 283个来源文件/原档指纹，所有冻结输入和来源在生成前后重算保持一致。receipt每键保留全部来源quote与locator、官方原行、单位因子、maturity和身份。

CSV：`outputs/stage023_quantity_price_overlay/execution_quotes.csv`，669条、166,524字节，SHA256 `90821fff6adee2812ea2fa6b718475892fc74686396af5411788f6239467c233`。

receipt：同目录`receipt.json`，4,600,071字节，SHA256 `ed46d2b4f40b9af5859b17a0183f9101d64c0d383190c5cb8e47de230777ee4a`。顶层有rows、output(path/bytes/sha256)、source_files、scope、policy、source_inputs、rejections与逐键evidence。

## 全样本结果与边界测试

当前scope 1,766个数量隔离键：

| 处理 | 数量 |
| --- | ---: |
| 完整证据接受到新执行层 | 669 |
| 与旧expiry已绑定重复，拒绝 | 133 |
| 缺唯一RQ或官方，拒绝 | 821 |
| 任一在场源OHLC分歧，拒绝 | 47 |
| 官方单位未知，拒绝 | 96 |

合计1,766，无无声遗失。新669条为SHFE439、INE32、CFFEX198；不因为某所没有合格证据而添加推定数据。

AL2110/2021-09-24作为通用集合成员自然出现：open23520/high23635/low22760/close23115，RQ V180549/OI87233；官方与旧TQ V191338/OI90833；输出minV180549、官方quote-only OI90833。没有改数量争议事实，也没有赋予该bar新开资格。

先写6项测试观察全部RED，随后实现GREEN：接受合格非到期数量冲突同价；错误epoch/date/未知身份/到期后拒绝；第三源任何OHLC分歧拒绝；非quantity/price隔离拒绝；V<1/非有限/非法几何拒绝；缺RQ/官方或重复RQ拒绝。最终6项定向unittest通过。

额外实际数据读回检查全669：CSV数量=receipt evidence数量、key唯一、所属冻结epoch、日期<=maturity、所有标志正确、每源OHLC与CSV相同、CSV V恰等于各源最小值且>=1、无expiry重复，原input指纹均未变。未声称全仓库测试通过；独立review由root安排，本agent没有自称独立审查者。

## 调研判断与下一步

延用前序网上/GitHub对vn.py/RQAlpha真实合约和生命周期的核验，以及本机Stage265官方纯reader。判断：价格和量仓资格可以分别建证据链；训练clean保持严格整键隔离，已有仓位的已证实真实价格可以进入独立执行层。此处“多源同价”不是反事实委托必然有市场深度或可完成成交的证明，日线执行近似仍需披露。

本阶段新增alpha参数无；新增为显式执行数据资格政策；金融回测结果新增/修改/删除无，期末权益、收益、回撤、Sharpe、滑点、交易次数、胜率N/A。

开始/结束过拟合判断：否，没有按收益、品种表现或截止成功择优；这是发现AL缺口后的合同修订，须保留旧失败与post-discovery边界。继续价值：是，通用数据语义修复能消除不必要的已有仓位退出阻塞。TODO：root先让独立failed_review检查本overlay/loader，再冻结新source binding和新run_id v2；金融结果必须重新独立review，不能改写v1失败。
