# Stage093：既有20bar纯X与当前完整母体的身份映射实现

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 18:26 CST。
- 当前为092冻结协议的准备实现，actual尚0；重要突破否、正式A/B/晋级否。
- 沿当前checkout，只新增093源码、3个新接线测试、本文与小实施收据，不改090/086/旧源/LINE/registry/根总账/其他线或生产。

已全文读092科学合同与机器协议，绑定协议SHA `580c59d77964b27372570b2d48e197ce7a75f5edd77dac0a9aa5e42548d3a736`。沿090一手资料判断：canonical BAG控制同一四元组集合，ORDER提供时间位置，但不保证预测或收益；本准备只是复用接受的023纯X，不重开旧DAY标签或来源工程。

## 新行为与输入边界

`stage093_sequence_alignment.py`只从当前NARROW标签文件读取原IDENTITY7列，从旧ID文件**仅读取event_id列**；不读取旧subset sequence_index、DAY目标/identified/known/mask，亦不加载tensor。按旧ID文件的接受顺序枚举tensor行，经event_id映射至当前完整399252母体。缺失映射为legacy_tensor_index=-1与sequence_missing=1；完整原顺序/身份保留，不改当前ready20资格。

验证旧ID不重复、都在当前母体、旧tensor行覆盖一一对应；验证完整母体sequence_index连续、原ID/日期/epoch不变，索引范围与缺失互补。新actual若另获授权，只导出完整sequence_alignment.csv.gz、摘要、start/terminal和显式角色manifest；不复制tensor、价格或原生库，不重新认证旧来源。

## TDD与冻结交接

3个新接线边界先RED（模块缺失断言），实现后GREEN：按ID而非位置连接且缺失行保留、重复/母体外旧ID拒绝、索引/共享missing/身份篡改拒绝。命令：

```text
.py311/bin/python -m unittest discover -s research/lines/futures_full_market_long_signal_ai/tools -p 'test_stage093_sequence_alignment.py'
```

真实输出`Ran 3 tests ... OK`，exit0；fixture fit0。未跑旧成熟/报价suite。

最终source_bundle：093源码8280B SHA `63822244dda82762f75007db9460665219804138dbf5ae3790df8bc9c5fedd44`；新test1838B SHA `86d8fa6b2d2d4d22d5c50db9b94621ff0ad614a0f2d01fc76d5148d0e18d4e4c`；引用accepted071纯I/O/identity helper33783B SHA `0a0a96baae5f971151845997ca2133b5e7d5d8cec31ecef85b21e9c192945910`。源码冻结后不小修；096预审与root精确授权后才允许实际一次。

CLI四参数：`--output --protocol-sha256 --authorization --authorization-sha256`。root授权schema=`stage092_exact_root_authorization_v1`，stage=`prepare`，authorized_by=root、exact_source_authorized=true、协议SHA、精确source_bundle、fresh output及input_bindings必须匹配。input_roles恰`narrow_labels`（092既定binding）和`old_event_ids`（092既定binding）。预期fresh输出`outputs/stage093_sequence_alignment/experiment/`，目前未创建。

manifest schema=`stage093_sequence_alignment_v1`，status completed、mode actual、protocol/authorization/source_bundle/input_bindings、alignment/terminal精确binding、mother_rows399252、legacy_tensor_rows194709、full_mother_order_sha256；actual计数SQL/fit/cash/labels/download/大库hash均0。094将只消费这一纯X接线与原始bound tensor，不读取旧DAY字段。

## 指标与前后反思

新增/修改/删除交易或模型参数0、金融结果0；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A。actual SQL/tensor读/fit/cash/labels/download均0，完整目标active未达成。

开始和结束是否新增收益择参过拟合：**否，严格实现事先冻结的ID映射；历史研究选择风险仍有。** 继续价值：**有，限保证纯X在完整当前母体中的合法引用**，不代表数据源新增、序列模型有效或收益进展。后续actual准备必须root独立签发，失败保存、不自动修复重跑。

## 18:29补记：唯一prepare actual完成

096对冻结093静态预审C/I0后，root签`prepare_root_authorization.json`（2276B，SHA `fa8326d1edea621bc717401eb011acb2c7a66b223c22979cde1c072d87d49af3`），本owner按上述四参数CLI执行一次，source/test未改。

终态completed、exit0、5.537573667秒：完整399252行，observed194709、missing204543；SQL/tensor/fit/cash/labels/download/大库hash均0。实际只读身份与旧event_id，未重建tensor或读DAY字段。新增金融结果仍0，财务指标N/A；研究fit/cash累计不因准备改变。

精确产物位于`outputs/stage093_sequence_alignment/experiment/`：manifest4446B SHA `4824bb1c88e9eea6778a35f6a5b85fc5954486701b63dc9fef1bd446692612f4`；terminal300B SHA `0c111545d97a32595d791e7b0401795a00e43071b637ea56d2cd1e3f7d8918c1`；alignment20230017B SHA `7279415586a18ca1713049021b7353842cb74b8ce738944d920656896424575e`。小summary与terminal已读回确认计数，并交root/096；不额外载入全表做重复资格化。

实际结束反思：本次没有新增收益择参过拟合，纯ID引用成功也不是新alpha；继续价值限094合法使用既有纯X，尚无模型或现金结论。094须另行root精确授权，作者没有自行启动。
