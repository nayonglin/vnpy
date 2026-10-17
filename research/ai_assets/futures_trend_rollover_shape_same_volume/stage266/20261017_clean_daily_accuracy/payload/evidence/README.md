# Stage266 全市场标准日线：数据入口与准确性验收

本机隔离研究数据，2010-01-01—2026-10-16；六所、97个有数据历史品种代码、9,520个有真实成交的合约、1,552,456条唯一日线。原始资料全部保留，主库及正式策略未修改。

**已完成清洗与来源合同内准确性验证；尚未生成月度AI训练样本或拟合模型。**

## 直接使用

- [隔离研究SQLite](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/clean_daily.sqlite)
- [机器可读数据清单](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/dataset_manifest.json)
- [逐合约CSV目录及校验值](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/csv_inventory.json)
- [最终独立准确性报告](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_independent_validation/independent_review_summary.json)
- [冻结单位合同](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/unit_contract.json)
- [数量争议键](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/stage266_units_quarantine.csv)
- [价格争议键](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/price_conflict_quarantine.csv)
- [训练依赖勘误](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/feature_dependency_clarification.json)

CSV位于本目录csv/交易所/PRODUCTYYYYMM.csv；使用完整交割年月避免郑商所跨十年同名，月均价F的product为L_F/PP_F/V_F。字段包含trade_date、datetime、open/high/low/close、volume、open_oi、close_oi，另附来源、数量转换因子与字段完整性。SQLite还能追溯原值、源文件、原始行定位和元数据。

数量已统一单边手；open_interest明确等于close_oi。只有真实来源提供open_oi时才有值，缺失保留为空，不用0或昨日收盘补造。784,746条七列完整，767,710条保留OHLC、成交量和收盘持仓但缺真实开盘持仓；后者不是脏数据，不应自动从所有模型研究中删除。

## 准确性做了什么

- 所选1,552,466条先逐行核对原始源，错误0；最后10条旧库分歧只做单调删除。独立SQL集合差确认无新增/修改、恰删10，最终1,552,456条继承原源一致性。
- 4,831个所选来源文件的SHA/字节核对通过。9,520个CSV全字段与SQLite一致；初次比较23,286,990字段，最终受影响10文件增量复核一致。
- OHLC几何、正成交量、非负持仓、真实合约年月、交易日、未来截断、来源转换因子与开收盘OI时点逐行验证。
- 2,294数量争议键、304价格争议键已整日隔离，泄漏0；未知单位、零成交填充和非法源记录不进入真实成交日线。
- 与旧主库812,865个共同键比较，812,855四价全同、10异；已隔离这10，未擅自判断或修正哪一源是真值。
- 63项针对性边界测试通过；独立review P0/P1/P2=0/0/0。准确性结论针对固定来源、字段和转换合同，不冒充每一条交易所历史数据的绝对真值认证。

## 关于月度108特征的必要勘误

**不能把旧CSV完整性当成月度108特征的训练资格。**物理字段legacy108_row_usable/train_eligible和函数require_legacy108_window最初命名过宽，实际只表示旧CSV七列字段齐全及严格交易日历窗口。读取器是研究适配器，正式loader没有切换。

真正月度108特征来自策略产品收益、成交与候选信号的滚动统计，不直接以open_oi字段作为模型列。本次已逐列核对冻结的108列表，直接open_oi列为0。缺开盘持仓不能单独证明2010—2019历史不能用于月度AI；其对统一策略源的间接依赖需要后续源生成确认。

原18池的诊断结果：48,506个映射当天有clean行，22,065个当天七列完整，18,649个候选日有完整120日旧CSV窗口；这些都不是训练样本数。映射文件目前只到10/14，所以10/15—16的月池诊断缺映射，不等于行情缺失。未来60日收益标签、真实label_end成熟和时间隔离尚需统一策略源生成。

## 研究读取示例

```python
from stage266_training_reader import load_contract_bars
frame = load_contract_bars('/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/clean_daily.sqlite',
    contract_epoch_id='INE.SC.202212', candidate_date='2022-11-29',
    open_oi_policy='mark_unusable')
# 日期严格截断；缺开盘持仓保留NaN。完整CSV接口窗口可调用严格窗口辅助函数。
# 月度AI训练应使用其真实108特征/成熟标签合同，不能拿这里的诊断标记代替。
```

准备数据的单入口为本线tools/stage266_prepare_training_daily.py；已有结果会拒绝重复覆盖。该工具组合初次清洗、价格分歧隔离、旧库交叉验证及最后增量隔离；本机原始行情依赖和冻结单位证据必须在场。日常研究直接只读现有数据，不重复运行清洗。

本轮没有下载、财务回测、模型拟合或订单。无按收益选参型过拟合；下一步有价值的是生成一致策略源和成熟标签，保持模型/策略参数固定后再做训练历史对照。
