# Stage230 当前正式版2025/2026近端独立窗口回测

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-09-21 14:16 +08:00`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：当前正式版本只读复跑、近端健康度检查
- 是否重要突破：否
- 是否触发A/B：否；同一正式身份、两个用户事前指定的独立冷启动窗口

## 外部调研与判断

- 参考资料：VeighNa 官方 `vnpy_portfoliostrategy` README 与官方组合策略文档；官方模块支持多合约组合策略的历史回测和实盘交易。
- 我的判断：继续复用仓库冻结的 Stage847/C9 真实组合引擎，不新建简化回放器；两个起点都必须重新初始化资金、持仓和策略状态，不能从全周期曲线切片。

## 本次变更

- 新增脚本：`research/lines/futures_trend_stage819_intraday_rules/tools/stage230_current_live_recent_windows.py`
- 修改脚本：无正式策略、配置或生产脚本修改
- 新增测试：`research/lines/futures_trend_stage819_intraday_rules/tests/test_stage230_current_live_recent_windows.py`
- 删除脚本：无
- 新增参数：无策略参数；只新增两个固定研究窗口 `2025-01-01`、`2026-01-01`，统一截止本地数据库最新完整交易日 `2026-09-18`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 正式身份：`Stage847-C9-15w` / `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- production HEAD：`2a7420a9f9550ab912b5c4a302a61acc5740b04c`
- 数据区间：窗口A `2025-01-01 -> 2026-09-18`，实际交易日 `2025-01-02 -> 2026-09-18`；窗口B `2026-01-01 -> 2026-09-18`，实际交易日 `2026-01-05 -> 2026-09-18`
- 账户规模：两个窗口均为 `150,000`
- 成本口径：正式正常成本，包含回测引擎手续费与滑点；表中总滑点单列
- 样本过滤：无品种、方向、交易或日期事后过滤
- 策略/归因口径：两个窗口分别独立冷启动；不继承窗口前权益、持仓或策略状态
- 分钟覆盖：Stage861 冻结分钟源叠加 Stage230 按实际开仓路径补齐的分钟源；窗口A实际开仓 `63/63` 笔、窗口B `35/35` 笔均有对应“合约+开仓日”足量分钟K，覆盖率 `100%`，最低分别 `224/225` 根，低于 `200` 根或缺失时程序 fail-close
- 补丁身份：`minute_patch.csv` 共 `15,105` 行、`49` 个合约日组，SHA256 `529f49fc1e57bf5e7b5737d6e16173ca93e3532585b2825acf01c7fd2740489e`；抓取状态 `49` 行，SHA256 `71dbf209173ec06a047463faff167e3842cb5195c01ff648319bb1341cb6ef64`
- 执行边界：production checkout 只读且 clean；这是纯历史回测路径，不导入 CTP gateway 或订单适配器，不连接 CTP、不提交或撤销订单

## 结果

| 窗口 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 非零交易日胜率 | broker10峰值 | broker100失败天数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025年1月至今 | 261,821.90 | 74.5479% | -20.5272% | 1.199469 | 14,460 | 126 | 50.9434% | 53.1918% | 0 |
| 2026年1月至今 | 143,162.50 | -4.5583% | -19.6926% | -0.152885 | 5,660 | 70 | 51.9231% | 45.4531% | 0 |

- 期末权益：窗口A `261,821.90`；窗口B `143,162.50`
- 总收益：窗口A `74.5479%`；窗口B `-4.5583%`
- 最大回撤：窗口A `-20.5272%`；窗口B `-19.6926%`
- Sharpe：窗口A `1.199469`；窗口B `-0.152885`
- 总滑点：窗口A `14,460`；窗口B `5,660`
- 总交易次数：窗口A `126`；窗口B `70`
- 胜率：非零交易日胜率窗口A `50.9434%`；窗口B `51.9231%`
- 其他关键指标：两个窗口 broker10 保证金/权益峰值均低于100%，分别为 `53.1918%`、`45.4531%`
- 数据纠错：初跑仅使用 Stage861 冻结分钟源，实际开仓路径分钟覆盖不足，产生了窗口A `49.6319%`、窗口B `+5.6077%` 的降级结果；独立 reviewer 发现后已作废。补齐实际开仓日分钟数据并加入100% fail-close闸门后，窗口B修正为 `-4.5583%`，本记录只保留完整语义结果。

## 输出文件

- report：`research/lines/futures_trend_stage819_intraday_rules/outputs/stage230_current_live_recent_windows/report.md`
- summary：`research/lines/futures_trend_stage819_intraday_rules/outputs/stage230_current_live_recent_windows/summary.csv`
- orders：无；只读历史回测，订单API调用为0
- trades：`research/lines/futures_trend_stage819_intraday_rules/outputs/stage230_current_live_recent_windows/trades.csv`
- daily：`research/lines/futures_trend_stage819_intraday_rules/outputs/stage230_current_live_recent_windows/curves.csv`
- quality：`research/lines/futures_trend_stage819_intraday_rules/outputs/stage230_current_live_recent_windows/identity_manifest.json`
- chart：`research/lines/futures_trend_stage819_intraday_rules/outputs/stage230_current_live_recent_windows/equity_nav_drawdown.png`

## 结论

- 本阶段结论：当前正式版在2025年起点累计收益 `74.55%`，但2026年起点为 `-4.56%`、Sharpe `-0.153`；两窗口账户均存活且保证金峰值未触及100%。这说明2025年以来累计仍为正，但2026年以来处于亏损，不能解读为近年表现稳定。
- 是否进入下一步：不产生策略晋级或配置变更；作为当前正式版近端健康度快照保留。
- 下一步：继续按当前正式身份做日常 shadow、真实成交 TCA 和账户对账；若要解释2026年负收益，应另做只读逐笔/品种归因，不按当前窗口调参。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：两个起点由用户事前指定，同一正式身份独立冷启动；未扫描起点、窗口、品种、方向或参数。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有，但价值在健康度监控，不在优化策略。
- 原因：结果明确区分了2025以来的累计正收益与2026以来的负收益；继续扫窗口或参数没有价值，继续积累forward实盘/TCA证据并做只读归因有价值。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加Stage230近端窗口结果。
- 是否更新 `research/registry.md`：否；未改变研究线定位或正式身份。
- 是否追加根目录 `memory.md/back_log.md`：否；这是近端复跑，不是突破、路线废弃或正式版本切换。

## 独立评审

- 状态：`PASS`；`P0=0 / P1=0 / P2=0 / P3=2`。
- 复核结论：两个窗口的 summary/curve/trades 指标逐项一致，权益恒等式通过；实际开仓日分钟覆盖分别为 `63/63`（最低224根）和 `35/35`（最低225根），补丁行数、49个合约日组及SHA256均一致。
- 非阻塞 P3：统一 `200` 根门槛不是按品种/交易所精确推导会话根数；分钟补丁有原始文件、状态表和哈希，但尚无独立一键再生成脚本。本次样本最低 `224/225` 根，不影响结果成立。

## 验证

- Stage229/230 定向测试：`15 passed`
- Stage230 脚本 `py_compile`：通过
- `git diff --check`：研究仓库与 production checkout 均通过；production checkout 保持 clean、HEAD `2a7420a9f9550ab912b5c4a302a61acc5740b04c`
- 全仓默认 pytest：因多个历史研究线存在同名测试模块，收集阶段报 `2 errors`；改用 `--import-mode=importlib` 后完整运行，结果 `3133 passed / 37 failed / 136 subtests passed`。37项失败均在既有 XGBoost/Alpha101/Stage137 冻结身份与产物漂移测试，不涉及 Stage229/230。
