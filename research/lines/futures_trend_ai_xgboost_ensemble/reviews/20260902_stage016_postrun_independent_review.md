# Stage016 运行后独立结果Review

## 结论

- 严重度：`P0=0 / P1=0 / P2=0`。
- 确认决策：`stage016_development_oos_proxy_fail_stop_no_holdout`。
- 当前九特征、固定浅树、双回归头门控形状必须停止。
- 不允许调参救援、运行development真实引擎A/C、读取sealed holdout或接入线上。

## 审查发现

P0、P1、P2均无。未发现会推翻失败结论的身份、PIT、模型、选择器、效果计算或产物完整性缺陷。

关键结果不是程序错误，而是模型没有学到区分能力：

- 30/30个模型均为64棵单叶树，`split_nodes=0`。
- 每个OOS月，两个回归头对9个候选分别只输出一个相同常数。
- 两头预测在15个月全部为负。
- 所有候选分位均为`0.555555...`，最终由预注册tie-break选择rank10。
- C的双正门15/15个月均未打开，实际替换为0。

## 身份与产物

- `run_authorization` SHA：`6134c97c795224afbbaaada1539995a4d14d223e8643b9fa92a5ab5d6330f69d`，五个绑定文件当前SHA全部匹配。
- 输入身份在运行前、训练后、效果评价后完全一致，并与当前文件身份一致。
- `artifact_manifest.json`精确覆盖41项产物，连同manifest共42个文件；全部SHA和大小一致。
- 30个UBJ模型与`model_manifest`、fold audit逐项匹配。
- 15折测试范围为`2024-04-30 -> 2025-06-30`，训练月数严格`24..38`，训练行数`216..342`，每折测试9行，PIT违规0。
- 独立重新训练两遍后，预测差、模型SHA差、已发布模型预测差均为0。

## 选择与效果

- 从`oos_predictions.csv`独立重算分位、双头等权分数、tie-break及A/B/C门控，15个月选择字段不一致数0、浮点最大差0。
- B选择rank10为15/15，C选择rank10为15/15。
- 从Stage015原始`development_labels.csv`重新回填五项realized标签，不一致数0。
- 替换月份0；收益增量、回撤改善及各自剔除最好月结果全部为0。
- 只有两个“分年非负”门因全零通过，其余7个效果门失败；`effect_qualification.json`与独立重算完全一致。
- 这不是“XGBoost策略收益为0”，而是XGBoost从未获得替换第10席的资格，不能据此发布组合收益或回撤指标。

## 隔离与测试

- 只读取冻结development标签，日期截至`2025-06-30`；读取sealed holdout标签路径数为0。
- runner没有CTP、订单或生产写入入口；无partial/quarantine残留。
- 生产目录保持clean，HEAD仍为`d492ee072aa5a9d71477235d79f17d2a5db59db3`。
- Stage016专项测试：`25 passed`；整线测试：`123 passed`。
- 本次审查未修改文件。

## 最终判断

- 本次冻结运行本身没有结果后调参，不能认定为运行过程过拟合；但现在继续调整树参数、阈值、rank、年份或品种，将直接构成development结果后的过拟合救援。
- 当前形状继续研究没有价值，必须停止。
- 若仍探索XGBoost，只能另立具有新结构性理由的假设、重新预注册，并保持sealed holdout不可见，不能在Stage016上修改参数后重跑。
- reviewer agent：`01a05f50-0d25-7213-a2f2-eccac9c53a5c`。
