# Stage106 SHFE 主体类别原表：固定历史锚点与 schema 核验

- line_id：`futures_full_market_long_signal_ai`。
- 时间：2026-10-18 19:22—19:28 CST；本机 `/Users/mac/Desktop/fian`，不改分支/Git/LINE/registry。
- 协议：`outputs/stage106_member_category_probe/protocol.json`，2822 B，SHA256 `803e029e048f4e09970ecb33af74493adeb0a925c6a3e9159ac5de613c489511`，执行前已核全部 bound input 小文件大小/SHA。
- 性质：固定 12 个日期 source-only HTTP；复用 Stage104 三日期；最多2并发、25秒、总16 MiB、12 GET、无自动重试、禁自动跟随重定向。没有另换日期、URL、来源或添加失败重试。
- 是否重要突破：否。确认更早类别信息与历史范围变化，不等于有效金融信号。
- 本次新增：106 实现脚本、12个原响应、逐请求元数据、两层只读审计与本中文记录。新增/修改/删除策略参数：无；既有金融结果修改/删除：无。
- 新增 fit / cash / SQL / 分钟下载：`0 / 0 / 0 / 0`。期末权益、收益、回撤、Sharpe、滑点、交易次数、胜率：本次均 N/A。

## 调研依据与判断

复用 Stage104 已读的 [官方信息办法](https://www.shfe.cn/regulation/exchangerules/otherrules/202508/t20250807_828526.html)、官方会员资格定义和 [AKShare 维护者 cot.py](https://github.com/akfamily/akshare/blob/main/akshare/futures/cot.py) / [cons.py](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/futures/cons.py)。维护者 parser 的 `RANK>0` 过滤会丢掉本类数据；本轮直接保存官方原响应。

root 另已查 [2013 信息发布制度一手说明](https://www.shfe.com.cn/content/cxxc/7wsxx.pdf)：2012 年初金银先试行分类汇总，2013 年扩展其他品种，涉及活跃月份。这是 root 提供的一手制度交叉证据；本执行没有为此增发 GET。下文原表结果与其相符，但不据说明猜各品种精确首日，也不把“活跃月份”改称所有上市月份。

**判断：2020 cutoff 前确有新增主体类别的历史支持锚点，但历史披露范围经历真实合约层 → product-all，以及参与者标签变化；尚未证明连续训练前缀或一个无缝稳定定义。** 2010/2011 没有类别行，不填仓位零。类别不是产业/投机、客户意图或聪明资金。

## 执行事实与文件

12个新日期全部一次 HTTP200、无截断、无网络错误，共 **4,180,472 B < 16,777,216 B**；每次实际耗时小于25秒。使用此前已经证明可用的只读网络 escalation，没有再制造一轮已知沙箱 DNS 失败。所有新 URL 形式严格为：

`https://www.shfe.com.cn/data/tradedata/future/dailydata/pm{date}.dat`

实际示例：[20130104](https://www.shfe.com.cn/data/tradedata/future/dailydata/pm20130104.dat)、[20191231](https://www.shfe.com.cn/data/tradedata/future/dailydata/pm20191231.dat)、[20261016](https://www.shfe.com.cn/data/tradedata/future/dailydata/pm20261016.dat)。2025-06-30/07-01 都在同一路径成功返回 JSON，不能据此认定所有前后日期、旧路径或镜像也连续可用。

绝对输出根：`/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage106_member_category_probe/`。

- `raw/pmYYYYMMDD.response`：12个原响应，未清洗/改值。
- `requests/YYYYMMDD.json`：URL、起止耗时、状态、完整响应头、字节、SHA、错误/截断状态。
- `execution_receipt.json`：执行总账与 Stage104 三日期引用；SHA `7fe885b8bfd327ac49b8b8ca828eded1ae019506554dbbcae05700031a04ed07`。
- 104 复用 `20100104/20200102/20230103` 原始文件引用，核原SHA/字节，未重下载/复制。
- `scope_summary.json`：**873 B**，最终完整 scope 小摘要，SHA `0da3b75b7910b272f0af7dcf922cc348d2b31d115538a8b3f871355835daa97f`。
- 实现脚本：`/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage106_member_category_probe.py`。

## 首审边界与唯一离线补充

首次提取器沿 Stage104 的 `instrument endswith(all)` 识别类别，输出312条 all 类别行/156 product-all scope。这些数对 all 层有效，**若把它们解释成全部类别会漏掉102条早期真实合约类别行**。没有因此重发网络、改原表或改金融代码。

原 `per_date_audit.json`、`all_category_quantities.json`、`all_product_balances.json`、`summary.json` 保留不覆盖，表示 all-suffix 首审层。随后唯一一次离线 `offline_scope_audit.py` 读取原响应，按原 `RANK<=0` 与原类别标签保留全部分类，并明确 `actual_contract / product_all / unknown`：

- `all_category_scope_quantities.json`：完整414条分类行，保留原行、rank、raw label/ID、数值原型与missing/zero/invalid状态；829419 B，SHA `1f63d65e42c37e519359a9caee7ee62d252de1d1d2da7e2b674447954cf31001`。
- `all_scope_balances.json`：207个同日同instrument成对范围；153103 B，SHA `52493d0ea4fa1b3ee23113636bbc64f662fa1d66b6de18f1eff48b62eadb3104`。
- `scope_per_date_audit.json`：15日期全部 schema、范围、缺口与时钟；17170 B，SHA `bc8cddc28a2395433fa7bd63f1669b0952c32d40d5af75f65d9ce9ad76edfe98`。
- `offline_scope_audit_receipt.json` 记录一次离线补充、0新网络、首审范围限制。没有新增镜像 parser 测试、旧 suite 或资格工程。

## 稀疏历史支持与范围

| 日期 | 新GET字节（复用为—） | 类别行 | 真实合约类别scope | product-all scope | 类别产品数 | NFC真双0 scope |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 20100104 | — | 0 | 0 | 0 | 0 | 0 |
| 20110104 | 108073 | 0 | 0 | 0 | 0 | 0 |
| 20130104 | 110559 | 8 | 4 | 0 | 2 | 0 |
| 20140102 | 146139 | 50 | 25 | 0 | 7 | 4 |
| 20150105 | 127575 | 44 | 22 | 0 | 7 | 4 |
| 20170103 | 193737 | 24 | 0 | 12 | 12 | 1 |
| 20190102 | 320649 | 28 | 0 | 14 | 14 | 4 |
| 20191231 | 409530 | 28 | 0 | 14 | 14 | 3 |
| 20200102 | — | 28 | 0 | 14 | 14 | 3 |
| 20210104 | 577370 | 30 | 0 | 15 | 15 | 7 |
| 20230103 | — | 30 | 0 | 15 | 15 | 8 |
| 20250102 | 490588 | 34 | 0 | 17 | 17 | 8 |
| 20250630 | 604757 | 36 | 0 | 18 | 18 | 7 |
| 20250701 | 599891 | 36 | 0 | 18 | 18 | 7 |
| 20261016 | 491604 | 38 | 0 | 19 | 19 | 12 |

2013类别只见 `au/ag` 的4个真实合约；2014/2015 为 `ag/al/au/cu/rb/ru/zn`，分别25/22真实合约。这些不能直接与之后 `auall` 等串成相同产品统计序列，更不能把已披露合约求和冒称全产品。

2017 all产品为 `ag/al/au/bu/cu/hc/ni/pb/rb/ru/sn/zn`；2019增加 `fu/sp`；2021有 `ss`；2025初增加 `ao/br`，6月有`ad`；2026有`op`。这是所取日期的实测集合，不是全历史上市清单或精确新增日。

有真实合约却缺类别的范围例子：2019末/2020 `nr`；2021 `lu/nr`；2023 `bc/lu/nr`；2025 `ec/lu/nr`；2026 `bc/lu/nr`。**缺类别不填0、不得删掉其他交易所/品种以缩小用户全市场母体。** 本轮未取DCE/CZCE/CFFEX/GFEX，不能宣称全国来源已齐。旧scope与当日可观察真实合约的集合也不等于所有上市月份。

## 全部分类数量、类型与平衡

414行=207成对scope，其中51真实合约scope、156 product-all scope。每scope恰有FC/NFC两行，三个原标签列一致，rank分别-1/0；重复类别、未知类别标签、负level均0。`CJ1/CJ2/CJ3` 与三个变化值共2484格，全为 JSON `int`：1852非零有限整数、632真零；缺key/null/空串/非整数/非法文本均0。变化可为负，未把负变化判成负持仓。

逐scope检查FC+NFC的买总和=卖总和：**207/207平衡，差值全0**。这是原表同范围内部关系，既不证明所有月份覆盖、也不与数据库OI分母做不当跨范围连接。原数量、原变化与缺失状态全存，不为凑平衡作替换。

NFC两侧真实0共68scope：8真实合约scope＋60 all scope。仅真实存在类别行、两侧数值都确为整数0，才记双0。无类别行不构造双0；数学上平衡的无NFC参与与大规模多空抵消仍是不同经济状态，不能因同可定义归一值0而称同一机制。此处只标数据状态，没有计算或选取策略scalar。

类别行 ID：2010—2015无ID列；2017也无；2019起原类行有`PARTICIPANTID1/2/3`，其内容是类别字面标签，不是此层稳定投资者/席位编号。正rank原表会员编号另有用途，不能把两个层级混同。

## Schema、主体标签与时钟

2010—2015原表只有cursor与成功码/消息等顶层信息，无report/update/print日期；行无PRODUCTNAME或ID。2017已有PRODUCTNAME、report/update/print，但无ID；2019起抽样见ID。2025抽样不再有PRODUCTSORTNO/print_date，`o_code`由整数0转字符串`"0000"`，不能把类型变化误判失败，也不能隐式依靠旧排序码当产品身份。

旧类别原标签为“期货公司 / 非期货公司”。20261016变为：

- “期货公司会员/境外特殊经纪参与者”
- “非期货公司会员/境外特殊非经纪参与者”

本轮为数量QA才映为FC/NFC两组，完整raw标签始终保留。**该映射不证明前后同一人群或合格的无缝特征版本**，也不证明非FC就是产业或套保者。后续必须显式处理定义版本，不能仅按rank把新标签偷偷拼入旧训练序列。

| 日期 | raw update | raw print |
| --- | --- | --- |
| 2017-01-03 | 20:59:30 | 20:59:40 |
| 2019-01-02 | 20:00:30 | 20:00:40 |
| 2019-12-31 | 18:44:30 | 18:44:40 |
| 2020-01-02 | 20:00:30 | 20:00:40 |
| 2021-01-04 | 19:57:20 | 20:00:40 |
| 2023-01-03 | 19:57:20 | 20:00:40 |
| 2025-01-02 | 15:25:02 | 缺 |
| 2025-06-30 | 15:54:34 | 缺 |
| 2025-07-01 | 15:40:04 | 缺 |
| 2026-10-16 | 15:29:00 | 缺 |

有report_date的抽样均匹配请求。2010—2015无report_date不伪填；实际合约年代与URL仅作来源锚点。更新/打印不是首次可见时间，HTTP Last-Modified/Date也不是当年首发证据；完整响应头已保留。采样时钟显示不能统一套16:30、20点或15点。未来若采用完整源日lag，仍属明确保守历史重建假设，夜盘归属、节假日、历史修订与定义版本不能由一个lag自动解决。

## 前缀资格、核验与反思

已确认2013/2014/2015及2017/2019的cutoff前稀疏真实内容，不是仅最新页或近90天。**尚未证明2012起每日连续覆盖、精确首日、缺口机制、2015—2017转换日、2025/2026标签转换日、原始首发字节一致性，或全部产品/月份范围。** 不创建资格通过声明，不立即训练。

最终独立于网络执行的本地小核：12日期与冻结清单完全相同，逐原响应status/bytes/SHA一致；414类别行/2484数量格/207scope及两层计数重核通过，0新HTTP。`verification_receipt.json` 612 B，SHA `524e84a7623e087fe019dd0aaaa58214fdd316466930182ceaccd7a83367ff82`。未散列大库、未扫描原行情、未跑旧suite。

开始/结束是否新增过拟合：**否**。固定日期与来源先于数据结果，0金融，不按盈亏择日期/品种/方向；整线历史多轮择题风险仍存在。首审schema漏行由原表与制度事实纠正，非救收益。

是否继续有价值：**是，仅限下一阶段另行冻结的连续 source-only 可得性核**，可把“不知道前缀”变成有缺口状态的真实证据。原表取得不是alpha；不把本次工程当全市场优质做多目标完成。后续实际获取、actor映射和训练均未启动；等待root另行冻结，不自行扩大HTTP预算。
