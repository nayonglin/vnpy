# Stage177 predecision lookback 扩展 manifest

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 04:03 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：点时化数据合同扩展 / 入场前 lookback manifest
- 是否重要突破：否，属于 Stage176 阻断后的必要数据合同修复
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - pandas `DataFrame.rolling` 文档：滚动窗口边界由 `closed` 控制，时间窗口必须明确包含/排除端点。
  - pandas windowing user guide：左开/右开窗口可用于避免当前信息污染过去信息。
  - vn.py `TickData` / `BarData` 源码：datetime、volume、turnover、open_interest、OHLC 字段语义足够承接 tick 聚合分钟线。
  - vn.py CTA strategy engine 源码：历史 bar/tick 查询在 start/end 边界上是显式请求对象，不应隐式补数据。
  - SSRN 金融回测过拟合研究：金融时间序列验证要重点防止时间泄漏和 OOS 假象。
- 我的判断：Stage176 证明当前 Stage152/153 全包虽然完整，但入场决策前闭合 bar 远不足以材料化 30m/60m 特征。继续缩短 lookback 或按品种/年份/尾部样本调参会把数据缺口变成过拟合规则；正确动作是统一扩展每个 entry decision 的前置数据合同，再用独立 validator 验证 `bar_end_ts <= decision_ts`。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage177_predecision_lookback_extension_manifest.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `TARGET_MIN_PREDECISION_CLOSED_BARS=61`
  - `UNIVERSAL_LOOKBACK_CALENDAR_DAYS=14`
  - `feature_cutoff_rule=bar_end_ts <= decision_ts`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045 官方路径曲线与 Stage152/153/176 已验收分钟数据合同
- 账户规模：沿用当前线既有曲线口径
- 成本口径：沿用当前线既有曲线口径
- 样本过滤：只取 Stage176 中 `entry_candidate_context=1` 的 `219` 个 entry decision；不按收益、亏损、年份、品种、方向筛选
- 策略/归因口径：只生成前置 lookback 扩展 manifest；不写 feature table、不创建交易规则、不运行 true engine

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `decision=stage177_predecision_lookback_extension_manifest_ready_wait_delivery_no_rule`
  - `entry_window_count=219`
  - `entry_shortfall_window_count=219`
  - `stage176_entry_full_60m_ready_count=0`
  - `extension_required_window_count=219`
  - `extension_request_count=219`
  - `extension_expected_file_count=657`
  - `extension_request_ready_count=0`
  - `total_additional_closed_bars_needed=12803`
  - `min_current_closed_bars=0`
  - `median_current_closed_bars=1`
  - `max_current_closed_bars=30`
  - `estimated_calendar_1m_slot_upper_bound=4415259`
  - request by exchange：CZCE `99`、DCE `30`、GFEX `4`、SHFE `86`
  - priority windows：right-tail `18`、bottom-loss `18`、maxDD `22`、low-resolution `70`、ordinary `91`
  - `feature_table_row_written_count=0`
  - `strategy_rule_created=0`
  - `true_engine_run=0`
  - `ab_triggered=0`
  - `order_api_called=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage177_predecision_lookback_extension_manifest/qmt_roll_stage177_c9_minrisk_predecision_lookback_extension_manifest_report_stage177_predecision_lookback_extension_manifest_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage177_predecision_lookback_extension_manifest/qmt_roll_stage177_c9_minrisk_predecision_lookback_extension_manifest_summary_stage177_predecision_lookback_extension_manifest_v1.csv`
- orders：无
- daily：无
- quality：
  - `qmt_roll_stage177_c9_minrisk_predecision_lookback_extension_manifest_lookback_policy_stage177_predecision_lookback_extension_manifest_v1.csv`
  - `qmt_roll_stage177_c9_minrisk_predecision_lookback_extension_manifest_extension_window_contract_stage177_predecision_lookback_extension_manifest_v1.csv`
  - `qmt_roll_stage177_c9_minrisk_predecision_lookback_extension_manifest_request_manifest_stage177_predecision_lookback_extension_manifest_v1.csv`
  - `qmt_roll_stage177_c9_minrisk_predecision_lookback_extension_manifest_current_shortfall_audit_stage177_predecision_lookback_extension_manifest_v1.csv`
  - `qmt_roll_stage177_c9_minrisk_predecision_lookback_extension_manifest_gate_status_stage177_predecision_lookback_extension_manifest_v1.csv`
  - 5 张 PNG 资金/回撤/shortfall/request/gate 视觉图

## 视觉检查

- 5 张 PNG 均非空，像素跨度均为 `765`。
- `predecision_shortfall_distribution`：绝大多数 entry decision 当前只有 `0-5` 根闭合 1m bar，只有少数夜盘 `00:00` 附近样本到约 `30` 根，全部低于 `61` 根 60m 合同线。
- `request_manifest_load`：CZCE `99`、SHFE `86` 是样本主力，但 DCE/GFEX 也同样缺前置 bar；视觉结论支持统一 lookback，而不是按交易所打补丁。
- `official_path_manifest_status`：官方资金曲线只作上下文展示，Stage177 没有改变资金曲线、交易、仓位或配置；底部图显示 `entry windows=requests=219`，`60m ready=0`，`rows written=0`。

## 结论

- 本阶段结论：Stage177 已把 Stage176 的点时化阻断转化为可执行的前置 lookback 扩展合同。当前问题是普遍的数据可见性不足，不是少数尾部样本或某个交易所异常。
- 是否进入下一步：是
- 下一步：实现/运行 Stage178，按 Stage177 manifest 分批交付 `raw/normalized/proof` 三件套；随后 Stage179 必须重新验证每个 entry decision 在 `bar_end_ts <= decision_ts` 下是否达到 `>=61` 根闭合 1m bar，再决定是否允许只读 feature table。仍不得创建策略规则、true engine、A/B 或正式候选。

## 过拟合反思

- 运行前判断：否。Stage177 只修点时化数据合同，不使用收益、亏损、回撤结果构造规则。
- 运行后判断：否。manifest 对所有 entry decision 使用同一 `14` 自然日 lookback 和同一 `61` 根闭合 bar 目标，没有按品种、年份、方向、right-tail/bottom-loss/maxDD 分叉。
- 原因：本阶段处理的是“决策前能看见什么”，不是“什么阈值赚钱”。视觉结果显示缺口是全局性的，统一扩展比样本内补丁更稳健。

## 继续价值反思

- 运行前判断：是。没有入场前可见的 30m/60m 特征，就不能构建分钟级高质量信号。
- 运行后判断：是。Stage177 产出了 `219` 个可执行扩展请求和明确的 Stage179 验证条件，下一步能把数据合同推进到真实 feature table 前的最后一道点时化门。
- 原因：当前线已完成 Stage152/153 全包验收，唯一阻断是前置 lookback 不足；补齐这个缺口后，才有资格讨论最小风险、高质量信号，而不是从 post-entry/event 标签反推规则。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage177 摘要。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是突破候选或跨线合入。
