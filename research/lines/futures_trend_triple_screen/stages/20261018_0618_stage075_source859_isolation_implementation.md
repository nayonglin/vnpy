# Stage075：source859 未证完成值预加载隔离实施

- line_id：`futures_trend_triple_screen`；记录时间 2026-10-18 06:17:53 UTC+08:00；实现者 `/root/ordered_execution_review`。本轮为 Stage071 的有限实施，不是独立审查或重要突破。
- 本线已存在；读取 registry/LINE 和 Stage071 合同，遵守同线并行只写唯一 stage，不改 LINE/registry。

## 实现与边界

新增 `tools/stage071_source859_isolation.py`：仅删除 source=`stage859_tqsdk_backtest` 且不在调用者已核完成值证明精确键集合的物理行；保留其余七值/source/额外列与顺序，不原地改 frame。沿002上海本地时间规范，缺列、非法键、重复物理键拒绝。证明集合每次context只规范化一次，物理成员判定向量化，audit只含总数/按symbol紧凑计数。模块stdlib bootstrap，调用时检查022冻结数值环境。

完成证明只允许调用者核验后的016 allowed_keys、已审061 full/anchor以及两个036完成anchor；不把旧demand、使用权或开盘吻合视作完成证明。模块不产生full/anchor权限。context应位于061最外层，061等值合并先执行，不可用提前隔离绕过其来源一致性门。当前没有改或接线031/036/062等任何runner。

进入context清cache并脱离原audit对象；正常、loader失败、context异常均恢复原loader和三个cache/audit对象引用；失败scope不保留新增成功audit。输入数据SHA/来源审查与调用者preflight仍由后续接线负责。

## 三项 RED→GREEN 证据

执行入口：`.py311/bin/python research/lines/futures_trend_triple_screen/tools/test_stage071_source859_isolation.py`（由原022配置冻结runtime，无模型smoke）。实现前旧行为3项语义失败，exit1/0.145秒；实现后三项exit0/0.215秒；两个新文件py_compile exit0。日志及台账在 `outputs/stage075_source859_isolation_implementation/`。未跑旧suite。

1. tiny混合frame：移除两条未证859（包括仅有旧anchor demand的一条），保留两条有完成证明859、016修正、249和061行；七值/source/额外列及输入不变。真实022 inherited predicates＋061 compose下，完成859 anchor和061新anchor均仅anchor，不升full。缺列/非法键/重复键拒绝；时区规范到同一上海无时区键。
2. fu2209/2022-05-31：先原request＋原receipt经真021 parser核345行。再由已pin066的1035字段差异、345完成CSV及原request existing226重建旧226投影，明确不是读取dead engine RAM或重读base全集。原policy真实021拒绝旧值冲突；新policy删225个859、保留249一行，真实021 append344、总345/full345、old_keys_changed=0。故意使保留249行high冲突仍拒绝、无commit。
3. context：正常完成、loader异常、body异常分别验证原loader/cache/symbolset/audit对象身份恢复、输入不变、失败audit无污染。

隔离改变物理existing集合，必须产生不同request身份。各case以真正021生成request写本目录明确`fixture_only` wrapper，引用同pin345CSV；这些wrapper只是单位机制验证，不能当新的独立市场数据签发，也不表示原B末包191已接受。未来实际金融必须真实resolver按新request重新资格；本次无response/pointer/root终态签发。父任务已明确批准该有限wrapper方法。

014来源交集结论仅复用固定摘要：A0实际106731读键source859=0；SHA `7f06df100b2c9b132991d8cbd956f52d5bf373266b40a9dfc4d6d0f494be79f0`。未重跑A0或复查全集，不能外推全市场价格正确。

## 最终指纹与后续

- 实现SHA：`12580b91d0e264ac4f63807679742cbbc67c8cb03e66dd42343cf9b72c26fe27`。
- 测试SHA：`fe26881b53d8c2a9891a7f35bfd17e3477b3b630fc9cd4219823193c2b9a29b5`。
- 原021 SHA：`150dd70a264f360046f6d633829a4dff9a81c371c34bad6288e41a081bbb498b`；未改。
- 测试使用061 SHA：`3570427b8d1543a7fc7dc14e3fb17978f394fb4864b809e85d75fa6609b5a73a`；仅测试组合接口，不代替061数据资格审查。
- Stage071合同SHA：`e31f66d17fb61bf940731556fdc5f5815a3df42f915f1bccbf27718b0b58a493`。
- 实现收据：`outputs/stage075_source859_isolation_implementation/implementation_receipt.json`；未自称独立review。下一步root安排有限独立复核并决定062 Task4接线，不自行开金融。

无策略参数新增/修改/删除，无回测结果新增/修改/删除。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A；金融回放/网络/模型训练/委托均0，未stage/commit/push。原B失败和历史PIT限制不变，目标未达成。

过拟合判断：否，本次用统一来源资格规则修复可复验的226旧物理值冲突，不看收益或选年/品种；既有策略选择偏差未消失。继续价值：是，机制证据表明可恢复正确完成值的必要接合并保持保留行严格冲突门；是否启用仍须root独立接受和对称接线。本轮置信度仅针对代码及这三个fixture，未证明收益或全部分钟质量。
