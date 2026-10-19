# Stage073：0.5%多手风险实现独立预审

审查时间：2026-10-20 00:34（Asia/Shanghai）；研究线`futures_trend_full_market_noai_one_lot`。独立审查agent未参与本次实现，仅写本报告，不改工具/旧源/LINE/Git，不下载、不访问生产，不运行金融。

**预审结论：PASS WITH LIMITS。当前未发现P0/P1金融阻塞，可以启动已授权的一次完整日线近似回放。** 这不是实际金融结果、全部运行路径或实盘资格认证；预审之后的金融源必须再次独立审查。

## 合同、基线与参数

用户已更正为**总权益×0.005=0.5%**，100万对应5000元；取消1手帽，不加仓。预算取标记总权益，不是free balance或旧sizing_equity cap。旧risk-mode比例、金额min/max、streak/recovery/overheat/30d货币倍率被新固定公式替代；原native数量、环境、ATR、资金/集群和保证金门仍走原顺序。不是简单把旧risk_ratio改成0.005。

N基线commit `e553d1703bc4efb9c612143a6c3f2ccc9885f6b3`，manifest SHA256 `859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25`；独立重算其manifest内26项文件hash一致。070构造settings相对N只变`max_position_size:1→2147483647`、新增`stage068_risk_fraction:0.005`，无原参数删除。整数上界只是技术哨兵；货币行为变化由068显式hook实现，不能因旧参数字段仍在就说旧预算仍生效。

## 代码与行为核验

- 068在native计算contracts_by_risk之前提供总权益0.5%预算；neutralize货币倍率并保留raw诊断。final selected取native最终量与新预算可承受整手量的min，不把native零量恢复为1。非法/非正权益提前拒绝；零手无法进入native原有max(1,volume)。
- 每次正整数授权冻结contract/product/side/signal/date/stop/风险预算/qty。实际开盘要求order qty=receipt qty=唯一未同步layer qty；原止损不能变化，止损已穿越、缺授权、方向/日期不符均整单拒绝。当前预算=min(原信号预算,因果opening equity扣已真实发生成本后的0.5%)；权益增加不扩大旧授权。
- 070实际MRO已去旧039/041一手base/guards；实际broker margin按全部qty计，旧同产品实际仓保护仍在。prepare_opening_risk仅用前结算边界、实际仓与今日open，不用今日close推开盘风险；之后只累扣真实费用。
- 075对059差异仅为新预算基类、正整数qty与匹配授权qty；exact-contract周证据/40有效完成周/严格MA5>10>20>40/信号可用当日完成周而open须严格早于今日均未改。所有long含rollover核双相位，short/close/env_probe不读周门。
- 074处理多手RSI计划分平后未成交状态：remaining layers+pending close qty=actual qty；pending仍占真实actual/资金，不重建已计划退出的layer。后续生命周期或换月仅queue尚未承诺余量，actual不合法/超平/方向或数量不一致硬失败。此适配不新增退出触发或提前成交。
- 069按整个OPEN聚合episode，分平只累计实际数量与退出现金成本；最后一笔close才进入完整样本。残余保留原量、已平量、余量、剩余入场成本和已实现segments。不能把每手或每次分平当独立胜率样本。
- 行情不足整单qty时070保留整单延迟，不部分缩单、换receipt或伪造退出；下个足量真实bar仍须重新经过原授权、周门、截止和开盘资金复核。

## 新鲜验证证据

最终命令（正常模块启动，非stdin multiprocessing入口）：

```text
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/fian-risk05-mpl PYTHONPATH=research/lines/futures_trend_full_market_noai_one_lot/tools .py311/bin/python -m unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p 'test_stage*.py'
Ran 285 tests in 28.264s — OK
```

其中本次068/069/070/074/075共57项合成测试单独GREEN，含070新增缺量延迟、不换receipt。独立临时审查脚本不复用实现函数作为oracle：288组多空、权益、手数、止损距离边界以Decimal自行算总风险/预算；200组随机完整或分平账本用直接现金公式算净额和残余入场成本；另2项最终runner真实cross_delayed_orders验证V2不足qty3保留授权，V3足量整单成交。共490项全部通过，无金融回放。

首次整线284项中的4项失败仅因并行Stage072尚不存在；模块落盘后最终285全过。独立oracle首轮被/tmp历史同名stage002遮蔽而导入失败，改显式本线sys.path首位后通过。两类审查harness/并行未完成事实保留，不冒充产品RED→GREEN bug证据；root另有stdin spawn harness失败，本代理用正常unittest入口未复现。

## 保留风险及后续实际审查

P2继承风险：旧target/state清理不完整可能使缺bar后旧OPEN重挂。新068对无有效receipt/layer的请求在实际变仓前fail-closed并清目标；本次尚无实际金融运行，不预判新运行是否发生、发生多少或收益影响。

原生pending close会先改变计划layers及计划realized/streak；074修的是层和实际量边界，不把这些计划统计认证为已到账现金。实际账户/费用仍以fill为准。每单V>=qty只是冻结bar量的保守下界，不是订单合计参与率、盘口深度、排队/冲击或实盘容量模型。退出报价的量仓争议、静态费率/保证金/规格、研究主力、授权停用C2/C9日内和供需过滤的边界都保留。

0.5%是开仓到初始止损的计划风险，不是gap退出亏损保证；费用不混入止损距离风险，前序真实成交费用会扣减开盘权益。285项包含展示契约测试，不等于未来实际HTML/UI验收。

下一步待`run_20261020_contract_weekly_risk05_v1/manifest.json`完整出现后逐笔独立复算全部授权预算、actual open风险、qty、周证据/时点、真实bar量、费用和MTM、所有分平及残余桥接、生命周期与输入/源码hash，JSON将精确绑定该源manifest；不对partial前缀输出绩效。

## 反思、资料与金融结果

过拟合：**否**，本次是用户预先固定0.5%与取消手帽的实现审查，无收益扫描/例外；但同样本后验研究不是样本外验证。继续价值：**是**，一次预注册完整回放可核实风险量纲和多手执行；不预认收益改善或正式晋级。

调研：[CME仓位与止损风险](https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size)、[vn.py官方目标仓位/实际仓位文档](https://github.com/vnpy/vnpy/blob/master/docs/community/app/portfolio_strategy.md)。判断：预算/止损确定手数与目标/实际分离符合接口原则，但外部说明不能替代本地真实账本证据。

本阶段新增/修改/删除金融结果均无；期末权益、收益、DD、Sharpe、滑点、交易数、胜率均不适用。源码SHA256见同名JSON，核心如下：

- `stage068_fractional_risk.py`：`c795551c7b5b3457016397320d7d131a99b5a032cb4f7d8f3aa6e8fdf8073982`
- `stage069_quantity_ledger.py`：`ef3597da5bc76a84a146ee50401cafd8d121da4f3d8a3a4e066fb68934b21382`
- `stage070_run_fractional_risk.py`：`51756973c0df8d3a209c1f0529ea6083932f0f20f095b33487caebff941eaf7c`
- `stage074_pending_close_quantity.py`：`2c098f576d2dd7be1458a1f9973b70314e8604ff242aaf546e3b4fc490f50255`
- `stage075_fractional_weekly.py`：`431c170b83d05171adbde5955ab8ef4e7ba6fc12b9c7c306fe6343f326ea26b2`
- `stage058_weekly_contract.py`：`546f2097b80117be1a0b0c2c29f4a39c380c9313270a6e31056bf29029eee491`
- `stage003_candidate.py`：`b1facda9ba608d900d7e634bbbbecb0bc1044ad947adbea779599d198d0167ca`
