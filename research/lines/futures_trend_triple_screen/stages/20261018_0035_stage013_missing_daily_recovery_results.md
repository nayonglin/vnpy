# Stage013 普通TqApi恢复精确缺失日线结果

- line_id：`futures_trend_triple_screen`；记录时间：2026-10-18 00:35 CST。
- 性质：数据恢复，非金融回测，非alpha突破；Stage013协议冻结后唯一连接，由root统一运行，未重连。
- 开始时间：2026-10-18 00:30:05；父进程251.75秒终端，worker251.15秒；峰值RSS **488,620,032 bytes**，570/600秒及1.5GB预算未触发。

## 调研与变更

复用本机旧日线下载脚本的公开普通`TqApi.get_kline_serial(symbol,86400,data_length=10000)`及ns→UTC→上海日期映射。[官方API](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)、[官方源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)仍走正常行情授权，未修改grants，不调用`tq_dl`、TqBacktest或私有网络接口。

新增`tools/stage013_missing_daily_recovery.py`与5个合成契约测试，先RED后GREEN；仅新增preflight/run数据入口及固定资源预算，没有新增/修改/删除策略参数。一个普通TqApi、一个本地TqSim，SDK原始stdout/stderr/logging丢弃，安全receipt不含凭证；没有CTP、订单、撤单、训练或金融账户回放。

## 目标、资格与实际结果

Stage011缺CSV的4,518个需求对应94个精确合约（159 full、4,359 anchor）；先排除16个无真实日线carry诊断，真实目标为 **4,502日**（159 full、4,343 anchor）。不按expired状态删除当前合约，也不扩展全市场。

- **94/94** 合约原始日线快照取得；**4,500/4,502** 目标通过：**159/159 full**及**4,341/4,343 anchor**。
- 每个合格目标都有同合约更大原id且严格更晚时戳的合法后继日bar；固定核对DB的OHLCV与`open_interest→provider.open_oi`六字段。DB closeOI明确N/A；新`close_oi`独立来自provider日线字段，不由DB推造，不宣称不同数据商独立认证。
- 两个anchor拒绝并保留：`fu2605.SHFE / 2026-04-30`、`fu2609.SHFE / 2026-08-31`，原因均为 **no_forward_successor**。它们为返回快照的末有效日bar；已到期不豁免完成性门，不以重连或放宽规则补救。
- worker状态 **completed_with_target_rejections**，父进程 **exit 1**；真实含义为快照获取完成、部分目标资格未通过。不能重标成全目标成功，也不应将4,500个已合格目标一并丢弃。
- 父进程确认冻结输入全部未变，无hard kill、无自动重试，原CSV/DB/策略/base/既有overlay均未写入。

## 输出与审查边界

输出根为`outputs/stage013_missing_daily_recovery/`：原始快照在`network_attempt1/raw/<exchange>/<native>.csv`，仅视作raw；合格目标在`network_attempt1/qualified_daily.csv`，SHA256 **89cd6502bba89bb32fce4ca032adb1266a8978b91fd7f1b0e1519aa464df6833**。目标逐项资格、两拒绝、后继id/ns、源SHA及父/worker receipt全部保留。未验证的其他历史不自动进入训练数据。

本记录时独立数据review **pending**；Stage015已准备代码与4个合成测试，但必须待独立receipt及root通知后，才对4,500个合格目标日和Stage012已验11个session做一次必要分钟增量资格，不重做Stage011原13,752个完成session。16个carry诊断、两条无后继日线与原3个分钟冲突继续保留约束。

**00:38补充：独立review已通过，P0/P1均0。** receipt为`outputs/stage013_independent_review/review_receipt.json`，SHA256 **194e48847c9e0927772c482cd5bacc3529a625ac76aeec2a157089924177c795**。独立核对全部4,500个目标的完成证据/CST映射及固定六字段差异均0，另抽4个raw快照；没有重新资格认证94份全历史，也没有重复查询DB。只允许这4,500个精确目标供Stage015使用，原exit 1、两拒绝、16个排除及`provider_all_targets_success=false`保持；真实delta构建仍待root通知。

权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均 **N/A**；本阶段金融attempt为0，累计金融attempt仍4、完成仍1，没有完整C0收益结论。

## 反思与下一步

开始/结束过拟合判断均 **否**：只恢复已冻结的精确数据缺口，按固定完成性和openOI口径验收，不看收益选规则。开始/结束继续价值均 **是**：159个full所缺七字段日线参考全部取得资格，下一步把其转为可用分钟覆盖；数据恢复本身不证明三重滤网优于原策略。未更新LINE/registry或根总账，未授权C0新attempt、fallback或生产。
