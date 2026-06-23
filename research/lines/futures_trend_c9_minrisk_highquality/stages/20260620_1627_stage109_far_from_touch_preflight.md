# Stage109 far-from-touch 只读预检

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 16:27 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读预检 / 路线反证；不写真引擎，不新增交易规则，不触发 A/B
- 是否重要突破：否，属于内部 OHLC 候选收束
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Michael Claeys, `When Backtests Guess: How Trading Platforms Silently Fabricate Results`，ResearchGate/SSRN 预印本，指出 OHLC bar 丢失 intrabar 顺序，在同一 bar 内 stop/target 同时可能触发时无法知道先后，典型 scalping 设置下 NQ 1分钟 bar 歧义比例可达 `18.47%`。
  - Backtrader 官方订单执行文档：market order 在下一根 open 执行，close order 在下一根 bar close 执行，stop/limit 只能用 OHLC 四价部分推断触发。
  - Broadfoot/Leveau, `A Guide to Trend Following Strategies`：趋势跟随是长期存在的系统策略，长期记录和危机期表现是核心资产，不应被局部分钟规则轻易切断。
  - CFA Institute 对 Greyserman/Kaminski managed futures 的书评：趋势跟随不是单一入场信号，position sizing、stop-loss、entry/exit、组合结构共同构成系统；细节决定可复制性。
- 我的判断：
  - Stage109 必须只问一个问题：无新数据时，剩下的 `far_from_touch` 是否真有独立信息。若它只是“过了一段时间还没触发 C9 stop/progress”，本质就是 Stage064 已关闭的 time-stop/no-progress 和 Stage102 的 runway bucket，不应包装成新候选。
  - 当前外部资料与本地 Stage102/103 共同指向：分钟 OHLC 可做视觉审计，但不能支撑靠近触价、同 bar 顺序、close 后下一根立即成交的执行优势。远离触价也只有在包含新信息时才有价值。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage109_far_from_touch_preflight.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；固定只读 proxy 为 Stage102 已有 `gt_five_bar_runway` 与 `no_c9_stop_or_progress_before_day_end`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage102 `219` 笔 timestamp-ready replay rows、Stage108 risk map、Stage045 官方资金曲线。
- 账户规模：官方 C9/15w 既有路径，仅做只读映射。
- 成本口径：沿用官方路径，未新增成交。
- 样本过滤：无交易过滤；只把 `gt_five_bar_runway` 与 `no_c9_stop_or_progress_before_day_end` 作为 frozen far-from-touch proxy 做预检。
- 策略/归因口径：不生成 C 策略、不写真引擎；检查 proxy 是否远离近触价、是否不依赖 close-next-bar collision、是否与旧形状重叠、是否含独立新信息、是否保护右尾并分离 bottom-loss。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `timestamp_ready_order_count=219`
  - `frozen_far_from_touch_proxy_order_count=105`
  - `frozen_far_from_touch_proxy_pnl_sum=16,945,848.10`
  - `frozen_far_from_touch_proxy_right_tail_count=9`
  - `frozen_far_from_touch_proxy_bottom_loss_count=9`
  - `frozen_far_from_touch_proxy_maxdd_context_count=10`
  - `frozen_far_from_touch_proxy_product_count=19`
  - `frozen_far_from_touch_proxy_year_count=7`
  - `far_proxy_old_shape_overlap_count=105`
  - `far_proxy_independent_signal_count=0`
  - `state_tail_conflict_count=3`
  - `promotion_gate_pass_count=4/9`
  - `preflight_rule_allowed=0`
  - `true_engine_allowed=0`
  - `strategy_feature_usable=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage109_far_from_touch_preflight/qmt_roll_stage109_c9_minrisk_far_from_touch_preflight_report_stage109_far_from_touch_preflight_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage109_far_from_touch_preflight/qmt_roll_stage109_c9_minrisk_far_from_touch_preflight_summary_stage109_far_from_touch_preflight_v1.csv`
- orders：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage109_far_from_touch_preflight/qmt_roll_stage109_c9_minrisk_far_from_touch_preflight_preflight_rows_stage109_far_from_touch_preflight_v1.csv`
- daily：官方资金路径图 `qmt_roll_stage109_c9_minrisk_far_from_touch_preflight_official_path_chart_stage109_far_from_touch_preflight_v1.png`
- quality：
  - `qmt_roll_stage109_c9_minrisk_far_from_touch_preflight_state_summary_stage109_far_from_touch_preflight_v1.csv`
  - `qmt_roll_stage109_c9_minrisk_far_from_touch_preflight_acceptance_overlap_stage109_far_from_touch_preflight_v1.csv`
  - `qmt_roll_stage109_c9_minrisk_far_from_touch_preflight_distinctness_matrix_stage109_far_from_touch_preflight_v1.csv`
  - `qmt_roll_stage109_c9_minrisk_far_from_touch_preflight_promotion_gate_stage109_far_from_touch_preflight_v1.csv`
  - `qmt_roll_stage109_c9_minrisk_far_from_touch_preflight_atlas_manifest_stage109_far_from_touch_preflight_v1.csv`
  - 视觉图：official path、state contribution、promotion gate、distinctness heatmap、5 页分钟 atlas

## 结论

- 本阶段结论：`stage109_far_from_touch_preflight_degenerates_to_no_progress_no_rule`。
- 是否进入下一步：是，但不沿内部 minute-OHLC 候选继续包装；只能转数据采购/执行回放，或做“正式路径不变”的外层监控/数据合同。
- 下一步：
  - 优先路线：授权 historical quote/depth 或 broker/production execution replay，按 Stage103 数据合同做 point-in-time 审计。
  - 若没有新数据，内部 OHLC 不再提出新交易候选；只能整理数据采购清单、执行回放字段、或做 forward-watch，不进入 true engine/A/B。

## 过拟合反思

- 运行前判断：否。Stage109 是预声明反证，不扫阈值，不按亏损样本调参数。
- 运行后判断：否。结果没有把 `gt_five` 或 `no event` 交易化，反而确认它们全部与旧 time-stop/no-progress 形状重叠。
- 原因：proxy 的 `105` 笔全部由“未触发 C9 stop/progress 的时间/路径缺席”定义，`independent_signal_count=0`；即使跨 `19` 产品、`7` 年，也只是广泛存在的路径状态，不是新的普世信息。

## 继续价值反思

- 运行前判断：是。Stage108 留下的唯一内部路线必须被验证，否则容易把同一个 OHLC 缺陷换名字重启。
- 运行后判断：是，但价值已经从策略候选转为路线收束。继续在内部 minute-OHLC 上造候选价值很低；继续价值在于拿新数据或执行回放。
- 原因：far-from-touch proxy 含 `9` 个右尾、`9` 个 bottom-loss、`10` 个 maxDD-context，视觉 atlas 显示同一类 runway 内既有 `jm2509/SH405/lh2505/au2510` 等右尾，也有 `SH607/cu2307/ru2409/lh2409` 等亏损，不能分离风险。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage109 结论与后续边界。
- 是否更新 `research/registry.md`：否，非正式候选、非跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破版本。
