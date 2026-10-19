# Stage102：0.25%周过滤启用v1实际单臂复盘与工具验证

- 时间：2026-10-20 02:12 CST；重要突破：否，显示生成/验收。仅enabled v1，关闭版JR201907截止无法完成退出且无完整manifest，原失败证据保留，不生成off曲线、不调用096配对或097 pairPASS。用户关于共同执行模型尚未形成已执行新金融证据，此页只呈现原规则完成单臂。
- 源：run_20261020_risk025_contract_weekly_v1，manifest 7614f09d8dab584fae901901bfafc6dae7f72bca1beba4b6193195642f323d35。1311完整entry/6974合约手数，7残仓/29手；0.25%=0.0025，100万2500。actual Stage101报告source绑定、verdict PASS_WITH_LIMITS，P0/P1为0；报告SHA3a0ba1efa4d54e887dc7862ee4be48baab0dfafd3b38952ceb0b2de29f7f950e。该金融独审来自另一agent，不是显示作者自行声明。
- 执行链均exit0：025 workers4（1311 contexts，elapsed200.133秒）→094_fractional→095_weekly→020(actual Stage101)→083_labels→067_reviewed_v2。所有目录新建，四显示模块哈希与0148冻结值一致，未改金融/旧代码/源/失败输出。
- 最终HTML：/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/outputs/recap_20261020_risk025_contract_weekly_v1_reviewed_v2/index.html；HTML SHA b0eca000d4af4b1af0f7868127da7c46bd267cec2b4e6a9136088c6990b74a48，records SHA 99a5aaac295e92fc226cd466e724fbd581b6bf13884c71a4d8a3be16a94d992b。最终records与weekly原字节相同；083只两处毛/净盈亏与手数卡片及转义说明，067只追加当前交易Reset，图形数据/坐标不变。
- 全量工具验证：stages/stage102_validate_enabled_v1_display.json（SHA 94284b8b043b16c93c23e2e961a169cf3fdea6b2105dedc9698743b84e1a47c3），复验caller 20261020_0208_stage102_validate_enabled_actual.py。097的081独算命名空间仅传enabled的raw/fractional/weekly/final，未调用pair函数；完整entry数量/分平费用/残仓分配、.0025原始及开盘预算/整笔R、源最后实际退出价/日期/marker、内嵌records、全部产物hash及全部JS语法PASS。结果明确pair_validation=false、独立agent审核=false；这是作者执行工具validation，页面实际独立reader与UI由root另做。
- 精确合约周图独算：1311笔/1004合约，96857周slots，484285个OHLCV与387428个MA值，最大绝对差0.0；35778缺周如实None，不补主力/不压缩坏周。非周payload hash 6095d1db46976578fc3522c45ae87a6a8c5e47f80b8cd26c41f93e6c7f450c16；所有周label/x/width原样。纯显示未实例化/查询金融周provider。
- 最终退出点为最后一笔实际成交价，涨跌使用全部退出数量加权均价，不逐fill画中间箭头；原顺序和尾部选择标签保留，补R不追溯重选。所有原日线近似/缺15m/背景代理/残仓与其他冻结边界保留，不称严格分钟C9/实盘或晋级。

## 冻结源指标（引用原summary，非本阶段新金融结果）

- initial_capital：1000000
- analysis_start：2015-01-01
- analysis_end：2026-10-16
- end_balance：809719.744577212
- total_return：-19.028025542278794
- max_ddpercent：-37.111968008936934
- sharpe_ratio：-0.19656998442423415
- total_slippage：207215.0
- total_commission：47445.255422787006
- total_trade_count：2641
- completed_episodes：1311
- win_rate_pct：31.88405797101449
- payoff_ratio：1.953592406378762
- profit_factor：0.9144475093687823

资金/回撤单臂状态overview由root另建，明确关闭版失败；本记录不伪造配对资金/收益。来源每日2862点的金融账与费用由Stage101独立核；本工具当前验证逐笔与图形，未用失败off执行pair overview。

## 实际日志与复验

7份原/tmp实际日志已复制为同stem_raw/fractional/weekly/reviewed/labels/reset/display_validation.log，下面JSON绑定各SHA；旧0201源预核JSON、旧失败logs及全部旧输出均保留。复验：

```sh
/Users/mac/Desktop/fian/.py311/bin/python research/lines/futures_trend_full_market_noai_one_lot/stages/20261020_0208_stage102_validate_enabled_actual.py --output <全新单臂工具报告.json>
```

新增/修改/删除金融参数或结果：无；未金融回放、下载、生产/订单、Git/LINE操作。外部调研沿用Stage094–097官方Plotly共享轴与CME单位风险资料；判断是复用冻结图形、精确区分策略与显示的证据，不因off失败补造对照。过拟合：本显示工作否，不选参/不选赢家；继续价值：是，原启用v1事实可审可复盘，但配对结论不成立，未来共同模型须另授权同源双臂。
