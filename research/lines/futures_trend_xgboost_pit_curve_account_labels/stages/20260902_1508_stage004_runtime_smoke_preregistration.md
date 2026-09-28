# Stage004 新冻结运行时与账户标签smoke预注册

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 当前模式：研究隔离/最小真实账户标签smoke
- 记录时间：2026-09-02 15:08 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：新研究数据库身份冻结、旧账户回放引擎适配、4任务A/A smoke
- 是否重要突破：否
- 是否触发A/B：是；仅授权固定4任务smoke，不授权270任务批次

## 外部调研与判断

- XGBoost官方Learning to Rank要求组内候选具有可比较标签；Stage004只验证标签生产机制，不训练：<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>。
- XGBoost官方仓库给出的ranking实现仍依赖可靠的`qid`和标签输入；复杂模型不能修复错误账户路径：<https://github.com/dmlc/xgboost/blob/master/doc/tutorials/learning_to_rank.rst>。
- 我的判断：当前最有价值的动作不是扩大任务，而是验证新资格路径能否在正式15万元真引擎中保持A/A确定性、同月决策前一致性和候选标签可辨识。smoke失败时继续跑全批次只会放大错误。

## 冻结上游输入

- Stage003 summary：SHA256=`b44e21dc5070675b23c03a26973cc76f4ad8c93d79c6add7be4fd480cd945c0a`。
- Stage003 jobs：SHA256=`7ee2062e9700d1c1e8800f42ce8dd0ba75470e4953e30c099c37741aed39b8f3`；资格审计：SHA256=`9bb8bbe8749b69f9436ef6bbb1a9665b7c58eb332859f1468b2eb0c2ffc642ed`；manifest：SHA256=`a1832f8d1313574296af6973c6e0aff56dc74d75310c2c85c2672a4f54465d77`。
- Stage002全排名与Stage003资格构造器继续沿用已冻结身份；`account_label_plan.py` SHA256=`ba4029611323d50bc274efd20dbee79f7b62b94c6564fd0b4e69f4c36fefea88`；Stage004纯证据门`runtime_smoke.py` SHA256=`c651cac7d515189edbed22b107899fef5464e5179179320b341e0e1f12a055e4`。
- 旧已验证真引擎辅助脚本只作账户口径和隔离机制来源：Stage004 helper=`fd1a5adf1e35088693d360ae5a7d4b61a64f7f984738e27ddc2cb9c87f14bfcc`，Stage007 identity=`60805e98f3def69b98b4221478c82301166d8f68b3e1ebc241ce8b9514afff20`，Stage010 label helper=`f5c22983b80cfffe17bb2e70869eb111326d05a1df29cd8acc0cee9ff3117161`，Stage015 batch=`1033b573d3c9faf6f9630acf637649127c8731adaa639f4d66e65c84c51a1c92`。
- 正式release/CURRENT/资格表和生产HEAD继续使用Stage003冻结身份；生产checkout必须clean。

## 新冻结数据库合同

- 源库：`/Users/bytedance/Desktop/person/vnpy_production_live/.vntrader/database.db`，预期SHA256=`5845010108e73661557e723556520d7a3ea42dc6bca4bbe5d50ca3bd419d4cad`，字节数=`112267264`。
- 预期SQLite只读审计：`integrity_check=ok`，`dbbardata=1,020,397`行，最大时间=`2026-09-01 00:00:00`。
- 新运行时固定为`/private/tmp/vnpy-stage004-curve-account-runtime`；数据库必须用macOS APFS clone复制到`.vntrader/database.db`，源和目标必须不同inode、相同字节数和SHA。
- 运行时`vt_setting.json`固定为无换行的2字节空对象`{}`，SHA256=`44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a`；禁止复制生产设置或任何CTP凭证。首次准备在策略运行前因文字与SHA不一致被身份门拦截并自动清理，本条是标签值读取前的字节合同纠正。
- 源库和克隆库在campaign准备后、每个worker输入前后、smoke完成后都必须保持SHA不变；克隆库只属于本研究，不得称为旧Stage015字节级复现。
- 准备前可用磁盘至少`1 GiB`，运行时目录必须原先不存在；禁止复用任何旧checkpoint或旧worker结果。

## 账户回放适配边界

- 复用旧Stage015已验证的正式15万元账户、成本/滑点/保证金、整数手、最多4持仓、冷进程、决策边界和内部会计reconciliation逻辑。
- 替换其任务与资格准备层：读取Stage003的270任务，仅为266个main job生成路径一致资格文件；4个A/A哨兵复用对应rank10资格。
- 每个资格文件落盘后SHA必须等于Stage003内存审计SHA；campaign manifest必须绑定新runner、预注册、jobs、全部266资格文件、空setting、克隆库和生产代码树。
- worker从新运行时目录启动，`analysis_end=next_eval_date`；不得读取账户标签封存12个月的任何标签值。

## 固定smoke与硬门

- 任务固定为：`20220128_R10`、`20220128_R10_A2`、`20220228_R10`、`20220228_R11`；不得替换月份、排名或品种。
- 4个任务必须是4个不同PID、TMPDIR和MPLCONFIGDIR；并行数固定2，单任务超时600秒；checkpoint/result reuse均为false。
- `20220128_R10`与`R10_A2`的`summary/label/curve/combined/trades/entry_candidates/entry_risk/trade_events`八类输出必须逐字节相同。
- `20220228_R10`与`R11`的决策前`curve/trades/entry_candidates/entry_risk/trade_events`SHA必须逐项相同；目标期entry candidate边界必须非空且signal非空数完整。
- 四任务内部权益、PnL、滑点和交易数reconciliation误差绝对值均`<=1e-9`；归一化runtime SHA相同，输入manifest运行前后不变。
- `20220228_R10`与`R11`的`label.json`必须不同；若固定挑战者没有产生可辨识标签，按预注册失败停止，不换样本。
- smoke不发布development训练标签，不训练模型，不读取封存账户标签，不连接CTP，不调用订单API。
- 全部门通过决策固定为`stage004_runtime_smoke_pass_allow_development_label_batch_preregistration`；任一失败固定为`stage004_runtime_smoke_fail_stop_no_development_batch`。

## 回测/归因参数

- 账户回放起点：`2018-01-01`；每任务终点为对应`next_eval_date`。
- 账户规模：正式15万元。
- 成本口径：与旧Stage015相同，不修改滑点、手续费、保证金、整数手或最多4持仓。
- 样本过滤：仅固定4任务，无结果后替换。
- 策略/归因口径：同月rank10 A基线与一个固定挑战者的账户边际标签生产smoke。

## 结果

- 期末权益：待运行；smoke不作为全周期策略效果。
- 总收益：待运行；smoke不作为全周期策略效果。
- 最大回撤：待运行；smoke不作为全周期策略效果。
- Sharpe：待运行；smoke不作为全周期策略效果。
- 总滑点：待运行。
- 总交易次数：待运行。
- 胜率：待运行。
- 其他关键指标：待运行。

## 结论

- 本阶段结论：授权按TDD实现运行时准备器与旧worker适配，并在身份门通过后运行固定4任务smoke。
- 是否进入下一步：是。
- 下一步：smoke通过后另行预注册270任务开发标签批次；失败则闭线。

## 过拟合反思

- 运行前判断：否，但smoke可辨识门会带来选择风险，因此明确禁止失败后换任务。
- 运行后判断：待运行。
- 原因：任务、品种、运行时和所有硬门均在账户标签值前冻结。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：待运行。
- 原因：4任务可用约2至4分钟验证昂贵270任务批次的核心正确性，信息价值高且成本有限。

## 合入建议

- 是否更新本线`LINE.md`：Stage004出结果后更新。
- 是否更新`research/registry.md`：Stage004出结果后更新。
- 是否追加根目录`memory.md/back_log.md`：smoke产生真实回测数据后必须追加`back_log.md`，并拉独立reviewer。
