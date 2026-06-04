# Stage302 full57 non-DCE new-family scout

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 03:22 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读结构审计；读取 Stage541 全57产品机会图、Stage548 source matrix、Stage601 source-first rescreen，确认是否存在非DCE、source稳定、低相关、材料性过线的新独立产品族；不做新收益回放、不改策略、不生成白名单。
- 是否重要突破：否，但它把“扩大品种池”边界从38个非核心产品补全到57个全产品，确认瓶颈不是产品列表漏扫，而是可部署有效风险槽不足。
- 是否触发A/B：否。`promotion_allowed=false`、`paper_selector_allowed=false`、`trading_whitelist_allowed=false`。

## 外部调研与判断

- 参考资料：
  - Man Group `Trend Following: The Optimal Market Mix for a Trend Follower`
  - `Optimal Allocation of Trend Following Strategies`
  - `skfolio` 的 Hierarchical Risk Parity / hierarchical clustering 文档
- 我的判断：
  - 用户提出的“减少单笔风险、扩大品种池、每年抓部分品种趋势、避免高相关风险”方向是正确的，但第一性原理不是产品越多越好，而是有效风险槽越多越好。
  - 有效风险槽至少要同时满足：低相关、不同产品族或不同风险驱动、真实数据源可持续、容量/TCA可落地、历史机会不只是单年偶然峰值。
  - 本轮继续做全产品结构复筛不是过拟合；它没有调入场、出场、阈值或TopN，只把已有证据按 core reuse / source / corr / materiality 分层。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage602_full57_non_dce_new_family_scout.py`
- 修改脚本：无策略脚本修改；审计脚本内曾修正图表标注和高相关正收益候选统计口径。
- 删除脚本：无。
- 新增参数：
  - `P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1=4`
  - `TARGET_EFFECTIVE_SLOTS=7`
  - `MAX_CORE_CORR_WATCH=0.10`
  - `SOURCE_RICH_COMPONENT_PCT=60.0`
  - `MATERIAL_PRODUCT_PNL=10000.0`
  - `MATERIAL_FAMILY_PNL=25000.0`
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不做新回测；读取 Stage541 全57单品种机会图、Stage548 外生源覆盖矩阵、Stage601 风险槽复筛。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：完整57产品；核心产品只做“已有核心贡献，不可复用为扩池新槽”的边界标注；38个非核心产品沿用 Stage601 复筛状态。
- 策略/归因口径：全产品风险槽 scout，不生成TopN、不做收益择优、不扫相关性阈值。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`full57_non_dce_scout_no_deployable_new_family`
  - products total：`57`
  - noncore products total：`38`
  - core products total：`19`
  - non-DCE new-family scout products：`8`
  - deployable non-DCE new family slots now：`0`
  - effective slots now：`4`
  - effective slots after full57 non-DCE：`4`
  - effective slots if black_ferrous source resolved：`5`
  - target effective slots：`7`
  - slot risk now if equal：`25.0%`
  - slot risk target if equal：`14.2857%`
  - hard gates：`4/7`
  - promotion allowed：`false`
  - paper selector allowed：`false`
  - trading whitelist allowed：`false`

## 全57复筛结论

- 全57产品没有漏出新的非DCE可部署风险槽。Stage601 的38个非核心产品已经覆盖完整非核心集合；本轮新增的信息主要是19个核心产品不能被重复当作扩池新alpha。
- `FG.CZCE/AP.CZCE/OI.CZCE/lc.GFEX/hc.SHFE` 等核心产品有正贡献，但它们已经属于 Stage526/核心体系；把它们再算作“扩池新增品种”会高估分散度。
- 当前P0仍只有 `4` 个有效独立槽，等权单槽风险约 `25%`；全57复筛后仍是 `4` 槽。
- 若未来解决 `black_ferrous(j.DCE/i.DCE)` 的 DCE source/TCA，最多先到 `5` 槽、等权单槽约 `20%`，仍未达到 `7` 槽、约 `14.3%` 单槽目标。
- 非DCE新族中，`br.SHFE` 是唯一有材料性正收益的代表，但核心相关 `0.2783`，明显越过 `0.10` 观察线；不能作为分散槽。
- `soft_agri/precious_metals/SF.CZCE` 等 source 较完整且低相关，但历史机会不足或为负；当前只允许 forward monitor，不投入TCA、不paper。

## 图表视觉复盘

- 图表路径：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage602_full57_non_dce_new_family_scout_chart_stage602_full57_non_dce_new_family_scout_v1.png`
- 第一次视觉检查发现左下候选缺口标签重叠、右上标题过长；已修正为颜色图例+短相关性标注后重跑。
- 第二次视觉复盘通过：左上散点能区分核心已有、P0已有槽、同族深度、DCE blocker、高相关拒绝；右上 family bar 明确核心贡献不能复用；左下非DCE scout 显示 `br.SHFE` 高相关、`soft_agri/precious_metals/SF` 无材料性；右下风险槽情景显示当前 `4`、DCE解决后 `5`、目标 `7`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage602_full57_non_dce_new_family_scout_report_stage602_full57_non_dce_new_family_scout_v1.md`
- product map：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage602_full57_non_dce_new_family_scout_product_map_stage602_full57_non_dce_new_family_scout_v1.csv`
- family summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage602_full57_non_dce_new_family_scout_family_summary_stage602_full57_non_dce_new_family_scout_v1.csv`
- non-DCE scout：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage602_full57_non_dce_new_family_scout_non_dce_new_family_scout_stage602_full57_non_dce_new_family_scout_v1.csv`
- slot scenarios：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage602_full57_non_dce_new_family_scout_slot_scenarios_stage602_full57_non_dce_new_family_scout_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage602_full57_non_dce_new_family_scout_gates_stage602_full57_non_dce_new_family_scout_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage602_full57_non_dce_new_family_scout_decision_stage602_full57_non_dce_new_family_scout_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage602_full57_non_dce_new_family_scout_chart_stage602_full57_non_dce_new_family_scout_v1.png`

## 结论

- 本阶段结论：方向成立，但当前不能晋级。低单笔风险+扩池+避相关应该继续作为结构目标；但当前没有新的非DCE独立产品族可交易，扩池不能靠“把57个产品都列进来”解决。
- 是否进入下一步：进入下一步，但不是收益回测或白名单；继续做可执行性补证和新风险族来源发现。
- 下一步：
  - P0继续补 `v/ao/lu` route/event/official endpoint/TCA，`y/c` 继续同族同向 top1-only。
  - `black_ferrous(j/i)` 只走可授权DCE源、交易所可下载替代源或稳定准官方源；普通 browser-cookie 路线已降级。
  - 非DCE新族只允许 source-first forward monitor；只有出现低相关、source稳定、材料性正收益、容量/TCA可过线的家族，才允许进入下一层paper协议。

## 过拟合反思

- 运行前判断：否。本阶段是全产品结构复筛，不根据结果改策略参数。
- 运行后判断：否。没有新增回放收益、没有扫TopN、没有扫小数阈值、没有把正收益产品直接提升为白名单。
- 原因：核心动作是把已知产品按风险族、核心/非核心、source、相关性、材料性分类；这属于可执行性边界审计，不是收益拟合。

## 继续价值反思

- 运行前判断：有价值。因为“选对品种”和“扩大池子”如果成立，应该能在全57产品中找到额外低相关风险槽。
- 运行后判断：仍有价值，但应缩窄路径。继续随机扩池价值低；继续找可执行 source 和真实独立风险驱动有价值。
- 原因：本轮证明产品列表不缺，缺的是可部署独立槽。下一步应该追求“source稳定的新风险驱动”，而不是继续宽池收益扫描。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage302 当前状态。
- 是否更新 `research/registry.md`：是，更新本研究线最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重大突破或跨线合并。
