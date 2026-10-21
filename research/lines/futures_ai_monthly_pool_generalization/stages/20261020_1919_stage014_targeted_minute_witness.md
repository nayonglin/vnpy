# Stage014 定向分钟参考事件见证

- 时间：2026-10-20 19:19 CST；line_id=`futures_ai_monthly_pool_generalization`；非重要突破。
- 范围：固定Stage012×Stage011交叉的CF/JM/M/AU四个both观察，不拓session、不补数、不修来源或Stage012、不改正式/其他线/LINE/registry。
- 实际执行：17个Stage011定位来源，Stage861只投影一次；逐文件/内部minute_source组件隔离，只有完整grid、合法OHLC、日聚合和首open一致才执行当前helper C2。
- 结果：2/4有匹配日线的单来源条件见证。JM@2021-09-30→10-08，Stage491 225分钟，首09:00同bar双触达，current adverse-ties参考stop、fill3224.5；AU@2021-07-30→08-02，Stage461 555分钟，先确认解除C2。CF完整225分钟来源与Stage012日OHLC不一致，未知；M不在helper域，unsupported。
- 重要边界：JM/AU其他来源仍有日OHLC冲突，未拼接/设provider优先级；2个点仅指定来源政策输出，不认证真实tick/正式交易/经济60日标签。真实交易认证数量0。
- 证据：`outputs/stage014_minute_witness/{README.md,summary.json,source_audit.csv,event_summary.csv,projected_source_*.csv}`；工具`tools/stage014_minute_witness.py`，测试`tools/test_stage014_minute_witness.py`。
- TDD：先红后绿；集成预检发现Stage011键名不同，在任何投影前停止，补schema回归红→绿；10项测试通过。成功金融账户回放0、fit0、下载0、订单0。
- 新增参数：无生效策略参数；修改/删除参数无；新增/修改/删除回测结果无。权益/收益/最大回撤/Sharpe/总滑点/交易次数/胜率N/A（未回测）。
- 调研判断：沿用Stage010官方vnpy源码与本地绑定helper，分钟bar内adverse-ties是参考政策，不能证明真实先后；来源不一致保留未知优于偷换源口径。
- 开始/结束过拟合反思：新增按成绩选参否，未扫R/改信号/C2；现有选择性分钟补数不是全市场无偏样本。继续价值是：将2个聚合歧义点转为可复核条件见证，明确另外2个阻塞，不证明任何收益改善。
- TODO：root/独立reviewer核本次逐来源投影与kernel；保持尚无完整经济标签/持续账本的边界，不直接训练或晋升。
