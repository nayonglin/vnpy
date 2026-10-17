# Stage054 SM009真实日线恢复与原B进程继续

- line_id：futures_trend_triple_screen；day模式，持续自主目标有效。
- 时间：2026-10-18T05:04+08:00；分支codex/ai-training-data-expansion，金融启动HEAD008575e132ea76032d904cbd407aa6f85566b349未改。
- 不是重要突破，不是新alpha版本；只解决当前完整B账户的真实数据缺口。原金融session70433/PID21822不重启，金融累计仍8次attempt/3个独立验收完整账户，B第1次尚未完成，训练0。

## 调研、设计和实际变更

- 官方API（https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html）及GitHub官方回测说明（https://github.com/shinnytech/tqsdk-python/blob/master/doc/usage/backtest.rst）支持标准行情序列/回测接口。实际固定SDK3.10.2源码的get_kline_serial最大10000，与旧说明页8000表述有差异；以本机已核哈希的正常SDK和实测为准，不更改授权、鉴权、端点或SDK。
- 我的判断：已成功037/041的25个历史packet仅保存实际目标4387行，extra=0，不能把不存在的额外分钟当缓存。普通latest分钟快照也不能保证SM009远离到期的Apr15覆盖，因此不新增该假设路线。日线普通快照则已证明可用于精确缺参考，并可后续逐日再资格。
- 051泛化原040的单一正常API日线恢复：1—8个选定真实需求/精确原合约日期、每request独立目录、最多1连接/570软600硬秒/1.5GB、只读DB六字段、原CSV及013已批准/拒绝scope不得覆盖。旧040/44—48不变。
- 052保留047联合/R/E/M/048语义，只新增真实051终态来源；原参考优先，旧实值冲突/缺后继不能改用新源救。当前051根若已存在须严格验该根，失败/残缺不得借缓存掩盖；否则只读同symbol、真root exit0且全SHA链匹配的已完成origin，冲突SHA拒绝。原origin目标值/proof独立核对后，本次真实日期另查DB六字段和raw真后继，仅签本次日期，绝不把其它snapshot日自动资格化。
- 新增参数均为数据工具的request/fileSHA、selected symbols、preflight/sourceSHA；没有新增/修改/删除策略参数，没有修改035/036、AI名单、0.5R/retry、仓位、风险或模型。

## 真实运行与有限审查证据

- batch004—006各4连接后真实exit0，batch007在3个交付后因SM009/Apr15缺日线参考真实exit1；同一B仍在等待，不是金融失败，也无新财务attempt。
- 051源码89a2de7464f4b30eb3b3887ac265ca5433c7288fafcb117802072360c6a6228a；协议ef26cec11539e488ad30d327afaa5ac7635826ed02c57aa5cff6a3ffe29add61；离线preflight692f0c45529fc2984c86d3a814ba09b07f85064d399412aeb97afac0029301d1。
- 独立053对当前真实225行full请求、DB6、源码/SDK/preflight/CLI父子执行链有限审查P0/P1=0；收据ed1fe6e9d4e16c4d1323d0a323a348205cf3161d1bfb6249b62f864e5f252d4a。051两项有意义RED→GREEN，不重复旧suite；worker首句新binder以外AST同040。
- root真正运行051 session72709，exit0、9.265389417秒、parent all_inputs_unchanged；root终态df922f4025a1031d0cbc61f0a80fe40b93e8a47eca23c9f518c9dfccaa370934，parent dc07ea9931a900c2d6d7b58ceedb9d6b0c650cc75b94327f9f16df742607c260，正常API1次，无金融/委托/CTP。
- 052最终source5b2772c700f0ddabb5536df4be1bfe1f70e07d8fea43400abfa74c66ae727b78。早期候选结构测试及当前缓存后续日有限case准确保留各自source SHA；Apr15 origin→Apr16真实DB/raw id139→140 helper为纯检查，不是实际新日签收。
- root首次真实052 main exit0、0.641秒，独立Apr15 daily receipt8b6ea864f0257976320cb33599d535f8ecae46e95de9a0feb208584c1d81b74d，结果needs_provider而非分钟已齐。
- 之后同一044/048、新batch008真正交付SM009 Apr15 full225，receipt b136434872b83890169e1e6b282d9e7e3f83066bc9e5163c115295c76ec1cd50；真实B resolver audit确认accepted，等候849.506266417秒，未跳信号/日线open fallback/截断。
- batch008/009均4连接后真实exit0。实际SM009 Apr17请求f7fe93e662e9f9bc2c9cc2b67d7ba20857633d8600e8d1ed4a17278222ee472c已通过同一Apr15 origin缓存再资格，reused_completed_snapshot=true；此项为真实签收而非Apr16 helper。当前后续批次继续，观察至Apr23。

## 回测结果及下一步

- 固定2020-01-01—2026-10-14，150000本金，历史AI eligibility、0.5R及一次retry开启、原滑点、commission参数0。完整券商成本资格仍未完成。
- B期末权益/总收益/最大回撤/Sharpe/总滑点/交易次数/胜率：全部N/A，原金融尚未真实终态，不能用数据交付数代替完整账本。
- outputs/stage054_root_batch_chain仅串行固定44/52、batch008—020，每批最多4分钟provider连接；原1800秒每等待/7200秒整次期限不延长。原链050及失败007证据保留。
- 下一步：原B完成后检查完整raw/seal/summary，并由独立038金融复算现金/库存/成本/预算/母链/七门。若实际失败保留失败证据，不补造盈利；正候选再进入固定多周期/成本验证。

## 反思与登记

- 运行前/后新增过拟合判断为否：未按B完整盈亏调参，历史研究选择风险不消失；没有全新OOS主张。
- 运行前/后继续价值为是：为已冻结B取得完整账户；数据工具成功没有达成更高收益且更低回撤目标。
- root更新本线LINE；registry有他线脏改动不动，根memory/back_log不追加。原始行情、DB、私有配置不入Git。仅保存必要源码/协议/资格元数据，金融运行中HEAD保持原值，不推送、不部署。
