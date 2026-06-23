# Stage063 DCE 官方 HTTP 直连可修复性审计

## 基本信息

- 时间：2026-06-20 06:30 CST
- 研究线：`futures_trend_c9_minrisk_highquality`
- 当前工作模式：`day`
- 当前官方正式版：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage847-C9-15w`
- 阶段性质：DCE 官方 HTTP 直连数据工程审计，不是真实组合引擎，不新增交易规则，不触发 A/B，不改正式配置，不连接 CTP，不调用订单 API。
- 是否重要突破版本：否。它不是收益突破；但它把 DCE 会员持仓公共直连路线从“可能修 parser”推进到“当前环境不可直接修复”的硬边界。
- 决策：`stage063_dce_direct_official_http_not_repair_ready`

## 外部调研和判断

- DCE 官方页面：`http://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/rtj/rcjccpm/index.html` 是官方日成交持仓排名入口。
- AKShare 文档同样把 DCE 会员持仓目标地址指向该官方页面，并说明 DCE 会员排名口径和其他交易所不同。
- AKShare issue #7002 已有 2026 年 `futures_dce_position_rank` 返回 `BadZipFile` 的问题报告，Stage062 与本阶段 direct HTTP 均复现这一类问题。
- 我的判断：DCE 会员持仓信息本身仍有经济意义，但当前公共 HTTP 路由不可直接作为历史点时化回填来源；继续在现有 member-ready 样本上做策略阈值是过拟合，不是研究。

参考：
- https://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/rtj/rcjccpm/index.html
- https://akshare.akfamily.xyz/data/futures/futures.html
- https://github.com/akfamily/akshare/issues/7002

## 本阶段改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage063_dce_official_http_direct_audit.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage063_dce_official_http_direct_audit/`
- 新增参数：
  - `PROBE_DATES = ["20240603", "20210301", "20251028"]`
  - `HTTP_TIMEOUT = 12`
  - direct route：DCE landing GET、`batchDownload` JSON source payload、`batchDownload` form `jm/all` payload、legacy portal `jm/all` HTML table。
- 修改参数：无正式策略参数修改；脚本内 landing URL 已按 AKShare 文档改为 `http` 而不是 `https`，避免协议误判。
- 删除参数：无。
- 新增回测结果：无真实交易回测；本阶段只做 HTTP 数据源探测，并复用官方资金曲线和 Stage028 DCE missing 贡献做视觉背景。
- 修改回测结果：无。
- 删除回测结果：无。

## 官方基准指标

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6339`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- closed-lot 胜率：`36.0902%`

## HTTP 结果

- probe dates：`3`
- HTTP probes：`10`
- data-ready probes：`0/10`
- batch zip count：`0`
- legacy HTML table count：`0`
- hard gates：`2/4` 通过；通过的是“DCE 缺失确实重大”和“不做策略搜索”，失败的是 batch zip 与 legacy table。
- DCE lot count：`50`
- DCE member missing：`50/50`
- DCE member missing net PnL：`+14,851,026.20`
- DCE member missing positive PnL：`+19,369,390.00`
- DCE member missing negative PnL：`-4,518,363.80`

| route | 日期 | 结果 | 说明 |
| --- | --- | --- | --- |
| DCE landing GET | current | HTTP 412 | 官方页面当前环境返回 HTML error，不是可解析排名页 |
| `batchDownload` JSON source payload | `20240603/20210301/20251028` | HTTP 412 | 全部返回 HTML，不是 zip |
| `batchDownload` form `jm/all` | `20240603/20210301/20251028` | HTTP 412 | 全部返回 HTML，不是 zip |
| legacy portal `jm/all` | `20240603/20210301/20251028` | DNS/connection error | `portal.dce.com.cn` 当前无法解析 |

## 视觉分析

- `route_status_chart`：三条数据路线在三个日期上全部为红色 `fail`，没有黄色“返回但不可解析”或绿色“data ready”的中间状态。直观结论是当前公共路由不能直接作为 DCE 历史会员持仓修复源。
- `dce_missing_context_chart`：官方权益曲线的后段台阶和 DCE missing 累计贡献同向，DCE missing 累计贡献在 `2024-2025` 后明显跃升至约 `+1485万`。这说明 DCE 缺失不是噪声，而是官方右尾的重要组成部分。
- 资金曲线层面：本阶段没有候选资金曲线；视觉图只用于说明“若没有 DCE 数据，会员持仓路线无法覆盖关键收益路径”，不能解释为跳过 DCE 的交易建议。

## 反过拟合反思

- 开始前判断：否。这个阶段不是根据历史盈亏切样本，而是验证 DCE 公共源能否支撑完整点时化回填。
- 完成后判断：否。结论是关停当前公共直连会员持仓策略研究，没有把 HTTP 412、DNS error、ready/missing 状态包装成交易规则。

## 是否仍有价值继续

- 开始前判断：有。若 DCE 官方源能直连修复，会员持仓仍可能成为比产品总 OI 更细的供需结构源。
- 完成后判断：策略方向暂时没有继续价值；数据工程仍有条件价值。继续必须改用授权/vendor 历史数据、浏览器人工链路 proof 或交易所可下载离线文件，不应在当前公共 HTTP 路由上继续重试参数。

## 结论和 TODO

- 结论：DCE 公共 HTTP 直连在当前环境下不可修复；会员持仓路线不能进入 true engine、A/B 或任何参数研究。
- TODO：
  - 停止 DCE/member-rank 策略研究，除非先拿到完整、可点时化、可复验的 DCE/CZCE/SHFE/GFEX 历史会员持仓源。
  - 若要继续数据工程，下一步只能做 vendor/authorized dataset、浏览器链路 proof、或离线官方文件落盘，而不是在 `batchDownload`/legacy public HTTP 上继续重试。
  - 若继续策略目标，应换到覆盖完整、入场前可见、非最终盈亏标签的新外生源，或回到 Stage045 `timestamp_ready=1` replay 子集做新的第一性分钟候选预声明。

## 产物

- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage063_dce_official_http_direct_audit/qmt_roll_stage063_c9_minrisk_dce_official_http_direct_audit_decision_stage063_dce_official_http_direct_audit_v1.json`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage063_dce_official_http_direct_audit/qmt_roll_stage063_c9_minrisk_dce_official_http_direct_audit_summary_stage063_dce_official_http_direct_audit_v1.csv`
- HTTP probe：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage063_dce_official_http_direct_audit/qmt_roll_stage063_c9_minrisk_dce_official_http_direct_audit_http_probe_stage063_dce_official_http_direct_audit_v1.csv`
- gates：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage063_dce_official_http_direct_audit/qmt_roll_stage063_c9_minrisk_dce_official_http_direct_audit_gates_stage063_dce_official_http_direct_audit_v1.csv`
- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage063_dce_official_http_direct_audit/qmt_roll_stage063_c9_minrisk_dce_official_http_direct_audit_report_stage063_dce_official_http_direct_audit_v1.md`
- 图像：
  - `qmt_roll_stage063_c9_minrisk_dce_official_http_direct_audit_route_status_chart_stage063_dce_official_http_direct_audit_v1.png`
  - `qmt_roll_stage063_c9_minrisk_dce_official_http_direct_audit_dce_missing_context_chart_stage063_dce_official_http_direct_audit_v1.png`
