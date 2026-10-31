# Stage015 正式替换授权后的独立技术预检

- 时间：2026-10-31T15:39:18.543549+08:00；line_id=futures_weekly_short_ma_slope_gate。仅scope=promotion_preflight，无新回测、无生产修改、无CTP连接、无订单或资金API、无commit/push。仅新增本记录与stage015_independent_preflight_review.json。
- 结论：TECHNICAL_QUALIFICATION_REQUIRED，review_completed=true，promotion_gate_accepted=false。P0缺口4、P1工作项2、P2技术缺口0；这是晋升前置缺口，不是声称当前线上已有4个已触发事故。
- 本轮用户已明确授权用Stage014 C_R150替换正式策略并推进master/生产安装（授权由root本轮任务载荷传达）；无需重复风险许可。授权不是技术qualified，不授权本审查连接CTP、资金划转或真实下单。目标Mac/既有生产主机和场外/同账户隔离两项实现约束正在由用户确认，本审查不代选、不重复询问。

## 已核实身份

研究checkout及本机候选稳定checkout的assert_official_checkout_matches_active_material均PASS，仅证明解析范围内CURRENT/manifest/顶层正式config一致。共同身份：strategy=ai_top10_plus_fu_official_live_v1；ruleset=stage037_stage034_long_short_mirror_hard_block_v1；material source=2a7420a9f9550ab912b5c4a302a61acc5740b04c；release=m0008_20261008T204054+0800_2a7420a9f955；release commit=334d18f069de06df3aa7728203e942e3ecb94ce9；manifest SHA=94b6936ab4b338430981f4c2f7e0f4ff38f24534c32f1d16722c8d1367d89474。这些都是现有m0008/Stage037，不是Stage014周线候选身份。

旧SOP权威目录/Users/bytedance/Desktop/person/vnpy_production_live不存在。本机Stage945 Home默认候选目录/Users/mac/Desktop/person/vnpy_production_live存在且非symlink，HEAD=d55887e1def72629fbfa310e439dc3a879969a14，tracked clean。root真实ls-remote/readback给出远端master=e41a0a01d53b7256001e45e686acad53667ef7bf；本审查本地Git对象独立复核其与候选拓扑：candidate ahead8/behind0，远端是候选祖先，1176文件差异；CURRENT/config两文件无差异。活动指针相等不代表源码HEAD相等，不能reset已有8提交或把它们默默当生产已安装。verified_production_source_commit=null。

私有状态根/Users/mac/Library/Application Support/qmt-roll-stage179/production-live存在，但release-manifest、qualification、activation/latest、runtime activation_receipt、data-readiness五项文件全部缺失。~/Library/LaunchAgents精确7份预期生产plist均缺；另逐一只读launchctl print gui/501/<精确label>，全部返回113且Could not find service，当前用户GUI domain loaded=false/state=null。未打印/保存环境，未bootstrap/kickstart/安装；不由此推断其他用户/系统域或其他机器状态。

Stage014最终交付SHA=50cc767eefee005e0f47eadbb2387e5dd11cf3a7ff3885057c1b93108dbec1bc；最终独审SHA=cb7d88671e1966d15591e0166d4a68558efd7cec9835d8a9ca1d43b6160657ad未改。59独立回放/54成熟5观察及NO_PROMOTION历史判定保留。preflight明确production_qualified=false；原19品种、全部AI关闭、无加仓、原OI分档风险、周线退出/短bottom20、halfR/C2关闭。它与当前C9的AI池/日内监控和资格profile不等价，不能仅复用15万资金标签或旧m0008资格。

## 必须补齐的技术门

1. P0-IDENTITY-QUALIFICATION：新runtime/source/ruleset/profile/release必须有独立技术资格。selected suite的真实零失败、source-bound formal CTP readonly与独立review必须引用实际相对文件与SHA，不借旧资格、不手填passed。用户override可改变晋升决策，不能制造技术证据。
2. P0-FUNDING-EXECUTION：stage014_reserve.py在118—125行以内存settled_balance += transfer模拟即时转入，只在合格flat/reverse信号、父sizing前转资；并非银行/期货真实转账服务。真正场外模式须先冻结请求→确认实际到账→更新T/R→重算sizing→再允许开仓，处理超时、部分到账、拒绝、重复/重启。未转入R不得计入broker可用资金。若用户选择同账户隔离，则应使用broker总权益减未释放R形成E，持续保证逻辑可用资金/实际broker保证金两道门；不能再次加钱或把总300000当交易本金。该物理放置选择会影响实盘合同，不能默认为研究版瞬时现金。
3. P0-CONSUMER-WIRING：Stage930仍路由Stage904/941，Stage904硬码STOP_RETRY_R=0.5与retry角色；注册profile仅C9/Stage372，Stage945/948仍C9_15W_PROFILE。应迁移shadow→detector→monitor→pending→dry-run→submit→durable ledger/state→daily receipt→qualification/installer全部消费者，并负测拒绝旧C9/halfR/retry意图、同时保留正常周线开平/减仓/对账。单改配置或关闭共享intraday标志可能漏拦或误伤普通订单。
4. P0-PRODUCTION-AUTHORITY：上述本机候选和远端差异、缺5资格运行文件/7plist/current GUI无7loaded均需处理。选择实际目标主机后，按受控发布器、fresh clone、Stage948完整闭环，不机械将旧机器路径替换为研究树并称已qualified。
5. P1-RUNTIME-CLOSURE：研究run入口固定59起点/2026-10-30/研究DB和SOURCE/VENDOR本机绝对路径，并关闭真实提交。应从干净独立来源树迁移依赖闭包、可执行位、模型/资产角色和发布inventory，不从ignored outputs运行。
6. P1-LIVE-STATE-MODEL：declared daily next-open/未确认分钟不能证明真实成交、费用、资金可用性和broker持仓一致。验证周线已完成/同epoch历史、实际交易时段与报价、broker当前仓/挂单/冻结资金、部分成交/拒撤、重启/去重、rollover与新cold start。转资等待不得倒填历史成交或追旧理论仓；未到账/状态不明阻断新开，平减仓与对账依SOP保留。

## 可以继续做与必须fail-closed的边界

当前可以继续：明确用户两项实现约束，准备独立clean迁移树；冻结候选规范/源依赖闭包；编写broker-independent资金状态机和全消费者回归；生成可审查的新profile/发布request，并在准备条件满足后走不可变release流程。用户已经授权推进，不应再次索取同一风险许可；本子任务不执行这些实现/提交。

当前不得宣称/执行：拿旧资格activate CURRENT、promote-master顶层正式代码、生产激活或新开仓；不能将候选发布冒充正式晋升。完整顺序是实现及纯测试→不可变release与fresh clone→匹配source/tree的新qualification/review→activate→受控promote-master/readback→fresh clone身份闭环→Stage948安装→六身份/manifest/activation receipt/7label/daily target最终校验。正式CTP只读取证须在正确主机/env/framework通过守卫并由负责者执行，本审查连接数0；安装本身不连接CTP、order/send/cancel均0。

## 经济风险、调研与判断

成熟54窗51正3负、5备用耗尽、37静态margin×1.65/E>100窗、最深DD约−59.77%、零手续费、5观察不投票都原样保留。这里的技术阻断来自上述缺失/不兼容接线；不以自然经济门失败冒充技术不兼容，也不把用户授权或离线会计PASS写成技术passed。实际broker可用保证金/资金到账是执行正确性门，不能靠风险override绕过。

网上/GitHub调研仅采用[官方vn.py AccountData](https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py)与[官方CTP gateway账户回报](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py)：账户权益、冻结、可用金额由账号数据/CTP查询回报产生。结合本地wrapper推断，研究内加余额不证明broker入金；该推断不是声称上游最新版已替换本地锁定runtime。未下载数据或更换库。

过拟合判断：是，Stage014同历史反复观察且多起点重叠，结果后选择有选择风险；本次技术迁移不调alpha、不扫参、不补跑金融。继续价值：是，将明确晋升意图变成可复验的资金/执行/身份链有价值，补齐技术门后再验收，不用“已授权”冒充“已完成”。

对应Skill明确要求：[freeze](</Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/skills/freeze-official-strategy-materials/SKILL.md>)“任何源码、规则集、物料、远端 master、生产安装或资格身份不完整时 fail closed”；[实盘SOP](</Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/skills/futures-live-execution-sop/SKILL.md>)“Never let an arbitrary development checkout override a stable HEAD, manifest, activation receipt, or daily-data receipt.”本记录将其用于禁止虚报已qualified/已安装，未把它解释为要求重复用户授权。以上源和观测的SHA/命令结构见JSON；此记录仅是预检快照，目标/资金合同回答后应新增后续审查，不覆盖Stage014。
