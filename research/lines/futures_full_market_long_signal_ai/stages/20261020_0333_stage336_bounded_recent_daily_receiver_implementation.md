# Stage336：有界六所真实月份日线接收器

时间2026-10-20 03:33（Asia/Shanghai）；line_id `futures_full_market_long_signal_ai`。非重要收益突破。先registry、333 next_scope/334最终盘点、335规则，再复用265必要传输/264脱敏与既有credential loader纯函数。只新工具/test、本stage与自身implementation；0作者真实连接、0私有config读取、0旧cache/经济/SQL/fit/cash/旧suite/下载/资金state/T0。

实现[run_batch](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage336_recent_daily_receiver.py)和唯一receiver tiny已GREEN；[bundle](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage336_recent_daily_receiver/implementation/source_bundle.json)、[授权模板](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage336_recent_daily_receiver/implementation/authorization_template.json)（authorized=False）。root338统一执行，作者不actual。API `run_batch(auth,output)` / CLI `--execute --authorization --output`，adapter创建fresh output本身，root只创建父目录；已存在时在config/API前拒绝。

## 传输与不可覆盖原件

显式`TqApi(TqSim(),auth=...,debug=False,disable_print=True,web_gui=False)`，只1连接，无重连retry/CTP/下单。一次`query_quotes(FUTURE,六所,expired=False)`；保留fresh原catalog、旧870及差集（old-only不冒称已经证实退市原因），union所有真月逐symbol保存success/missing/error/已试未存/未试状态。18个DCE l/pp/v的F后缀真实月份不误筛掉，连续/主力/指数/组合/期权拒收状态保留。

每个symbol独立`get_kline_serial(symbol,86400,data_length=35)`，不使用多symbol对齐series。沿265 chunk80异步订阅、ready40秒；硬global720秒含SDK同步阻塞，connect/catalog/calendar各45秒，close最多8秒；连续连接异常3或全未ready批次3断路，globaldeadline到后不再派发。显式检查`is_serial_ready`，不把`wait_update=True`当ready。一次同连接`get_trading_calendar`保留日期与取得证据；失败继续raw-only/dateunknown，不伪造假期。

ready或未ready的已返回frame立即deepcopy，不改SDK原表；全部35行含padding/invalid都保存。逐列取datetime原dtype，不iterrows、不先转float；raw ns整数、原literal/type、本地ISO和缺失字段均留。float ns不宣称无损int。所有原量价/OI/native字段不缩放，`units_status=provider_raw_units_unverified`；≤10月16日原件保留给后续与331compact有限overlap，绝不由旧截止日前factor1规则给新日自动授单位资格。

批次与symbol文件均exclusive create，不覆盖旧批次/版本；321真实UTC append给目录、calendar、每symbol原件及失败状态firstseen。部分写入故障保留已成功/raw/receipt；错误后的target全量补状态，已试不改未试。已有capture manifest不覆盖，外层追加post_capture_failure作为effective_manifest，terminal明确指向，避免“成功现场仍在却终态说全未试”。

credential仅root actual门内读取现有本地设置；AST复用既有`require_credentials`，不import旧全合约CLI/vnpy配置入口。错误仅type+既有redactor脱敏message，stdout/stderr与SDKdebug关闭；不保存config、TqAuth/Account或traceback秘密。root preflight只presence属于root证据，作者没有读取实际credentials。

## 335日期/时钟与339接口

只有root显式`tq_daily_midnight_label_calendar_v1`、86400、北京时间精确00:00且fresh/绑定calendar该日True，才给operational label；这不是服务器统一午夜语义的证明。非midnight默认unknown；只有已声明session-start契约且唯一命中确认具体interval才映射，不18点/周末兜底。原始ns/local和不确定行永不丢失。

`source_completed_at`只取已确认u最后session_end；实际fresh-ready的321receipt是`completion_observed_at/received_at`。无session_end、尚未闭市或未ready则完成时钟None；不以晚取Oct19的R伪造冻结后u。D为下一confirmed源交易日，Dopen须明确session/假期证据，否则None；不以午夜/auction/下一根日K补开盘资格。T0=None/active=False/vendorfinality与首发时间unknown。

identity_map是`symbol→epoch字符串`。验证exchange/product/F与名义月尾码一致，不能把FU2701因2026-12到期而改成202601；没有显式绑定的年码（特别CZCE3位）留identityunknown。root可另绑定331current/inventory唯一候选map，新fresh目录未绑定仍raw保存。

normalized artifact含raw binding/321receipt、post16 observations及unknown_rows；每行保留raw row_index/native_values/date/identity/units/quality/clock状态。`canonical_quality_status=unknown`、`model_input_eligible=False`、`canonical_model_rows=[]`，**传输success不等canonical accepted**。337/root之后基于有限overlap与来源证据显式签accepted overlay，339才可喂原固定模型；receiver不借新日源资格改alpha或默默乘2。

## 唯一新tiny与调研

唯一方法`test_true_month_raw_receipts_unknown_clock_timeout_and_immutability`先RED核心未实现（首次测试语法括号错误先修）；后同组明确unknown资格和注入journal I/O故障先暴露字段缺失/target状态不全后修。最终exit0/1test/0.045秒。fake transport但真实temporary immutable文件与321journal；覆盖六所/F/retired差集、单symbol35、notready timeout、连接断路、secret脱敏、1ns不丢/float nsunknown、非midnightunknown、sourceEnd与R分离、错误nominal-year绑定拒绝、freshdir拒覆盖和已采success失败后保留。没有跑旧任何suite或实际API。

有界2queries/2pages核[官方TqAPI](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)与[维护者GitHub API](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)：独立serial与ready/起点含义、目录/calendar能力，并以本机3.10.2必要源段复核；网站3.10.3不触发升级。接口事实不证明本账户权限、全目录新bar覆盖或vendor finality；现需root实际接收并337审新证据。

新增/修改/删除金融参数/结果均0，权益/收益/DD/Sharpe/费滑/胜率N/A。本次无新增拟合过拟合搜索，既有历史择题风险仍在；继续价值是取得真实新接收证据，不能把raw/未知单位或tiny绿色当alpha、forward已启动或生产ready。原模型/策略/LINE/registry均未改，0调度/邮件/CTP。

03:35：337发现唯一窄终态窗口，root授权仅把report.update与manifest写入共同移入既有try/except以附receiver_report。已作该移动，当前新receiver组仅复验一次exit0/0.045秒；未增组/旧suite/数据/API。final bundle/template/fixture绑定同步更新，到此停止。
