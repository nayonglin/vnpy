# Stage007 分钟源覆盖修复与质量标签重绑

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01 12:44 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读覆盖审计；读取 Stage006 `closed_lots`，比较既有分钟 CSV 源并重绑 quality labels；不重跑策略、不改实盘、不连接 CTP、不调用下单。
- 是否重要突破：否，但修复了 Stage006 的证据绑定缺口。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - TqSdk API 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html`
  - TqSdk 与 vn.py K线差异说明：`https://tqsdk-python.readthedocs.io/en/stable/advanced/for_vnpy_user.html`
  - Probability of Backtest Overfitting：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253`
  - Deflated Sharpe Ratio：`https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf`
  - Meta-labeling/triple-barrier：`https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/`
- 我的判断：
  - TqSdk/vn.py K 线生成与存储机制不同，研究阶段应先比较本地已下载 CSV 源，不能把单一 Stage861 覆盖不足直接归因成策略或特征无效。
  - PBO/DSR 继续约束本线：本阶段只修复分钟绑定源，不按质量桶结果调参。
  - meta-labeling 只有在标签覆盖和年际稳定性足够后才有资格做二级风险预算验证，不能直接上线加仓。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage007_minute_source_coverage_rebind.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增只读 `PRIMARY_SOURCE_ID=stage152_complete` 用于绑定分钟首根。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据底座：Stage006 `closed_lots=3,401`
- 比较分钟源：
  - `stage861_visual_atlas`
  - `stage449_session_rebuild`
  - `stage152_complete`
  - `stage152_local`
  - `stage152_raw`
  - `stage900_gap_backfill`
- 主绑定源：`qmt_roll_stage152_stage861_candidate_stage449_859_stage900complete_full_minute_bars_v1.csv`
- 策略/归因口径：沿用 Stage006 质量标签定义，固定 `0R` 方向判断 `entry_open_aligned` 和 `first_bar_aligned`。

## 结果

- 分钟覆盖根因：
  - Stage006 使用的 `stage861_visual_atlas` 只覆盖 `899/3,401 = 26.4334%`
  - `stage152_complete` 覆盖 `3,311/3,401 = 97.3537%`
  - 结论：Stage006 覆盖不足主要是分钟源选窄，不是当前重建版 closed-lot 本身缺分钟证据。
- 各分钟源覆盖：
  - `stage152_complete`：`97.3537%`
  - `stage152_local`：`96.8539%`
  - `stage152_raw`：`65.3043%`
  - `stage449_session_rebuild`：`52.9844%`
  - `stage900_gap_backfill`：`32.0494%`
  - `stage861_visual_atlas`：`26.4334%`
- 重绑后只读质量桶：
  - `all_closed_lots`：`3,401` 笔，PnL `71,392,804.00`
  - `entry_or_first_aligned`：`1,373` 笔，`18` 产品，`9` 年，PnL `60,642,420.00`，胜率 `54.5521%`
  - `ai_rank_4_6`：`803` 笔，PnL `20,275,609.80`
  - `ai4_6_entry_or_first_aligned`：`306` 笔，`13` 产品，`7` 年，PnL `22,617,180.00`
  - `ai4_6_not_aligned`：`497` 笔，`14` 产品，`7` 年，PnL `-2,341,570.20`
  - `aligned_not_ai4_6`：`1,067` 笔，`17` 产品，`9` 年，PnL `38,025,240.00`
  - `missing_first_bar`：`90` 笔，PnL `-519,102.00`
- 交易/实盘安全：
  - `strategy_changed=false`
  - `order_api_called=false`
  - `ctp_connected=false`

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage007_minute_source_coverage_rebind/rebuilt_c9_stage007_minute_source_coverage_rebind_report_stage007_minute_source_coverage_rebind_v1.md`
- coverage_compare：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage007_minute_source_coverage_rebind/rebuilt_c9_stage007_minute_source_coverage_rebind_coverage_compare_stage007_minute_source_coverage_rebind_v1.csv`
- quality：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage007_minute_source_coverage_rebind/rebuilt_c9_stage007_minute_source_coverage_rebind_quality_features_stage007_minute_source_coverage_rebind_v1.csv`
- quality_summary：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage007_minute_source_coverage_rebind/rebuilt_c9_stage007_minute_source_coverage_rebind_quality_summary_stage007_minute_source_coverage_rebind_v1.csv`
- annual_quality：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage007_minute_source_coverage_rebind/rebuilt_c9_stage007_minute_source_coverage_rebind_annual_quality_stage007_minute_source_coverage_rebind_v1.csv`
- missing_lots：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage007_minute_source_coverage_rebind/rebuilt_c9_stage007_minute_source_coverage_rebind_missing_lots_stage007_minute_source_coverage_rebind_v1.csv`
- chart：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage007_minute_source_coverage_rebind/rebuilt_c9_stage007_minute_source_coverage_rebind_coverage_quality_chart_stage007_minute_source_coverage_rebind_v1.png`

## 结论

- 本阶段结论：Stage006 的 `26.4334%` 首分钟覆盖是分钟源选择问题，已用 `stage152_complete` 修到 `97.3537%`。重绑后，`ai4_6_entry_or_first_aligned` 从 Stage006 的 `27` 笔/`2` 年扩大到 `306` 笔/`7` 年，且与 `ai4_6_not_aligned` 出现显著只读分化。
- 是否进入下一步：进入，但仍不能直接上线或加仓。
- 下一步：Stage008 做冻结只读代理，比较“核心 C9 不挤占 + 高质量标签小额非挤占加风险预算”的上界；必须继续复核年际稳定性、左尾、broker10 和任意大于一年起点正收益，代理通过后才写真实组合引擎。

## 过拟合反思

- 运行前判断：否。目标是定位 Stage006 分钟覆盖缺口，变量只有分钟源选择，不调交易规则。
- 运行后判断：否。只比较既有分钟 CSV 的覆盖并重绑固定 `0R` 方向标签，没有按结果调参或改 C9。
- 原因：Stage007 修的是证据覆盖，不是策略收益；质量桶结果只作为下一阶段预声明候选，不作为当前可交易结论。

## 继续价值反思

- 运行前判断：是。若覆盖缺口来自源选择错误，修复后才有资格继续做高质量信号代理。
- 运行后判断：有。覆盖已接近完整，且 `ai4_6∩aligned` 与 `ai4_6_not_aligned` 出现清晰差异，值得做冻结代理。
- 原因：这条线开始接近用户目标里的“AI 选品进一步优化、识别超高质量信号、加大风险投入”，但还缺真实引擎和多起点约束。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段仍是只读证据修复，不是正式候选或重要合入。
