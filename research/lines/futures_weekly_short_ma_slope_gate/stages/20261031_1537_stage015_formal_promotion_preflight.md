# Stage015 周线19品种替换正式实盘：晋升预检与迁移要求

- 时间：2026-10-31T15:37:03.843217+08:00（北京时间分钟15:37）；line_id=futures_weekly_short_ma_slope_gate；day。
- 用户已明确选择“替换当前正式实盘策略，并推进master与生产安装”，对象为Stage014 C_R150。授权范围已明确，不再要求同一晋升的重复风险许可；未授权银行/期货资金划转或真实下单。
- 重要里程碑：正式晋升预检；尚未发生正式晋升。无新回测，策略参数新增/修改/删除均无，旧回测未改删。

## 已核实身份与证据

来源研究提交e6f19df6dd41c3b2f4ad73b4f3a2c6cdf03dfbd0；金融冻结688754057ba1dc07caa9edc537ceec486f678372；数据截止2026-10-30。Stage014交付397小文件pin与71金融源码pin全部保持；59独立回测的独审接受边界仍为离线模型会计与报告。

本地正式identity解析并assert通过：ai_top10_plus_fu_official_live_v1 / stage037_stage034_long_short_mirror_hard_block_v1 / source 2a7420a9f9550ab912b5c4a302a61acc5740b04c / release m0008_20261008T204054+0800_2a7420a9f955 / release commit 334d18f069de06df3aa7728203e942e3ecb94ce9。远端master经真实只读readback为e41a0a01d53b7256001e45e686acad53667ef7bf；该commit的CURRENT及正式config字节与本研究树相同。未把这些本地/远端证据冒称为已加载生产身份。

旧SOP权威路径/Users/bytedance/Desktop/person/vnpy_production_live不存在；本机Stage945 Home默认候选稳定目录/Users/mac/Desktop/person/vnpy_production_live存在，HEAD d55887e1def72629fbfa310e439dc3a879969a14。该目录是候选checkout，不能机械替代旧机器已资格身份。私有运行根/Users/mac/Library/Application Support/qmt-roll-stage179/production-live缺少release-manifest、qualification、activation、runtime receipt及data-readiness五项核心证据。精确7个生产label与plist/loaded状态由独立预检另列；不能只因目录存在声称生产已生效。

## 技术缺口

1. Stage014仅为研究入口，preflight明确production_qualified=false；写死冻结59起点/截止30/研究行情与本机vendor路径，并主动将真实提交/daemon环境关为0。正式来源必须另建可移植runtime与参数合同，不能从ignored outputs直接跑生产。
2. 周线19品种/无AI/无加仓/short bottom20/原OI风险/无0.5R及C2的候选与现有C9不同。Stage930仍路由Stage904 monitor和Stage941 C9 detector；Stage904硬码STOP_RETRY_R=0.5与c9_retry_open_once；Stage948资格校验仍绑定C9_15W_PROFILE。需要让shadow、detector、monitor、pending/executor、durable-state、qualification、installer和daily receipt全部绑定新profile；旧C9 intent必须拒绝，不能只改顶层config/CURRENT。
3. Stage014 reserve通过self.settled_balance += transfer模拟资金转入，没有银行/期货到账证据、真实资金服务或生产重启恢复协议。实盘需确定真正场外转入还是同账户隔离；前者必须到账确认后再重算/开新仓，后者必须以broker总权益减去未释放备用明确E与风险/保证金容量，并对账/去重/重启恢复，不能把虚拟增资当真实可用现金。
4. 新代码/新物料需要自己的source-bound selected suite、formal_ctp_readonly、independent review，以及不可变release/qualification/activation。旧m0008资格不证明新周线规则。技术门缺失与经济失败分列，不能伪造passed，也不能以改名代替完成。

## 冻结风险与调研判断

满一年54窗51正3负、观察5窗3正2负；最深E回撤−59.77%、5窗耗尽15万备用、37窗静态放大保证金超过E、手续费0。用户晋升请求不修改原NO_PROMOTION经济判定，不把含入金NAV当alpha。技术迁移即使通过也不应抹掉这些历史负例。

参考[vn.py官方组合策略文档](https://www.vnpy.com/docs/cn/community/app/portfolio_strategy.html)与[官方GitHub实盘引擎](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/engine.py)：实盘需独立完成历史初始化、策略启动与真实接口/账户状态；研究结论是必须验证真实资金、成交与持久状态接线，不能把回测内部余额变更当入金资格。

运行前/后过拟合风险：是，重复同历史、窗口重叠；本轮不改alpha不寻优，不新增反证回测。继续价值：是，晋升预检具体发现真实资金与执行路径缺口，技术迁移有明确价值；不能以用户授权或离线会计PASS覆盖资格缺失。

## 后续路径与完成边界

当前先确认生产目标与备用金物理放置；然后在独立干净来源worktree迁移新profile/资金与全消费者，定义可审查的技术合同及恢复/旧intent隔离。通过正确性、真实保证金/费用与冷启动资金可执行验证，再由发布器prepare→commit→verify→fresh clone→qualification→activate→promote-master→fresh clone closure→Stage948安装→最终六身份闭环。prepare/publish不得把未接线C9源码冻结成周线版本，不得把候选发布称正式晋升。

本轮仅新增Stage015预检材料，未改CURRENT/正式config/历史release、44品种研究、生产、CTP、订单或资金。真实金融回放0，order/send/cancel/transfer API0；remote push0。具体机器/资金输入和独立预检将补齐到后续唯一记录，不改Stage014冻结材料。
