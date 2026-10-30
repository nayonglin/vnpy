# Stage009 工作进度（不属于冻结金融输入，完成后封存）

- 用户规则：总30万=交易15万+备用15万；新有效flat/reverse信号且含MTM交易E不足15万时补差额至15万，最多剩余备用；备用只减不回填无息，永久隔离；盈利超过15万按全部交易E动态开仓，用户已明确确认。
- 沿Stage008的23起点、同2026-10-29截止；46新候选引擎，控制是旧A/C账本+闲置15万同30万总本金；22成熟+1观察/臂。原19/无加仓/MA斜率与多头价格门关闭，C只保留短底20。
- 冻结commit HEAD0d08d2e152b4b0a769ddee889b4285c950282525；金融batch结束前不要commit/改HEAD。
- freeze stages/stage009_freeze.json SHA d53d36fc21b8308b220cd69484697ae3d1b29074abd23311f28f58feec4e406a；22 source SHA。必需新金融6文件+design/plan/data_preflight2，不可修改。
- 独立金融前code预审PASS，stages/stage009_independent_code_preflight.json SHA dc31bfccc0e090a2392c01e690280f632718a344db325f9a72d8de65a2d2365f；root46tests GREEN，独立41tests GREEN，均金融前。
- data预检JSON SHA bbe46874c9cd8c13a47389b51d61dcf3283ab75e90062dfa4def93ea9ba1fd59，四行情SHA同Stage008；已有历史/手续费/静态保证金/PIT限制全部继承。
- prepare精确复验旧46源完成（session86339 exit0）。canary2015Jan A/C完成（session23242 exit0），新registry validated2,pending44,failed0，等待独立真实财务canary批准再resume，不可擅自批量。
- canary A总权益4110505，T31580，R118420，5补资；C总4325345，T43960，R106040，5补资，仅canary不是23窗结论。
- root纯后处理：tools/stage009_accounting.py(7tests), stage009_derive.py(2 raw统计适配tests), stage009_report.py(4tests)；均新增不改旧。真实idle临时目录适配PASS3811110；真实canary temp适配session44551正在跑（不金融），还未启动实际92缓存watch。
- raw辅助曲线=150k+真实PnL；交易E=raw+cumT，R=150k−cumT，总W=raw+150k=300k+真实PnL。主绩效总W30万，内部转账不能算盈利。raw<=0不等交易/总账户破产。
- derive新增stateless AST env provider，仅旧pure curve_metrics raw Sharpe为None时按冻结s650 pct_change/inf→nan→0/std公式匹配源raw指标，其余库存/成本/逐日/参数审计不改，主总W另算。独审同意此边界不重跑金融。
- 所有event.raw须严格等同日真实raw daily；Stage502/827实际队列先fills后on_bars，runner另真实fill_phase证明且post-sizing fill须0。P1伪造event原始时点未锚、P2 long_case3放宽都已金融前RED/GREEN修复。
- agents：independent_review负责46新窗口/精确canary审批及final aggregate；data_extension金融源码已稳定，正在新finalizer+测试；multicycle_runner的plots已稳定完成5tests，不再改financewrapper。
- report字段：summary92=四variant A_idle/A_R/C_idle/C_R×23，paired46=start×arm，指标idle_/reserve_前缀（total_return_pct保持全名）；cohort12=arm×January/June/combined×成熟/观察；daily141996；主比较同30万。
- 图模块tools/stage009_plots.py render_five(summary,paired,daily,reviewed=False)返回五Figure不保存。五名：01_full_2015_nav_drawdown.png,02_january_starts_nav.png,03_june_starts_nav.png,04_reserve_effect_heatmaps.png,05_cohort_reserve_summary.png。只有92缓存/46金融/46独审齐备才发布pending报告，锁final SHA后生成reviewed副本及receipt，不改pending。
- 最终期望：stages/stage009_independent_final.json(PASS/P0P1P2failures0,freezeSHA,arm_windows46,paired_windows46,independent_starts23,report_comparison_sha256)，reviewed receipt绑定最终SHA+绝对路径五图SHA。finalizer原子46逐窗中文+唯一分钟总stage+总manifest，最后提交本地，不推送。
- 旧Stage001—008/LINE/根registry/根总账/44线/正式/生产不改；旧未跟踪stage003_offline_delivery保留。无HTTP，无CTP/下单/邮件/行情下载。

## 批量阶段更新

- 双canary独审PASS并批准，批准SHA edf93fa2a1407947227ab13536205b20689b33cd7a960a6465be252a950961a9；金融resume session96273正在跑余44，当前14/46 validated、3running、0failed（counts会继续变化，读registry）。HEAD0d08不变。
- 原independent_review及continuation turn因模型容量错误停止，但原stream存活PID12876并持续46纯审计，绝不可重复启动。当前11份PASS收据。新独立agent stage009_final_audit（gpt-6-astra/high，按executing-plans最终强审要求选用）已接手最终aggregate/report，全量21完成周实际开仓暖机复核，当前可正常工作。
- root耗时完整deep canary temp已A/C都PASS；正式cache改为load_signed_accounting，精确复用已签窗口独审的rounds/末MTM及源snapshot/input/auditorSHA，从原daily+events重新算W/T/R/phase/risk；同canary signed派生与deep派生逐指标一致，无金融重跑。末未平周期数从真实positions末日end_pos非零合约数取证。derive/accounting目前锁稳定不再改。
- 实际92缓存watch已启动session59548，log stage009_accounting_stream.log；46idle全已派生，之后每份新独审receipt完成后才派生对应reserve。当前57/92，变化读cache目录。无需重复启动。
- root实际主报告tools/stage009_report.py完成4 tests RED/GREEN；五图source已稳定。root report build只有46validated+46audit+92cache齐备才可执行，141996真点必须齐；paired指标idle_/reserve_total_return_pct全名。comparison.variants是名称list4，summary缺省cohort由start判定。
- 新finalizer tools/stage009_finalize.py及11tests稳定，CLI --locked-review-sha <SHA> [--validate-only]，不输出重定向到stages活跃文件（否则封存后的stdout改变SHA）；用stdout或/private/tmp。等待最终finalJSON锁定+五已审图后才能真实封存。各源金融started/completed时间与交付时间分开。
- multicycle_runner正新增stage009_reviewed_visual.py+测试，仅展示不金融，等最终锁定SHA再执行；不要改pending图/报告/独审JSON。
- 最终仍需：全部46金融+独审/92缓存、root build完整pending报告与view五图、fresh最终独审锁SHA、reviewed派生五图与receipt/视觉验收、finalizer validate/publish46中文+总manifest、逐SHA复验、仅本地提交Stage009新文件（金融结束后才改HEAD），最终中文全23结果/同本金A/C资金对照与反思，NO_PROMOTION。

## 审计调度恢复与后处理稳定

- 原stream进程确已在11/46时停止（旧模型capacity turn失败），原空日志保留。fresh stage009_final_audit独审确认后新增纯调度v2，不改window审计源码；root读全源码后托管运行session87046，max2，PID18091，全局flock继承到子进程，临时收据扩展.pending，完整验收后原子canonical .json，不与计数glob混淆。v2源码锁SHA7ee738981d36174e147501f47600f1ce15ec4e25af81414e3762421c9e6d3054；old window SHA63e9...不变。现审计已追到34，financial35，0金融失败。
- root主financial session96273、cachewatch59548、audit87046、报告waiter22025均归root托管，勿重复启动。report_build.log等待all46金融/独审+92cache才调用build。
- 当前Stage009全套75tests通过，证据stages/stage009_root_all_tests_75.txt，后续最终测试由独审根据锁定源重跑。
- reviewed_visual工具/test已稳定，源码SHA1304eb90be7df49054426a727848175fa8d061029c6416e2e4c9d888fa79ea68 /7cbd1f096427c0d469e6fd6c24025439c905c57d26ccda779bcc212e998ea05a；CLI --locked-review-sha，最终review.source_files_sha256须绑定这两文件。CSV float_precision=round_trip保证重建pending PNG逐字节同；最后才出reviewed，不改pending。工具已75suite含5专项测试，synthetic完整92/46/141996点roundtrip smoke PASS，没有真实reviewed产物。
- 新最终独审agent会从原始92 daily/events重算所有metrics/risk/curve，不调用生产后处理函数；新增全部真实开仓同epoch21完整周且周内session完整核验。finalizer11tests稳定，已知comparison.variants为精确list，summary无cohort按start判，pooledcohort12/paired46。
- root未改变任何金融冻结源/HEAD；所有中途产物不是最终报告。
