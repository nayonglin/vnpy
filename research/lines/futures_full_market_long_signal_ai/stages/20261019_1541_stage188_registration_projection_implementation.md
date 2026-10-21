# Stage188：固定登记变化scalar与全身份投影实现准备

2026-10-19 15:41 CST；line_id=`futures_full_market_long_signal_ai`；非重要突破，仅实现183/184/185已定合同。先读registry、185decision与必要129小manifest；与186作者及187审查者直接锁定接口。未读新raw、186实际数量、标签、收益/价格、SQL或金融结果；本轮未实际全量投影。只新增本stage、`tools/stage188_registration_projection.py`和对应测试，不改LINE/registry/旧代码/183/184。

实现分两层：186规范输入先形成product相邻报告pair，再按129原身份向全部399252母/1552456 actions投影。每scope `F=(Qv−Qw)/(Qv+Qw)`，两qty明确0时F=0；Decimal精度50、无epsilon/clip，原官方delta不参与计算。只有完整required集合、每组唯一原普通总计/合格覆盖、同scope身份/版本/单位码与覆盖指纹均通过，才等权平均各scope F。任一坏组、成员不完整/未归属、集合或schema/coverage变化使wholeproduct missing，不平均好子集，不混加qty，不取交集/nearest/fill。原类型/单位仍条件代码，不签物理库存。

时钟直接用129原full052索引：原u_date/u_index是决策D；prospective entry=D+1、reportv=D−1、reportw=D−2。保存各date/index，绝不减去2010偏移，也不以实际延期fill移时钟。D<2等完整历边界保留missing。原parent/action每行身份和顺序保留，action与parent product/family/date/index、mother event和immutable anchor闭包逐行核对；保留无child母行及全部98代码/95family/六所。ordinary/F不自动alias；未映射域留unknown。186当前没有可认证not-applicable清单，188不自行按CFFEX/EC/后缀补分类。

186接口已固定：`scope_observations.jsonl.gz`与`product_scope_status.jsonl.gz`，后者product键为`mapped_research_product_id`；scope唯一合格coverage为`complete_nonduplicated_source_rows`。manifest schema=`stage186_warehouse_history_normalization_manifest_v1`；其既定`calender`字段仅精确比对188的`calendar`输入，不修改186旧拼写或做代理猜测。scope_identity、presence、scope_id、qty Decimal字符串及坏组状态原样消费，未再扫描raw。

全量必须另由root精确授权：CLI `--decision --decision-sha256 --authorization --authorization-sha256 --output`。decision固定185 SHA `40787dfd0b4a8bfebe257fbcc9ea397ba982ea76ff9f60305caaab5ba7fbc017`。auth schema=`stage188_exact_root_authorization_v1`、stage=`projection`、authorized_by=`root`、exact_source_authorized/normalized_source_accepted=true；完整source_bundle必须精确绑定本工具及测试，输出为全新 `outputs/stage188_registration_projection/<run>`。inputs共11项：normalization_manifest、normalization_review、scope_observations、product_scope_status、product_overlay、dataset_manifest、mothers、actions、calendar、feature_design、scope_ruling。

187小receipt必须 schema=`stage187_registration_normalization_review_v1`、accepted=true、C/I/M=0，并精确绑定同一个186 manifest；同时186completed/exit0、规范文件与calendar传递binding、129完整manifest/文件binding、183/184固定hash都校验。不能只依赖root boolean放行。187尚未出实际receipt，本实现不代写accepted。

原大规范gz及129源文件不重复泛hash：继承已审manifest SHA绑定，仅size/stat前后核，并各一次流读。129用`usecols`只读取7母身份列/11动作身份列，不读取原标签、量价或收益列；同步计算identity digest与全域闭包。固定calendar保持完整范围。新输出只保存本次投影/检查，不改变训练标签/COMMON或交易资格。

预计输出包含两张完整projection、全部source-status定义pair及投影所需无源pair的`product_scalar_pairs`、`scope_pairs`、母子闭包、含零product-year覆盖、identity checkpoint/source读收据与started/terminal/manifest。scalar_missing=1时value为空，不冒充0；known零单列统计。已完成identity checkpoint先落盘再补汇总，失败目录保留且禁止自动重试。190/191实现者已收到最终projection列与时钟接口，金融协议另定，不由本程序启动fit/cash。

有限验证采用TDD：缺实现先RED；修正导入笔误、186最终product字段单键适配及覆盖状态未阻断问题，均由合成失败复现后修复。最后只跑新增9项测试：

```text
.py311/bin/python -m unittest research/lines/futures_full_market_long_signal_ai/tools/test_stage188_registration_projection.py
Ran 9 tests in 0.227s — OK
```

覆盖尺度/符号不变与双0、等权scope比率而非数量混加/官方delta、任一坏组/未归属、scope/coverage/schema/presence断点、完整历clock/非nearest、多child与F不alias/身份闭包、重复/父事件错误、显式NA与stat保护、187拒绝及同manifest绑定闸门。未跑旧suite、未用真数组/账本做fixture。

当前锁源（15:44最小schema修复后）：tool 27063B / SHA `bd3da6e25b4d4b445b4b3ecb7ca78eb03411d0cebe6a86c993b3c0de50593d71`；test11997B / SHA `3fbebe9019cf6eba4feb60fcb15bd99f68d146ec1a2dd7d66ec061e8148d413e`。15:41旧tool `8fc5e8...d6b9da`及旧test `e4e805...057ff9`均已作废，不得授权。之后修改须由root重签source；本轮真实projection、fit、cash、SQL、标签、下载均0，累计409fit/218cash不变。权益/收益/DD/Sharpe/滑点/交易数/胜率无新结果。

开始/结束新增结果调参过拟合否，因为只实施固定F/时钟/权重与缺失合同，没有看新scalar/收益；同史择题和归档修订风险仍是。继续一次经独审source的固定投影有价值，按可用性补alias/恢复物理类型、扫描F/lag/K/模型/止损风险无价值。调研继承183/185主源结论，不重复网络或单位字典工程。下一步root静审源码、187规范验收后单独签一次actual projection；不能由source/投影接受推alpha、PIT、执行、加注或正式资格，完整goal未完成。

## 15:44 actual前输入字段最小修复

187静审指出186两张规范表实际日期字段统一为`request_date`，本工具两loop及fixture误用了`date`。按code-review/TDD先把两种fixture源行改为真实schema，原9项测试出现7个`KeyError: date`，复现阻断；随后只改`RegistrationSource.__init__`的两处字段读取为明确的`row['request_date']`，不加fallback、不改186或任何科学规则。原9项测试再跑一次，`Ran 9 tests in 0.241s — OK`。只更新本唯一stage中的锁源收据，未actual、未读真实规范数量、未顺手重构；root须使用上方新hash授权。
