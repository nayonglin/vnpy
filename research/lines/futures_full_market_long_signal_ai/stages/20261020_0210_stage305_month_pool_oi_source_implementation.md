# Stage305：lag1真实成交月份池OI份额源实现，0actual

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 02:10 CST；非重要突破、非正式A/B。
- 先核registry，全文读304协议（27686B，SHA `729aa21945cc9dc0f446485dd2671a970cec443f1c32783a083b99ce10ffe6a4`）。外部先验与GitHub/source判断继承302/304：OI期限分布有套保期限/基差风险解释，不是净多资金或统一收益方向。此次只落实冻结量，不重复联网或采样。

## 实现与固定边界

新增`tools/stage305_month_pool_oi_source.py`和对应test，不改旧工具。actual才会从304绑定的native库执行一次只读immutable十列SELECT；全原native行压成OI/volume/factors、epoch/date、source/quality/unit编码证据，供308独立重算全部pool/unknown/q而0二次SQL，不复制OHLC。

P严格为同精确exchange.product、同v、accepted且finite V>0月份；普通/F分池，v为冻结source-calendar的u_index−1。复用绑定085.unit_state，不二次转换canonical单位。P内任一OI负/非有限或单位未知整池unknown，不能drop坏月缩分母；query缺v不carry、不当0；sumOI≤0 unknown；真q0与单月q1合法。池外未观察月不称OI0，不称全部上市月或资金迁移。

原129 actions只允许三身份列一次流，核完整sequence及当前u真实epoch身份，再精确映射v；不读Y、价格、COMMON大NPZ或mothers。输出`sequence_index:int64 arange1552456`、`q:float64/unknown NaN`、`available:uint8==finiteq`及diagnostic state_code。manifest schema为`stage305_month_pool_oi_source_manifest_v1`；inputs.actions/mothers/common精确继承130，后二者只引用；artifacts为dictbindings。

## 有限验证与绑定

使用test-driven-development流程：3个tiny先因新行为缺失全部预期FAIL，再实现后GREEN（最后`Ran 3 tests in 0.023s, OK`）；syntax/`--help`均exit0。覆盖精确lag不carry/不受未来影响、坏OI/单位整池unknown、合法零/单月、不同已接受来源同池、普通/F隔离、旧delta无法重构份额的代数例及原sequence守恒。不跑旧suite，不执行真实SQL。

- source：19799B，SHA `08409ec19a503a67b12cab11a12fec4b12756f3dc62a865f95f6b7fd397460ef`。
- test：5130B，SHA `a74a3dc162b93c7feed6eb3cbea8a73f6bb730969bb6d1d556cca68c98429d40`。
- `outputs/stage305_month_pool_oi_source/implementation/source_bundle.json`：1678B，SHA `d494d9e1200ef4ca981925b194859889f5a7ba7aba2337b95b2a0a8647610655`。
- 同目录`input_bindings.json`：2125B，SHA `593173d77fcd2b2598efcf1575108d786b666796d4c1695c925c460dc96db653`；`authorization.template.json`：2645B，SHA `bd786489303be43c19dbe49acabc530375c676621bba867aa2ef6cf1d390e862`。模板authorized=false，不是actual授权。
- 308已收到最终source/test/bundle，待其唯一静态审查。原生DB只继承SHA，actual前后核stat，不重hash；新输出fresh目录且失败不自动重试。

root另签精确授权后唯一CLI：

```text
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage305_month_pool_oi_source.py --execute --authorization <root-auth.json> --output /Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage305_month_pool_oi_source/actual_run1
```

## 结果与反思

本阶段0实际OI/动作/NPZ大输入读取、0 SQL、0 labels、0fit、0cash、0下载；只有小协议/源码/小manifest和合成测试。交易参数/财务结果新增修改删除0，权益/收益/DD/Sharpe/滑点/交易/胜率N/A。未创建actual目录，不改LINE/registry/旧source。

开始/结束新增收益调参过拟合否，同史择题风险是；落实冻结单量供一次反证有价值，补全上市OI/换池/换窗救参无价值。实现和tiny通过不是源actual或金融支持，不授窄损安全、加注、PIT或生产资格；完整用户目标仍未完成。作者到此停止，actual只由root执行。
