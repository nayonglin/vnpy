# Stage110：A_OFF完整独立会计审计接受

- line_id：`futures_trend_triple_screen`；时间：2026-10-18 07:52:54 +0800。
- 重要alpha突破：否；本次是封存完整账户的独立只读复算，新增/修改/删除策略参数0。
- 身份：Stage099修复族A_OFF attempt1只是族内序号；全局A_OFF第2次，run_id `7cf2c2bffdc34d8cbd926693aa75dd10`。原全局A1失败N/A、105原095审计失败及真实工具终态全部保留。
- root原金融终态37421/0832ea exit0；同104completion SHA `fd6272aeeb94b8546008224d54479aeab5e5e11d2cf5e73439c110b097f17944`。原金融不重跑。

## 真实执行与结论

107独立reader审查P0/P1/P2=0/0/0，收据SHA `5987f37d8ca3320b65906081b51549d91394037c1837b4968e267ce67a1b1123` 后，冻结106对同一104 completion只调用一次完整审计。实际子进程exit0，耗时`7.568858917`秒，无stderr；wrapper工具session92054/chunk690afc记录其真实结束，子进程returncode另存本输出`actual_audit_terminal.json`。金融重放/模型/行情DB重载/网络/旧suite均0，未读取B账户或途中PnL。

完整结论：`accepted_independent_cash_inventory_costs_identity_and_OFF_account`，P0/P1/P2=0/0/0。正式收据：`/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/outputs/stage106_off_financial_audit/A_OFF/7cf2c2bffdc34d8cbd926693aa75dd10/reader_account_checks.json`；SHA `1cc00ed0e9c86acbe926b240c725d4e27b166d6b4adf3ae115ea1396b794ffad`。原095算法收据SHA `77765ae3c68953d29357eca0beaa275964edade5496731d49e13b76a43e8f8aa`。106源SHA `6688020ff61a6b14ae2cc0ce158c7f54cf2692d1696b53a525596c76ec4f4b49`；冻结095源SHA `be688b02314b7c9d5a23d21f3cf0575e9d66a6e1f7a8a5b8c80ebcd627426b6f`。

本次只读审计不增加金融attempt。按root此前口径全研究仍11金融attempt；此次A完整独立接受可使原accepted3增加为4，由root统一记账，不改LINE/registry。B尚待其真实完整终态及独立审计；此处没有B结果或四行胜负结论。

## 完整经济结果（15万、全1641日）

| 指标 | 独立复算结果 |
|---|---:|
| 期末权益 | 2,151,930.00 |
| 总收益 | 1334.620000% |
| 最大回撤 | -48.388528% |
| Sharpe | 1.344825004 |
| 最低权益 | 141,440.00 |
| 总滑点金额 | 575,670.00 |
| 总commission | 0.00 |
| 实际成交fill数 | 817 |
| 完整母单胜率 | 35.849057%（114/318） |
| 日收盘1.10保证金/权益峰值 | 64.243016% |
| 1.10日级超过100% / 90%天数 | 0 / 0 |
| 额外1.65日级诊断峰值 | 96.364524% |
| 1.65日级超过100% / 90%天数 | 0 / 3 |

原冻结成本参数commission为0，本次逐fill核对如实保留，不另造费用、不声称成本压力通过；滑点按实际volume×contract_size×原slippage逐fill只扣一次。

## 完整账本、母链和资格边界

- 全1641日（2020-01-02至2026-10-14）与真实preflight calendar完全相同；raw/frames/capture→实际CSV逐表SHA对应，root工具终态、raw/manifest/seal/context/preflight/readiness和原source快照绑定闭合。checkpoint writer与金融runner身份不同，实际A为exact native、ordered=None，无伪B/TS表。
- 独立实际817条TradeData一一对应，283条synthetic真实parent信号身份补齐、冲突0；原producer缺signal_datetime不能被当成普通身份缺失放过。实际pairwise rank=0记录886行，共同八OFF键严格一致、runtime None、月AI资格保留、完整参考settings/parameters仅允许八键及空信号路径归一化。
- 库存start/end按fill独立重建，一次positions扫描506,986行；持仓方向mark、现金至权益、日Pnl累积、内部权益、每日费用/交易数与原指标一致。最大现金权益残差`2.328e-09`；母周期加末日MTM残差`2.561e-09`；start/end库存残差均0，滑点及commission残差均0。
- 合约闭合周期403，完整母单318，其中盈利114；确认同日真实retry母链85、真实旧合约close→新合约open换月链8。末日仍开1合约，其未平净MTM4800计入账户恒等式；仍活跃母根全部排除母单胜率分母。交易次数817是实际fills，不能当作318个母单或胜率分母。
- 105日期reader P1由已独立107接受的106在raw_exports完整原验证之后copy usage.signal_date严格规范解决；原母链/换月/成本/现金算术未改。105退出1和原证据仍是真实历史，不改写为首次成功审计。
- 本审者自己实现过071/087，因此来源资格只继承独立078/081/历史094与实际100当前两scope源收据；不自审这些数据source，也不重做全市场/1590source资格或市场哈希。

## 置信度、目标与后续

对该完成账户的现金、库存、成本、母单身份和导出一致性置信度高，范围只到封存账本与已绑定实际源。OFF运行确认未调用pairwise；它不能自动消除全研究选择、月AI资格和数据链的全部PIT限制。原A0固定模型反事实仍受057/058两P1限制，不得把旧数值当严格PIT公平基准。

1.10是原日级报告口径；额外1.65只是诊断，不替换七门，不建立分钟组合保证金峰值，也不声称fill时预算再次硬约束。单条完整历史路径没有新增OOS、多起点、多周期、未见样本或成本压力证明。

开始/结束过拟合判断均否：只审封存账本与已定日期reader，没有收益救参。继续价值是：A已完成公平OFF基准核对，可等待B真实终态后沿同一独立算术再审，届时两臂均accepted才允许固定四行对照与原001七门。不能只胜较弱A_OFF就宣告原“2020—2026收益更高且DD更低”目标完成。当前original_goal_achieved=false、promotion_allowed=false、production_qualified=false；不主动再跑任何金融或审计。
