# Stage035 独立逐日 episode driver 与两固定真实参考复核

- line_id：`futures_ai_monthly_pool_generalization`；2026-10-20 21:29 CST；非重要突破版本。仅独立复核目录与本唯一 stage，不改 root 实现、LINE、registry、生产或其他线。
- 范围：Stage031 冻结 roll shape/delay helper、Stage034 reference entry-episode driver、Stage036 两已固定 AU/JM 历史 witness。不是完整月度适应性源，也不是正式 A/C 或模型提升试验。
- 结果：13 个 reviewer 手写合成案例/86 字面断言，另 8,852 个独立 artifact/Decimal/源数据/指标/网格/shape 检查；合计 **8,938 检查，零失败**。独立实际运行 Stage031 12 测试、Stage034 11 测试通过。未解决 P0/P1/P2=0/0/0。所有详细可重跑脚本与收据在 `outputs/stage035_independent_driver_review/`。
- 根本复核：不调用作者记账函数，Decimal 逐腿复算 211 synthetic+120 historical reference trace；84 SQL 键只读重查、四 AM41 独立 Wilder RSI6/前 MA20、四 projection SHA/独立225日盘+0/120/330夜盘网格/首open/日聚合；Stage006费率、JM adverse tick和close_today、两个冻结AST及八个shape history独立EMA递推均一致。
- reviewer 推动修复：configured guard 与 fill tick 分离；NaT/bool 数值证据拒绝。作者同时修复 unknown snapshot 不得暴露 whole-path 确定值。最新 synthetic inputs/outputs 与首版字节相同，Stage036 revalidation 同输入结果字节相同、七个首跑 artifact 原封不动；历史旧 code SHA 与当前新收据分开，未重绑定首跑。
- 独立手算：qty3@100/stop90/multiplier10，RSI96先请求减1后 D2open110实际减1，再 D3open90清2，初始货币R300固定，gross=-100、fee15、net=-115；D2 MTM仍持2且pending清仓，net91。换月 A2手 multiplier10@100→110 旧平、B1手 multiplier20@1100→1090 清，gross0、fees15、net=-15、R仍200，无跨合约价格差损益。新 anchor 缺失保留旧平 actual-reference 腿而 whole value 未知。
- 两固定历史参考：AU货币R360、gross -7920、static fees40、net -7960、net/R -22.1111111111；JM货币R877.2、gross -900、fees464.868、net -1364.868、net/R -1.5559370725。AU .18点入场风险，C2确认后失效、日级收盘发出退出并在次session首open平，未截为-1R；JM 同分钟两触 adverse-first policy 不代表真实tick顺序。静态费用 historical_validated=False、qty2诊断、零额外压力只为声明输入，两个结果均无训练标签资格。
- D60以signal后第60源交易日固定，AU/JM为2021-11-02/2021-12-30；早平不挪clock、不fresh重开。只加载两天真实bar而后flat可维持已关闭episode值；如果仍持仓/待roll则必须未知，不能补0。
- 参数新增/修改/删除：模型、alpha无。局部输入语义新增独立configured C2 guard、NaT/bool拒绝与unknown输出限制；不按这两例收益择源、改费用、改R阈值或救参。halfR/retry仅训练源关闭、C2保留，训练profile SHA与Stage014相同。
- 金融回测绩效：账户期末权益/总收益/最大回撤/Sharpe/总滑点/总交易次数/胜率均 N/A；以上为两个有条件单episode的四条reference fill腿，不是全账户回测。完整60日训练标签0、fit0、下载0、生产修改0。
- 调研与判断：复核继承本线已记录官方vn.py/GitHub执行时间合同，并独立读冻结method、当前日内kernel与绑定源码。先pending后actual-reference fill、分支路径保留、固定成熟期和成本未知传递有第一性价值；不能把有限正确算术扩张成全市场来源认证。
- 开始/结束新增收益调参过拟合：否，预声明语义反例与固定 witness，不依据收益救参；有限相容 witness 仍有选择范围。继续价值：是，但下一门槛是完整source中fresh-entry与calendar/roll/PIT economics/单位R或整数政策及未知处理，不能直接接旧108或重训。
