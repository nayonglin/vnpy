# Stage306：滞后月份池OI份额的固定52残差offset实施

- 时间：2026-10-20 02:10 CST；line_id：`futures_full_market_long_signal_ai`；仅实施，**0actual**，非重要突破。
- 冻结协议：`outputs/stage304_month_pool_oi_share_protocol/protocol.json`，27686B，SHA `729aa21945cc9dc0f446485dd2671a970cec443f1c32783a083b99ce10ffe6a4`。
- 候选：`LAGGED_MONTH_POOL_OI_SHARE_OFFSET`。科学/外部依据沿302及304冻结的一手调研，本阶段没有另扫资料、旧q或296/297金融成绩。303机制判断独立保留，本轮不实施allocator。

## 唯一改动与接口

新工具 `tools/stage306_month_pool_oi_offset_fit_select.py` 最小适配已接受296源；改304协议、305源manifest、308静审、302来源证明、candidate及自有授权/输出schema。另将新CSV gzip压缩级别设为1，float64/17位输出不变。未改任何旧工具、LINE、registry。

305接口为 `stage305_month_pool_oi_source_manifest_v1`/completed，`artifacts.source_vector`内sequence_index/q/available（完整1552456对齐，q缺失NaN、合法0保留），actions/mothers/common必须与原130绑定相同。新schema为 `stage306_month_pool_oi_offset_fit_select_manifest_v1`；main完整161014父行在 `artifacts.choices_main`，原156 K结构在 `artifacts.boundaries`，source/fit输入绑定保留供307消费。

六fold原成熟身份、sample_weight/net_R_stress直接float恢复、原52系数/intercept/scaler冻结、finite q训练内加权标准化和单一残差scalar公式均复用。完整1933480前向仍只读一次旧scores，保留0offset原scorebits，先D<K再positive/选月；不限定旧4365集合。main/held完整父域、held自身fold和最小5列标签未知语义、紧凑finite train/anchors及身份门不变，不另输出完整新score。held R诊断不充当现金门；实际cash另由307/root控制。

## 有界验证与冻结

按TDD先写一个新身份行为fixture：准确304/OI/306授权可通过freshout入口；旧296候选或授权schema被拒；源manifest及大输入不打开。初次RED exit1为尚未实施身份，随后GREEN exit0，1方法/0.004s。**0fixturefit、0旧suite、0研究actual/fit/cash、0SQL/network、大表读取0。** 数值算法已接受复用，没有重跑296六项suite。独立308只需新身份diff与冻结绑定审查，不将作者fixture替代独审。

| 文件 | SHA256 |
| --- | --- |
| 新工具 | `06cf254e5d87359c1b9694709cf34bb1eb1cb29f2b3ee745d5c5566120347faa` |
| 新test | `4d2f8489814f6c0c02de6278bdf3c6aa882a8acb2445ccee773a952f21df7845` |
| implementation/source_bundle.json | `f9da5985563bd2461be24990243fee86b8e86008beeca04ef02ee4e8f505374c` |
| implementation/fixture_terminal.json | `7eb383541c9b5dc6583e7ec5c07e582eafbed3f72ac18834286a3cdd0a52851c` |
| implementation/authorization_template.json | `709fff317901975a7a39d14d057412ba832ce2ae2f88eb77401cd9d81e4b537e` |
| implementation/input_bindings.json | `62680811d4281f996f1e4fd9d4a5526bb66149e2b5f7340d34a46510d8ee3b7e` |
| implementation/implementation_receipt.json | `c4d25bcdaed2c8538cfca0530e1c6726a77d30cb3a7df065473fa585620cd7e7` |

以上implementation文件均在 `outputs/stage306_month_pool_oi_offset_fit_select/implementation/`。source_bundle仅6个必要小源码，不绑定/读取旧金融结果。模板的305 actual manifest与308 static_receipt保留placeholder，root须用真实completed精确binding替换后签发授权。工具本身要求freshoutput及exact authorization；作者没有执行下列actual命令。

```sh
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage306_month_pool_oi_offset_fit_select.py \
  --authorization <root_final_authorization.json> \
  --authorization-sha256 <root_final_authorization_sha256> \
  --source-manifest research/lines/futures_full_market_long_signal_ai/outputs/stage305_month_pool_oi_source/actual_run1/manifest.json \
  --output research/lines/futures_full_market_long_signal_ai/outputs/stage306_month_pool_oi_offset_fit_select/actual_run1
```

## 反思与后续

新增/修改/删除金融参数与金融结果均0，权益/收益/DD/Sharpe/滑点/交易次数/胜率N/A。没有新成绩调参；多轮历史自适应选题风险仍是。继续价值：仅按302/304一次固定份额反证有，本阶段没有证明alpha、PIT、低DD或穿越周期，目标未完成。等待305真实完成、308静审接受及root唯一actual；不得自动重跑或救参。源码已交root/308，后续实际结果由root统一记录。
