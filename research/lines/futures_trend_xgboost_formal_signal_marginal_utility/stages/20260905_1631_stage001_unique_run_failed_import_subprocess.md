# Stage001 唯一执行失败：导入期子进程依赖

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility`
- 当前模式：正式LR选品 + C9根入场事件的XGBoost二级过滤资格研究
- 记录时间：2026-09-05 16:31 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage001唯一无标签执行失败闭线与只读根因诊断
- 是否重要突破：否；没有产生事件特征资格、标签、模型或收益证据
- 是否触发A/B：否；未进入候选策略或A/C回测
- 是否触发独立reviewer：否；本次没有跑出有价值版本，遵循“仅有价值版本才拉reviewer”的最新约束

## 外部调研与判断

- 参考资料：Matplotlib官方环境变量文档说明`MPLCONFIGDIR`同时承载配置和缓存：<https://matplotlib.org/stable/install/environment_variables_faq.html>。
- 参考资料：Matplotlib官方GitHub源码显示字体发现会调用`fc-list`与macOS `system_profiler`：<https://github.com/matplotlib/matplotlib/blob/main/lib/matplotlib/font_manager.py>。
- 本机精确证据：运行环境为Matplotlib `3.10.8`、`FontManager.__version__=390`；已安装源码在`font_manager.py:1625-1639`先尝试`fontlist-v390.json`，缓存缺失后构造`FontManager`，并在`font_manager.py:250-270`调用外部进程。
- 我的判断：Stage001失败来自资格runner与被导入生产模块图之间的执行合同冲突，不是策略主动联网、报单、训练或XGBoost机制失败。只补字体缓存不足以修复，因为生产材料resolver还会在导入时执行`git cat-file -e`；不能通过放宽子进程禁令救援。

## 本次变更

- 新增脚本：无。
- 修改脚本：无；唯一执行后没有修改被冻结runner。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 新增记录：本Stage001失败记录，并同步更新本线`LINE.md`。

## 唯一执行

- 命令：`.py311/bin/python -B research/lines/futures_trend_xgboost_formal_signal_marginal_utility/tools/stage001_formal_event_feature_qualification.py --run --authorization research/lines/futures_trend_xgboost_formal_signal_marginal_utility/stages/20260905_stage001_execution_authorization.json`
- 授权SHA256：`c6e1b8b5bf97e5e89286f078e928943e808431bb3adc3d4dbc95cdc304bca396`
- 执行结果：退出码`1`，约`5.6s`后在A1阶段失败。
- 错误：`WorkerStage001Error: worker_failed:A1:sensitive_operation_forbidden:subprocess`。
- 唯一性：authorization、claim与campaign nonce均已消费，`replay_permitted=false`；本线禁止重跑。

## 根因证据

- 失败回执SHA256：`9ea62ba07c46cd72bd6d2fbaa9107429fc77913f66bcd4dac9440c5d782c8312`。
- 失败产物manifest SHA256：`033449a22b22e81a9743e5f32b1404c3fb591a2948deb6d4561669a83b1c3750`。
- 不可变event链完整：sequence `1 claimed -> 2 A1 running -> 3 capability registered -> 4 failure bundle publish -> 5 failed`；末条SHA256为`031dc0d58cd67f6c693aedc58d4aa266f3e6a2f445bed3307f2dd7113b9d18d6`。
- 敏感计数只有`subprocess_spawn_count=1`；标签读取/生成、fit、predict、候选策略、holdout、网络、CTP、账户、订单和生产写入均为`0`。
- 在`.py311/bin/python -I -S -B`、空`MPLCONFIGDIR`、独立HOME/TMP/cwd、网络守卫和同一Python敏感守卫下进行的非Stage001导入诊断精确复现：`Stage901 -> Stage513 -> matplotlib.pyplot -> font_manager -> subprocess.check_output(['fc-list', '--help'])`。
- 将本机`fontlist-v390.json`仅复制到临时诊断目录后，字体探测消失，但同一非Stage001导入诊断继续被`qmt_roll_official_strategy_material_resolver._git()`中的`git cat-file -e <release_commit>:<manifest>`拦截。
- 上述诊断只加载模块以定位调用栈，没有调用`_run_live_c9`，没有读取标签、生成标签、训练、预测或回测，不构成已消费Stage001的重放。

## 回测/归因参数

- 数据区间：计划区间`2020-01-02`至`2026-08-28`，但在基准回放开始前的模块导入阶段失败。
- 账户规模：计划口径15万元，未形成回测结果。
- 成本口径：未进入回测，不适用。
- 样本过滤：未生成根事件样本。
- 策略/归因口径：未进入标签、XGBoost或A/C路径。

## 结果

- 期末权益：未产生（未回测）。
- 总收益：未产生（未回测）。
- 最大回撤：未产生（未回测）。
- Sharpe：未产生（未回测）。
- 总滑点：未产生（未回测）。
- 总交易次数：未产生（未回测）。
- 胜率：未产生（未回测）。
- 其他关键指标：A1/A2特征资格、事件覆盖、可复现性均未形成结论；`qualification_claim_permitted=false`。

## 输出文件

- report：本文件。
- summary：`artifacts/stage001_formal_event_feature_qualification_failed/failure_receipt.json`。
- orders：无；订单API调用计数为`0`。
- daily：无。
- quality：失败包、完整不可变event链，以及两次不进入回放的最小导入诊断。

## 结论

- 本阶段结论：Stage001技术失败并闭线。失败只否定当前隔离执行夹具，既不支持也不反证XGBoost能提高收益、降低回撤。
- 是否进入下一步：本线不进入Stage002，不读取标签，不训练模型。
- 下一步：只有另立新线才可继续。新线必须先冻结并通过“纯导入、零子进程、零网络、零生产写入”的预检；字体缓存必须作为版本绑定输入，Git release校验必须改为直接读取Git对象或等价的无进程、fail-close适配，且不得修改生产代码或放宽子进程计数门。预检通过前不得消耗新的唯一回放。
- reviewer策略：不对本次失败诊断和常规修复启动reviewer；只有后续真实回测跑出同时改善收益与回撤、并通过基础稳健性门的候选版本后才启动独立reviewer。

## 过拟合反思

- 运行前判断：否；Stage001只做无标签身份、事件与特征资格，不基于收益结果调参。
- 运行后判断：否；失败发生在模块导入阶段，没有观察标签、收益、回撤或交易结果，也没有据此改变特征、模型或阈值。
- 原因：当前问题属于执行基础设施合同不完整；修复方向必须由已证实的调用栈决定，不能利用历史绩效反馈。

## 继续价值反思

- 运行前判断：是；先验证正式根事件能否在严格隔离下稳定重建，是进入标签与模型前的必要条件。
- 运行后判断：有条件继续，但必须另立新线；根因可精确复现且存在不放宽安全门的工程路径，仍值得做一次预检优先的重构。
- 原因：当前没有alpha证据，继续价值只来自消除资格基础设施假阴性；若新线纯导入预检仍不能做到零外部进程，应停止该生产模块直载方案，改为冻结事件输入接口，而不是继续补丁式豁免。

## 合入建议

- 是否更新本线`LINE.md`：是，更新为Stage001唯一执行技术失败闭线。
- 是否更新`research/registry.md`：否，由统一合入者维护，且本次不是重要模型突破。
- 是否追加根目录`memory.md/back_log.md`：否；没有正式候选、跨线合并或收益突破。
