# Stage000 纯导入零子进程预检预注册

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v2`
- 当前模式：正式LR选品 + C9根入场事件XGBoost二级过滤的基础设施资格研究
- 记录时间：2026-09-05 16:37 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：V2标签前、回放前的纯导入合同冻结
- 是否重要突破：否；尚无策略效果证据
- 是否触发A/B：否；禁止运行候选策略和A/C回测
- 是否触发reviewer：否；纯导入资格不构成有价值模型版本

## 外部调研与本地证据

- Matplotlib官方文档确认`MPLCONFIGDIR`承载配置与缓存：<https://matplotlib.org/stable/install/environment_variables_faq.html>。
- Matplotlib官方源码确认缺少可用字体缓存时会执行`fc-list`，macOS路径还可能执行`system_profiler`：<https://github.com/matplotlib/matplotlib/blob/main/lib/matplotlib/font_manager.py>。
- 本机运行版本为Matplotlib `3.10.8`、FontManager缓存版本`390`；本地源码从`fontlist-v390.json`加载成功时不会构造新的FontManager。
- V1只读诊断确认第二个导入期进程调用来自`qmt_roll_official_strategy_material_resolver._assert_release_commit()`中的`git cat-file -e`。
- 在临时字体缓存和严格限定的无进程release适配同时存在时，Stage901、live config、contract metadata和`vnpy_portfoliostrategy`完成纯导入，全部敏感计数及网络尝试为0。

## 固定输入身份

- 生产根：`/Users/bytedance/Desktop/person/vnpy_production_live`。
- 生产HEAD：`d492ee072aa5a9d71477235d79f17d2a5db59db3`。
- release commit：`e3bff060154736e18e3dff1268ca55137c39d462`。
- release id：`m0005_20260901T165450+0800_1961d98ccb2b`。
- strategy version：`ai_top10_plus_fu_official_live_v1`。
- manifest相对路径：`official_strategy_materials/ai_top10_plus_fu_official_live_v1/releases/m0005_20260901T165450+0800_1961d98ccb2b/manifest.json`。
- manifest原始bytes SHA256：`d62e58d01284e30b28054387592604862ffeff6e55a13c63192793e95bc55c21`。
- manifest Git blob OID：`eb0d87aee85607ade41872ff504a8b3651c72ef2`。
- CURRENT内manifest identity：`4d92133bd67821a421bf6017c477015e79a3a8e36889ae4eb527bb11a31956a5`。
- Matplotlib版本：`3.10.8`；FontManager缓存版本：`390`。

## 实施合同

1. 生成只包含Matplotlib随包相对字体条目的最小`fontlist-v390.json`；拒绝绝对字体路径、路径逃逸、缺失字体、版本漂移与空TTF/AFM列表。
2. release适配器只替换resolver的`_assert_release_commit`，只接受上述唯一repo、commit与manifest路径；以冻结attestation核对CURRENT原始SHA、字段、manifest原始SHA和Git blob OID。任何其他调用立即失败。
3. 适配器只在生产上下文导入期间存在，退出后无论成功失败都恢复原函数；resolver其余manifest schema、inventory、payload SHA及路径校验保持生产实现。
4. worker以`.py311/bin/python -I -S -B`启动，环境只含固定HOME/LANG/LC_ALL/MPLCONFIGDIR/线程数/PATH/TMPDIR与QMT guard；worker cwd中存在独立`.vntrader`和空`vt_setting.json`。
5. worker在导入第三方与生产模块前以真实写探针证明macOS sandbox拒绝worker根外写入；sandbox允许初始exec、禁止派生进程、禁止网络，只允许写worker根和`/dev/null`。
6. Python guard同时拦截`subprocess.Popen`、`subprocess._fork_exec`、`os`进程入口、socket连接、生产写入、敏感模型/CTP模块与fit/predict/账户/订单调用。
7. worker只导入Stage901、live config、contract metadata和`vnpy_portfoliostrategy`并核对真实模块路径、正式版本、15万元和active release身份；禁止调用`_run_live_c9`或任何回放函数。
8. 父进程顺序启动A1/A2两个冷worker，比较除PID、时间和临时绝对路径外的portable receipt；任一计数非0、适配调用不是恰好1次、模块身份不同或A1/A2不一致即失败。
9. Stage001输出只允许包含纯导入receipt、模块/运行时身份、敏感计数和输入SHA；不得包含事件、行情值、仓位、交易、收益、回撤、标签或模型数据。

## Stage001硬门

1. 两个worker均在独立PID、独立runtime、`-I -S -B`和OS sandbox下完成。
2. 两个worker的外部进程、网络、越界写入、敏感模块、标签、fit、predict、候选策略、CTP、账户和订单计数全部为0。
3. 字体缓存版本、portable结构、相对路径和SHA一致，加载后未发生缓存重写。
4. release适配器每个worker恰好调用1次，参数与attestation完全一致，退出后原函数已恢复。
5. 四个生产上下文模块的真实路径与固定生产checkout一致；正式版本、材料release、manifest identity和15万元精确匹配。
6. A1/A2 portable receipt逐字段一致。
7. 代码静态检查和测试证明没有引用或调用`_run_live_c9`、标签构建、XGBoost或候选回测入口。

## 失败纪律

- 任何硬门失败都不得进入V2 Stage002。
- 不通过白名单放行`fc-list`、`system_profiler`或`git`，不降低敏感计数门，不修改生产代码。
- 常规失败诊断与修复不拉reviewer；只有未来真实回测产生同时改善收益和回撤、且通过基础稳健性门的候选版本才拉reviewer。

## 回测结果字段

- 期末权益：不适用（本阶段禁止回测）。
- 总收益：不适用（本阶段禁止回测）。
- 最大回撤：不适用（本阶段禁止回测）。
- Sharpe：不适用（本阶段禁止回测）。
- 总滑点：不适用（本阶段禁止回测）。
- 总交易次数：不适用（本阶段禁止回测）。
- 胜率：不适用（本阶段禁止回测）。

## 过拟合与继续价值

- 运行前是否过拟合：否；合同完全由已复现的导入调用栈和安全边界决定，不接触绩效。
- 当前是否值得继续：是；先把可重复纯导入门做对，可以避免再次消耗正式回放资格后才发现基础设施假阴性。
- 停止条件：若无法在不改变策略逻辑、不放宽安全门的前提下通过纯导入，停止直载生产模块，后续只能评估冻结事件接口。

## 合入建议

- 是否更新本线`LINE.md`：是，记录Stage000合同已冻结。
- 是否更新`research/registry.md`：否，由统一合入者维护。
- 是否追加根目录`memory.md/back_log.md`：否；尚无模型或回测突破。
