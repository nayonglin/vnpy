# Stage618：期权排重与 GLD 官方实物持仓源规范

- 时间：2026-10-21 09:11（Asia/Shanghai）。研究线：`futures_full_market_long_signal_ai`；本阶段不修改 LINE、registry 或正式策略。
- 性质：来源可行性与规范记录，不是重要突破版本，不是策略收益验证。新增参数、修改参数、删除参数均为 0；新增训练、现金回放、SQL、行情请求均为 0。
- 结论：期权方向与既有 244/501/570 等重复，本轮停止；GLD 官方实物存量是值得保留的新观测，完成源规范但尚未建立特征、可知时刻连接或模型。不能把下载成功或数据跨度当作 alpha 证据。

## 调研与判断

先读本线 registry 并排查旧记录。国内商品期权并非完全没有本机原件：旧 Stage265 小 inventory 的 2018 年 SHFE 排除样例包括 `cu1901C45000`、`cu1901C46000`；本阶段只读小元数据，没有读取对应 ZIP，混合“替代/合计”计数不能称为期权链条数。维护者 [AKShare 郑商所期权下载源码](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/option/option_czce.py) 仍指向官方年度文件路线，此路线已在旧阶段研究，未带来本轮新增信息，按 root 决策不再刷新 schema 或探测原件。

随后转向 [SPDR GLD 官方页面](https://www.spdrgoldshares.com/usa/gld/) 直接链接的[官方历史归档](https://api.spdrgoldshares.com/api/v1/historical-archive?product=gld&exchange=NYSE&lang=en)。官方页面与 XLSX 均由 root 唯一获取；本阶段不重复请求。AKShare 的 [GLD 维护源码](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/economic/macro_constitute.py) 实际使用第三方 Jin10，不能替代本次官方来源认证，也未调用其行情接口。

官方表有 `Ounces of Gold per Share`、`Total Ounces of Gold in the Trust`、`Tonnes of Gold`、`Total Net Asset Value in the Trust`，但**没有发行在外份额总数**。`Daily Share Volume` 是日交易量，不能当份额存量或净申赎；AUM 同时受金价等影响。吨数是实物存量，变化不等于已确认的资金净流入；每份含金量与费用、黄金处置等解释仍须独立处理，本轮不从比例反推份额或流量。

## 原件、方法及冻结产物

原件：`outputs/stage616_new_measurement_source_probe/gld_official_archive.xlsx`，542026B，SHA256 `d2e35ce7b39fb0415f7a18d352ba119e973b7fc539adb5ec5bdd68650c16ee8e`。root receipt 留存 HTTP200、官方下载地址及 Last-Modified `2026-10-20T22:06:04 GMT`。

本阶段原 XLSX 磁盘读取 **1 次**，以 stdlib ZIP/XML 保存两张表的全部 literal cells，后续规范仅读自己的小 cache。解析源码与执行方法留存在 `outputs/stage618_options_gld_source_screen/`：

- `parse_official_once.py`：SHA256 `1287bd25d4e4b6d39078f22fa63096c63d656b0299178ecfdee26527fc34a86e`；同次读取核原件 hash，不修改工作簿。
- `normalize_captured_literals.py`：SHA256 `12fba80760d3a99a9177b78dd36e9f89c647ff935d9052add2e5a500abd69b4b`；不插值、前填、去重或推导份额。
- `literal_source_rows.json.gz` 保留全部原列、行号、单元格类型/格式及 XML 数字字符串；`source_parse_method.json` 记解析约定。
- `daily.csv.gz`：131895B，SHA256 `acebaf505c44693d3f8d6b6773c969a150740634727e2477ee03ed7d052b6f6f`；只规范日期、吨数、总金衡盎司、每份金衡盎司及各 literal/state/原行身份。数值保留原 XML 文本，未为外观修圆。
- `summary.json`：7061B，SHA256 `56c48b3e497b7830e0b571a9172ee01896e8f0458a8b1056459470c893c0b3f0`；`manifest.json` 状态为 `source_normalized_not_training`，绑定原件、源码、规范及小摘要。
- `ounce_tonne_check.json` 保留 5512 个数值日期的单位换算差，不按差值筛行。

上述规范与源码已冻结，已通知 Stage622 用独立方法一次核对原 XLSX 与规范；本记录写作时独审尚未终态。

## 真实覆盖与数据边界

历史表 `US GLD Historical Archive` 为 A1:K5718，11 列，含表头；另有 `Disclaimer`。完整保留 **5717 个日期**，跨度 **2004-11-18 至 2026-10-19**，唯一日期 5717，重复、日期解析失败均为 0，原顺序严格递增。

- 5512 行三项实物字段均为正数；205 行明确记为 `US Holiday`，数值留空并保存原 literal/state。没有将 holiday 当 0 或补值。
- 3 个周末日期均在 2022 年，保留原状。跨度内缺少 4 个周一至周五日期：2006-12-25、2007-04-06、2012-10-29、2012-10-30；未擅自认定错误、补日或假设交易所日历。
- 首日原值：260000.0 金衡盎司、8.09 吨、0.1 金衡盎司/份；末日原值：34030941.71999999880791 金衡盎司、1058.47000000000003 吨、0.09165907 金衡盎司/份。
- 以 1 金衡盎司 = 31.1034768 克作一致性观察，`吨数－总盎司×0.0000311034768` 最大绝对差 0.015292812149114730541844 吨，中位绝对差约 0.0067571440 吨；3830 行绝对差大于 0.005 吨，1126 行大于 0.01 吨。数量级相对存量很小，但不能无依据说全部已被“两位小数四舍五入”解释。原格式有精度差与 XML 浮点尾数，全数保留，不为小差返工。

日期只是源观察日期；价格/NAV 列标题的 NY 时间不能直接赋给持仓数量。文件 Last-Modified 也不是历年首次发布时间。当前规范没有 PIT 发布时间认证、历史修订版本认证或下一国内时段可用性保证。末日期为 19 日，不因文件 20 日更新就补造 20 日记录；本线既有期货样本截止与此无连接。

## 财务、过拟合与后续

期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全部 **N/A**；本轮没有新增、修改或删除收益结果。累计仍为 551 fitted objects / 290 completed cash + 旧 partial1。

本轮**没有做结果驱动过拟合**：未读取 Y、试窗口、估计系数或交易；但整条研究线已筛过大量想法，不能把“新物理字段”自动升格为稳定优势。**值得继续保留这一来源，但不立即训练 GLD**：现阶段确定的是长期官方实物存量，而非净申赎或方向信号。后续若独审通过，只能在先冻结经济问题、时钟与适用范围后讨论一次检验；全 98/95 母域不缩小，未受该观测解释的品种保留原 A fallback。root 当前优先处理最终模型准入价值对照，本阶段到源规范即止。
