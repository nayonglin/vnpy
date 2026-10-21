# Stage368：固定纯52研究初态的独立签名接线

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-20 04:33 CST；本线独立实现，不是收益突破，不触发正式A/B。
- 先读registry，承接367和root另存的370 initialization_scope；不改359/360/357、LINE/registry或其他策略线。工具尚未被root实际执行；实际初态/T_init/资金proposal均未产生。

## 调研与判断

沿本轮367已核的[Freqtrade维护者说明](https://github.com/freqtrade/freqtrade/blob/develop/docs/lookahead-analysis.md)：完整dataframe可暴露未来，单品种切片还会改变跨品种排名。本阶段不重跑其历史工具。判断：下一步需要真实初态时间证据，而不是继续快照并误称已完成连续资金观察。

源码核对明确区分纯kernel与现金runner：131只校验并导入070，070只校验并导入042，042的main有guard。后继复制三个相邻未改定义文件，正常导入保留原globals/closure；没有新增AST白名单或优化算法。

## 本次变更与固定参数

- 新增`tools/stage368_initialize_paper_reference.py`与唯一`test_stage368_initialize_paper_reference.py`，无旧源码修改。`prepare`只保存source_bundle和authorized=false模板；`initialize`另需root授权、完整binding和fresh output。
- 固定source calendar 44,824B，只从绑定的BytesIO加载日期数组，u20索引必须5290。模型/scaler/时钟/320/321/322/325均指向359冻结实体；131/070/042另存新payload，不写回359。
- base/stress独立ID、各100万、空仓/pending0；各调用322.new_state一次，绑定真实321日志的原325 policy hash。原identity不加自定义key。单family0.0025、总risk0.02、margin0.25、buffer1.1、0.25N、base/stress费滑及原退出/F0不变。
- 完整双态、state文件绑定、源码/运行版本/参数、359真实freeze关系和370 scope精确绑定一起进入真实321 `paper_state_initialized`。T_init只取该事件recorded_at；原T0不改。
- preflight须早于20日15:15；append后若T_init已越界，保留`initialization_late/active=false`，时钟早于原T0则标invalid。始终没有资金proposal。后续仍须另核T_init早于实际源完成、新的完整325 proposal seal早于完整域D_open；不能继承未注资seal或把start_u20静默跳为21。
- 新增/修改/删除科学参数均0；没有修改模型或收益目标。后继范围仅初始化，不包含future wrapper、更多日接收或调度。

## 验证与输出

唯一夹具先RED：缺初始化工具，1 test失败；实现后GREEN。最后因root要求追加370 scope绑定，复跑同一夹具：`Ran 1 test in 0.267s / OK`。没有再加其他测试、旧suite或金融回放。夹具只在自动删除的临时目录生成合成研究初态；使用真实kernel/321，并阻止SQL、非绑定calendar的np.load、现金run、行情loader、seal/advance，核场景隔离、完整签名、未授权/错SHA/重复输出拒绝。

实现输出目录：`outputs/stage368_paper_reference_initialization/implementation/`：

| 文件 | 字节 / SHA256 |
| --- | --- |
| source_bundle.json | 5866 / `859ce7f56227a51c0c1b7fbc7d3ba2ef982b923a1d6bb96d3bd21d328167fe2c` |
| root_authorization_template.json | 1849 / `607fe60cc56e40eeb2af1056771d8c08a289feb3168a2bcce1d5e2ad8a056de0` |
| 工具源码 | 16964 / `c5f3dbadb18237eb6d72b47020262b5e298e75a5c18b5e3114baf84674f555f2` |
| 唯一fixture源码 | 5750 / `6c27e3f5ad762e15242712dd8a58449ee6f94aa67af2c2435eefbd21f4a284b2` |

`fixture_receipt.json`记录上述作者单组实测。root可在369独审后，另存authorized=true授权文件，再对预留370/actual_run1调用initialize；本文不代签授权、不执行该动作。370 scope绑定3166B/SHA `fe77bce172b81c19da026e198e56add1b08d65bdbf51ec606d26b8f32b38074d`已进入模板。

## 结果与反思

实际初始化0、fit0、cash0、模型推断0、行情/API/SQL/Git0，资金proposal0；无回测结果新增/修改/删除。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A，累计453fit/246cash及原partial不变。

开始/结束新增按成绩调参过拟合：否，未读新成绩或变更政策；历史择题偏差仍在。开始/结束继续价值：是，此有限接线使后续新样本可检查连续预算/成本来源；短期表现、极窄损承载性和加注资格尚未证明。

下一步仅独立369核当前代码、唯一夹具与绑定；root据此决定是否做唯一真实初始化。LINE/registry和根memory/back_log不更新。
