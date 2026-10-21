# Stage267：固定现货参与过滤的新源码独立审查

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-20T00:30:34.744831+08:00。本线唯一267记录；非重要突破、非正式候选/晋级。
- 结论：**core_blockers=0，仅通过冻结264协议下的265/266源审门。未运行现金；金融输出另需独立review。**
- 新增fit/cash均0，累计439/234；SQL/网络/raw body/新源现货CSV/原生价格/标签/旧大型训练CSV/旧测试suite均0。只修改本stage及267 receipt，不改LINE、registry、作者代码或旧文件。

## 调研与判断

先读AGENTS、registry、冻结264协议与source_acceptance、263接口盘点及必要原131/132/148/157接口源码。协议SHA为`d18b82b34719425439a7190325fa692c912c93aa42db7d0d46493f2544013d42`。公开依据复用251已归档的[AKShare维护者实现](https://github.com/akfamily/akshare/blob/main/akshare/futures/futures_basis.py)，本批不再联网或重复262来源资格审查。判断：报价文字连续性只支持条件历史证伪，不支持PIT、物理benchmark或可成交价认证。

## 源码与sidecar核对

1. 265采用55个精确literal映射，排除“聚乙烯”宽映射；3833原源日历先去重校验再排序，`bisect_left(u)`只取严格u前21日。完整21天均须正Decimal、同unit_id；任一天缺失、重复literal、非正/非法或单位切换均unknown继承。仅有效且newest<=oldest取消，固定u；不压缩日期、不填0或前填。
2. 265完整161014母行/98产品域、4365原选择机会逐行父子身份对齐。独立遍历**新**choice/signal sidecar，核行号、event唯一性、available/action/keep不变量、窗口严格小于u及聚合计数，5个新输出bytes/SHA均匹配manifest。信号可用2782、unknown继承1583、取消1108、保留3257；原信号涉及70产品，98是完整选择域分母，并非全部98都获得新信息。
3. 266对原4365信号私有副本仅作keep mask；完整399252原mothers供131.organize生成canonical。score、月份、u/D、N、风险、原生命周期/自愿K有效边界及退出列保留；132缓存恢复和148市场接口进入原131核，不重做156/130、不修157 CLI、不筛旧fills。16个继承小源码SHA现场匹配。
4. 仅固定2020连续/2023冷启两窗口×base/stress四候选，原157四控制只读复用；真实kernel started/completed在失败时保留terminal/manifest，fresh目录阻止覆盖，无自动重试。两stress均权益差严格>0才过主要证伪门；两者回撤差亦>0才称同时改善，负回撤差值方向已核对。完整实际账本算术尚未产生。
5. 阅读作者三个265 synthetic及两个266 mock fixture定义与绑定记录；作者报告均GREEN。独审未重跑任何fixture或旧suite；源审依据为本次源码、绑定及新sidecar独立一致性断言，不把作者测试报告写成独立执行。

## 作用边界与后续

266仅继承旧大表/缓存证据，本审未独立重hash大mother或读native价格；这属于已接受158/263范围延续。历史known_at、benchmark/grade/region/tax/vintage及日线成交/容量仍未知；重叠双窗和累计439fit/234cash后的择题不能构成独立OOS。267 receipt精确绑定265/266四个新源/fixture及覆盖manifest。root仍须签精确授权，最多一次四候选现金；之后由另一独立agent做金融输出、数据、逻辑、置信度及bug review。

新增/修改/删除策略参数、金融结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数及胜率均N/A。本次不能宣称alpha、原goal完成、生产资格或加注资格。

## 开始与结束反思

- 新增按成绩调参过拟合：**否**。仅验证事前冻结接口/政策，未看新金融表现；长期同史择题过拟合风险：**是**，保留为结论限制。
- 继续价值：**是，仅一次固定经济证伪有价值**。本次源审已完成，继续来源资格循环或扩大检查无新增价值；如双stress任一本权益差<=0，结束该机制，不改方向/窗口/阈值/风险救参。

输出：[267 receipt](../outputs/stage267_spot_policy_source_review/receipt.json)。
