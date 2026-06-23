# Stage266 授权 W0/orderflow 真实包 validator

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-22 17:14 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读真实包验收 validator；不创建策略规则
- 是否重要突破：否，属于外部数据到货验收链补齐，不是 alpha 突破
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Apache Parquet file format：https://parquet.apache.org/docs/file-format/
  - Apache Arrow / PyArrow Parquet：https://arrow.apache.org/docs/python/parquet.html
  - Databento MBO：https://databento.com/docs/schemas-and-data-formats/mbo
  - Databento MBP-10：https://databento.com/docs/schemas-and-data-formats/mbp-10
  - Frictionless Table Schema：https://frictionlessdata.io/specs/table-schema/
- 我的判断：W0/orderflow 真实包不能只按文件名或行数接收，必须同时验证 raw bytes、normalized parquet schema、proof JSON、license/source、hash、sequence gap、request 时间窗覆盖。Parquet/Arrow 的价值在于可检查列式 schema 与 row metadata；MBO/MBP10 的价值在于区分 L3 order event 和 L2 depth ladder；Table Schema 的价值在于把字段约束显式化。因此 Stage266 应做 validator，不做参数、阈值或交易规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage266_authorized_w0_real_package_validator.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增验收常量 `EXPECTED_W0_REQUEST_COUNT=41`、`EXPECTED_W0_FILE_COUNT=123`、`EXPECTED_ROUTE_WINDOW_COUNT=485`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage251 官方 A 臂 `2018-01-02` 至 `2026-06-15`
- 账户规模：沿用官方 A 臂 15 万口径
- 成本口径：沿用 Stage251 官方 A 臂
- 样本过滤：无新增交易样本；只读审计 Stage135 的 5 个候选 W0 drop root、Stage124 的 123 文件合同、Stage120 的 48 个 canonical 字段、Stage124 的 12 个 proof 必填字段
- 策略/归因口径：不创建策略规则、不运行 true engine、不触发 A/B、不连接 CTP/SimNow、不调用 order API

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - `decision=stage266_authorized_w0_validator_no_real_package_no_rule`
  - drop root candidates `5`
  - existing roots `0/5`
  - roots with files `0/5`
  - accepted W0 package `0`
  - expected per package：W0 request `41`、role file `123`、route window `485`
  - current best role file coverage `0/123`
  - current best request role complete `0/41`
  - route window ready `0/485`，missing `485/485`
  - raw/parquet/proof observed `0/0/0`
  - request hard accept `0`
  - parquet schema audit `205` rows，pass `0`
  - proof/hash audit `205` rows，proof pass `0`，raw hash match `0`
  - canonical field contract `48`
  - proof required field `12`
  - package gate `10/60`，通过项仅为 5 个 root 的只读无订单副作用与无禁用标记；真实 root、文件、schema、proof/hash、Stage112/113 release、策略/true engine 全失败
  - 视觉文件 `6` 张，像素方差检查全部非空

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage266_authorized_w0_real_package_validator/qmt_roll_stage266_c9_minrisk_authorized_w0_real_package_validator_report_stage266_authorized_w0_real_package_validator_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage266_authorized_w0_real_package_validator/qmt_roll_stage266_c9_minrisk_authorized_w0_real_package_validator_summary_stage266_authorized_w0_real_package_validator_v1.csv`
- drop root inventory：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage266_authorized_w0_real_package_validator/qmt_roll_stage266_c9_minrisk_authorized_w0_real_package_validator_drop_root_inventory_stage266_authorized_w0_real_package_validator_v1.csv`
- file role audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage266_authorized_w0_real_package_validator/qmt_roll_stage266_c9_minrisk_authorized_w0_real_package_validator_file_role_audit_stage266_authorized_w0_real_package_validator_v1.csv`
- request package audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage266_authorized_w0_real_package_validator/qmt_roll_stage266_c9_minrisk_authorized_w0_real_package_validator_request_package_audit_stage266_authorized_w0_real_package_validator_v1.csv`
- parquet schema audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage266_authorized_w0_real_package_validator/qmt_roll_stage266_c9_minrisk_authorized_w0_real_package_validator_parquet_schema_audit_stage266_authorized_w0_real_package_validator_v1.csv`
- proof/hash audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage266_authorized_w0_real_package_validator/qmt_roll_stage266_c9_minrisk_authorized_w0_real_package_validator_proof_hash_audit_stage266_authorized_w0_real_package_validator_v1.csv`
- package gate：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage266_authorized_w0_real_package_validator/qmt_roll_stage266_c9_minrisk_authorized_w0_real_package_validator_package_gate_stage266_authorized_w0_real_package_validator_v1.csv`
- quality：6 张 PNG，分别覆盖官方资金路径、drop root matrix、file role coverage、request hard accept heatmap、schema/proof/hash gate、package hard gate

## 结论

- 本阶段结论：Stage266 已把授权 W0/orderflow 真实包到货后的验收流程补成可执行 validator；当前仍没有任何真实 W0 包，`accepted_w0_package_count=0`。所以“还差多少覆盖”的 W0 口径是：`41/41` 个 W0 request、`123/123` 个三件套文件、`485/485` 个 route window 全部未覆盖。
- 是否进入下一步：进入下一步只允许继续外部数据到货监控、或在真实包出现后跑 Stage266 -> Stage112/113 -> Stage141；不允许回到本地 OHLCV/OI 阈值救参。
- 下一步：若 W0 包到货，先看 Stage266 是否 accepted；若没有到货，只能复跑 Stage264/266 监控与验收，不创建规则。

## 过拟合反思

- 运行前判断：不是过拟合，因为本阶段只固定验收合同，不选择交易条件。
- 运行后判断：仍不是过拟合，因为没有根据收益、年份、品种、方向或单笔表现调任何策略参数。
- 原因：Stage266 的信息增益在于把外部数据的真实性、完整性和可复验性约束住；它不解释收益，也不尝试优化回撤。

## 继续价值反思

- 运行前判断：有价值，因为 Stage263/264/265 已经证明真实缺口在外部 orderflow 与执行回放，到货验收需要可复跑工具。
- 运行后判断：有价值但不能无限补本地路线；Stage266 补完了 W0 侧 validator，当前剩余推进依赖真实外部包。
- 原因：现在本地分钟/formal feature 覆盖已不是瓶颈，W0/orderflow 真正差的是 `0/485` route window 和 `0/41` W0 request hard accept。继续补同类本地证据的边际价值下降，后续应等待真实包或做数据采购/forward capture。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage266 摘要。
- 是否更新 `research/registry.md`：否，本阶段不是正式候选、跨线合并或路线废弃。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段为当前线日常验收工具补齐。
