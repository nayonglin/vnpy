# Stage001 纯导入零子进程预检通过

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v2`
- 当前模式：正式LR选品 + C9根入场事件XGBoost二级过滤的基础设施资格研究
- 记录时间：2026-09-05 16:57 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：标签前、正式回放前的生产上下文纯导入资格
- 是否重要突破：否；只消除了V1执行夹具假阴性，没有产生alpha证据
- 是否触发A/B：否；正式回放、候选策略和A/C回测调用均为0
- 是否触发reviewer：否；没有跑出有价值的策略版本

## 外部调研与判断

- Matplotlib官方环境文档：<https://matplotlib.org/stable/install/environment_variables_faq.html>。
- Matplotlib官方字体管理源码：<https://github.com/matplotlib/matplotlib/blob/main/lib/matplotlib/font_manager.py>。
- 调研结论：空`MPLCONFIGDIR`会触发字体发现外部进程；版本绑定缓存可避免该副作用。生产resolver的`git cat-file -e`不能白名单放行，改由冻结commit/path/blob attestation做窄范围、无进程等价身份校验。
- 我的判断：V2 Stage001证明了生产模块图可以在不降低安全门的情况下纯导入；下一步仍必须单独验证正式根事件和12项特征，不能把本结果外推成XGBoost有效。

## 本次变更

- 新增脚本：`tools/stage001_import_preflight.py`。
- 新增测试：`tests/test_stage001_import_preflight.py`。
- 新增材料：`materials/fontlist-v390.json`，只保留Matplotlib随包的38条TTF与60条AFM，绝对路径0条。
- 新增材料：`materials/release_manifest_commit_attestation.json`。
- 修改脚本：无生产脚本修改；V1闭线runner未修改。
- 删除脚本：无。
- 新增参数：CLI `--run --output-dir`以及内部worker绑定参数。
- 修改参数：无策略参数修改。
- 删除参数：无。

## 资格参数

- worker数量：2，顺序冷启动A1/A2。
- Python：`.py311/bin/python -I -S -B`。
- OS隔离：`sandbox-exec` deny-default，允许初始exec，禁止派生进程与网络，只允许worker根写入。
- 生产HEAD：`d492ee072aa5a9d71477235d79f17d2a5db59db3`。
- 正式版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- 账户规模：15万元身份校验；没有运行账户回放。
- release：`m0005_20260901T165450+0800_1961d98ccb2b`。
- release commit：`e3bff060154736e18e3dff1268ca55137c39d462`。
- manifest identity：`4d92133bd67821a421bf6017c477015e79a3a8e36889ae4eb527bb11a31956a5`。
- 字体缓存SHA256：`13e74b8b71bc612a81a67da228ab73c718d92ffb80896f3bdf481c0119938479`。
- release attestation SHA256：`e4e8a149173b58c208533492723d02184a2fd5bf36c3ff7c7110b4fe2a1a0d9a`。

## RED/GREEN与实际运行

- release attestation测试先因模块缺失RED，再实现精确repo/commit/path/CURRENT/manifest SHA/Git blob校验后GREEN。
- release适配器测试先因入口缺失RED，再实现上下文内替换与异常后恢复原函数后GREEN。
- portable字体缓存测试先因生成器缺失RED，再实现绝对路径过滤、版本/路径/存在性校验与确定性排序后GREEN。
- 子进程、网络和`_run_live_c9`阻断测试先RED，再实现Python guard后GREEN。
- 双冷worker集成测试先因CLI未实现RED，实现父子入口后GREEN。
- 首次实际命令使用相对`--output-dir`时，sandbox探针仍为相对路径并在worker cwd下得到`ENOENT`；失败目录完整保留为`artifacts/stage001_import_preflight_failed_relative_path/`。
- 新增相对路径集成RED后，只把父进程输出根规范化为绝对路径；同一集成测试GREEN，随后同一实际命令成功。

## 结果

- Stage001状态：`passed`。
- A1 PID：`17243`；A2 PID：`17253`；PID独立门通过。
- portable receipt：逐字段一致。
- release适配调用：每worker恰好1次，退出后原函数恢复。
- 正式上下文：Stage901、live config、contract metadata和`vnpy_portfoliostrategy`真实路径全部匹配。
- `subprocess_spawn_count`：0。
- `network_connection_attempt_count`：0。
- `production_file_write_count`：0。
- `candidate_strategy_run_count` / `formal_replay_call_count`：0。
- 标签读取/生成、fit、predict、holdout、敏感模块、CTP、账户和订单计数：全部0。
- 测试：`11 passed`；`py_compile`通过。
- 生产仓状态：clean detached HEAD，未修改生产目录。

## 回测结果字段

- 期末权益：未产生（本阶段禁止回测）。
- 总收益：未产生（本阶段禁止回测）。
- 最大回撤：未产生（本阶段禁止回测）。
- Sharpe：未产生（本阶段禁止回测）。
- 总滑点：未产生（本阶段禁止回测）。
- 总交易次数：未产生（本阶段禁止回测）。
- 胜率：未产生（本阶段禁止回测）。

## 输出文件

- report：本文件。
- summary：`artifacts/stage001_import_preflight/summary.json`，SHA256 `42e05d8ed9e49841790b3e2622d83c070cc4a2b84cf5a313a6a7aa57e8257add`。
- A1 receipt：`artifacts/stage001_import_preflight/A1/receipt.json`，SHA256 `d498c0f425fca6e6c0e6e4348999803a9c219835c9edc25dacd5bdb649297f21`。
- A2 receipt：`artifacts/stage001_import_preflight/A2/receipt.json`，SHA256 `eceac4e250065dff621c12c180f0ac6888239bb570d75592c7b5f79bc95aaedb`。
- orders：无；订单API计数0。
- daily：无。

## 结论

- 本阶段结论：纯导入资格通过，V1已知`fc-list`与`git cat-file`假阴性均在零外部进程前提下关闭。
- 是否进入下一步：是，但只允许预注册V2 Stage002正式根事件与12项决策时点特征资格；不解锁标签、模型或候选回测。
- 下一步：从V1冻结经济对象复用特征定义，但重新建立V2输入manifest与worker合同；正式回放必须显式允许且精确计数，仍保持网络、生产写、标签、fit、predict、CTP、账户与订单为0。
- reviewer：不启动。只有未来真实回测形成同时改善收益和最大回撤、并通过基础稳健性门的候选版本才启动。

## 过拟合反思

- 运行前判断：否；纯导入预检不读取绩效。
- 运行后判断：否；所有回放、标签、训练与预测计数均为0，修复只由可复现的路径错误和导入调用栈驱动。
- 原因：没有根据收益、回撤、年份或品种反馈改变任何策略参数。

## 继续价值反思

- 运行前判断：是；它阻止再次在唯一正式回放中才发现导入基础设施问题。
- 运行后判断：是，但价值仍限于进入下一层资格验证。
- 原因：生产模块已能在严格隔离下稳定纯导入，正式事件样本是否覆盖、可复现以及是否适合树模型仍未知，必须继续用硬门反证。

## 合入建议

- 是否更新本线`LINE.md`：是，记录Stage001通过及Stage002边界。
- 是否更新`research/registry.md`：否，由统一合入者维护。
- 是否追加根目录`memory.md/back_log.md`：否；尚无回测或模型突破。
