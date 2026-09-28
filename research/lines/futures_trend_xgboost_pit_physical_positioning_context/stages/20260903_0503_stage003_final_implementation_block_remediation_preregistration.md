# Stage003 最终实现阻断项修复预注册

## 身份与边界

- 修复冻结时间：2026-09-03 05:03 CST。
- `line_id`：`futures_trend_xgboost_pit_physical_positioning_context`。
- 被审实现 runner SHA256：`c169bd4f39b979193ab2d5a2a8ee4eeab3a025e1197812493bd54ede89ea3306`。
- 最终实现 BLOCK review：`reviews/20260903_stage003_final_implementation_review.md`，SHA256=`2479f673c1a60e1032a39b7452142a101fcf03919f7be7548c7f051b131443af`。
- BLOCK decision：`reviews/20260903_stage003_final_implementation_review_decision.json`，SHA256=`46aef3e6415c51e61f3a87e493d3efc02f9c965c00b77c2d80cd5d5cf0bcdfc1`，`P0/P1/P2/P3=0/0/2/1`。
- 当前只授权修复两个无标签实现缺陷、补合成/静态反例并重新独立审查；不授权创建一次性运行授权，不读取真实 aggregate/per-job/holdout 标签数据行，不执行真实 fit、预测、效果评价、回测、真实引擎、生产、CTP或订单。
- 本修复不改变153行development、65行holdout feature、13 active+4 fallback、六项特征、joint maximin标签、32棵深度2单Ranker、LR/XGB等权融合、11项效果门和一次失败永久闭线规则。

## P2-1：right-only连接修复

- `_join_raw_probability_projection`不再用left join结果行数推断额外记录。
- 连接前分别建立feature键集合与full-split投影键集合；只要求每个feature键在split中唯一存在，同时明确计算`split_keys - feature_keys`。
- 因冻结full split包含不具备完整物理证据的候选，合法的right-only范围必须由Stage002资格宇宙决定：只允许不在Stage002 feature panel中的非资格键存在，但这些键不得进入连接结果。这里的“额外连接”为同一Stage002资格键之外、却伪装成应连接资格记录的重复/冲突键；机器可判定边界改为：Stage002 feature键必须全部且仅一次命中，right-only行数单独披露但不再错误报告为`extra_join_rows=0`。
- 为满足第三份remediation原先“missing/extra均0”的语义，新增一份合同修订：`extra_join_rows`专指连接后产生的非feature行，固定0；`right_only_source_rows`记录full split中合法非资格行。任何新增right-only源行必须使冻结全文件SHA失配并在解析前阻断；纯函数反例则要求调用者提供冻结允许的right-only键集合，否则新增右侧键失败。
- 增加对抗测试：合法允许集合通过；额外右侧键失败；失败发生在label read、fit、artifact create之前。

## P2-2：统一事件账本与静态不可达证明

- 新增单一append-only运行事件账本，记录aggregate header核验、eligibility读取、label文件读取、active seal复核、训练标签使用、每次fit、每次predict和每个pre-effect artifact create；事件只含身份、phase和计数，不保存标签值。
- `PhaseGatedJobLabelStore.final_audit`必须从事件序列计算初始/测试/唯一标签读取、seal前读取、other-main、A2、holdout、同折标签训练和测试标签参与选择等计数，不得返回预填零常量。
- production label store显式接收153个允许job、其余113个development main job和4个A2 job身份；任何越界读取事件都使技术门失败。
- fit/predict计数来自模型受控接口事件；active/repeat模型字节、seal和磁盘工件继续作为交叉证据。
- 对绑定runner执行AST静态审计：只允许固定import/call面；证明不存在参数/特征/seed搜索、early stopping、重跑择优、subprocess/命令、真实引擎、生产写、CTP和order调用节点。静态审计结果与runner SHA绑定，运行事件不得代替代码不可达证明。
- `_build_execution_scope_audit`从事件账本、AST审计和实际工件差集推导计数，不得从`EXECUTION_SCOPE_COUNTS`复制零值后与自身比较。
- 最终发布接收冻结完整expected artifact集合；写manifest前检查missing/unexpected差集，原子发布后重新核验manifest覆盖、文件SHA/size和最终文件集合。插入额外最终artifact必须失败。
- 增加反例：伪造training summary不能伪造fit/label/访问计数；额外label/command/final artifact事件或AST节点使技术门/发布失败。

## 授权链修订

- 保留当前BLOCK review和decision原文件，分别新增绑定键`stage003_final_implementation_block_review`与`stage003_final_implementation_block_review_decision`。
- 本文件新增绑定键`stage003_final_implementation_remediation_preregistration`。
- 原`final_implementation_review`与`final_implementation_review_decision`键改指向后续`20260903_stage003_final_implementation_rereview.md`及其decision。
- authorization exact bound key数由24改为27；未来一次性authorization必须绑定修复后的contract、runner、三组tests、BLOCK链、本remediation和最终rereview全部实际SHA。
- 只有新rereview给出精确`ALLOW_STAGE003_ONE_TIME_RUN_AUTHORIZATION_REQUEST`、`allowed=true`且`P0/P1/P2=0/0/0`，才允许向用户申请一次性真实运行授权。

## 回测记录

- 是否产生回测数据：否。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：不适用，均未运行。
- 新增/修改/删除参数：无。
- 新增/修改/删除回测结果：无。
- 是否重要突破：否。

## 反思

- 是否过拟合：否。本次只修连接集合与证据链，不能提高任何模型结果；真实标签和结果仍不可见。
- 是否值得继续：是，但只值得完成这次确定性的无标签治理修复和复审。若新review仍有P2，不得运行模型。
