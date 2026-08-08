# Stage209 C9/15万 >=2R 大赢家15分钟K线图谱结果

- line_id：`futures_trend_stage819_intraday_rules`
- 记录时间：2026-08-08 18:01 CST
- 实际生成完成时间：2026-08-08 18:00 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：冻结回测样本的只读分钟K法证，不是新回测
- 是否重要突破：否。完成了可审阅图谱和逐事件覆盖审计，但没有产生或验证新策略规则。
- 是否触发A/B：否。未改正式策略、参数、AI池、回测引擎或执行链路。

## 外部调研与判断

- 参考 mplfinance 官方仓库及其“数据过多”说明：<https://github.com/matplotlib/mplfinance>。
- 调研结论：跨11个交易日直接画分钟线会过密；15分钟聚合能保留 OHLC 路径和成交量结构，同时仍应压缩休市空白、保留交易日边界。外部实现只用于绘图工程参考，不提供策略参数依据。
- 我的判断：本阶段的价值是把右尾交易变成可复核证据；不能因为图形看起来相似，就把事后赢家形态直接写成交易条件。

## 正式版本与冻结口径

- 正式版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 账户规模：`150,000`
- 回测样本起点：`requested_start_month=2020-01`
- 聚合键：`open_trade_id`
- 聚合收益率：`aggregate_r=sum(realized_pnl)/sum(risk_amount)`
- 大赢家门槛：`aggregate_r >= 2.0`
- 排序：`aggregate_r desc, realized_pnl desc, entry_date asc, open_trade_id asc`
- 窗口：开仓日前5个正式交易日 + 开仓日 + 后5个正式交易日
- K线粒度：15分钟；上涨红、下跌绿；无插值、无空桶补值

## 本次版本变更

- 新增时间：2026-08-08 17:50 CST
- 修改时间：2026-08-08 18:00 CST
- 新增脚本：`tools/stage208_c9_2r_winner_15m_atlas.py`
- 新增测试：`tests/test_stage208_c9_2r_winner_15m_atlas.py`
- 新增参数：`WINNER_R_THRESHOLD=2.0`、前后窗口 `5/5`、周期 `15min`、单图 `18x9@150dpi`、Atlas每页4笔
- 修改参数：无
- 删除参数：无
- 正式策略代码变更：无
- 订单/CTP：`send_order_api_called_count=0`、`cancel_order_api_called_count=0`、`ctp_connected=false`

## 数据源根因修正

首次正式生成得到完整 `3`、部分 `11`、缺失 `57`。系统化排查确认这不是合约代码映射错误：71笔涉及的67个合约全部存在于 Stage861 文件中；真正原因是 Stage861 的“完整覆盖”只承诺 Stage825 的 `341/341` 笔开仓日有分钟线，并不承诺每个合约连续保存开仓日前后5个交易日。此前根据全文件起止日期和合约集合推断“只有1笔缺失”属于逐合约窗口语义误判。

修正后仍以 Stage861 同时间戳记录为最高优先级，并只从仓库已有 `downloaded_futures/**/*minute_backtest.csv` 中按“精确合约 + 精确交易所”补充目标窗口：

- 命中的本地逐合约缓存：`321` 个文件
- 前缀相似合约与错误交易所文件：明确排除
- 同时间戳冲突：Stage861 优先
- 下载、插值、前值填充：均为 `0`
- 缓存文件逐个 SHA256：`outputs/stage208_c9_2r_winner_15m_atlas/minute_cache_sha256.csv`
- 缓存 bundle SHA256：`fa8526d49f871f2638896ecd0bbc6a775ee8bf135c1cac98ec91a383aea24f07`

## 结果

- 聚合开仓事件：`309`
- `>=2R` 大赢家：`71`
- 单图：`71`
- Atlas页：`18`
- PNG哈希校验：`89/89`
- 完整11交易日覆盖：`52`
- 部分覆盖：`19`
- 完全缺失：`0`
- 实际交易日最少/最多：`2 / 11`
- 最短覆盖：排名41，`BACKTESTING.626 / jm2609.DCE / long / 2026-06-03 / 4.6667R`，本地只有开仓日与次日2个交易日；保留为部分覆盖，不伪造其余9天。

收益率前三：

1. `BACKTESTING.336 / rb2210.SHFE / short / 2022-07-07 / 213.5000R / PnL 333,060`
2. `BACKTESTING.288 / jm2205.DCE / long / 2022-02-14 / 96.0000R / PnL 195,840`
3. `BACKTESTING.335 / hc2210.SHFE / short / 2022-07-07 / 83.4000R / PnL 404,490`

完整71笔清单见 `winner_manifest.csv`，逐笔覆盖与来源数量见 `coverage_summary.csv`。

## 回测指标口径

本阶段没有运行新回测，因此以下指标没有新增、修改或删除：

- 期末权益：不适用（未跑新回测）
- 总收益：不适用（未跑新回测）
- 最大回撤：不适用（未跑新回测）
- Sharpe：不适用（未跑新回测）
- 总滑点：不适用（未跑新回测）
- 总交易次数：不适用（未跑新回测）
- 胜率：不适用（未跑新回测）

## 视觉与机器验证

- 单测：`9 passed`
- `py_compile`：通过
- `git diff --check`：通过
- 机器闸门：排名严格 `1..71`，`aggregate_r` 单调不增，单图 `71`、Atlas `18`、coverage `71`、PNG SHA256 `89/89`
- 视觉抽查：排名 `1`、`36`、`71`、最短覆盖排名 `41`、Atlas首页；蜡烛、成交量、日期标签、开仓日底色、开仓价和标题无截断或重叠。
- `jm2609` 两日缓存的 volume 原值为0，图中如实显示平坦成交量轴，没有补造数据。

## 输入SHA256

- closed lots：`9489b34637171f6f833d40f573f84ff73cc4ce39f2c41628463a3bf6e5183df4`
- curves：`b22201f615ae408e7e49c02a6cd59b26268d2e00e24e0a61713deed52f789d02`
- trades：`d1b6954b89195a4440b016256780e2fe63a4d055cd15aa516c8f934857d08051`
- Stage861 minute bars：`8e861633b08a82819a668c30c6799e2098d2beaa6863698351145018ea586784`

## 输出

- 输出目录：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_stage819_intraday_rules/outputs/stage208_c9_2r_winner_15m_atlas`
- 清单：`winner_manifest.csv`
- 覆盖：`coverage_summary.csv`
- 决策：`decision.json`
- 报告：`report.md`
- PNG哈希：`png_sha256.csv`
- 分钟缓存哈希：`minute_cache_sha256.csv`
- 单图：`winner_*.png`
- 分页图谱：`atlas_page*.png`

PNG合计约14MB，作为可再生产物保留在本地，不写入Git历史；CSV/JSON/Markdown和哈希清单作为审计元数据提交。

## 过拟合反思

- 运行前判断：否。样本门、排序、窗口和周期先冻结，未根据图形调参。
- 运行后判断：当前工作本身仍不是过拟合，因为没有修改策略或生成规则；但它有显著的幸存者偏差，71笔全部是事后赢家。任何后续规则假设都必须回到全部309个聚合事件，并做跨年份、跨品种和未参与归纳的验证，否则就是过拟合。

## 继续价值反思与TODO

- 是否还有价值：有，但“继续画更多同类赢家图”的边际价值已经较低。
- 下一步有价值的方向：先人工浏览图谱并只记录低自由度、可实时判定、可被反证的形态假设；若要验证，必须纳入309笔全集及亏损/普通交易对照，不允许只在71笔赢家内部找共同点。
- 数据TODO：如需把 `19` 笔部分覆盖补成完整11日，先做缺口 manifest 和合法本地源审计；在没有合法数据前保持部分覆盖，禁止插值或下载未授权数据。

## 决策

`stage209_c9_2r_winner_15m_atlas_complete_52_full_19_partial_no_rule`

