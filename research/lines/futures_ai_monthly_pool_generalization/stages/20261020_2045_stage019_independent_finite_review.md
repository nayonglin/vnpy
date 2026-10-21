# Stage019 五日以内有限合成账本独立复核

- line_id：`futures_ai_monthly_pool_generalization`；2026-10-20 20:45 CST；day。
- 角色：独立reviewer，只写本阶段outputs和本记录；未修改root实现、LINE、registry、正式配置、原始行情或其他研究线。
- 是否重要突破：不是收益或模型突破；验证有限路径账本的机制边界。

## 方法与实际结果

先读registry、Stage016/017与Stage010语义，以及当前Stage827 after-open hook和执行helper，确认C2只扫描入场session。采用不调用Stage018实现/helper的手写Decimal oracle，从固定fixtures独立显式Cartesian枚举、核对全部逐日状态。额外边界挑战才调用公共入口。

修复后审查目标为`outputs/stage018_finite_path_probe_guard_fixed/`：12案例、46场景、185逐日行全部一致；43 known、1 execution_unknown、2 path_unknown；不删除未知分支。5196项检查0失败，含CSV逐行与SHA绑定重算、8个有效补充边界和5个非法输入挑战。Stage018公开16项测试单独执行通过。

已核关键反例：相同日OHLC先stop/先confirm保留不同未来；多空镜像；minute open先确认而后极值不能倒推stop；同minute双触按政策；gap亏损超过1R不截断；不利tick且可达检查；subtick C2 inactive不抬高R；C2不跨日；stop后无retry；fixed R下末日只是MTM；flat缺日仍有已知realized，holding缺日保持未知；五日32条同终态路径不合并。

## 发现与解决

P2共1项，已由root修复并复核。初版使用`risk < guard_tick`，而当前源码为`risk < max(configured_tick,1e-9)`。合成E=`1e-8`、S=`9.5e-9`、configured/fill tick=`1e-12`时，初版错误激活C2并stop；源码应guard inactive，持仓估值约-0.8R。root先加回归测试见红，再返回effective guard并保持原始R；修复后再次独审通过。初次输出保留、fixed输出另存。原12固定案例经济数值不变。

未解决P0/P1/P2=0/0/0。证据保留`outputs/stage019_independent_finite_review/{review.py,review.json,independent_185_trace.csv,extra_challenges.json,finding_guard_floor.json,README.md}`。

## 判断与边界

通过的仅是有限合成合同门槛，不是完整策略源、净收益或60日标签资格。抽象minute slots没有真实timestamp和session认证；未实现普通退出、费用、历史乘数/手数、保证金、roll或资金竞争；有限集合也不覆盖所有OHLC相容现实路径。missing holding路径吸收unknown是声明的严格证据政策，不应误称任何后续纯MTM终点都在数学上不可识别。

模型参数、策略阈值、TopN、训练窗口新增/修改/删除：无。金融回测结果新增/修改/删除：无。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。实际真实数据回测、fit、60日净标签、下载、订单均0。

调研沿用Stage017已核对的VeighNa官方源码与Backtrader执行说明；本独审以实际仓库源码和可复现反例为判断依据，通用文档不证明真实历史成交。开始/结束新增按收益调参过拟合：否，固定合成机制反例，未筛选收益或现实品种；继续价值：是，有限合同可支撑下一步真实源设计审查，但不能跳过完整退出和经济字段定义。
