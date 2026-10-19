# Stage093 0.25%有周门/无周门共用入口与差异白名单

时间：2026-10-20 01:43（Asia/Shanghai）。研究线：`futures_trend_full_market_noai_one_lot`。新增 `tools/stage093_run_quarter_pair.py`，本阶段只实现与单测，不跑金融。

父执行身份：`run_20261020_contract_weekly_risk05_v3`，manifest `f2fb3b9d17621ab5d9d64001238b305fbf9fb4fd3dd8fa72432bc0a3955f6860`，commit `83e7669aca75811e50e009c3095c015311e646df`。数据父身份继续为N，manifest `859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25`；legacy baseline e553/N字段保留供旧显示读取，不是本次比较臂。两臂manifest/summary同时显著记录上述parent_execution与frozen_data字段。

## 预声明两臂及白名单

| 项目 | enabled臂 | disabled臂 |
|---|---|---|
| 风险 | 总权益×0.0025，100万2500元 | 完全相同 |
| long周线 | exact当前交易合约40根完成周严格5>10>20>40 | 完全不启用 |
| short周线 | 无门 | 无门 |
| 费用/保证金/账本/执行/alpha/生命周期 | 父v3+090/092 | 完全相同 |
| provider | 原058，按真实查询导出 | 不构造、不查询、不取export属性 |
| 周门检查/违规 | 真实计数及原证据 | checks/rejections/candidates=0，violations=None，validation=not_applicable |
| features | 原查询合约subset | 正确header空表，scope=disabled_no_weekly_queries、queried=[]、rows=0 |

相对父v3的native parameters差异仅 `stage068_risk_fraction: 0.005→0.0025`；两臂parameters字典完全相同。配对臂只在CLI `--weekly-filter enabled|disabled`、最终weekly MRO、相应审计政策及派生周证据上不同。无AI、不加仓、不限一手、无4产品帽、100万、冻结2015-01-05首个有效交易日至2026-10-16、原日期设置及每日proxy/禁C2C9intraday/禁供需政策不变。原START标签仍沿父2015-01-01，冻结数据首个有效交易日为1/5，不改变窗口或起始会话。

090-092保持单一原风险算法和执行事实算法，不建立另一套noWeekly核算。两臂共用 `AccountingStrategyMixin`，其所有方法AST与086 FeeStrategy逐语句相同；CleanExecution除初始化空weekly audit外，所有方法AST一致。CleanExecution使用共同003基类判定，使disabled也必须经过stale_open_intent检查，不能因其不属于091子类而漏门。

接口为 `select_classes(weekly_filter, mode)`，返回两最终strategy/engine；四种execution类分别覆盖enabled/disabled与daily-proxy/strict。CLI必须显式给weekly-filter。`configure_weekly_provider`严格布尔并在add_strategy前绑定engine。关闭臂没有091 weekly mixin，无provider的构造/query/export访问。`weekly_feature_artifact`/`weekly_check_summary`关闭路径直接返回空表/NA，不读取engine属性。trades保留stage059字段，但disabled填JSON null而不是伪allallowed。

manifest/summary保留精确0.0025公式，`parent_parameter_changes`只列该风险属性，legacy N参数差异另列1手→sentinel及None→0.0025。两臂code_snapshot均显式保存090/091/092/093，保证共同源码hash一致；沿原run的拒绝覆盖输出、代码起止hash、冻结原始表字节比较与账户/账本核对。父v3 manifest在运行前后复核；旧v1/v2历史provenance继续归档。

拟Root唯一输出：`run_20261020_risk025_contract_weekly_v1`、`run_20261020_risk025_no_weekly_v1`。本阶段没有创建这两个金融输出，没有金融回放。

## TDD/验证

090首轮6项5 fail RED→6 GREEN；093缺双模式工厂的RED→最终99项/0.512秒/GREEN。测试涵盖双方真实long/short成交、noWeekly的provider poison仍正常开long、enabled坏周拒long、三类long sizing及short/env_probe无周查询、缺量/缺bar→完整native on_bars→以后真实fill的原授权保留、fresh/孤儿/mapping/生命周期、原budget/stop拒单、forced/资金/PnL及全部074/078保护。纯函数关闭导出对任何engine/provider属性访问都会抛错的poison也通过，构造器poison证明关闭臂零实例化。旧068类型即使字段0.0025仍拒绝，新090类型字段0.005也拒绝。

090/091/092文本差异白名单、093 Accounting和Clean关键方法AST对白名单通过。按父v3 manifest逐一核对旧068/075/085/086/074/078六个金融模块hash均保持冻结值。

完整命令：

```text
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/fian-risk05-mpl .py311/bin/python -m unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p 'test_stage*.py'
Ran 513 tests in 32.062s
OK
```

| 文件 | SHA256 |
|---|---|
| 090 | f4d21961f53a6dff26c0b6c6c71804de6b9bfbd65c93e29aa970b5975fa31eae |
| 091 | f62474b4d21b1b0d0b19f48967ca6a7e353db6ef6f134bfde25d150bd0a6f983 |
| 092 | 3e0a64b49f59284c51174e2eae38208affd140fe8e7358d5242d0f56cb92798e |
| 093 | a4be6f21de029ee2588cd9e2b0cf7c4828bb87108564e424ae2e9a0b30635fd3 |
| test090 | ade62a466b231daa41cf0e8a45f01bae1002e0db84e1c1e9ea04a033e93c21fe |
| test093 | 66d3f4b4aeaaa1d8e8f4178eb360d510c3fe1d70360fe58847c5e88385bc46e2 |

## 调研、边界与下一步

复核冻结068/075/085/086及实际vn.py持仓/委托同步链，采用 [Version A/B Experiment](../../../../skills/version-ab-experiment/SKILL.md) 的预声明与防过拟合原则；这是用户明确指定的当前研究线成对研究，不涉及正式策略/生产身份、晋级或激活。外部方法参照此前核对的 [vn.py 官方组合策略模板](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/template.py)，本次不引入新金融理论或未核实依赖。

不是过拟合实现：固定风险和二元周开关均由用户预声明，未按任何新结果挑选参数；若以后只依据同段历史赢家认定正式优势，仍缺样本外和跨周期证据。有价值继续，同风险成对比较能区分额外周门的贡献。两臂共同继承父v3已披露限制（静态规格/费用、日线执行代理、原native planned rollover风险缓存语义等），不差异化修补，不保证两臂空头路径完全一致，现金和资金路径会间接变化。

新增经济参数无；修改比例0.005→0.0025；新增明确weekly模式属于臂标识，原生参数字典两臂相同；删除经济参数无。没有新增有效金融结果，期末权益、收益、最大回撤、Sharpe、滑点、次数、胜率均不适用。等待未参与实现者独立预审，Root预注册、提交冻源后并行唯一运行两臂，并分别进行独立实际审查。本作者参与实现，不能认证自身金融结果；不修改LINE/registry/Git/旧输出或生产。

## 捕获日志补记（01:45命名）

此前513项/32.062秒通过的输出来自工具stdout，未保存物理日志。为给冻结绑定，本作者同命令重新自动发现并捕获至 `20261020_0145_stage093_full_suite.log`，期间展示作者新增测试，实测515项/38.119秒/exit1，唯一错误来自新增097展示合成fixture的 `off_trade_claims_weekly_authorization_expected_null`。完整失败证据SHA256为 `5cb954c6c0c2e7982f60ae46de40ac61d8bc91f85686b9f2d9cc254608145f4a`，保留不覆盖；090-093四份金融源码hash均复核未变。已通知Root和展示作者修其fixture，依Root指示不重复盲跑、不修改094-097。

独立作者Stage099同命令物理日志 `20261020_0145_stage099_quarter_pair_independent_preflight_audit_code/stage099_full_suite.log` 经本作者只读查看，515项/41.258秒/OK，SHA256 `5d6a7db0055c3cdb7136872dfb28b48d6aa6b6c0edc1d762d6f6e175976ea7c5`。此处仅引用其日志，独立结论和oracle以Stage099记录为准；Root可在展示稳定后再作最终完整单测。没有金融运行。
