# Stage131：真实合约月选择现金执行实现

- 时间：2026-10-18 21:41 CST；line_id：`futures_full_market_long_signal_ai`。非重要突破；实现已冻结，尚未授权实际现金回测。
- 依据root冻结Stage128协议，SHA `bbd24a6e352fe0fbc77f710eeee18918cc1b4670749339e4f3ae67632095efe0`。已读registry、127调研、129/130接口、070/042原政策与124纯报告函数。沿用127的RBA、德银原披露及LEAN源码调研：真实月份选择是不同经济动作，资料没有证明薄月或日线1%参与率可实际成交。

## 改动

新增隔离的 `tools/stage131_contract_choice_cash.py`、`tools/stage131_contract_choice_kernel.py` 与唯一新语义测试；不修改accepted070/042/124、LINE、registry、其他研究线或正式策略。新kernel本地继承原报价/账本并复制原资金循环，仅插入固定anchor、容量与未知状态，不调用旧金融entrypoint、不重放旧账户。

现金只读取130的main A/B完整前向choices，从选中真实epoch重新取得u的Wilder20 N、20low、close、精确经济参数和生命周期；动作身份用child action_id，保留mother_event_id及原canonical anchor。未来label_state、闭合状态、D是否有价均不成为u行动筛选。完整母表及未选择状态仍由原绑定choices和mothers保存，现金信号只取selected=1的family winner。

新增政策参数限root128已冻结的共同1%日量周转容量：`C=L*floor(.01V_u/L)`，`E=L*floor(C/(2L))`；原u联合预算及整数化后取min E，D只能按自身预算减量，不把余额重分给别的family。BUY及可能同日完整stop保留两次毛周转。原本金100万、单family风险0.0025、总风险0.02、保证金0.25/buffer1.10、.25N止损/自身20low和基础/压力成本不变，无止盈、新风险倍数或分钟数据。

held月可以不同于初开canonical，anchor不变；未来canonical改变或无观察签发下一准确source日open退出，已发请求不因回归取消。自身生命周期优先、缺held价仍保留原stale/deferred理想清算局限。D新开缺价记 `entry_execution_unknown`：理想账本不造fill，不能解释为真实执行已知零仓。

每个账户 `(epoch,D)` 的全部BUY/SELL毛手数共享准确native日D−1的1%容量，减仓与随后stop不重复分配，不能买卖净额、不回找前一条有价记录或用D量。超限/缺参考保留理想SELL数量与PnL，逐笔/episode/账户吸收 `execution_capacity_unknown`。任一受影响比较不能晋级；即使未冲突，也只证明固定日量假设内未发现冲突，不证明盘口可成交。共同cap意味着A不保证复刻旧070整条曲线。

## 接口及有限验证

CLI：`--protocol --protocol-sha256 --authorization --authorization-sha256 --output`。auth schema为 `stage128_exact_root_authorization_v1`、stage=`cash`，要求精确source_bundle、新输出目录及授权文件SHA。输入实际为7个role：market_protocol、dataset_manifest、fit_manifest、actions、mothers、choices_main、held_diagnostic；不读COMMON矩阵、模型或child_scores。校验129单SQL、130已完成6fit/零SQL/零现金及其terminal/bindings。130 held报告同时含main与两held组，现金闸门只取两held组，完整报告原样披露。

实际预算为A/B×2020连续/2023独立冷启动×base/stress，共8新账户，一次共享native读取、0fit/0下载/0整库hash。输出逐户原账本、容量逐笔审计及entry执行未知，主目录含四组现金比较/原绑定bootstrap、年度及family含零贡献、集中度/gap/>1R/未平仓与stale诊断；最终manifest schema为 `stage131_contract_choice_cash_v1`。异常保留failed run，不自动重试。

测试先红后绿，仅运行新10项语义fixture：往返容量199/200和L=2的399/400边界；anchor锁存/生命周期；非canonical初开不变DAY；当天BUY+stop共享毛量；准确D−1缺失不回填；D缺价unknown；多笔SELL保持理想数量且共享cap；容量不重分其他family预算；真实月信号及parent anchor；容量unknown不能通过名义正向闸门。最终10 passed，0.031秒；CLI help通过。未重跑旧suite，测试合成数组不代表真实收益验证。

冻结凭证：`outputs/stage131_contract_choice_cash/implementation_freeze.json`。截至本阶段实际SQL=0、fit=0、新现金账户=0、下载=0；权益、总收益、最大回撤、Sharpe、滑点、交易数及胜率均N/A。旧回测结果无修改或删除。

## 反思与下一步

开始/结束过拟合：历史同数据择题风险**是**；按本轮收益修参**否**，尚无实际结果。继续价值**是**，仅执行这一次固定动作空间证伪；容量未知不能以优化阈值或增风险救结果。下一步由root以精确source/input/output授权一次129→130→131，实际后由132独立全面复审，再由133作决定。完整全市场高质量long、极窄损及加大投注目标尚未实现。
