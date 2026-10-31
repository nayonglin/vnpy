# Stage016 周线默认selected兼容迁移与执行接口续修

- line_id：`futures_weekly_short_ma_slope_gate`；记录时间：2026-10-31 18:57（北京时间）。
- 工作区：`/Users/mac/.codex/worktrees/weekly19-official-20261031/fian`；原研究树、生产源码只读。
- 状态：`SELECTED_COMPATIBILITY_CANDIDATE_NOT_QUALIFIED`，`production_qualified=false`。非重要突破版本；固定Stage014工程兼容，无策略参数搜索或金融回测。
- 承接18:25的controller/native候选。本阶段源码与root bridge仍在并行变化，旧source SHA不是本轮完整源；1835资金V6锁的931整文件SHA也不能冒充当前931。保留各阶段证据，不覆盖旧证明。

## 调研与判断

继续依据已核对的VeighNa官方OffsetConverter、Portfolio StrategyTemplate及本机真实vn.py Direction/Offset枚举、既有Stage179/931执行源码判断。没有升级策略依赖或引用网络新实现替代原sender。当前机器真实值包括Long/Short、Open/Close、Close Today/Close Yesterday；这些是确定的类型兼容问题，不是alpha规则。

## selected完整诊断与兼容迁移

1. 原 `/private/tmp/weekly19_new_default_selected_attempt001.log` 只有进度，约90%后exit2，无summary；不能称完成。attempt003加-vv后精准定位：旧Stage947 postclose-precompute测试只mock旧C9 pipeline，周线默认使其进入实际os.execve并替换pytest进程，随后weekly CLI缺资格输入退出2。没有真实CTP或SMTP。两个原日志均保留并复制到本线，不能抹掉中途退出事实。
2. 历史C9测试显式配置历史身份；保留原positive/negative断言，不删case、不skip、不放宽SHA、资金、scope、lease、资格或receipt校验。涉及official config/Stage037、activation/release qualification、C9 artifacts、persistent authorization、945/946/947历史控制面。历史cold start明确2026-07-23，实际当前周线仍2026-10-31。
3. 新 `tests/weekly19_legacy_c9_fixture.py` 加载固定m0008冻结C9 builder，硬pin历史manifest SHA `94b6936ab4b338430981f4c2f7e0f4ff38f24534c32f1d16722c8d1367d89474` 和config SHA `82faa02ebf4f782d6e2e2c531eafac0f95b6f8d10c62253dcc16b8922db74ac5`。离线路径仅作为显式参数fixture，不补造历史数据；策略字段、13项Stage037 delta及C9参数消费原断言保留。当前正式import另断言weekly身份、fixed19/noAI、备用金不参与权益。
4. 945/947测试默认拦截外部execve；需要检验实际argv的case再局部mock，并断言命令。Stage947新增独立当前周线测试，验证canonical profile/context/weekly CLI，确认旧pipeline不调用。旧C9路径继续单独验证，避免用mock旧worker来意外执行新入口。
5. attempt011完成全部78个required suites、2116 items，结果 **2113 passed / 3 failed / 0 skipped，380.59秒**，具有完整summary与JUnit。剩3例均为历史C9 pairwise模型实体缺失，不是周线规则或测试断言错误。此结果没有改写成一次全绿。

## 真实枚举接缝修复

- ledger与931的业务offset normalizer补明确Close Today/Close Yesterday别名，保留旧英文紧凑写法、中文与枚举名称；未知字符串仍拒绝。原生3/4及broker_offset分开保留。
- 931 request恢复先保留CLOSETODAY/CLOSEYESTERDAY，再作业务close规范，不能把物理平今/平昨抹成普通close。
- `qmt_roll_official_live_broker_open_date_seal.py` 仅增真实Long/Short/Open别名；不接受任意字符串，不改native raw字段。真实原931授权spool→native→seal→次日close综合fixture因此恢复，通过原lease/幂等/ownership守卫。
- quota正例改用真实 `reserve_execution_ledger_intent` 分配close attempt/token/checksum后再reserve API slots。原CAS保持严格；不保留一个没有合法close lease的伪正例。

## 单一路径LFS实体恢复

唯一缺项为：

`official_strategy_materials/ai_top10_plus_fu_official_live_v1/releases/m0012_20261019T191034+0800_7e13664e0912/payload/ai/stage182/pairwise/model.joblib`

候选原为129字节LFS pointer，物理SHA `ba7eb11c23b7ecef9da99fc27034dc007734409769f04b8d6e236858f013e53c`，声明oid `ba982708a476be74e30ed966883d1eae8ef52010bf8df3763a83d6fc5c719d66`、size2865。经root授权，从生产同相对路径只读复制已存在实体；source/target均为regular、无symlink路径，复制前后source均2865字节且SHA命中声明，target同值。不修改历史manifest、Git blob、生产文件，不读取未知pickle。

修复后仅重跑原3个失败例：**3 passed / 1.61秒**。已声明SHA、预期两行实际模型推断概率和严格绑定断言全部未改。按root指示不再重复之前2113项，也不把两次结果合成同一次all-pass JUnit。

操作缺陷如实保留：首个LFS配置读取返回无值/exit1，但执行agent只打印output漏查exit，未在copy前停止；事后精确path只读status显示M。`git lfs version`确认本机PATH没有git-lfs，filter未配置。没有Git index/config写入；root Git owner负责真实LFS工具/过滤配置及最终clean-source核验。当前正确实体是可逆的已声明对象，不能在无正确LFS clean时误提交为新二进制blob。

## root批准的执行桥接口续修

1. native factory及current transport context提供same connection的main_engine/event_engine/gateway/td_api，给真实MD ingress/journal注册使用，不另建gateway或CTP连接。
2. 新合法状态 `deferred_durable` 必须有state_sha256及durable_deferred_id。真实Order累计先于Trade、尚未重放时，不能谎称applied。931在rows['_weekly19_deferred_broker_events']保存可恢复集合。
3. 集合非空临时阻所有NEW send（含新close请求），既有cancel duty、实际callbacks、只读query/replay继续；不永久invalidate transport。prelease/preAPI/每个native child均核此门，service publication/readiness也核。
4. 只有实际重放并fsync后的applied/duplicate receipt.resolved_deferred_ids可精确清除；query admission还需source_qualified、实际warm_capture_reference与state_sha256。sourcequalified布尔值本身不清队列。跨重启未解决队列须由bridge装回pending map后才能readiness。非deferred源失败仍永久撤销当前generation新发送资格。
5. 核心V6 weekly19_physical_batch_manifest、quota结构、callback batch字段在此续修中未改变。当前关键函数AST hashes另存manifest，供下一锁比较；没有1835旧931字节snapshot，因此不声称能证明与旧整文件相同。

## Stage935手工旧AI入口禁用

root授权补实际consumer漏洞：当前weekly main在mkdir/lock、下载、训练、文件发布、邮件之前输出 `disabled_for_weekly19_fixed_universe` 并exit0；publication helper也按configured canonical profile先拒weekly，即使caller把材料标签改成旧AI也不能绕过。旧C9 AI测试使用显式历史resolver/物料fixture，原对照不删。新两例先RED，修后相关 **44 tests / 1.19秒通过**。Stage935源码本已在critical清单，legacy helper新增进critical。

## 验证与证据边界

- 完整selected attempt011：2113通过/3失败/0skip，380.59秒；诊断完整。
- 原3失败实体恢复后：3通过，1.61秒；不冒充一次完整全绿。
- 当前执行deferred/native与原serve专项：91 tests，1.101秒，OK。
- owned native/service/config专项：38 tests，3.15秒，OK。
- 历史config/launcher/release专项：139 tests，20.46秒，OK。
- Stage935禁用+历史AI/current weekly入口：44 tests，1.19秒，OK。
- 各组有重复，不能累加为独立总数。金融回测新增/修改/删除结果均无；权益、收益、回撤、Sharpe、滑点、成交次数、胜率均N/A。

原日志、完整JUnit、目标补验、source SHA与函数AST见 `20261031_stage016_execution_selected_compatibility_manifest.json` 及同前缀附件。此处不宣称真实qualification、activation或已安装生产；最终clean source、真实source-bound selected qualification、native capture authority与root整分支独审仍必须基于最终源码重建。

运行前后过拟合判断：否，只有执行身份/枚举/生命周期/fixture隔离，不搜索策略收益。继续价值：是，修复真实默认切换接缝并取得完整测试诊断，防止错误地把未完成runner、LFS pointer或旧C9证据说成周线正式通过。用户已授权替换，不增加重复风险许可。
