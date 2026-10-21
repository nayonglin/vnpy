# Stage448：固定两项原集中度与Con4的有限实现

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 21:33 CST。本阶段为implementation-only，真实来源actual由root另行签发和执行；作者未启动真实actual。非重要alpha突破，没有新增回测或策略候选。
- 开始前读registry、LINE头部及Stage447 `next_scope.json`，5,073 B、SHA256 `ff5b700ac93499739a09d4afb1c6680af1864f86015db563d833bd327b190760`。沿用root已先行完成的官方/原论文/GitHub维护者调研，不重复取数。
- 开始过拟合：本次没有看新收益或选择参数，直接结果救参否；历史自适应择题风险仍高。继续价值：有限是，只检验已确认不同于旧分类净仓的两项原字段是否有可复验数值；不从列名存在自动跳到alpha训练。

## 固定实现

新增 `tools/stage448_cot_Con4_numeric.py`，12,331 B，SHA256 `fb1e087a22cc81600914a9e2634893a72003b05cbe606a3d8fdb679bd53f9943`。

未来唯一actual只沿407绑定的2010—2025十六ZIP，各自一次 `read_bytes()`，用相同bytes核大小/SHA后交 `ZipFile(BytesIO(...))`，唯一成员一次CSV流消费到EOF以验证CRC。完整CSV只为定位固定八代码，输出仅映射原行的两项比例、Con4和必要证据，不导出160,607行宽表。没有导入或执行下载器，只复用407纯parser模块中的固定映射与 `_dates`；实际前还会核该模块的407绑定。

只取精确原列：

- `Conc_Net_LE_4_TDR_Long_All`。
- `Conc_Net_LE_4_TDR_Short_All`。
- `Con4Net_All=(long_pct-short_pct)/(long_pct+short_pct)`。

数值由Decimal检查有限且在闭区间0..100，原始token完整保留；缺值、非有限、越界、格式不合法均unknown，不clip。单端0合法得到±1；两端相同正数合法得到0；双0保留两项0且Con为null、原因 `denominator_zero`。同代码/asof若多个完整原行token hash不同，保留所有来源token及位置并把该槽数值/Con判为冲突unknown，不挑known或取均值。完全相同原行重复只保留重复来源，不增加槽数。

每个origin保存原CFTC代码token（不转整数）、市场名、两日期token、FutOnly/Combined token、两比例token、ZIP SHA/大小、原年份、member、CSV起止行号、原全行token SHA、日期解析状态与行形状状态。2010—2012明确使用 `Report_Date_as_MM_DD_YYYY`，2013以后明确使用 `Report_Date_as_YYYY-MM-DD`，同时支持407既存实际值格式；不靠星期二过滤。若绑定已验源意外出现不可定位的映射日期，实际立即停止，不猜日期或发布日期。

完整输出槽按407 aggregate小型各年 `mapped_asof_dates` 的835日期并集×固定8代码生成6,680行，不按比例known、Conknown或未来盈亏删样本；缺原行仍保留明确unknown。旧mapped/canonical不读取。每行 `publication_available_at=null`、`strict_firstseen=false`、`clock408=retained_not_yet_applied`；408仅保留scope绑定，不读取或应用时钟，不生成Friday近似或交易日visible panel。

未来summary固定提供year×channel的total/knownpair/knownCon/missing/denzero/outofrange/conflict/unknown计数、所有原token的parse-status计数、Con范围及16年实际读取/扫描/保留计数。835持仓日期不是835个已认证发布事件，6,680槽不是独立训练经验。

## 最小合成验证

使用test-driven-development有限流程，先写6个合成unittest方法，骨架返回未实现结果时观察到11项预期断言失败；初次fixture未先检查列表长度导致1项IndexError，补长度断言后再次RED为11项断言失败、0 error，再实现。最终6方法全部GREEN，exit0，0 failure/error：

1. 单端0的±1与两端相等正数的合法Con0。
2. 双0保留两比例0但Con未知。
3. 缺值、101、负数与NaN保持unknown。
4. 两个实际精确日期header、两个实际格式及非周二日期；代码前导0/尾部空格与原行号保留。
5. 同代码/asof不同原行冲突保留两个origin、Con未知。
6. 缺原行槽保留unknown。

测试只使用内存StringIO合成CSV，没有读取真实ZIP/data、价格、Y、score或旧mapped/canonical；没有跑大套件。fixture源 `outputs/stage448_cot_Con4_numeric/fixture_checks.py`，3,369 B、SHA256 `d81e046acd91f50b961f606f47b65cadd6ef0f052c0476dd0750b342a119ec81`；CLI `--help` exit0。未安装依赖，所有Python均使用 `.py311/bin/python`。

## root实际启动入口

输出固定 `outputs/stage448_cot_Con4_numeric/actual_run1/`，已有目录会拒绝覆盖。root签发的authorization JSON必须恰为：

```json
{
  "schema": "stage448_numeric_actual_authorization_v1",
  "authorized": true,
  "code_sha256": "fb1e087a22cc81600914a9e2634893a72003b05cbe606a3d8fdb679bd53f9943",
  "scope_sha256": "ff5b700ac93499739a09d4afb1c6680af1864f86015db563d833bd327b190760"
}
```

本文只是交接最小schema，作者仅写 `authorized:false` 的 `authorization.template.json`，没有自行签发实际授权。CLI：

```sh
PYTHONDONTWRITEBYTECODE=1 .py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage448_cot_Con4_numeric.py --authorization <root签发的authorization.json绝对路径>
```

实现收据 `outputs/stage448_cot_Con4_numeric/implementation_receipt.json`，2,190 B、SHA256 `76d1dc37c71a298e07ef0271cd4bba77d23c2a4cc531250c5a15c62458298b1a`，记录implementation-only与真实读取0，不冒充数值actual收据。真实数值actual及449独审的事实只能由后续各自终态确认。

## 结束边界与反思

本作者截至implementation交接：真实ZIP/data/mapped/canonical读取0；新下载/API/SQL/价格/Y/score/fit/cash/未来D/模型账户生产改动均0。未修改LINE、registry、旧阶段、原档或正式版；金融参数、回测结果新增/修改/删除均0，期末权益、收益、最大回撤、Sharpe、总滑点、交易数、胜率全部N/A。

外部调研判断沿用447：原论文Con4形式可提供不同于分类净仓的潜在观测，但美国同期/周频回归不证明中国发布后窄止损、成本后或OOS优势；官方最大4交易者多空排行不保证同四人，不能把其称MM身份或真实资金流。数值可用率尚未读取，因此未知；时钟、独立增量、long alpha、加注与生产资格也未知。

结束过拟合：没有新收益选择字段/方向/窗口，直接结果救参否，历史择题风险仍在。继续价值：最小实现和边界验证已完成，单次原数值投影有有限价值；若字段质量不足，不换4/8、Gross/Net、Old/Other或净仓类别救数据，root再决定是否继续，当前不做金融。

## root实际终态补记（2026-10-20 21:41 CST）

root随后按冻结code/scope精确授权单次执行actual，session72928 exit0，16ZIP/CSV各一pass、6680完整槽均knownCon，原token13360均有限0—100。449独审单次全新行/3原anchor通过、remaining_core_problems=0，最大Decimal误差1.0101010101E-16；无模型/金融/网络。原作者implementation阶段actual0保留为当时事实，当前实际见actual_run1/receipt.json及450决策。
