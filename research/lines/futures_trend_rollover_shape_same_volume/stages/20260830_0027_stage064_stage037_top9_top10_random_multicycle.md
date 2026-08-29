# Stage064：Stage037、Top9、Top10随机多周期压力测试

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：day
- 记录时间：2026-08-30 00:27（Asia/Shanghai）
- 工作区/分支：`.worktrees/stage056-ai-top14-plus-fu` / `codex/stage064-random-multicycle`
- 阶段性质：用户确认的离线随机起点多周期反证
- 是否重要突破：否
- 是否触发A/B：是，A=正式Stage037 Top8+fu，B=Top9+fu，C=Top10+fu

## 外部调研与判断

- 参考资料：Bailey等《The Probability of Backtest Overfitting》（https://papers.ssrn.com/sol3/Papers.cfm?abstract_id=2326253）；Politis与Romano《The Stationary Bootstrap》（https://www.tandfonline.com/doi/abs/10.1080/01621459.1994.10476870）；White《A Reality Check for Data Snooping》（https://onlinelibrary.wiley.com/doi/pdf/10.1111%2F1468-0262.00152）。
- 我的判断：随机起点可以补充固定1月/6月起点，观察候选优势出现的频率与尾部；但窗口会重叠，不能当作192个统计独立样本，也不能覆盖Stage063已经出现的固定多周期硬失败。随机窗口和门槛必须在结果前冻结，不能失败后重抽。

## 本次变更

- 新增脚本：`stage064_stage037_top9_top10_random_multicycle.py`。
- 新增测试：`test_stage064_stage037_top9_top10_random_multicycle.py`。
- 新增输入：`stage064_stage037_top9_top10_random_windows.csv`。
- 修改脚本：无策略脚本修改。
- 删除脚本：无。
- 新增参数：1/2/3年各随机64个起点；总窗口192；随机种子 `1246746679971163672`。
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测参数与冻结合同

- 数据区间：`2018-01-02` 至 `2026-08-28`，数据库SHA `ee83eae2159afec2b745a5827f73aaf9da1e71d65af2c0a624496555c08b6ebe`。
- 窗口：1/2/3年各从所有可完整覆盖的实际交易日起点中均匀无放回抽64个；三臂严格共用相同窗口。
- 窗口计划SHA：`5a0997ea77eb0f17167810f72789dc52f18a7ec71c5b42ccf03de7d2e7c5af12`。
- 账户规模：每个arm-window均为15万元、空仓、独立引擎/持仓/账户状态冷启动。
- 成本口径：沿用Stage037/Stage063既有真实引擎成本、滑点、保证金和风险参数。
- A：master/CURRENT中的Stage037 m0016 Top8+fu；B：Top9+fu；C：Top10+fu。B/C只改变AI eligibility路径和strategy标识。
- 总运行：192窗×3臂=`576`个独立真引擎回测；每臂窗成功后写SHA校验checkpoint。
- 门禁：每个1/2/3年和全部随机窗分别要求收益胜/非劣率不低于50%、收益差中位不低于0、DD非劣率不低于80%、Sharpe非劣率不低于80%、聚合滑点不超过正式版105%、账户存活且DD50/broker100失败不劣化。
- 固定边界：Stage063固定1月/6月门已经失败；即使随机窗口通过，也不能晋升或救回候选。
- 身份边界：checkout/master为Stage037，稳定生产仍为Stage021-Q；沿用用户对本连续离线研究的显式身份豁免，不允许安装、晋升、CTP或订单API。

## 运行前反思

- 是否过拟合：是，风险高。Top9/Top10来自看过Top10–19和Top9结果后的后验边界候选。
- 是否有价值继续：有，但只限这一次预冻结随机压力测试。它能衡量固定窗口结论是否只是少数起点现象；完成后不继续扫TopN、种子、样本量或窗口。

## 回测结果（运行后补充）

- A期末权益/总收益/最大回撤/Sharpe/总滑点/总交易次数/胜率：待运行。
- B期末权益/总收益/最大回撤/Sharpe/总滑点/总交易次数/胜率：待运行。
- C期末权益/总收益/最大回撤/Sharpe/总滑点/总交易次数/胜率：待运行。
- 随机门与最弱窗口：待运行。

## 输出文件（运行后补充）

- report：待生成。
- summary/comparison/aggregate/curve：待生成。
- 五图：待生成。
- decision：待生成。

## 结论（运行后补充）

- 本阶段结论：待运行。
- 是否进入下一步：待运行。
- 下一步：完成独立review后停止TopN随机扫描。

## 运行后反思（运行后补充）

- 是否过拟合：待运行。
- 是否有价值继续：待运行。

## 合入建议

- 是否更新本线 `LINE.md`：结果后更新。
- 是否更新 `research/registry.md`：否，研究线不变。
- 是否追加根目录 `memory.md/back_log.md`：否，除非出现改变研究政策的重要突破；本阶段预期仅为稳健性反证。
