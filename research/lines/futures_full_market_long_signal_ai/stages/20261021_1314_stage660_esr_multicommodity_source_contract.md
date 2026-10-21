# Stage660：ESR多商品来源补齐合同

- 时间：2026-10-21 13:14 CST；line_id=futures_full_market_long_signal_ai；day模式；分支codex/ai-training-data-expansion。非重要突破；源准备，不是正式A/B或策略晋级。
- 开始/结果前新增按收益过拟合：否，未读新金融Y/score/模型，按官方商品身份选不同经济来源；同史选择风险高。继续价值：是，Corn-only不足以验证跨商品迁移，但新增源不等于alpha。
- 调研：658官方发布/停摆补发原件，659官方MYCO与原论文/SDK；净销售/出货/未交付有恒等联系，不当成独立信息；相同MYCO日期不可随意去重，Corn-only其他94族回A不能叫通用性通过。
- 本次实际只冻结新增5个公开历史查询：ALL WHEAT107/id7、SOYBEANS801/id14、MEAL901/id15、OIL902/id16、ALL UPLAND COTTON1404/id27；原Corn401/id10复用649/651，0新GET。
- 查询截止参数统一10/16/2026；源实际统计末日以响应为准。最多5新GET，各4MiB/20秒/0自动重试，不碰凭证/管理端点。保存raw后解析，原12字段+原649格式5列，完整保留所有行/顺序/MY身份/负值/null。棉花running_bales不转吨；ALL汇总不另加子类别。
- 不推断release/asof、不合并MYCO、不清洗恒等残差、不连市场标签/特征；658合并报告不认证各周当前值首发。历史/PIT/alpha资格仍未建立。
- 新增参数：来源下载/格式预算；修改/删除策略参数、旧结果0；新增fit/cash/SQL/分钟/行情下载0，累计563fit/294完成cash+1旧partial不变。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A。
- 661唯一实际下载/规范化，662独立全字段复核后root结案；本轮不以今天国内日线为前提。合同[contract.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage660_esr_multicommodity_source_contract/contract.json)，SHA deb73fe042ac94bd7694a9e751f2d0173ceed1e84ed55f562b5b51876c134eb6。
- root本阶段不改LINE/registry/根日志，结案统一一次；不做Git/生产操作，完整goal active。
