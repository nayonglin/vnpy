# Stage018 新m0002候选与周一09:00安装交接

记录时间：2026-11-01T05:17+08:00。本文件为本轮最终工程状态：**新候选已冻结及复现，尚未激活/推master/安装生产**。用户已授权继续替换正式策略，CTP只读连接等2026-11-02周一09:00；自动最终结算解析和自动银行到账producer已取消，由operator人工核验，不再要求补做。

## 当前结果

- 截至10/30完成周，固定19品种无新的原始MA交叉/开仓候选，独审19/19；15万元空仓条件核对，不是资金压零。真实旧持仓未知，不据此省略实际平仓/减仓/换月核对，也不保证下周新数据始终无信号。
- 显式operator_manual_v1、人工私有确认CLI、同actor现金/运行状态原子消费及Stage945独立日历/cold_start路由已完成；完整90套件2309通过、0失败/错误/跳过，288关键文件前后无漂移且逐Git blob匹配source。独立增量52次及纯资金原85分阶段封存，失败证据完整保留。
- 新物料378文件；官方发布器prepare/commit/verify通过，独立clone --no-local、无alternates、空LFS cache实际fetch，378 payload/顶层SHA和全部执行位一致，manual CLI可执行、历史模型2865bytes实体正确、所有历史manifest通过。该克隆不是remote master fresh clone，没做克隆runtime资格或生产资格。

## 精确身份

| 字段 | 当前值 |
|---|---|
| strategy_version | official_live_weekly19_base15w_reserve15w_stage014 |
| ruleset_version | stage014_week_close_19_short_bottom20_original_risk_external_reserve_v1 |
| source_commit | e89fdcbb68260a647372f03626800110470f61dd |
| material_release_id | m0002_20261101T050816+0800_e89fdcbb6826 |
| release_commit | 48839375c26081bf6aeb5610aab70c72c688c59c |
| remote_master_sha | e41a0a01d53b7256001e45e686acad53667ef7bf |
| production_source_commit | d55887e1def72629fbfa310e439dc3a879969a14 |

manifest文件bytes SHA为`1a23fda7a25051c4890d190c146ce33068ba1c478ce90fc3e0385e733ec5989c`；manifest嵌入canonical SHA为`85425232204ab3af875167705afbc58d57f8000985e86f0e46ff8373d0eaa7b4`，两者含义分别记录，激活须走官方API，不能把它们互换或手填CURRENT。物料qualification仍为candidate；旧m0001及CURRENT旧m0008未改。

远端master通过GitHub连接器branch API只读核实；native git ls-remote本次60秒超时，不能称Git fetch/push通路已证明。周一promote前需重新fetch并检查同一远端SHA/无并发变化；不得用连接器只读回执冒充推送成功。

## 周一从这里继续

1. 工作区`/Users/mac/.codex/worktrees/weekly19-official-20261031/fian`，分支codex/weekly19-official-20261031。本对话一次性任务9-19已ACTIVE，RRULE COUNT=1，主机时区已核CST+08。届时需电脑及Codex运行。先读最新SOP、Stage018_installation_handoff.json、实际stable/CURRENT/五件套和jobs，若已完成就避免重复变更。
2. 用正式ctp_live.local.env和macOS vnpy_ctp/api/libs framework优先序做只读CTP；不读broker-test默认env。source的忽略配置已从真实stable准确私有复制为0600，实际生产配置未改；任何日志保留私有，不打印密码或原始账号。本步骤不能委托/撤单/转资/SMTP。
3. 初始真实账户仍须15万权益、空仓、无活动委托，账户ID由真实CTP生成，不能复用OFFLINE fixture。遇余额/仓位差异先保存真实阻断，不自动转资、平仓或追模拟仓。计划新cohort起点11/2，但尚未创建/激活context，最终以实际资格/安装日期和真实首个完成日为准；945验证曾用10/31是测试场景，不是生产冷启动事实。
4. 已备完整市场generation：`/Users/mac/Library/Application Support/qmt-roll-stage179/weekly19-calendar-candidates/Stage018_calendar_20261101T043315_ad4afb28/Stage018_complete_market_20261101T043552_3f8943b8`。六源pin和actual TQ calendar见Stage018_signal_scope_complete_market_generation_receipt.json；market_context_fragment.json可作接线输入。不要再从旧研究树加载数据，勿把forward calendar充作未来日K。11/2后每个完成日仍用真实held集合更新OHLCV/closeOI/physical epoch。
5. 获得正式只读证据后，用官方trusted qualification runner重新构建release-bound资格，完整tests/independent review/两次formal CTP及零API须来源正确。通过才activate、受控promote-master、核远端读取/fresh master clone；再按真正的生产HEAD重新生成精确绑定的新生产资格/manifest，最后Stage948原子安装与7/7jobs闭环。不能拿material祖先source_commit当生产HEAD，不能套用Stage018离线CI为production资格。
6. 实际stable目标`/Users/mac/Desktop/person/vnpy_production_live`；当前clean d558、旧m0008，五件套缺失、owned loaded0/冲突0。更新前保留现有分支/ref和原8个本机commit，源码工作区da01合并已保留历史；不reset/stash/force/discard。新master formal source与private状态不得手工拼装或越过Stage948复制plist。
7. 新production私有context明确cash_verification_mode=operator_manual_v1，并配置checkout外0700的manual_cash_review_root。初始/每日实际现金观察来自真实CTP；有新现金变化/日切时由operator按Stage018_operator_manual_cash_runbook.md确认，原actor消费。人工记录不虚增E/Available、不能直接写活跃bundle，也不是订单授权。

## 证据入口

Stage018_selected_final_attempt002.json/XML/log；Stage018_review_signal_acceptance.json；Stage018_review_manual_integration_acceptance.json；Stage018_m0002_release_receipt.json；Stage018_m0002_fresh_clone_receipt.json；Stage018_review_m0002_readback_result.json；Stage018_root_owned_launchd_surface.json。首次中断CI和全部独审RED保留；没有新增金融回测或改写Stage014经济结论。

结束判断：未调策略参数，过拟合为否；继续有价值，后续工作是实际账户及来源资格和正式安装，不再做同历史参数优化。
