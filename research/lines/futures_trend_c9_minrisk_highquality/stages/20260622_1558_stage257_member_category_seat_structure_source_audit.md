# Stage257 会员类别/席位结构 source inventory 与字段合同审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 15:58 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读数据源与字段合同审计；回答 Stage099 的 `member_category_seat_structure` 还能不能靠本地公开会员排名继续补覆盖
- 是否重要突破：否；没有形成策略候选，但完成一条外生路线的字段层闭环
- 是否触发A/B：否；没有正式候选，也没有运行 true engine

## 外部调研与判断

- 参考资料：
  - AKShare 期货数据/会员持仓排名文档：https://akshare.akfamily.xyz/data/futures/futures.html
  - SHFE Daily Data / Member Volume, Open Interest Rankings：https://www.shfe.com.cn/eng/reports/StatisticalData/DailyData/
  - DCE Daily Data / 成交持仓排名：https://www.dce.com.cn/dceg/channel/list/471.html
  - CZCE Market Data / Position Ranking：https://english.czce.com.cn/en/MarketData/TradingRanking/H081002007index_1.htm
  - GFEX Daily Volume & Position Ranking：https://www.gfex.com.cn/en/DailyStatisticsDVPR/Statistics.shtml
- 我的判断：交易所和 AKShare 公开口径能支持“会员成交/持买/持卖排名”这类报表，但不能直接给出稳定会员/席位 id、会员类别、席位类别、角色映射、精确发布时间戳和授权元数据。会员类别/席位结构的本质问题不是继续补几个交易日，而是字段层级不够。公开排名最多回答“谁上榜/产品总量是多少”，不能回答“哪类风险承接者在推动趋势”。

## 开始前反思

- 是否在过拟合：否。本阶段不根据盈亏结果挑阈值、年份、交易所、品种或会员名单，只审计字段是否存在、是否点时化、是否能覆盖当前 `219` 个 entry decision。
- 是否还有价值继续：有。Stage255 已确认分钟层覆盖补完、真实订单流缺失；Stage256 已否定 COT。继续把 Stage099 的会员类别/席位路线做 source inventory，可以避免在“公开会员排名日期覆盖”上继续空转。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage257_member_category_seat_structure_source_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；固定字段合同包含 `trade_date/exchange/product/contract_month_source/member_or_seat_id/member_category/seat_id/rank_type/volume/long_oi/short_oi/publish_timestamp/raw_path/raw_hash/source_license`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：官方 C9/15w 基准沿用 Stage251，`2018-01-01 -> 2026-06-15`
- 账户规模：`150000`
- 成本口径：官方基准成本口径，不新增成本压力回测
- 输入数据：
  - Stage239 `219` 个点时 entry 标签
  - Stage251 官方 A 臂资金曲线与 summary
  - Stage095 会员排名/仓单数值解析产物
  - Stage087 member_rank 覆盖 scorecard
  - Stage099 更细信息源 manifest
  - 本地 `member_rank_sum_daily_20230101_20260417.csv`
  - Stage091 CZCE member_rank raw 文件
- 样本过滤：无盈亏过滤；所有 Stage239 entry 都进入字段覆盖审计
- 策略/归因口径：
  - 只读审计 `member_category_seat_structure` 是否具备字段和覆盖
  - 不创建策略规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP/SimNow、不调用 order API

## 结果

- 官方期末权益：`39,176,437.60`
- 官方总收益：`26017.6251%`
- 官方最大回撤：`-45.0827%`
- 官方 Sharpe：`1.6331`
- 官方总滑点：`2,730,130`
- 官方总交易次数：`787`
- 官方胜率：`53.2560%`
- entry 样本数：`219`
- Stage091 CZCE raw 会员排名文件：`731`
- Stage095 member_rank 数值特征行：`1,274`
- Stage095 member_rank linked lot：`182`
- Stage095 member_rank 产品数：`8`
- Stage095 member_rank target date：`731`
- Stage095 member_rank raw hash ready：`1,274`
- 当前 `219` 个 entry 中能 join 到产品总计会员排名数值上下文：`103/219 = 47.0320%`
- 当前 `219` 个 entry 中会员类别/席位结构 rule-ready：`0/219 = 0.0000%`
- 缺会员类别/席位结构 entry：`219/219`
- 稳定会员/席位 id ready：`0/219`
- 会员类别 ready：`0/219`
- 席位结构 ready：`0/219`
- 合约月级会员排名来源 ready：`0/219`
- 字段合同总数：`19`
- rule-ready 字段数：`12`
- 阻断缺失字段数：`6`：`contract_month_source`、`member_or_seat_id`、`member_category`、`seat_id`、`publish_timestamp`、`source_license`
- promotion gate：`5/11`；通过公开排名存在、本地 raw 存在、raw hash provenance、产品总计数值解析、entry 产品总计 join 非零；失败 role 字段全覆盖、稳定 id、会员类别、合约月来源、发布时间戳/授权元数据和 true engine
- 决策：`stage257_member_category_seat_structure_fields_absent_no_rule`

## 视觉分析

- official path member role coverage：资金曲线上的全部 entry 都是 `Role/category/seat missing` 红叉；蓝圈只代表产品总计数值上下文，不代表角色结构。官方资金路径未被任何角色字段解释。
- field readiness heatmap：交易日、交易所、产品、成交/持买/持卖总量、raw path/hash 可用；`member_category`、`seat_id`、稳定 `member_or_seat_id`、发布时间戳和 source license 全红。
- asset inventory chart：本地 legacy cache、Stage091 raw、Stage095 数值特征和 Stage099 manifest 均显示 `cat=0, seat=0`；数量存在不等于角色字段存在。
- entry exchange/year coverage heatmap：CZCE 2020-2026 的产品总计数值覆盖为 `103/103`，但 role 仍为 `0/103`；DCE/SHFE/GFEX 也都是 role `0`。这说明问题不是单一交易所或年份日期缺口。
- promotion gate chart：前 5 个数据存在性 gate 通过，后 6 个角色/授权/真引擎 gate 全部阻断。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage257_member_category_seat_structure_source_audit/qmt_roll_stage257_c9_minrisk_member_category_seat_structure_source_audit_report_stage257_member_category_seat_structure_source_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage257_member_category_seat_structure_source_audit/qmt_roll_stage257_c9_minrisk_member_category_seat_structure_source_audit_summary_stage257_member_category_seat_structure_source_audit_v1.csv`
- local asset inventory：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage257_member_category_seat_structure_source_audit/qmt_roll_stage257_c9_minrisk_member_category_seat_structure_source_audit_local_asset_inventory_stage257_member_category_seat_structure_source_audit_v1.csv`
- field contract：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage257_member_category_seat_structure_source_audit/qmt_roll_stage257_c9_minrisk_member_category_seat_structure_source_audit_field_contract_stage257_member_category_seat_structure_source_audit_v1.csv`
- entry coverage：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage257_member_category_seat_structure_source_audit/qmt_roll_stage257_c9_minrisk_member_category_seat_structure_source_audit_entry_coverage_stage257_member_category_seat_structure_source_audit_v1.csv`
- entry exchange/year coverage：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage257_member_category_seat_structure_source_audit/qmt_roll_stage257_c9_minrisk_member_category_seat_structure_source_audit_entry_exchange_year_coverage_stage257_member_category_seat_structure_source_audit_v1.csv`
- promotion gate：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage257_member_category_seat_structure_source_audit/qmt_roll_stage257_c9_minrisk_member_category_seat_structure_source_audit_promotion_gate_stage257_member_category_seat_structure_source_audit_v1.csv`
- visuals：`official_path_member_role_coverage`、`field_readiness_heatmap`、`asset_inventory_chart`、`entry_exchange_year_coverage_heatmap`、`promotion_gate_chart`

## 结束后反思

- 是否在过拟合：否。字段缺失后直接阻断，没有继续用 103 个产品总计样本做阈值、TopN、会员简称、年份、交易所或方向救参。
- 是否还有价值继续：有，但会员类别/席位这条公开数据补洞路线没有继续价值。它只有在拿到真正带稳定 member/seat id、member category、seat id、合约月来源、发布时间戳和授权元数据的数据源后才值得重启。
- 原因：当前缺口是 schema/permission gap，不是 date coverage gap。继续补公开 CZCE 产品总计报表，只能把产品总数做满，不能产生类别/席位结构。

## 后续 TODO

- 停止用公开会员排名产品总计继续做日期覆盖补洞；不得把 `103/219` 产品总计 ready 当成交易条件。
- 若要重启会员类别/席位路线，先取得或构建带以下字段的授权/官方数据合同：稳定 `member_or_seat_id`、`member_category`、`seat_id`、合约月级 rank source、发布时间戳、source license/raw hash。
- 未取得这些字段前，不进入 true engine、A/B 或正式候选。
- 若继续外生路线，优先转向 Stage099 其他未闭环信息层级，例如库存/基差/期限结构联动的 source contract audit；合约月份 OI 迁移已由 Stage104-107 证明只剩解释/forward-watch，不应再重复补。
