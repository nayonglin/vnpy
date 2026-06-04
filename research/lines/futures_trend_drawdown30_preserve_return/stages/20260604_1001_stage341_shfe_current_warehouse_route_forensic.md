# Stage341 SHFE 当前仓单官方路线取证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 10:01 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：`base_metals/ao.SHFE` 当前仓单官方源 route forensic；阶段级输出，不追加 master
- 是否重要突破：否；确认当前 SHFE 仓单官方 payload 仍不可自动化，但明确了旧 JSON 形态和当前阻塞类型
- 是否触发A/B：否；没有策略版本进入正式候选、paper 或交易白名单

## 外部调研与判断

- 参考资料：
  - SHFE dailystock UI：`https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_params=dailystock`
  - SHFE Daily Data English page：`https://www.shfe.cn/eng/reports/StatisticalData/DailyData/`
  - AkShare 旧仓单接口说明：`https://cloud.tencent.com/developer/article/1666918`
  - 本地 AKShare 源码：`.py311/lib/python3.11/site-packages/akshare/futures/futures_warehouse_receipt.py`
  - 本地 AKShare 源码：`.py311/lib/python3.11/site-packages/akshare/futures/receipt.py`
  - 本地 AKShare 源码：`.py311/lib/python3.11/site-packages/akshare/futures/futures_stock_js.py`
- 我的判断：
  - 旧 SHFE 仓单数据形态确实存在，`20200702dailystock.dat` 可返回 `o_cursor`，能解析 `铜/铝` 等仓单字段。
  - 当前本地 AKShare 已把 `20140519` 后仓单入口指向 `https://www.shfe.com.cn/data/tradedata/future/dailydata/{date}dailystock.dat`，另有 `stockdata/dailystock_{date}/ZH/all.html` 解析路线；这些与 Stage640/641 的当前端点测试一致。
  - 但当前交易日附近 `20260603/20260604/20260602/20260529` 的 SHFE 官方仓单 payload 没有任何一条通过：DAT 为 `404`，UI/HTML/stockdata 为 WAF/人机校验，`tsite` 解析失败。
  - Jin10/AKShare 第三方周库存即便未来可用，也只能作为 monitor 参考，不能替代官方 PIT source 或 selector。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage641_shfe_current_warehouse_route_forensic.py`
- 修改脚本：
  - 同一脚本内修正两处取证口径：
    - 将 `page_ready` 与 `payload_ready` 分离，避免把普通页面或 WAF 页误判为可交易 payload。
    - 将 browser fetch 从 `page.evaluate(fetch)` 改为 Playwright `context.request.get`，排除跨域 CORS 假阴性。
    - 图表左上热力图改为按 `source_role` 聚合，避免标签拥挤和视觉误导。
- 删除脚本：无
- 新增参数：
  - `PROBE_DATE=20260603`
  - `CURRENT_DATES=20260603,20260604,20260602,20260529`
  - `LEGACY_DATE=20200702`
  - direct/session/browser/cookie replay 四层取证
  - AKShare wrapper 探针：`futures_shfe_warehouse_receipt`、`futures_stock_shfe_js`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不新增策略回测；只抓取 `2026-06-04 10:00 CST` 当时可见的 SHFE/AKShare/Jin10 路线
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：
  - 当前日期候选：`20260603/20260604/20260602/20260529`
  - 历史形态参考：`20200702`
  - 官方路线必须区别 page evidence 与 payload evidence
- 策略/归因口径：
  - 不重放策略、不改交易规则、不扫参数
  - 不追加 master PIT ledger
  - 不生成 selector/paper/A/B/交易白名单
  - 不连接 CTP、不调用订单 API

## 结果

- 期末权益：不适用；本阶段不是新策略回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - decision：`shfe_current_warehouse_route_blocked_legacy_shape_validated_selector_locked`
  - official current payload ready rows：`0`
  - legacy payload shape validated rows：`4`
  - blocked current rows：`96`
  - WAF-like rows：`51`
  - browser attempted：`1`
  - browser cookie count：`4`
  - cookie replay attempted：`1`
  - third-party monitor ready rows：`0`
  - selector rows：`0`
  - paper/whitelist rows：`0`
  - hard gates：`10/11`

## 路线结果

| route 类别 | 结果 | 解释 |
| --- | --- | --- |
| `www_dailydata_dat_202606xx` | `404` | 当前日期附近 DAT 路径不存在或不可下载 |
| `www_dailystock_ui` | WAF-like | 返回 `WEB 应用防火墙/向右滑动填充拼图`，不能自动化 |
| `www_dailydata_html/stockdata_zh/stockdata_en` | WAF-like | direct/session/cookie replay/browser context 均不能得到仓单表 |
| `tsite_*` | DNS/连接失败 | 旧 tsite 路线不能作为当前自动化路线 |
| `www_english_dailydata` | page ready | 浏览器可渲染英文 Daily Data 页面，但这是页面证据，不是当前仓单 payload |
| `legacy_www_dailydata_dat_20200702` | payload ready | 历史 JSON shape 可解析，`o_cursor=326`、base metal matched rows `85` |
| `AKShare wrapper` | 未解锁 | 本阶段检查 wrapper，但当前官方 wrapper 未给出 current payload；第三方 monitor 不进入 selector |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage641_shfe_current_warehouse_route_forensic_report_stage641_shfe_current_warehouse_route_forensic_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage641_shfe_current_warehouse_route_forensic_decision_stage641_shfe_current_warehouse_route_forensic_v1.json`
- orders：不适用
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage641_shfe_current_warehouse_route_forensic_http_probe_stage641_shfe_current_warehouse_route_forensic_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage641_shfe_current_warehouse_route_forensic_browser_probe_stage641_shfe_current_warehouse_route_forensic_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage641_shfe_current_warehouse_route_forensic_browser_cookies_stage641_shfe_current_warehouse_route_forensic_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage641_shfe_current_warehouse_route_forensic_akshare_probe_stage641_shfe_current_warehouse_route_forensic_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage641_shfe_current_warehouse_route_forensic_route_matrix_stage641_shfe_current_warehouse_route_forensic_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage641_shfe_current_warehouse_route_forensic_gates_stage641_shfe_current_warehouse_route_forensic_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage641_shfe_current_warehouse_route_forensic_chart_stage641_shfe_current_warehouse_route_forensic_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage641_shfe_current_warehouse_route_forensic_browser_page_stage641_shfe_current_warehouse_route_forensic_v1.png`

## 图表视觉复盘

- 左上图：
  - `current_dailydata_dat/current_dailydata_html/current_stockdata_zh_html/current_stockdata_en_html/current_ui_page` 的 `parse/match` 和 `current ready` 全为 `0`。
  - 部分 route 有 hash 或 no-WAF，但没有可解析仓单 payload；这证明“页面/响应存在”不能等同于“可实盘特征源”。
- 右上图：
  - direct、after_session_warmup、browser_cookie_replay、browser_context_fetch 均有大量 rows，但绿色 `current ready` 全为 `0`。
  - WAF/block 红柱在 direct、session warmup、cookie replay、browser context 中均明显存在，说明浏览器 cookie 不能关闭当前阻塞。
- 左下图：
  - `current official` 红柱为 `96`，而 green 为 `0`。
  - `legacy shape` 只有 `4` 条 green，说明历史形态有效但不能补当前 PIT。
  - `third-party monitor` 为 `0`，本阶段没有第三方可用行。
- 右下图：
  - 唯一红灯是 `current_official_payload_ready=0`；其他绿色包含 fail-closed discipline，不代表晋级。
  - `selector_rows_zero/paper_whitelist_zero/master_append_zero` 均为绿色，符合本阶段只取证不晋级的纪律。
- 浏览器截图：
  - 英文 Daily Data 页面可渲染，能看到完整表格页面；但这只是 `page_ready`，不是 dailystock 当前 payload。
  - 浏览器上下文请求 legacy DAT 可成功，说明取证链路不是浏览器失败；当前 payload 失败更可信。

## 结论

- 本阶段结论：
  - `base_metals/SHFE` source-first 方向暂时不能晋级。
  - SHFE 历史仓单 JSON 形态可解析，但当前官方日更 payload 在 direct/session/browser/cookie replay 下均不可用。
  - 这不是 alpha 失败，而是实盘 source 执行失败；不能把 SHFE 当前仓单写入 PIT master、不能进入 selector、paper、A/B 或交易白名单。
- 是否进入下一步：继续，但不继续在同一批公开 URL 上反复试。
- 下一步：
  - `base_metals` 分支转向授权/官方可下载渠道确认，或 LME OLP/licensed distributor 许可确认。
  - 若无授权渠道，`base_metals` 只保留 source backlog，不再占用扩池主路径。
  - 扩池主线应继续寻找两个非 DCE、低相关、source 可执行的新独立经济驱动，或继续累计已通过 active fetch 的 `lh.DCE` 官方月度源 PIT。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有看收益、没有改策略、没有调参数、没有生成白名单。
  - 中间出现假阳性后主动收紧口径，避免为了推进路线而误把页面可达当成数据可用。
  - 结论是锁定晋级，而不是用源取证包装成 alpha。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但 `SHFE 当前公开仓单 URL` 这条子路线上继续价值下降。
- 原因：
  - 本阶段排除了 direct/session/browser/cookie replay 的常规修复路径，减少了重复试错。
  - `base_metals` 仍可能有价值，但下一步必须靠授权渠道或 LME 许可，不应继续用同一公开路径扫 URL。
  - 扩池大方向仍有价值，因为年度机会和独立风险槽缺口仍存在，但 source 可执行性必须先过关。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage341 当前状态。
- 是否更新 `research/registry.md`：是，更新最新关键阶段和下一步。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是正式候选、路线废弃、跨线合并或重大突破。
