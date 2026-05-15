# Stage002 热门品种数据修复与逐个 add-one 验证

- line_id：`futures_trend_hot_universe_expansion`
- 当前模式：day
- 记录时间：2026-05-14 21:34 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：数据覆盖修复 + Stage78-1 A/C 候选验证
- 是否重要突破：是，明确反证了“热门且结构预筛通过即可加入”的简单逻辑
- 是否触发A/B：是；本轮采用 A/C，B 独立品种策略没有可交易意义

## 外部调研与判断

- 参考资料：
  - vn.py / VeighNa 官方 GitHub：`https://github.com/vnpy/vnpy`
  - vn.py CTA 策略模块 GitHub：`https://github.com/vnpy/vnpy_ctastrategy`
  - vnpy_tqsdk 数据服务：`https://pypi.org/project/vnpy_tqsdk/`
  - 趋势跟踪长期证据：`https://arxiv.org/abs/1404.3274`
- 我的判断：
  - 趋势策略扩池的第一性原理不是“热门品种越多越好”，而是增加有流动性、有波动、有趋势结构、且不破坏组合风险路径的独立风险来源。
  - vn.py/TQSDK 链路适合做近端真实合约日线修复；数据修复本身不是 alpha 优化。
  - CTA/趋势跟踪长期证据支持跨市场分散，但必须用固定规则做样本外或分段反证；不能用一次全样本收益直接升级正式池。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage264_hot_product_gap_audit.py`
  - `examples/portfolio_backtesting/repair_qmt_roll_stage265_hot_products_recent_tushare_data.py`
  - `examples/portfolio_backtesting/repair_qmt_roll_stage266_hot_products_recent_tqsdk_data.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage267_hot_product_official_add_one_validation.py`
- 修改脚本：无正式 Stage78-1 策略脚本修改
- 删除脚本：无
- 新增参数：
  - 热门目标品种：`ag/sc/fu/TA/m/p/y/i/v/c/ao`
  - Stage267 候选：`TA/ag/sc/m/p/y/i/v/c/ao`
  - 账户规模：50万
  - A：`official_stage78_1_static18_plus_fu`
  - C：A + 单一候选品种
  - `streak_risk_state_exclusion_mode=profit_only`
- 修改参数：无正式执行参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 至 2026-04-30
- 账户规模：500,000
- 成本口径：沿用 Stage78-1 当前回测成本/滑点口径
- 样本过滤：
  - Stage264：热门缺口覆盖、结构预筛、保证金/流动性审计
  - Stage266：TQSDK 修复 `TA/m/p/y/i/v/ao` 近端主力合约日线
  - Stage267：逐个 add-one，不同时加入多个候选
- 策略/归因口径：
  - A：Stage78-1 正式 18 品种 + `fu.SHFE`
  - C：A + 一个热门候选品种
  - 结构预筛未通过者只能视为 counterfactual，不允许直接 promotion

## 数据修复结果

- Stage265 Tushare 修复尝试：
  - 缺失合约：14
  - 缺失映射日：636
  - 结果：14个全部失败，原因是当前 `TUSHARE_TOKEN` 无效：`您的token不对，请确认。`
- Stage266 TQSDK 修复：
  - 修复目标：`TA.CZCE, m.DCE, p.DCE, y.DCE, i.DCE, v.DCE, ao.SHFE`
  - 保存合约：14/14
  - 覆盖缺失映射日：636/636
  - 修复后缺失合约：0
- 重建 full-market tradable universe：
  - 合格品种：57
  - 11个热门目标全部进入可交易覆盖范围
- 重建 structural prefilter：
  - 结构池：24
  - 新入选品种：`TA.CZCE, UR.CZCE, eb.DCE, pg.DCE, fu.SHFE, sn.SHFE`
  - 目标11品种里，除已在基准的 `fu.SHFE` 外，仅 `TA.CZCE` 直接通过结构预筛。

## 结果

### Stage267 A/C add-one

| 版本 | 层级 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | vs A 判断 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| A: static18+fu | baseline | 26,353,935 | 5170.7870% | -40.1659% | 1.1374 | 2,057,380 | 883 | 43.3628% | 新数据口径下的本轮基准 |
| +TA.CZCE | direct | 17,826,270 | 3465.2540% | -42.5307% | 1.0210 | 1,690,550 | 949 | 42.6804% | 结构过筛但失败，不升级 |
| +ag.SHFE | counterfactual | 45,602,735 | 9020.5470% | -45.6781% | 1.2803 | 2,151,570 | 939 | 42.9167% | 收益强但回撤越过40%，只保留研究线索 |
| +sc.INE | counterfactual | 23,821,000 | 4664.2000% | -39.7260% | 1.1137 | 2,118,540 | 947 | 43.3884% | 收益/Sharpe下降，不升级 |
| +m.DCE | counterfactual | 22,564,665 | 4412.9330% | -42.6489% | 1.1023 | 2,015,030 | 957 | 42.9448% | 收益、回撤、Sharpe均伤害 |
| +p.DCE | counterfactual | 21,854,590 | 4270.9180% | -45.5700% | 1.0705 | 1,781,750 | 945 | 41.8219% | 明显伤害 |
| +y.DCE | counterfactual | 29,058,645 | 5711.7290% | -39.7260% | 1.1798 | 2,218,170 | 933 | 43.6059% | 当前最干净正向线索，需鲁棒性验证 |
| +i.DCE | counterfactual | 16,512,270 | 3202.4540% | -53.7439% | 0.9665 | 2,049,260 | 958 | 41.8367% | 强反证 |
| +v.DCE | counterfactual | 22,488,415 | 4397.6830% | -39.7260% | 1.1030 | 1,961,420 | 917 | 44.1365% | 回撤改善但收益/Sharpe下降 |
| +c.DCE | counterfactual | 26,381,750 | 5176.3500% | -40.3146% | 1.1485 | 2,138,230 | 941 | 42.8274% | 基本中性，优先级低 |
| +ao.SHFE | counterfactual | 25,697,685 | 5039.5370% | -40.1659% | 1.1253 | 2,124,610 | 917 | 43.8298% | 小幅伤害 |

### 额外证据

- 全市场57品种直接跑入策略：期末权益 `740,055`，总收益 `270.0275%`，最大回撤 `-70.1846%`，Sharpe `0.3579`，总滑点 `234,425`，总交易次数 `2,175`，胜率 `37.8871%`。
- 结论：直接全市场扩池会显著破坏 78-1，必须继续用筛选/反证，而不是靠“热门品种全覆盖”。
- full-market AI suitability：
  - AUC：`0.5752`
  - 月度 rank IC：`0.0602`
  - 判断：AI 排名有弱信号，但还不够作为交易开关；只能作为辅助排序/复核工具。

## 输出文件

- Stage264 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage264_hot_product_gap_audit_report_stage264_hot_product_gap_audit_v1.md`
- Stage265 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage265_hot_products_recent_tushare_data_report_stage265_hot_products_recent_tushare_data_v1.md`
- Stage266 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage266_hot_products_recent_tqsdk_data_report_stage266_hot_products_recent_tqsdk_data_v1.md`
- Stage267 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage267_hot_product_official_add_one_validation_report.md`
- Stage267 comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage267_hot_product_official_add_one_validation_comparison.csv`
- Stage267 equity HTML：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage267_hot_product_official_add_one_validation_equity_curves.html`
- Structural prefilter report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_full_market_structural_prefilter_report_full_market_structural_prefilter_v1.md`
- AI suitability report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_full_market_walkforward_report_product_suitability_full_market_wf_v1.md`

## 结论

- 本阶段结论：
  - 不升级正式 78-1。
  - `TA.CZCE` 虽然结构预筛直接通过，但 add-one 明显伤害 A，停止作为直接候选。
  - `y.DCE` 是当前最值得继续的低调线索：收益、回撤、Sharpe 同时改善，但因为结构预筛未过，必须走起始年份、季度冷启动、弱窗口和滑点压力验证。
  - `ag.SHFE` 是高收益线索，但最大回撤扩大到 `-45.6781%`，超过40%风险边界，不能进入实盘候选，只能作为研究分支。
  - `c.DCE` 接近中性，优先级低。
  - `m/p/i/TA` 明确反证；`sc/v/ao` 暂不值得升级。
- 是否进入下一步：是，但只对 `y.DCE` 和 `ag.SHFE` 做鲁棒性反证。
- 下一步：
  1. 对 `y.DCE` 跑 start-year、季度冷启动、弱窗口、1x/3x/5x滑点压力。
  2. 对 `ag.SHFE` 单独检查回撤来源、保证金占用和弱窗口，不以收益漂亮为升级理由。
  3. 暂停 TA 直接加入正式池的讨论。

## 过拟合反思

- 运行前判断：有受控风险。
- 运行后判断：有受控风险，不能直接 promotion。
- 原因：
  - 本轮没有调策略参数，没有为单一品种改阈值，也没有同时组合多个候选救曲线。
  - 风险来自多候选比较：看了10个 add-one 后自然会出现漂亮结果。
  - 因此 `y.DCE/ag.SHFE` 只能进入下一轮反证，不能因为单次全样本胜出直接加入正式执行池。
  - `TA.CZCE` 结构过筛却失败，反而说明本轮没有机械迎合预筛或收益结果。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但范围要收缩。
- 原因：
  - 这条线已经回答“原始18+fu是否覆盖所有热门品类”：没有完全覆盖。
  - 同时也回答“热门品种是否应该全加”：不应该，全市场57品种直接扩池很差。
  - 下一步继续做 `y/ag` 反证有价值；继续扫 `TA/m/p/i/v/sc/ao` 的直接加入价值较低。

## 合入建议

- 是否更新本线 `LINE.md`：是，状态改为 `y/ag 强线索，TA直接候选反证`。
- 是否更新 `research/registry.md`：是，更新本线最新阶段和下一步。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；暂不写 `memory.md`，因为还没有正式候选升级。
