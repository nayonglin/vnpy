# Stage000 metadata写副作用预检预注册

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v3`
- 记录时间：2026-09-05 17:49 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：正式metadata构造的零回放I/O隔离资格
- 是否重要突破：否；没有事件、标签、模型或回测结果
- 是否触发A/B：否
- 是否触发reviewer：否；基础设施预检不属于有价值回测版本

## 上游反证

- V2 Stage002唯一执行在A1调用`_metadata()`时被写保护阻断，错误目标为workspace的静态18+FU品种池CSV。
- 生产仓模块身份正确；目标落到workspace的原因是生产`examples/portfolio_backtesting/backtest_outputs`为指向研究工作区同目录的符号链接。
- V2失败位于`_run_live_c9`之前，没有事件或绩效信息，V2 claim已消费且禁止重跑。

## 在线与本地调研

- Python官方`tempfile`文档建议显式指定临时目录，高层临时目录支持上下文管理和自动清理。
- Python官方`contextlib`文档给出`try/finally`型上下文管理器，确保成功或异常路径都释放/恢复资源。
- pandas官方`DataFrame.to_csv`文档确认输出目标可以是路径或文件对象。
- 本地静态调用图：`_metadata -> _c3_overrides -> build_official_stage78_overrides -> build_official_stage78_paths`。
- 唯一可达写点：`build_static18_plus_fu_universe -> UNIVERSE_PATH`与`build_ai_satellite_post_signal_eligibility -> AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH`。
- `load_product_universe_symbols -> build_contract_metadata -> build_resolved_metadata`仅执行文件读取和内存计算。

## 冻结输入与目标

- 派生品种池期望SHA256：`72c5ca576bfe8aebe12da1e750d9eac980633a43ab9944479a77a7e824a71e34`，size `6272`。
- 派生post-signal eligibility期望SHA256：`fa5fb5c1cfe06ace44dadc92bd2cc1a77bd4ee74beeab362234952950ca5bb3b`，size `51303`。
- 生成源结构品种池SHA256：`dc389dce4f6d404061127390deea04e15b7cd641f6bb6c265f9721a7c65fc309`。
- 生成源AI Top8 eligibility SHA256：`63c976a09f035fd1b7e57401de5da2d48c2b9538382ede8fe28fbc71d6017242`。
- 正式身份继续固定为m0005、`ai_top10_plus_fu_official_live_v1`、C9-15w与生产HEAD `d492ee072aa5a9d71477235d79f17d2a5db59db3`。

## 固定实现合同

- 不全局替换`DataFrame.to_csv`，不跳过两个生产build函数，不把workspace或生产目录加入写白名单。
- 只在worker内通过上下文管理器临时替换拥有函数全局字典的生产模块两个Path常量，目标必须位于worker私有`derived/`目录。
- 上下文退出后两个原始Path对象必须按对象身份恢复；异常路径同样恢复。
- 每个worker只调用`s901.s513._metadata()`一次，`_run_live_c9`调用数必须为0。
- 生成两个CSV后立即与冻结期望文件比较size与SHA256；任一不等即失败。
- metadata只允许输出规范化SHA、字段名、`vt_symbols`/`product_symbols`数量和源分类计数，不输出曲线、交易、标签或绩效。
- A1/A2必须使用不同PID，portable receipt与metadata规范化SHA完全一致。
- 外部进程、网络、生产/workspace写、正式回放、标签、holdout、模型导入、fit、predict、CTP、账户和订单计数全部为0。

## 通过与停止条件

- 全部门通过：只允许讨论新的事件资格预注册；不直接生成标签、训练或回测。
- 存在未枚举写点、派生文件不等、路径未恢复、metadata不一致或任一敏感计数非0：V3停止，不放宽写权限。
- 纯实现缺陷可在不调用正式回放且不观察事件/绩效的前提下修复；不得借预检修改任何策略或样本参数。

## 回测结果字段

- 期末权益：不适用；未回测
- 总收益：不适用；未回测
- 最大回撤：不适用；未回测
- Sharpe：不适用；未回测
- 总滑点：不适用；未回测
- 总交易次数：不适用；正式回放固定为0
- 胜率：不适用；未回测

## 过拟合与继续价值

- 当前是否过拟合：否。研究只验证确定性I/O与metadata复现，不读取事件、标签或绩效。
- 当前是否值得继续：是。若两个派生文件与冻结输入逐bytes一致，即可在不改变策略语义的前提下消除V2暴露的写副作用。
