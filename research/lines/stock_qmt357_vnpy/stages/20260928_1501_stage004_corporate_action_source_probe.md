# Stage004 公司行为补源只读探针

- line_id：`stock_qmt357_vnpy`；记录时间：2026-09-28 15:01（Asia/Shanghai）。
- 性质：只读数据可行性；非重要突破；不触发 A/B；未改 alpha、代码、冻结数据、LINE 或 registry。
- 范围：仅 `000538`、`600027`；使用 `.py311/bin/python -I`、已安装 AkShare 1.18.55；未重试已失效 Tushare 认证。
- 未运行回测；无新增/修改/删除策略参数；权益、收益、回撤、Sharpe、滑点、交易次数、胜率均不适用。

## 官方来源、接口与实际返回

- AkShare 官方文档：[stock.md](https://github.com/akfamily/akshare/blob/main/docs/data/stock/stock.md)；官方实现：[stock_fhps_em.py](https://github.com/akfamily/akshare/blob/main/akshare/stock_feature/stock_fhps_em.py)。
- 新浪原站列表：[000538](https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_ShareBonus/stockid/000538.phtml)、[600027](https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_ShareBonus/stockid/600027.phtml)。公开页面抓取接口，不等于承诺稳定的数据服务 API。
- 实测 `stock_history_dividend_detail(symbol, indicator="分红")`：000538 返回 37 行，600027 返回 25 行；`stock_fhps_detail_em(symbol)` 分别返回 33、22 行。
- 新浪原表表头明确“每 10 股”“含税”：`cash_dividend=派息/10`，`split_ratio=1+(送股+转增)/10`，不可直接照接口简略单位解释为每股。
- 原始字段：`公告日期、送股、转增、派息、进度、除权除息日、股权登记日、红股上市日`；只处理 `进度=实施` 且有效除权日不晚于截止日的事件。
- 详情调用的 `date` 是公告日期，不是除权日；例 `date="2024-11-19"` 对应 2024-11-25 事件，返回 `item/value`。
- 新浪详情原站：[000538 特别分红](https://vip.stock.finance.sina.com.cn/corp/view/vISSUE_ShareBonusDetail.php?end_date=2024-11-19&stockid=000538&type=1)。

## 现有缺口覆盖及限制

- 000538 新浪实际含特别分红：2024-11-25 每 10 股 12.13 元、2025-09-24 每 10 股 10.19 元、2026-09-24 每 10 股 10.38 元；东财本次返回均未含这三笔。
- 000538 新浪含 2022-05-05 的“10 送 4 派 16”（股份倍率 1.4、税前现金每股 1.6），但列表红股上市日为空，不能默认新增股份当日可卖。
- 600027 两源均含 2024-07-25 每 10 股 1.5 元，覆盖此前停牌日事件丢失的可用源证据；事件应独立于可交易行情保留，不能静默移到复牌日。
- 600027 新浪含 2026-06-26 每 10 股 1.4 元；另有 2026 中期每 10 股 0.9 元“预案”且无除权日，不能提前计账。
- 原始展示精度差：000538 的 2019 年现金在新浪为每 10 股 `20.0013`，东财为 `20.001254`；保存原字段，冲突须实施公告裁决，不从因子倒推股息。
- 列表无独立 `pay_date`；详情有“红利/配股起始日（送、转股到账日）”，本次特别分红为 2024-11-25，但不足以普遍认定现金除权日到账或股份立即可卖。
- Baostock 另一独立探针确认 000538 的 2024/2025 `report`、`operate` 两模式都遗漏上述两笔特别分红；证据：`examples/stock_backtesting/qmt357/data/probes/coverage_20260928_1457_baostock.json`。
- 只验证两只股票：可覆盖已知 7 笔漏项中的 000538 两笔，并为停牌 600027 提供事件；其余 5 笔及全池完整性未在本阶段验证。
- 两个既有异常因子（000002 2025-01-09、302132 2025-02-18）尚未解释，持仓因子无事件闸门必须继续硬失败；不得过滤股票或放宽闸门救回测。
- 最小建议：用户确认后，仅数据层以新浪补事件、东财交叉核验、公告解决冲突，并保留停牌权益日历和派现/股份到账限制；本阶段不实施。
- 开始/结束反思：不是过拟合（无调参、无收益挑选）；值得继续（账务真实性是长窗验证前置），但仅凭两股可用性不能宣称全池完整。
