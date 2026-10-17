# Stage096：A_OFF真实终态——回放返回后快照guard失败

- line_id：`futures_trend_triple_screen`；2026-10-18 07:19 CST，root。
- 本轮为progress：实际双臂预检/本地冻结/首次A真实运行已执行，随后真实失败证据改变下一步；当前不是verified wait，原session已终态，不再poll或restart它。

## 原样保留的运行事实

A_OFF attempt1，run_id `982636a096884e7e9610b1ad49eb1ae1`，source HEAD `4e439c2e5d653d4171c4396afdc2aad037c547c7`；工具session13114真实终态chunk **8c75d9**，**exit1**。追踪栈表明run_profile_once已返回，save_raw_checkpoint在_account_only(payload)处抛出`checkpoint_forbidden_engine_or_history`。之后partial failure_capture已保存；完整raw_account、validation_seal、summary均不存在，不能称成功或给绩效。

- 真实终态：`outputs/stage096_A_OFF_actual_failure/actual_tool_terminal.json`，SHA `8eb4dfbfd675102a01ad4f6cf7b3aa8cfb814e590f00a396935a088d753fb085`。
- run_failure SHA `6a21416440f3f3441599435ebf55c1ae688006d865d5683a537fea5af2c3d082`。
- failure_capture.pkl.gz SHA `443216dc4e7b3b2550f97aeafee33c9f4376a94aa1513ad3f8e19f5c71cfd96f`。它是partial、无seal，不能当完整金融输入。
- 没有data_wait目录/真实补数请求，没有启动087 driver/provider，无新数据网络连接。B_OFF未启动；其同一checkpoint缺陷应先查清，不能让B重复同错。

## 后续有界处理

097由非065/084作者独立检查真实失败、精确被拒metadata键、partial表覆盖及完整等价恢复可行性；先判断是否可恢复已有账本，不能凭estimated_equity或截断capture冒称完整收益。098由原作者只读定位/给最小修复设计，尚未授权改冻结源。095审计适配已冻结，但其真实exit0+sealed完整账本门会拒本次失败，不运行它或改写completion模板。

root只授权诊断，不清空/覆盖A_OFF，不启动B、不重跑旧suite或账户、不放宽价格/对象/成本/时间门。若实际字段不足以恢复，应明确缺项并重新设计合法下一attempt身份，不能删除目录伪装attempt1。任何必要修复只针对账户保存正确性，未获新金融运行授权。

## 参数、结果及反思

正式月AI10+fu、共同八项OFF、0.5R/retry、2020-01-01—2026-10-14、150000本金、成本和原限额不变。新增/修改/删除alpha参数0，新增完整成绩0；期末权益/总收益/最大回撤/Sharpe/总滑点/交易次数/胜率均N/A。累计金融9attempt/3accepted、训练0，原失败/负结果/PIT限制保留，目标未达成，production_qualified=false。

开始及结束新增过拟合判断：**否**，失败来自保存边界，未看PnL救参。继续价值：**是**，优先恢复已计算结果和修正会导致账本丢失的必要缺陷；但不能把工程通过或失败投影当策略优势。

## 097独立闭环与099必要修复授权

097正式receipt SHA `66dbcae018de1a76b58ad08dcadee85ed8b0d1a3c56fdb52872d2a0e47835a13`，P0/P1/P2=0/1/1。独立确认被拒路径为payload.preflight.ai_pool_audit.strategy，值为合法字符串ai_top10_plus_fu_official_live_v1；没有engine对象。原fixture preflight只有7键、无ai_pool_audit，漏掉实际元数据结构。partial已核817条唯一trades/usage身份一致、1697内部equity含56个preload日，不能替代缺失combined和13张frames等原件。不能完整等价恢复，绩效保持N/A。phase=engine_not_returned为置位太晚的诊断误标，不否定真实engine已返回。

root按`20261018_0723_stage099_checkpoint_repair_run_family_contract.md`授权098一波必要修复及095纯路径/当前review接线适配，100另作一次独立定向复核。原A目录不删不移，新族固定stage099_pairwise_off_account；族内attempt1不隐去全局A下一次第2次/B第1次和金融历史9attempt，parent096失败是新readiness必需绑定。当前没有新金融或网络授权，需修复/独立接受/新实际闭包后再定首次新族执行。未扩alpha、阈值、成本或时间限额。
