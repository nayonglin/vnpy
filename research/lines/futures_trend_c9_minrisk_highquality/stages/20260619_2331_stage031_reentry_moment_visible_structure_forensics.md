# Stage031 C9 重入当刻可见结构只读法证

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-19 23:31 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：官方 C9/15w stop/retry 重入当刻可见结构归因；不新增交易规则、不改正式配置、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Clare/Seaton/Thomas/Smith, `Trend following, stop losses and the frequency of trading`：https://openaccess.city.ac.uk/id/eprint/17842/8/BLACKBOX%20%20%20SSRN-id2126476.pdf
  - Alpha Architect, `Trend Following: The Epitome of No Pain, No Gain`：https://alphaarchitect.com/trend-following-the-epitome-of-no-pain-no-gain/
  - GitHub breakout/scanner 参考：`trading-breakout-scanner`（https://github.com/jmragsdale/trading-breakout-scanner）、`SimpleBreakoutStrategy`（https://github.com/steffansong/SimpleBreakoutStrategy）
- 我的判断：外部资料支持“假突破/whipsaw 要看确认与风险纪律”，但不支持在历史 stop/retry 结果上继续调小参数。若继续研究重入，只能看重入当刻或之前已可见的信息，如是否站回入场、止损后最深逆行、收复斜率；不能用 `open_after_reentry` 或最终盈亏标签。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage031_reentry_moment_visible_structure_forensics.py`
- 修改脚本：无其他脚本
- 删除脚本：无
- 新增参数：无交易参数；只读 taxonomy：`thin_close_reclaim`、`wick_or_close_back_inside`、`close_body_strong_reclaim`、`close_strong_reclaim`、`missing_reentry_minute`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：官方 C9/15w closed lots `2018-01-15` 至 `2026-06-02`
- 账户规模：`150000`
- 成本口径：沿用官方 C9/15w 输出，总滑点 `2,730,130`
- 样本过滤：只对 Stage030 中已发生重入的 `54` 个 event keys 做重入当刻结构归因；官方 `399` 笔 closed lots 仍作为基准。
- 策略/归因口径：官方 PnL 来自 Stage030 features；Stage861 full minute bars 用于重入当根和 first-stop 到 reentry 前路径特征。`flat_retry_failed/open_after_reentry` 仅是未来归因标签。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot `36.0902%`
- 其他关键指标：
  - reentry event count：`54`
  - reentry lot count：`109`
  - reentry net PnL：`+265,710.60`
  - flat_retry_failed net PnL：`-2,056,381.00`
  - open_after_reentry net PnL：`+2,322,091.60`
  - reentry minute ready events：`54/54`
  - zero-range reentry events：`54/54`
  - volume ratio ready events：`0/54`
  - `thin_close_reclaim`：`32` lots，净 PnL `-446,651.70`；其中未来 retry failed `-1,192,889.40`，未来 open after reentry `+746,237.70`
  - `wick_or_close_back_inside`：`45` lots，净 PnL `+712,362.30`；其中未来 retry failed `-863,491.60`，未来 open after reentry `+1,575,853.90`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage031_reentry_moment_visible_structure_forensics/qmt_roll_stage031_c9_minrisk_reentry_moment_visible_structure_report_stage031_reentry_moment_visible_structure_forensics_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage031_reentry_moment_visible_structure_forensics/qmt_roll_stage031_c9_minrisk_reentry_moment_visible_structure_summary_stage031_reentry_moment_visible_structure_forensics_v1.csv`
- orders：无
- daily：
  - `qmt_roll_stage031_c9_minrisk_reentry_moment_visible_structure_path_reentry_shape_chart_stage031_reentry_moment_visible_structure_forensics_v1.png`
  - `qmt_roll_stage031_c9_minrisk_reentry_moment_visible_structure_reentry_moment_scatter_stage031_reentry_moment_visible_structure_forensics_v1.png`
- quality：
  - `qmt_roll_stage031_c9_minrisk_reentry_moment_visible_structure_event_features_stage031_reentry_moment_visible_structure_forensics_v1.csv`
  - `qmt_roll_stage031_c9_minrisk_reentry_moment_visible_structure_lot_features_stage031_reentry_moment_visible_structure_forensics_v1.csv`
  - `qmt_roll_stage031_c9_minrisk_reentry_moment_visible_structure_event_shape_summary_stage031_reentry_moment_visible_structure_forensics_v1.csv`
  - `qmt_roll_stage031_c9_minrisk_reentry_moment_visible_structure_lot_shape_summary_stage031_reentry_moment_visible_structure_forensics_v1.csv`
  - `qmt_roll_stage031_c9_minrisk_reentry_moment_visible_structure_shape_year_matrix_stage031_reentry_moment_visible_structure_forensics_v1.csv`
  - `qmt_roll_stage031_c9_minrisk_reentry_moment_visible_structure_shape_product_matrix_stage031_reentry_moment_visible_structure_forensics_v1.csv`
  - `qmt_roll_stage031_c9_minrisk_reentry_moment_visible_structure_shape_state_heatmap_stage031_reentry_moment_visible_structure_forensics_v1.png`
  - `qmt_roll_stage031_c9_minrisk_reentry_moment_visible_structure_product_shape_heatmap_stage031_reentry_moment_visible_structure_forensics_v1.png`
  - `qmt_roll_stage031_c9_minrisk_reentry_moment_visible_structure_atlas_page001_stage031_reentry_moment_visible_structure_forensics_v1.png` 至 `atlas_page004`

## 视觉观察

- path chart 显示，重入事件总账只是小幅净正，成功重入右尾被失败重试长期抵消；两个可见形状都不是稳定上行曲线。
- scatter 显示，未来成功和失败在 reentry close gap、latency、止损后最深逆行、收复斜率上明显混杂；存在少数大赢家离群点，不能作为普世规则。
- shape-state heatmap 显示，同一个 `thin_close_reclaim` 同时包含 retry failed 和 open after reentry；`wick_or_close_back_inside` 虽净正，但也有多产品、多年份失败样本。
- product-shape heatmap 显示结果由 OI/FG/sp/lh 等正贡献与 jm/MA/rb/fu 等负贡献拉扯，不能写产品补丁。
- minute atlas 显示，Stage861 的重入当根多数是“触线式重入”，但当根 high/low/open/close 往往退化为同价，量能 ratio 全部不可用；因此 body、close-position、volume expansion 在当前数据口径下不能作为规则证据。

## 结论

- 本阶段结论：`stage031_reentry_visible_shape_no_candidate_mixed_future_outcome`
- 是否进入下一步：不进入交易规则、true engine 或 A/B。
- 下一步：停止基于当前 Stage861 重入当根 body/volume 的规则设想；若继续 stop/retry，只能先修更高质量的 tick/真实分钟成交量源，或只研究当前可用的更长窗口路径结构但必须保持只读。更优先的方向是转向真正外生、入场前可见且覆盖完整的风险源，避免继续围绕 stop/retry 小变体挖历史标签。

## 过拟合反思

- 运行前判断：中等。重入成败天然带未来标签，最容易把 `open_after_reentry` 错写成交易规则。
- 运行后判断：否。本阶段没有写规则、没有参数扫描，并把未来状态和数据退化限制明确记录。
- 原因：成功/失败在所有可用散点上混杂；任何按年份、产品、方向、重入等待、close gap 或历史赢家离群点筛选，都会过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage030 证明 stop/retry 总账净负但成功重入有右尾，需要确认重入当刻能否识别质量。
- 运行后判断：继续 stop/retry 小变体的价值下降；继续目标本身仍有价值。
- 原因：当前分钟源在重入当根的 body/volume 信息不可用，且可见路径特征混杂。若不补更细数据，继续 stop/retry 只会围绕历史标签过拟合；应转向外生源或更高质量数据工程。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage031 摘要与下一步约束。
- 是否更新 `research/registry.md`：否；非正式候选、非重要突破、非跨线合入。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段是本线内部只读归因，不是正式候选或重大突破。
