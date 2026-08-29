# Stage063：正式Stage037、Top9、Top10多周期对比

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：day
- 记录时间：2026-08-29 23:26（Asia/Shanghai）
- 工作区/分支：`.worktrees/stage056-ai-top14-plus-fu` / `codex/stage063-ai-top9-top10-multicycle`
- 阶段性质：用户明确要求的离线TopN边界多周期诊断
- 是否重要突破：否
- 是否触发A/B：是，A=正式Stage037，B=Top9，C=Top10

## 外部调研与判断

- 参考资料：Lopez de Prado 关于金融研究多重检验偏差的论文（https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3177057）；公开walk-forward实现对独立窗口与独立初始资金的说明（https://github.com/fxstr/walk-forward）。
- 我的判断：多起点验证可以暴露单一全周期复利路径掩盖的启动时点依赖，但不能消除Top9/Top10来自后验TopN扫描的选择偏差，因此结果只作离线诊断，不自动晋升。

## 运行前冻结

- 数据区间：`2018-01-01` 至 `2026-08-28`。
- 账户规模：每窗15万元、空仓、独立引擎和独立账户状态启动。
- 成本口径：沿用Stage037/Stage061/Stage062既有真实引擎成本、滑点和保证金口径，不改参数。
- A：活动 `CURRENT` 与远端master中的Stage037，ruleset=`stage037_stage034_long_short_mirror_hard_block_v1`，AI Top8+fu，共9品种。
- B：Stage062 Top9+fu，共10品种；只改变AI eligibility路径与strategy标识。
- C：Stage061 Top10+fu，共11品种；只改变AI eligibility路径与strategy标识。
- 全周期：3臂复用Stage062并逐值核验summary与2101点curve。
- 滚动窗口：1/2/3年每个可完整覆盖的1月1日和6月1日起点，共42窗；A的42窗复用Stage059并逐窗校验，B/C新增84次真引擎运行。
- 五图：全周期、1年网格、2年网格、3年网格、combined/January/June聚合摘要；正式版黑色虚线、Top9红色、Top10蓝色。
- 完整周期门：候选收益不低于正式A；最大回撤恶化不超过2pp；Sharpe不低于A超过0.02；滑点不超过A的105%；账户存活；broker10超100%天数不劣化。
- 滚动聚合门：收益胜/非劣率不低于50%；收益差中位不低于0；DD与Sharpe非劣率不低于80%；聚合滑点不超过105%；账户存活；DD50和broker100失败数不劣化。每档分别计算combined、January、June，任一失败不能由其他周期覆盖。
- checkpoint：84个候选窗口保留首跑时的原engine runtime hash，明确只覆盖候选引擎、数据库与eligibility，不事后冒充新合同。当前runner的新runtime hash用于未来重跑，已纳入Stage059/061/062实际复用文件；本次发布另以publication hash锁定冻结提交 `ec84131ebcb36563415c61b4049601876fd652d5` 的Git blob、绘图脚本及五图，且复用目录存在未跟踪文件时直接失败。

## 身份边界与用户授权

- checkout/CURRENT：Stage037 / `m0016_20260829T034012+0800_374df2d52e4f` / source `374df2d52e4f17220c5e2d4cae76f50d45bec47d`。
- 远端master：`a7d8599e9d895aa6fc7c73b25ef7f2e48d4e4c14`，与Stage037正式物料匹配。
- 稳定生产：仍是Stage021-Q / m0015 / source `c097d7836dd4133a88e61effa230b473c24355b3`，与Stage037不一致。
- 首次预检因此停止；用户随后明确确认按远端master/CURRENT的Stage037作为离线正式对照继续。
- 本授权只允许离线回测身份豁免，不允许晋升、安装生产、连接CTP或调用order/send/cancel API。

## 本次变更

- 新增脚本：`stage063_stage037_top9_top10_multicycle.py`。
- 新增测试：`test_stage063_stage037_top9_top10_multicycle.py`。
- 新增参数：无策略参数；仅新增研究arm B=Top9、C=Top10和Stage063运行身份。
- 修改参数：无。
- 删除参数：无。

## 运行前反思

- 是否过拟合：是，风险高。Top9/Top10是在已经观察Top10-Top19全周期响应后选择的边界点，本阶段不能把任何漂亮窗口当作无偏发现。
- 是否有价值继续：有，但只限本次固定多周期诊断。它可以判断Top10全周期优势及Top9近似正式版表现是否跨1月/6月起点稳定；结果后不再扫描TopN、起点或门槛救参。

## 回测结果

- A 正式Stage037：期末权益 `16,859,940.60`、总收益 `11139.9604%`、最大回撤 `-39.9147%`、Sharpe `1.538821`、总滑点 `1,659,555`、总交易次数 `734`、非零交易日胜率 `53.2310%`、broker10峰值 `93.5807%`、超100%天数 `0`。
- B Top9：期末权益 `16,871,625.40`、总收益 `11147.7503%`、最大回撤 `-39.9147%`、Sharpe `1.517586`、总滑点 `1,762,115`、总交易次数 `766`、非零交易日胜率 `53.3650%`、broker10峰值 `93.5807%`、超100%天数 `0`。
- C Top10：期末权益 `21,870,488.80`、总收益 `14480.3259%`、最大回撤 `-39.9147%`、Sharpe `1.586976`、总滑点 `2,163,390`、总交易次数 `798`、非零交易日胜率 `53.7348%`、broker10峰值 `93.5807%`、超100%天数 `0`。
- Top9全周期相对A只多 `7.7899pp` 收益，回撤相同，但Sharpe低 `0.021236`、滑点比 `106.18%`；严格失败Sharpe和105%成本两门。
- Top10全周期相对A多 `3340.3655pp` 收益，回撤相同、Sharpe高 `0.048155`，但滑点比 `130.36%`；严格失败105%成本门。

### Top9 对正式版多周期

- 1年combined：16窗，收益胜/非劣 `14/16=87.50%`、收益差中位 `0.0000pp`、DD非劣 `15/16=93.75%`、Sharpe非劣 `15/16=93.75%`、滑点比 `1.0487`；combined通过，但January滑点比 `1.0593` 失败。
- 2年combined：14窗，收益胜/非劣 `12/14=85.71%`、收益差中位 `+4.2577pp`、DD非劣 `11/14=78.57%`、Sharpe非劣 `14/14=100%`、滑点比 `1.0431`；combined及June的DD非劣率失败。
- 3年combined：12窗，收益胜/非劣 `9/12=75.00%`、收益差中位 `+11.0517pp`、DD非劣 `10/12=83.33%`、Sharpe非劣 `10/12=83.33%`、滑点比 `1.0497`；combined通过，但January Sharpe非劣仅 `4/6=66.67%`，June滑点比 `1.0550`，两组失败。
- 最弱收益为3年 `2020-01`：相对正式少 `71.0267pp`、回撤恶化 `2.3705pp`、Sharpe低 `0.0685`。最大回撤恶化为1年 `2023-01` 的 `5.0101pp`。
- 结论：Top9在多数窗口与正式版相同或小幅改善，但不是稳定改进；全周期与多个January/June分组存在硬失败。

### Top10 对正式版多周期

- 1年combined：16窗，收益胜/非劣 `14/16=87.50%`、收益差中位 `0.0000pp`、DD非劣 `13/16=81.25%`、Sharpe非劣 `15/16=93.75%`、滑点比 `1.1248`；三组均因成本失败，January另有DD非劣 `75%` 失败。
- 2年combined：14窗，收益胜/非劣 `13/14=92.86%`、收益差中位 `+13.2917pp`、DD非劣 `10/14=71.43%`、Sharpe非劣 `14/14=100%`、滑点比 `1.1422`；combined/January/June均失败DD与成本，June还新增1个broker100失败窗。
- 3年combined：12窗，收益胜/非劣 `10/12=83.33%`、收益差中位 `+35.5050pp`、DD非劣 `8/12=66.67%`、Sharpe非劣 `12/12=100%`、滑点比 `1.1470`；三组均失败DD与成本，June还新增1个broker100失败窗。
- 最弱收益为3年 `2019-06`：相对正式少 `52.4800pp`；最大回撤恶化为2年 `2023-06` 的 `5.8361pp`。1年 `2025-06` Sharpe低 `0.0860`。
- 结论：Top10的收益优势跨多数起点存在，但其来源同时伴随稳定的交易成本扩张和更差的回撤路径；不能把更高全周期权益等同于更优正式策略。

## 产物与运行证据

- output：`artifacts/stage063_stage037_top9_top10_multicycle/`。
- report：`stage063_multicycle_report.md`。
- summary/comparison/aggregate/curve：`stage063_window_summary.csv`、`stage063_window_comparison.csv`、`stage063_cycle_aggregate.csv`、`stage063_equity_curves.csv`。
- 五图：`stage063_full_period_equity_abc.png`、`stage063_equity_curves_1y_abc.png`、`stage063_equity_curves_2y_abc.png`、`stage063_equity_curves_3y_abc.png`、`stage063_cycle_aggregate_abc.png`。
- 运行：单次连续首跑生成84个候选checkpoint，复用checkpoint为0；没有因策略、校验或图片问题重跑任何真引擎窗口。
- 图片：首轮图例含两个系统字体缺字；新增独立纯绘图入口 `stage063_render_charts.py`，只读取最终CSV重绘五图，不改变runner合同、数值产物或checkpoint。
- 验证：新增Stage063测试从最初模块不存在的 `5 failed` 转为合同通过；纯绘图入口经历缺模块与DtypeWarning两次红灯后修复。最终逐窗从曲线独立复算129个臂窗全部关键指标和27行聚合；新增复用源Git漂移失败测试与图片SHA追溯测试后，Stage063聚焦测试 `10 passed`。
- 安全边界：order/send/cancel=`0/0/0`，`ctp_connected=false`；未改正式物料、远端master或稳定生产。
- 独立review：首轮数值复算确认129臂窗、27行聚合、84个checkpoint与Stage059/062复用值均一致，发现P0=0、P1=1、P2=0、P3=1。P1为复用源未锁冻结Git blob，P3为图片重绘SHA未入decision；二次复核确认P3关闭，但指出旧engine hash与当前runner hash不能混称。现已分层记录engine/current-runner/publication三份合同，publication逐文件锁Git blob、绘图脚本与五图，未重跑真引擎。最终独立回签 `PASS`，P0/P1/P2/P3=`0/0/0/0`；现场复算84个checkpoint均绑定旧engine hash、当前runner及publication hash逐字一致，数值与安全边界未变。

## 结论

- 决策：`offline_top9_top10_multicycle_has_hard_fail_keep_stage037`。
- Top9全部门通过：`false`；Top10全部门通过：`false`；`promote_to_official=false`。
- 是否进入下一步：否。保留正式Stage037，停止继续扫描TopN、起点、周期或事后放宽成本/DD/Sharpe门。

## 运行后反思

- 是否过拟合：是，风险仍高。固定多周期本身没有新增调参，但Top9/Top10选择来自已观察过的TopN响应；结果不能被解释为无偏样本外发现。
- 是否有价值继续：本次有价值且已完成。它证明Top10的高收益伴随跨周期成本和回撤代价，也证明Top9并未形成稳定优于正式版的平台；继续扫描宽度已经没有价值。
