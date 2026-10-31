# Stage018 Stage945周线目标日历与冷启路由修复候选

时间：2026-11-01T04:52+08:00。所属线futures_weekly_short_ma_slope_gate。重要突破：安装路由接缝修复候选，非生产晋升。

## 发现与触发

Stage945已有weekly session command及daily receipt分支，但_resolve_target_date仍无条件subprocess Stage922；后者要求main_contract_mapping_trading_calendar旧C9来源。_target_is_before_live_shadow_start仍仅认全局旧cold常量，_validate_target_date_calendar_window仍C9窗口。配置切weekly不能让该前置路由自动正确。新增第一条测试直接断言weekly禁止Stage922，原代码实际误调并失败；其余新API路径共8条原始RED（1FAIL+7ERROR）保留。

## 最小修改

仅改Stage945已有源码及已有test_stage945_production_launcher.py，没有新增critical源码文件，也没有修改Stage922、资金、runtime、core alpha或旧C9分支。

- weekly目标从固定PRODUCTION_RUNTIME_ROOT/weekly19/context.json读取自有private0600 JSON，核schema/profile与cold_start_date严格ISO真实日期。
- 复用现有public resolve_completed_target验证五源pin、具体calendar文件SHA/日期与今天以后的覆盖；不读旧C9 main mapping，不猜周末/假日。
- payload来源明确weekly19_private_context_pinned_market_calendar。绑定controller.immutable_context_digest（仅cash_sources可变）、calendar具体SHA、五源SHA、cold日期、目标/next session、Shanghai aware asof与16:30 readiness。
- cold skip重建当前source与完整payload校验，再计算target<cold；不是信布尔，也不使用旧C9常量。输出weekly19_context_cold_start_date/cold_start_source，保留既有成功skip状态及API0，不要求pre-cold dailyreceipt、不进入生产env/exec。
- weekly calendar window核同日/非future asof、receipt target/release/profile/next-session/源5pin/calendar SHA，重算当前eligible target。保持16:30门、真实holiday跳过、夜盘与周六late continuation，不把weekly source假装旧main_contract_mapping。
- 合法人工cash ref追加仅改变cash_sources，不让无关日历绑定漂移；profile/cold/market等变化一律拒。
- cold之后原load_and_validate_weekly19_daily_receipt仍必经；没有将source bool或calendar可读当作dailyreceipt/qualification。

## 保留与验证

旧C9三个函数在去掉新增weekly dispatch（_resolve额外now注入参数）后，函数AST与基线commit b086a81264383a0504dc51aef88191d9e24230c5一致；新辅助均在945内。原C9 Stage922、旧cold常量与窗口代码保持原样，旧regression继续通过。

11个新增weekly用例覆盖：不调用Stage922；ctx cold与旧常量分离；改bool/改cold拒；错profile/非法cold/日历pin/五源漂移/不安全权限拒；receipt next日/source mismatch拒；允许cash_sources追加；16:30前后、夜盘、周六延续、真实calendar声明holiday、stale/legacy来源拒；pre-cold main在dailyreceipt/env/exec之前成功skip；post-cold dailyreceipt缺失仍原门拒。

Stage945+Stage947+weekly context+weekly daily receipt共106 tests/3.046s绿，包含11个新增weekly用例。旧RED与first-green均单独保留。另用本次真实TQ完整market generation（同目录6真实basename pin）做public945条件proof：11/2 09:00→完成目标10/30，private context cold=10/31→skip=true，无Stage922/subprocess。该private context明确为条件fixture，不是实际账户/activation。

## 来源与边界

Stage945 SHA bf43bd03ea358cdc8a8599a9423c63c1bd9e46eaa70852a99e32555d34a448d3。源码、测试、证明与日志的SHA见Stage018_review_launcher945_candidate_hashes.json。

本轮未connect CTP、未SMTP/HTTP服务、未实际launchd/exec、未Git/index/commit或生产写入。daily receipt、release/activation/code qualification等原闸门保持。策略参数与金融结果新增/修改/删除均无，各权益/收益/回撤/Sharpe等不适用；没有金融回测。真实CTP、人工cash review与生产资格仍由root继续，不能将此候选测试作为实盘已安装/可执行证据。

过拟合：否，修复profile来源路由，不改alpha/参数。继续价值：是，避免周一仍依赖错误旧calendar/coldstart；后续应独审并重新冻结945 source，再由root管理release/安装。
