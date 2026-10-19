# Stage099 0.25% 两臂最终独立预审

时间：2026-10-20T01:45:42.712180+08:00。结论 **PASS_WITH_LIMITS_PREFLIGHT**，P0=0、P1=0。仅核已冻结090—093实现与指定daily proxy研究合同；没有新金融回放或收益结论。不是重要策略突破，旧0.5%源码/结果不改。root完成预登记、hash复核与source freeze后可按授权各完整跑一次，实际完成后每臂另审自己manifest。

基准N manifest ` 859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25 `；父0.5%完整v3 manifest `f2fb3b9d17621ab5d9d64001238b305fbf9fb4fd3dd8fa72432bc0a3955f6860`。四金融源码SHA如下：

| 文件 | SHA256 |
|---|---|
| stage090_quarter_risk.py | `f4d21961f53a6dff26c0b6c6c71804de6b9bfbd65c93e29aa970b5975fa31eae` |
| stage091_quarter_weekly.py | `f62474b4d21b1b0d0b19f48967ca6a7e353db6ef6f134bfde25d150bd0a6f983` |
| stage092_quarter_pending_open.py | `3e0a64b49f59284c51174e2eae38208affd140fe8e7358d5242d0f56cb92798e` |
| stage093_run_quarter_pair.py | `a4be6f21de029ee2588cd9e2b0cf7c4828bb87108564e424ae2e9a0b30635fd3` |

090真定义独立Receipt/RiskSizing/OpeningRisk，.0025而非旧068别名；原stage068_*字段名仅共享归档兼容。预算为总权益×.0025，不乘原money倍率/金额floor/cap；原native quantity/env/ATR/margin/cluster门保留。实际开盘预算是原信号与当日因果marked权益扣前序真实cost后的.0025较小值；原授权整手整单，超限全拒，无一手fallback、无加仓。1m→2500的边界和跨代旧收据拒绝已实测。

091仅依赖090，enabled的所有long含rollover保留exact-contract40周signal/preopen双门；092仅切新类型并严格bool控制long周授权，其余085生命周期、事实资金/PNL、078scope与取消算法原样。093两臂同settings、同源/费率/日期/数据白名单，相对父版本仅.005→.0025。disabled的两个周mixin都不在最终MRO，provider不构造、不query、不取导出属性，features仅固定header且scope disabled_no_weekly_queries，checks0、violations为null/NA；long依然过090预算与全部共用原candidate Clean/expiry/quantity/fresh/deferred guard。

独立标准discover **515 tests / 41.258s OK**；另用最终两臂真实类做独立 **212 checks GREEN**，没有金融历史回放。每臂完整83项覆盖真实500+pending270=770、额外reserve7=777不双算，078规划范围扣已queue CLOSE但普通真实保证金不提前释放；真实long/short PNL±250且未成交OPEN为0；缺bar缓存只派单/估值不进AM或fill；原receipt跨native reconcile/flatplan/rebalance不丢、不重新授权；延期map变化在fill前取消，普通首个次开盘不额外加map门；long/short跳空、旧Receipt、伪造新类.005均flat拒单；disabled poison provider完整不触碰。原074多手/分平/幂等、078真实vs计划scope及AST/文本白名单在515suite通过。

有限项：继承native换月计划PNL缓存释放的P2边界不在本阶段改，当前heatgate=False、90非空独立cluster+3空cluster，换月continue/次日refresh。日线次开盘、静态非PIT费用/保证金、成交量和执行报价近似、授权禁用C2/C9与缺供需过滤仍限制真实性；.25%不是极端跳空/组合总亏损保证。新增EOD actual/funding/reserved/clusterPNL导出是后续实际审查证据，不能用合成测试代替。

审计代码与日志原字节：`/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/stages/20261020_0145_stage099_quarter_pair_independent_preflight_audit_code`；每项SHA、最终两MRO和完整独立检查清单在配套JSON。source_manifest_sha256=null明确代表预审，不伪装真实运行PASS。

过拟合判断：有样本内选择风险，因为看到.5结果后新增.25与无周门。当前仅按用户固定两臂、不扫描阈值/不剔品种/不放宽截止，并保留旧亏损和失败证据；不得把两臂赢家当样本外或自动晋升。继续有价值，目的是如实回答预登记风险/周门问题，资金路径差异可能使short数量也变，不要求两版short逐笔同样。

外部核验参考：[CME仓位风险距离](https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size)、[官方vn.py组合策略文档](https://github.com/vnpy/vnpy/blob/master/docs/community/app/portfolio_strategy.md)。判断仍来自冻结本地链和独立算式，没有复制外部收益结论。
