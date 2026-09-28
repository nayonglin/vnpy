# Stage001 metadata写副作用预检通过

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v3`
- 记录时间：2026-09-05 18:17 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：正式metadata构造的零回放I/O隔离资格
- 是否重要突破：否；这是继续事件资格研究所需的基础设施门，不是有价值回测候选
- 是否触发A/B：否
- 是否触发reviewer：否；没有收益和回撤结果

## 本次改动

- 新增双冷worker metadata-only runner与13项测试。
- 固定1420个只读输入，绑定V2唯一失败证据、V3代码、正式材料、生产源码、元数据源和期望派生文件。
- 仅在worker内部临时重定向生产候选模块的`UNIVERSE_PATH`与`AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH`，上下文退出后按对象身份恢复。
- 两个派生CSV只写入worker私有`derived/`，随后与冻结正式文件逐bytes比较。
- worker采用`/usr/bin/sandbox-exec`和`.py311/bin/python -I -S -B`；禁止网络、外部写入、子进程、标签、holdout、模型、预测、CTP、账户、订单和正式回放。
- 未修改任何策略逻辑、样本参数、模型参数、正式材料或生产文件。

## 新增参数

- `input_file_count=1420`
- 冷worker数量：2（A1/A2）
- 正式回放允许次数：0
- metadata调用次数：每个worker 1次
- 派生输出白名单：每个worker私有`derived/`目录下2个固定CSV

## 修改参数

- 无策略参数修改。
- 相比V2 Stage002，将`_metadata()`的两个确定性写目标从workspace符号链接落点收窄到worker私有路径。

## 删除参数

- 无。

## 输入合同

- 逻辑键SHA256：`55fb023d71a137c797e2ce49f7d35d01e9a80fb87afb7d89fc48728733869fdd`
- 文件合同SHA256：`cd4708a7d36a7e9a39cbee48481593b63785e8fc07656203e6dc4ad343d1b97a`
- runtime合同SHA256：`04396eb74da1ed4812b0eabcc94e28cd2a64f90a1839d08ace6630faf2149e1e`
- 生产HEAD：`d492ee072aa5a9d71477235d79f17d2a5db59db3`
- 正式release：`m0005_20260901T165450+0800_1961d98ccb2b`
- 正式策略：`ai_top10_plus_fu_official_live_v1`
- 正式执行版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 资金口径：150000元

## 预检结果

- 状态：通过
- A1/A2 PID不同：是
- A1/A2 portable receipt完全一致：是
- metadata SHA256：`9eae2c3afa8626eb0db87249598ddcbdc8ebfbfbde99790c4c3e56d661b688b2`
- metadata合约数：801
- metadata品种数：19
- metadata来源：`tqsdk=801`
- 静态18+FU派生文件：size `6272`，SHA256 `72c5ca576bfe8aebe12da1e750d9eac980633a43ab9944479a77a7e824a71e34`，A1/A2均逐bytes一致
- post-signal eligibility派生文件：size `51303`，SHA256 `fa5fb5c1cfe06ace44dadc92bd2cc1a77bd4ee74beeab362234952950ca5bb3b`，A1/A2均逐bytes一致
- metadata路径恢复：A1/A2均通过
- 正式回放调用：0
- 网络连接尝试：0
- 全部敏感计数：0
- reviewer：未启动

## 验证

- `.py311/bin/python -B -m pytest -q research/lines/futures_trend_xgboost_formal_signal_marginal_utility_v3/tests/test_stage001_metadata_side_effect_preflight.py`：`13 passed`
- 持久化运行后、写本记录前重新校验完整input manifest，通过。
- 生产仓保持clean detached HEAD `d492ee072aa5a9d71477235d79f17d2a5db59db3`。
- workspace正式期望文件的SHA与mtime均未变化。
- 证据目录：`artifacts/stage001_metadata_side_effect_preflight/`

## 在线调研与判断

- Matplotlib官方环境变量说明支持用`MPLCONFIGDIR`隔离配置和缓存目录；本次继续使用已验证的便携字体缓存：https://matplotlib.org/stable/install/environment_variables_faq.html
- Python `tempfile`与`contextlib`官方文档支持显式临时目录和`try/finally`型恢复：https://docs.python.org/3/library/tempfile.html 、https://docs.python.org/3/library/contextlib.html
- pandas `DataFrame.to_csv`支持显式路径目标：https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_csv.html
- 判断：V2失败确认为可隔离的确定性派生文件副作用。V3已证明重定向不改变两个派生文件bytes和metadata返回语义，因此可以进入新的事件特征资格预注册；该结论仍不构成XGBoost收益证据。

## 回测结果字段

- 期末权益：不适用；未回测
- 总收益：不适用；未回测
- 最大回撤：不适用；未回测
- Sharpe：不适用；未回测
- 总滑点：不适用；未回测
- 总交易次数：不适用；正式回放为0
- 胜率：不适用；未回测

## 后续规划和TODO

1. 新建并预注册V3 Stage002事件特征资格，继承本次metadata重定向，不重放已消费的V2 Stage002。
2. Stage002仅提取无标签根事件特征，先验证事件数量、年度/方向/品种覆盖和特征非退化。
3. 只有事件资格通过后才预注册标签；只有真实候选同时改善收益和最大回撤并通过稳健性门后才启动reviewer。
