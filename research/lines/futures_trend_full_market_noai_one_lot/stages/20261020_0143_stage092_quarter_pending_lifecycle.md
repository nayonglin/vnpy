# Stage092 两臂共用0.25%延期/资金/真实PnL闭环

时间：2026-10-20 01:43。只新增 `tools/stage092_quarter_pending_open.py`，冻结085逐字复制，仅将receipt依赖改为090、weekly授权类型改为091，并添加严格显式的engine布尔周门模式，在enabled时沿用原long周授权校验，disabled时跳过该项。

模式由093在创建strategy之前明确绑定 `engine.weekly_filter_enabled`；缺失、字符串或数字不被当成合法关闭状态。真正关闭周门来自093的无weekly strategy/engine MRO和False布尔，不能靠无授权或异常provider绕开。

原085全部状态逻辑同源：真实活动OPEN+冻结原授权才保护延期；原receipt/stop/qty/signal不重算；无真实活动单的孤儿target不复活；fresh层和receipt对象身份只用于本回调资金过渡；缺bar缓存仅供派单/估值，后续实际填单仍须真实足量bar；仅已真实延期/每日preserve原receipt在后来fill前核因果映射，普通首次next-open不加门；生命周期仍原gate；取消不能生成假CLOSE或擦除真实仓/待平量。

资金仍为actual物理保证金+有效未成交意向，global/cluster一致，078已见证reserve不重复计，未知额外reserve只保守叠加。真实cluster PnL为同步剩余层+仍未填的pendingClose实际份额，排除未成交OPEN。078规划作用域、074部分待平保护完全同口径，无新阈值。父版本已披露的原生rollover planned snapshot缓存风险语义限制两臂共同继承，不在本阶段差异化修补。

源码SHA256：`3e0a64b49f59284c51174e2eae38208affd140fe8e7358d5242d0f56cb92798e`。085→092文本差异白名单通过；两种最终093 MRO完整复验延期、mapping、资金/真实PnL、fresh、forced取消及部分CLOSE，完整513项通过。

新增/修改/删除经济参数无，唯一布尔模式为配对臂标识，native parameters字典两臂完全相同。没有金融运行，业绩统计不适用。不是收益窗口补丁，有价值保持成对实验执行闭包。等待独立预审和Root冻源金融运行，作者不提供自身金融独立认证；旧模块、旧输出、LINE/Git/生产不改。
