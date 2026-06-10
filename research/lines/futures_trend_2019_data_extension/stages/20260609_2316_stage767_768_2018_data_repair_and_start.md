# Stage767/768 2018 数据修复与起点回测

- 时间：2026-06-09 23:16 CST
- line_id：`futures_trend_2019_data_extension`
- 是否重要突破版本：否。属于数据延展与只读鲁棒性验证，不改正式策略。
- 工作模式：`day`

## 本次调研和判断结论

- 网上/文档调研：
  - vn.py 官方数据库文档确认 `get_database().save_bar_data()` 是标准 K 线入库路径。
  - Tushare `fut_daily` 可作为期货日线来源，但本机 Tushare token 返回“token不对”，本阶段不依赖它。
  - TQSDK 文档/GitHub 生态确认 `get_kline_serial`/`DataDownloader` 是历史 K 线常规接口；仓库内已有 `vnpy_tqsdk` 封装可直接查询并转换为 `BarData`。
- 判断：2018 延展应优先补真实合约日线，不应为了覆盖率伪造无成交段；`fu` 2017-2018 的旧合约存在大量低/无成交和映射尾端缺口，必须在结论中标 caveat。

## 版本改动

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage767_2018_data_repair_readiness.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage768_2018_start_stage757_stage764.py`
- 新增数据修复：
  - 使用 TQSDK/vn.py datafeed 补入 `fu1711.SHFE`、`fu1804.SHFE`、`fu1805.SHFE`、`fu1905.SHFE` 日线到 `.vntrader/database.db`。
  - 原始修复 CSV 保存到 `examples/portfolio_backtesting/downloaded_futures/tqsdk_stage767_2018_data_repair/SHFE/`。
- 新增参数：
  - Stage768 新增独立起点 `2018-01-01`，预热起点 `2017-01-01`。
  - 终点保持 `2026-05-29`。
- 修改参数：无。
- 删除参数：无。
- 策略逻辑、AI、品种池、风控倍率：全部冻结，不做任何 PnL 反推调参。

## 数据修复结果

- Stage767 修复前缺失映射日：`176`。
- Stage767 修复后仍缺映射日：`141`。
- 剩余缺口全在 `fu.SHFE`：
  - `fu1711.SHFE`：`87` 天，主要在 2017 预热早段。
  - `fu1804.SHFE`：`36` 天，主要在 2017 预热早段。
  - `fu1805.SHFE`：`7` 天，2018-05-02 至 2018-05-10 的交割尾端。
  - `fu1905.SHFE`：`11` 天，2018-06-29 至 2018-07-13；TQSDK 数据从 2018-07-16 开始出现明显真实成交量。
- 解释：缺口不是全市场数据不可用，而是 `fu` 老合约低/无成交、重新活跃前后的映射和真实 K 线不完全一致；其他实际策略品种覆盖正常。

## 回测结果

口径：Stage757 C50 OI restore 与 Stage764 45w/5w cash reserve；初始总资金 `500,000`；终点 `2026-05-29`；2018/2019 早期成交无 Stage149 next-real-open proxy，使用 `fallback_daily_next_open`。

| 版本 | 起点 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 日胜率 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage757 C50 OI restore | 2018-01 | 7,412,135 | 1382.43% | -44.79% | 1.174 | 754,880 | 706 | 52.38% |
| Stage764 45w/5w reserve | 2018-01 | 8,793,115 | 1658.62% | -41.41% | 1.235 | 876,350 | 703 | 53.06% |
| Stage757 C50 OI restore | 2019-01 | 7,412,135 | 1382.43% | -44.79% | 1.251 | 754,880 | 706 | 52.38% |
| Stage764 45w/5w reserve | 2019-01 | 8,793,115 | 1658.62% | -41.41% | 1.317 | 876,350 | 703 | 53.06% |
| Stage757 C50 OI restore | 2020-01 | 9,171,130 | 1734.23% | -41.65% | 1.422 | 901,820 | 691 | 52.52% |
| Stage764 45w/5w reserve | 2020-01 | 8,554,870 | 1610.97% | -42.62% | 1.400 | 852,290 | 689 | 52.46% |

## 关键发现

- `2018-01` 与 `2019-01` 的期末权益、交易数、滑点完全一致。
- 曲线核对显示：
  - `2018-01` 起点从 2018-01-02 开始有日线曲线，但权益一直保持 `500,000`。
  - 第一笔权益变化发生在 `2019-02-12`。
- 结论：补 2018 数据后，当前冻结逻辑在 2018 年没有实际开仓；2018 起点只是增加了一年空仓预热，不产生新增交易机会。
- 这说明当前 Stage757/Stage764 的实际首个交易路径仍从 2019-02 开始，不能把 2018 起点当作一个新增 OOS 交易年份。

## 过拟合反思

- 不是过拟合：本阶段只做数据补齐和起点前推，没有根据 2018 或 2025/2026 表现调整任何策略参数。
- 需要警惕的点：如果后续为了让 2018 “有交易”而反推降低预热、放宽信号或手动补 `fu` 无成交价格，那就是明显过拟合/数据污染。

## 是否继续有价值

- 有价值，但方向要收敛：
  - 继续价值在于确认更早数据边界、解释为什么 2018 没有交易，而不是继续扫参数。
  - 下一步应做 `2018 no-trade` 归因：分解是信号条件未触发、AI/品种资格未生效、还是预热长度/主力链切换导致候选不足。
  - 若要让 2018 成为真正 OOS 样本，必须先证明当年有足够真实可交易信号和执行代理，而不是强行扩大交易。

## 输出

- Stage767 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage767_2018_data_repair_readiness_report_stage767_2018_data_repair_readiness_v1.md`
- Stage768 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage768_2018_start_stage757_stage764_report_stage768_2018_start_stage757_stage764_v1.md`
- Stage768 资金曲线：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage768_2018_start_stage757_stage764_equity_curves_stage768_2018_start_stage757_stage764_v1.png`
