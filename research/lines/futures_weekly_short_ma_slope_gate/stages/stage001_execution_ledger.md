# Stage001 执行账本

- 新worktree git source=24b975025，独立分支codex/weekly-short-ma-slope-20261029；用户明确授权单规则修改和完整回测。
- 独立数据预审153检查零失败；本线及继承回归42测试通过。
- A001/C001在配置生成前置失败：新worktree缺Git忽略的structural universe输入，尚未进入金融引擎，无有效成绩。保留原日志/目录。
- 根因：克隆不恢复本地backtest_outputs辅助CSV；从冻结源复制2个精确SHA输入到新worktree本地运行目录。原规则与资金参数未改。路径normalize仅允许相同相对路径迁移，文件存在时要求SHA一致。与44池无共享写路径。
- Ruling: MA方向仅约束新信号开仓，换月为延续原持仓且没有新开空信号，维持原换月规则；若用户期待连换月也重新筛选，则应另立实验，不能混入本次结果。
- Ruling: 此次用用户点名Stage033A研究基准，不将其冒称正式物料A；全部NO_PROMOTION。
- A002/C002金融引擎完成但后置settings校验失败，没有有效成绩：唯一未声明差异是supply_demand_signal_path从旧line的empty_signals迁为本线empty_signals。两端文件均不存在，无任何策略信号输入变化。以实际settings做失败测试→GREEN；仅明确允许指定空路径且要求两端都不存在，策略类/参数/数据均未修改。保留失败terminal和原诊断，使用003机械重跑。
- 有效A003/C003均completed_pending_independent_review，全部内置数据/执行/周退出/AI/MACD/无加仓/历史闸门通过，postflight输入不变。
- 独立审查PASS_WITH_LIMITATIONS，P0/P1/P2=0/0/0；A251973、C250994、跨臂6778检查通过。预声明综合门DD失败，不晋级。
- 最终相关回归46/46通过；图表1652/1652点，源值不变且目视检查通过。未修改旧线和44池；保留分支/worktree供后续研究，不合并/推送。
