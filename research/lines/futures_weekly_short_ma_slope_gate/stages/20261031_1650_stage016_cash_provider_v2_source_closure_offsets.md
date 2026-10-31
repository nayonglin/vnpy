# Stage016 原始券商provider V2：语义依赖闭环与原生平今/平昨对接

- line_id：futures_weekly_short_ma_slope_gate；day。
- 时间：2026-10-31 16:50 CST；隔离树 /Users/mac/.codex/worktrees/weekly19-official-20261031/fian。
- V1 checkpoint：1231a7fa6；1622阶段原manifest/合同/日志与原provider独审历史全部保留，不改历史SHA。
- 本次性质：独审P1/P2输入闸修复及真实CTP业务offset适配，不改alpha、初始15万/场外15万资金比例或策略风险。
- 是否重要突破：否；是否触发A/B：否。production_qualified=false。

## 调研及独立判断

- 沿用前阶段已核对的[官方CTP结构定义](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/api/include/ctp/ThostFtdcUserApiStruct.h)与本机6.7.2.1字段：native OffsetFlag/CombOffsetFlag 0为开、1为平、3为平今、4为平昨；必须保留原生具体offset，同时原策略parent只消费业务open/close。
- 独审指出provider直接调用funding._broker/_parse/_money及broker_account_snapshot._context，但mandatory trust清单仅3源。复现表明调用方把这两个依赖pin显式置0或删除仍会被旧条件loader接受；仅全release未来pin并不能消除此独立输入闸的盲区。
- 独审另复现两个P2：未知native Direction/OffsetFlag映射None能与异常ledger None相等并输出null；新鲜outer observed_at可以包装陈旧bank query/callback，旧parser没有重核内层时间。均先写反例验证，再修复。
- 判断：SHA仍只证明字节，不证明broker源资格；本次只消除已声明源pin被忽略、未知enum漏拒和原生/业务offset混同，不把fixture变生产证明。

## 四项修正

1. **P1直接语义源闭环**：CAPTURE_SOURCE_FILES mandatory为5源，publish和load完全相同：Stage174、provider、late_retry_fill、funding、broker_account_snapshot。缺任意mandatory pin、错误pin、当前源漂移或capture与当前源不同均拒绝。调用方额外declared pins也逐一校验，不能当注释忽略。
2. **pin路径边界**：只支持规范相对repo代码路径（.py/.pyi/.c/.cc/.cpp/.h/.hpp/.sh/.rs/.m/.mm），全路径O_NOFOLLOW和regular单链接文件；绝对、..、隐藏路径、非规范双斜线、env/不支持类型显式拒绝，校验前不读私有env。全release更广transitive closure仍由root不可变物料pin负责。
3. **P2/SHFE成交offset**：未知native Direction或OffsetFlag立即拒绝，不输出null。唯一原始Exchange/OrderSysID对应订单的CombOffsetFlag和Direction必须与trade完全一致，不能只靠caller业务close。ledger若声明broker_offset也必须精确一致。public orders/fills的offset/business_offset为open|close；另保留broker_offset=open|close|closetoday|closeyesterday及native_offset_flag原0/1/3/4，原raw capture字节SHA不改。native open绝不能误配业务close。
4. **P2银行query内层时间**：parser独立验证request_sent_at及每个callback均带时区且<=300秒fresh、sent<=callback<=outer observation<=now；匹配BankSerial的原生发生时刻必须<=承载该行的data callback。新鲜outer时间不能续期30天旧查询，发生晚于原始回调不能被接受。

## 测试和兼容

- 新增8个行为测试（含多组子反例）：五源identity、missing/wrong两个依赖pin、所有declared extra pin、out-of-root/env/隐藏/软链路径、模拟依赖代码漂移（仅临时复制源码，不改锁源）、unknown枚举、SHFE close/closeToday/closeYesterday 6组正例/5组反例、银行内层陈旧/发生在callback之后。
- TDD第一轮：原23+新增4=27tests，12组反例失败；修closure后27tests绿。第二轮增加enum/offset/bank时序，31tests先4失败+3错误，修后31tests全部绿。
- 本轮最终 provider31 + 冻结资金V2 51 + Stage174既有22 = 104 tests，exit0。内存compile、git diff --check通过。
- 新provider SHA：f5e1ef1cb95e8641a098e8f44940b29d50ac3db98891f8213f1a9c83032d94d4。
- 新tests SHA：bd8c195152fffa6936a25e3fe6a35be3e7427b896499d9fea210d34dc269ff2e。
- locked_funding_v2_unchanged：{"examples/portfolio_backtesting/qmt_roll_weekly19_funding.py": true, "examples/portfolio_backtesting/qmt_roll_weekly19_funding_store.py": true, "tests/test_weekly19_external_funding.py": true}。
- 只改本agent owned provider.py/tests；没改Stage174源、资金V2源或其它agent文件。没改Git index/commit、生产、凭证、CTP连接、银行或SMTP。

## 资格限制与后续

- 真实capture authority、真实银行callback样本资格和最终cashflow statement/day-close parser仍缺；默认require_production_qualification=true保持block，production_qualified=false。
- 任何explicit offline false只用于条件审查，不能宣称实际资金E2E已通过。query-last/clock仍不能替代最终现金流关闭证明。
- 没有金融回测，期末权益/收益/回撤/Sharpe/滑点/成交/胜率/payoff/PF均不适用，旧研究结果原样保留。
- 已向独审agent发送锁源SHA，请其复验原P1/P2；独审结果另记，不提前宣称通过。root负责按新5源pins更新真实runner、runtime/execution/report并重建不可变新manifest。
- 不更新LINE/registry/根总账；V1证明不覆盖改写。

## 反思

- 开始/结束过拟合：否。固定输入闸与真实CTP语义修复，不依赖历史收益或扫参。
- 开始/结束继续价值：是。避免语义依赖漂移、null枚举与SHFE有效平仓被错拒；下一步价值是真实源资格和独审，不是继续增加参数。
