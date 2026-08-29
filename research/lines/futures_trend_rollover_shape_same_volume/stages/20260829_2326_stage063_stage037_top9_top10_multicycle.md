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
- checkpoint：键包含冻结runtime合同、数据库SHA、候选eligibility SHA、远端master、arm与窗口；只有文件SHA和窗口覆盖复验通过才可复用。

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

## 回测结果（待运行后补充）

- 期末权益：待运行。
- 总收益：待运行。
- 最大回撤：待运行。
- Sharpe：待运行。
- 总滑点：待运行。
- 总交易次数：待运行。
- 胜率：待运行。
- 多周期门禁：待运行。
- 独立review：待回测产物生成后执行。

