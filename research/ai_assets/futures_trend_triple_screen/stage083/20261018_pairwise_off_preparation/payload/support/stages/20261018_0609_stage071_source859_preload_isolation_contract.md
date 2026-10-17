# Stage071：未获完成值资格的 source859 预加载隔离合同与实施计划

- line_id：`futures_trend_triple_screen`；2026-10-18 06:09 CST；root 决策。
- 同一 `codex/ai-training-data-expansion` 分支，无 worktree。原 B、补数工具已真实 exit1；本合同不启动金融、网络、训练或生产。
- 目标仍为 2020-01-01—2026-10-14、原 150000 本金，收益更高且回撤更低；未达成。不是重要突破。

## 依据与判断

已读 registry 和现有研究线。Stage063/064 证明最后请求不是超时，而是旧物理行七值冲突；066 在 fu2209.SHFE/2022-05-31 的旧226键中定位225个 source859 行，全部 V=0 且 OHLC 相等，完成数据225键/1035字段不同。最后失败包无实际 commit，不能并入061的190个已提交包。

原859生产器在新K线时间戳变化后立即记录最后一根，并按 seen_id 不再更新；时间戳存在不代表完成。天勤官方示例明确区分新K线与后续 close 更新：[官方示例](https://doc.shinnytech.com/tqsdk/latest/demo/base.html)。也查阅 [官方 GitHub](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/backtest/backtest.py)，不据其网页版本宣称本机SDK升级或全市场历史正确。当前使用冻结本机环境。

root选择**在新研究的预加载结果中隔离未获完成值资格的 source859 行**，保留所有原始文件和021七值相等闸门。相比不断逐日改价，这个统一政策按来源和证据判定，不看收益、年份或品种。不是断言所有859价格错误；缺失的是可用于完成分钟OHLCV/OI的资格。原010/022赋予的开盘anchor使用权不等于完整七值完成证明。

## 唯一政策

输入为原002→011→015→020、016四个已审完整日、两个已审anchor、061已审增量依序组成的物理frame。在最外层loader返回之前，仅删除同时满足下列条件的行：

1. `minute_source == 'stage859_tqsdk_backtest'`；
2. 精确 `(vt_symbol, 上海本地无时区 bar_datetime)` 不在完成值证明键集合。

完成值证明键只取已验证016的 `allowed_keys`、经独立数据审查的061的 `full_keys | anchor_keys`、原036实际解析并验证的两个独立完成anchor键。调用者必须完成原loader/review/SHA门并把其身份纳入preflight；本模块不另造签发机构、数据资格receipt或宽泛fallback。旧demand/predicate、源标签、O/openOI吻合不能自动进入完成值集合。

保留所有非859行以及有上述证据的859行，七值、source和其他列逐行保持；不填价、不改价、不改时间、不改full/anchor权限。即使完成anchor证明其单根七值可靠，也只有anchor权，不能自动获得整日权。原016有资格的已修正行保留。最后失败包191不作为已接受增量继承；有限测试可以把它作为原本独立完成的delivery交给真正021，证明新政策能正常补齐该请求，不声称旧B已接受。

金融时仍由原021基于实际订单或合法未触发intent生成精确请求。隔离后缺失的键必须走原来源解析、完成bar与daily审查；保留物理行仍逐项七值相等，否则fail closed。**不修改021，不允许保留值被delivery覆盖。** A_OFF/B_OFF完全同政策、层顺序和来源资格，不能只对B修数据。

## 新小模块接口

新增 `tools/stage071_source859_isolation.py` 和 `tools/test_stage071_source859_isolation.py`。模块仅stdlib bootstrap；数值依赖在调用时按原022冻结环境装载。

```python
def isolate_unqualified_source859(frame, completed_value_keys):
    """返回新frame和紧凑audit，不修改输入或给予交易权限。"""

@contextmanager
def temporary_source859_isolation(s901, completed_value_keys, audit):
    """最外层loader context；finally恢复loader和原cache对象。"""
```

规范化沿原002，不引入另一套日期/数值标准；缺必需列、非法key或重复物理键应拒绝。完成值集合规范化一次；避免为被移除的全量859物理键另建巨型JSON/集合，向量化成员判定即可。audit含政策schema/source、原行数、859行数、保留/移除859数、非859保留数、按symbol紧凑计数、完成值证明键数量；数据/政策SHA由调用者preflight绑定，不要求重复全市场真值审计。

context保存并恢复 `_load_stage861_full_minute_bars`、`_FULL_MINUTE_BY_SYMBOL_CACHE`、`_FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS`、`_LAST_MINUTE_AUDIT` 的原对象；进入时清cache以免复用未隔离结果，失败不得污染cache或audit。回放前调用 `_ensure_c9_minute_bars`，再按隔离后物理frame生成原022 predicates，并接原036 anchor限制和061 `compose_qualification`。061新增anchor不因非859标签升级full；隔离模块本身不构造资格predicate。

该模块置于061 context外层。061仍只等值合并此前实际commit的190包；它们经过原021旧值比较，原066失败末包已排除。若这一步仍发现真实不等值，拒绝并记录，不能把隔离提前用于绕过061的来源一致性门。

## 有限实施与审查

1. 先写RED，再实现，固定最多三个必要合同测试，不重跑旧suite、不跑金融或全市场下载。
2. tiny混合frame：仅移除未证859；保留合格859、016修正、非859；原七值/source/输入对象不变。完成anchor在真实022+061组合下仍非full；不能把旧anchor使用权当完成值证明。
3. 真实失败投影：只读066锁定的该天226行和最后独立delivery345行（可由已pin066差异+已pin完成CSV精确重建投影，并明确其为证据重建，避免重复扫描全集）。原政策下真正021报旧值冲突；新政策移除225、保留249的1行，真正021成功append344并得到345完整键、old_keys_changed=0。保留行故意七值冲突仍拒绝，不吞异常。无账户或收益读取。
4. context正常/失败恢复cache原对象；014已审A0实际106731读键source859=0，仅复用其SHA绑定的来源交集结论，不重跑A0、不把它升级全市场价格正确结论。
5. 写唯一Stage075实现记录/证据；交独立agent仅审新模块/三个反例和本合同。root确认后，才供062 Task4接线。实现者不修改原021、LINE、registry、其他agent文件，不stage/commit/push，不自己启动金融。

## 金融边界与反思

本合同没有新增/修改/删除策略参数或回测结果；期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A。原A0仅有受057/058限制的历史参照，原B失败/N/A均保留；新OFF盈利优于A_OFF也不自动满足最初绝对目标。

开始和结束新增过拟合判断：**否**，这是全时期统一的数据资格政策，不按PnL选择删行或调参；历史策略选择偏差未消失。继续价值：**是**，真实225个不完整旧bar已经阻断正确回放，本政策用一个来源规则消除重复逐日补丁，同时保留严格旧值闸门。若新源仍不足，只处理真实请求缺口，不改日期或放宽资格。
