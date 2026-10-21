# Stage066 上期所历史session证据与边界

- line_id：`futures_ai_monthly_pool_generalization`；时间：2026-10-20 23:06 CST。
- 性质：只读规则/本地候选映射研究；非重要突破，不触发正式A/B；用户授权连续自主推进。

## 调研与判断

交易所原始[历程](https://www.shfe.com.cn/content/lxjy/main.html)和[旧金属业务问答](https://www.shfe.com.cn/content/lxjy/f18-3.html)可支持AU/AG夜盘上线与到02:30、夜盘计入下一交易日、法定节日前夜暂停等原则。[旧黑色业务问答](https://www.shfe.com.cn/content/lxjy/mtbd8.html)明确RB/HC最初到01:00、RU到23:00；所以静态2020+ helper不能整体外推早年。2018贵金属手册只有交易日和开盘原则，未替代本次缺失的全部历史时刻。

[当前交易所时段页](https://www.shfe.com.cn/services/calenderandholidays/tradinghours/)只能作为当前交叉核对。GitHub上游[RQAlpha时钟](https://github.com/ricequant/rqalpha/blob/master/rqalpha/data/trading_dates_mixin.py)与[changelog](https://github.com/ricequant/rqalpha/blob/master/CHANGELOG.rst)支持交易日映射、品种时段和元信息分离的工程判断，不能认证我们的session。

判断：先按精确事件确认规则，再逐来源audit，不新增模型。11个已有本地native候选的SHFE事件里，AU2/AG1/RU1可进一步做有界reference政策审查；RB4/HC3还缺2016年缩短夜盘的交易所原始变更通知。搜索出现的券商转发不作为primary验收，7个事件暂不升级。本阶段4个候选也尚未注入，物理session/PIT/broker资格仍False。假日/交易所临时停开盘不能由日线OHLC相同自动证明。

## 变更与结果

新增本目录证据表/来源JSON与阶段文件；修改/删除代码、策略参数、模型参数、源标签均0。11候选事件、19文件链接（以summary为准）；已核原始规则与未取得原始通知显式分开。没有运行金融回测/模型，期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A，不能把分钟输入检查包装成绩效。

## 反思与下一步

运行前/后新增按成绩择参过拟合：否；只按缺失事件和来源确定范围，不看C2结果或收益选provider；参考时段完整性仍是研究限制。继续价值：是；已有下载缓存可能补数据，但不能因为想增标签就假设历史时段。等待其他交易所证据后，固定有证据范围统一audit、独审，只有通过才允许进下一版纯证据补充回放。未改source v1和正式策略，半R/retry仅本训练源关闭，C2保留。
