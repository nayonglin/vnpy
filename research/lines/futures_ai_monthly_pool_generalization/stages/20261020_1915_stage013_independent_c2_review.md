# Stage013 C2 参考四分表独立审查

- line_id：`futures_ai_monthly_pool_generalization`；时间：2026-10-20 19:15 CST。
- 是否重要突破：否；本次改动仅独立审查产物及本唯一 stage，不改 root 实现、LINE、registry、正式配置或其他线。
- 新增/修改/删除策略参数：无；没有收益或阈值扫描。
- 审查结果：185 条月末 fresh 域完整；只读 SQL 740 条日线，独立公式重算全部 stop/nextopen/signedR/configuredtick/阈值/分类匹配，1,289 项断言通过；9 小测试另跑通过。P0/P1/P2＝0/0/0。
- 独立计数：signedR 合法 172，wrong-side/zero gap 13；neither 66、onlystop 51、onlyconfirm 35、both 20、unknown 13。152 条动作条件可识别，没有精确成交或 session 认证。
- 用户开关范围：训练 half-R=False 同时不走 retry；C2=True；正式配置没有被改动。参考 signedR guard 不是冻结 C2 的 abs 行为等价声明。
- 版本 review：绑定冻结 m0008 stop/C2 源与当前 repaired helper；独立二 minute 反例证实 open-first 修复与冻结 low/high stop-first 不等价，不得混用。日线 both 不能直接按 adverse-first 给结果。
- Stage011 交叉：185 域/next_source_day 一致；27 行只有目标日期库存代理，其中 both 4/20，不能认证完整分钟 coverage。全部 session/full_execution 资格仍 False。
- 新增/修改/删除金融回测结果：均无；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均 N/A。fit/financial/60d labels/orders＝0/0/0/0。
- 调研判断：沿用 Stage010 对 vnpy 官方 GitHub 撮合频率与策略回调的引用；主要证据来自绑定的仓库冻结/修复源码与实际反例，官方机制不证明本 C2 收益或覆盖有效。
- 开始/结束过拟合反思：新增按收益选参型过拟合＝否，无收益、fit 或参数寻优；参考目标定义和历史策略选择风险仍存在。
- 开始/结束继续价值：是；先辨认数据与执行缺口，再考虑经济标签，有助于防止日线冒充分钟因果顺序。不能把这批观察的计数当成扩域模型收益改善。
- TODO：root 汇总本线状态；若继续，必须给 canonical session、历史经济条款和实际分钟源独立验收，不把库存时间戳当覆盖资格。
- 证据：`outputs/stage013_independent_c2_review/README.md`、`review.json`、`independent_185_recomputed.csv`、`minute_inventory_proxy_crosstab.csv`、`review.py`。
