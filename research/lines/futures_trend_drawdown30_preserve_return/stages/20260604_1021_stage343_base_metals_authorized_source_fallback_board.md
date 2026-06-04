# Stage343 base_metals 授权 source fallback 决策板

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 10:21 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：`base_metals` 在公开 SHFE/LME 路线阻塞后的授权/官方可下载/供应商 source fallback 决策板
- 是否重要突破：否；明确了授权路径存在，但当前不具备 selector/source ready
- 是否触发A/B：否；没有新增策略版本、paper、白名单或实盘候选

## 外部调研与判断

- 参考资料：
  - LME Data distribution：`https://www.lme.com/Market-data/Market-data-licensing/Data-distribution`
  - LME Market Data FAQs：`https://www.lme.com/en/about/faqs/market-data-faqs`
  - LME Warehousing / OLP off-warrant reports：`https://www.lme.com/en/Physical-services/Warehousing`
  - SHFE authorized vendor list：`https://tsite.shfe.com.cn/eng/services/marketdata/vendorlist/`
  - SHFE Information Management Rules：`https://www.shfe.com.cn/eng/services/Rules/SHFERules/202508/t20250807_828562.html`
  - CQG SHFE warehouse data notice：`https://news.cqg.com/news/announcements/2023/06/shanghai-futures-exchange-shfe-warehouse-data`
- 我的判断：
  - `base_metals` 不是“没有官方数据”，而是“公开网页/公开 DAT 当前不能作为实盘 source”。
  - LME 的 OLP/XML next-day feed 与 SHFE 授权 vendor 路线是目前可见的正规机器可读路径；但这只是 contract path，不等于我们当前拥有可用数据。
  - SHFE 信息管理规则和 vendor list 说明，实盘自动化必须走授权或明确可下载服务；继续绕 WAF/验证码抓公开网页既不稳，也不符合长期实盘纪律。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage643_base_metals_authorized_source_fallback_board.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - source option：`lme_xml_next_day_feed`
  - source option：`lme_olp_daily_off_warrant_report`
  - source option：`lme_public_web_current_report`
  - source option：`shfe_authorized_market_data_vendor`
  - source option：`shfe_public_current_dailystock`
  - source option：`third_party_monitor_only`
  - 明确拆分：`post_contract_candidate` 与 `owned_selector_ready`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不新增行情回测；只读 Stage640/641 冻结 source 证据与外部授权资料
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：
  - Stage640 `base_metals` 官方源 active fetch 探针
  - Stage641 SHFE 当前仓单 route forensic
  - 外部官方/授权 source 页面与供应商公告
- 策略/归因口径：
  - 不重放策略，不看收益，不改交易规则
  - 不联网抓授权数据，因为当前没有授权账号
  - 不连接 CTP，不生成 selector/paper/A/B/交易白名单

## 结果

- 期末权益：不适用；本阶段不是新策略回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - decision：`base_metals_authorized_source_paths_exist_contract_missing_selector_locked`
  - official current payload ready rows：`0`
  - legacy payload shape validated rows：`4`
  - blocked current rows：`96`
  - WAF-like rows：`51`
  - post-contract candidate rows：`2`
  - owned selector-ready rows：`0`
  - authorized paths identified：`3`
  - machine-readable authorized paths：`2`
  - hard gates：`3/6`
  - selector rows：`0`
  - paper / whitelist：`0/0`

## source option 判断

| option | 判断 | 当前能否 selector |
| --- | --- | --- |
| `lme_xml_next_day_feed` | 官方、授权、机器可读，包含 warehouse stock movements 这类报告；需要 OLP/订阅 | 否，未拥有 access |
| `shfe_authorized_market_data_vendor` | SHFE 授权 vendor 路线，CQG 也有 SHFE warehouse data 公告；需确认字段、频率和自动化权利 | 否，未拥有 access |
| `lme_olp_daily_off_warrant_report` | 官方 OLP report 路线；需确认格式是否机器可读 | 否 |
| `lme_public_web_current_report` | Stage640 未形成 current payload | 否 |
| `shfe_public_current_dailystock` | Stage641 证明 current DAT/HTML/stockdata 为 `404/WAF/blocked`，legacy 只证明旧形态 | 否 |
| `third_party_monitor_only` | 只能辅助观察；授权、PIT、schema provenance 不闭合 | 否 |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage643_base_metals_authorized_source_fallback_board_report_stage643_base_metals_authorized_source_fallback_board_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage643_base_metals_authorized_source_fallback_board_decision_stage643_base_metals_authorized_source_fallback_board_v1.json`
- orders：不适用
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage643_base_metals_authorized_source_fallback_board_source_options_stage643_base_metals_authorized_source_fallback_board_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage643_base_metals_authorized_source_fallback_board_public_route_summary_stage643_base_metals_authorized_source_fallback_board_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage643_base_metals_authorized_source_fallback_board_gates_stage643_base_metals_authorized_source_fallback_board_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage643_base_metals_authorized_source_fallback_board_chart_stage643_base_metals_authorized_source_fallback_board_v1.png`

## 图表视觉复盘

- 左上图：
  - 蓝色 `shfe_authorized_market_data_vendor` 与 `lme_xml_next_day_feed` readiness score 最高，但右侧都标注 `owned=no`。
  - 这说明它们是“可签约后可验证”的路径，不是当前可用 source。
- 右上图：
  - `641 current ready` 为 `0`。
  - `641 blocked=96`、`641 WAF=51` 是最高红柱，视觉上确认公开路线阻塞不是偶发小问题。
  - `641 legacy shape=4` 是绿色，但高度远小于 blocked/WAF，只能证明历史 schema 存在，不能证明 current route 可用。
- 左下图：
  - LME XML 和 SHFE authorized vendor 在 official/contract/machine readable/post-access hash/schema 上多为绿色，但 access/current payload/selector 都是红色。
  - SHFE public 与 LME public 只有 owned/public 绿块，没有当前 payload 和 selector 绿块，说明“能访问网页”不等于“能实盘采集”。
- 右下图：
  - 绿色只有 `public_route_retry_stopped`、`authorized_contract_path_identified`、`paper_and_whitelist_zero`。
  - 红灯集中在 `public_current_payload_ready`、`owned_access_now`、`selector_allowed_now`，结论清晰：授权路径存在，但 selector 继续锁定。
- 视觉质量：图表无关键遮挡；右上图已改短标签，避免长文本影响判断。

## 结论

- 本阶段结论：
  - `base_metals` 可以保留为经济驱动方向，但不能继续靠公开 SHFE/LME 页面推进。
  - 当前只有两条值得继续的正式路径：`LME XML next-day feed` 与 `SHFE authorized vendor feed`。
  - 在没有签约/供应商 access、没有一日 raw-hash parser probe、没有 PIT 样本累计和 outcome/TCA 之前，`base_metals` 不能做 selector、paper、A/B 或交易白名单。
- 是否进入下一步：继续，但只在“授权 access 已获得/供应商字段确认”后继续；否则 `base_metals` 暂降级为 source backlog。
- 下一步：
  - 若愿意投入数据源：优先确认 LME XML next-day feed 是否包含我们需要的 LME warehouse stock movements 字段，并确认自动化和内部研究使用权。
  - 国内路线：确认 SHFE 授权 vendor（如 Wind/Refinitiv/Bloomberg/CQG/上期所授权列表内供应商）是否有 daily/weekly warehouse warrant 字段、机器接口、历史回补和使用条款。
  - 若短期不走授权：停止 `base_metals`，把扩池精力转向已经有官方源累计的 `lh.DCE`，以及另找两个非 DCE、低相关、source 可执行的新独立经济驱动。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：
  - 本阶段不看收益、不改交易规则、不做品种白名单，只验证 source 可执行边界。
  - 结论没有为了保留 `base_metals` 强行降低 source 门槛，反而把公开 route 锁死。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值但需要条件。
- 原因：
  - `base_metals` 年度机会和经济驱动仍有价值，且授权路径客观存在。
  - 当前没有 access，所以继续写公开抓取脚本价值低；真正有价值的是合同/供应商确认，或切换到其他已具备 official source 的独立风险槽。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage343 当前状态。
- 是否更新 `research/registry.md`：是，更新当前阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是正式候选、路线废弃、跨线合并或重大突破。
