# Stage395：固定2010县级像元成员取得并全行解析

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 14:00 CST；非重要突破，承接393已实际定位的唯一2010成员，不改391原产量/生育暴露。
- 先读registry及root固定`outputs/stage395_fixed2010_county_source/protocol.json`，SHA256 `d9315f65ddd7ef7d801f9f491751f509b00b836984b8d3b11232b7693a5456ce`。只取2010县级像元表，不取其他年份/当前频率层、全国大图或完整ZIP。
- 开始过拟合判断：固定年份、成员和6类在本次数据/金融结果前写入协议，不按收益挑源，本轮直接调参否；既有长期择题风险仍需披露。继续完成这一小实物有价值，可将393的可行路径推进为实际空间结构输入。

## 实际结果

单次原请求成功、单次离线解析成功，无重试或机械失败。原CSV共**3,109行、3,109唯一县FIPS、49个州邮政缩写（48个大陆州与DC）**，无删行：

| 检查项 | 实际结果 |
| --- | ---: |
| 原列数 | 134 |
| 身份列 | 2：`StPostal`、`Fips` |
| 原计数列 | 132：122个`Category_*`、10个`*_all` |
| 校验的原计数单元格 | 410,388 |
| 缺失计数单元格 | 0 |
| 非非负整数字段 | 0 |
| 重复FIPS行 | 0 |
| 6类之和与原`Soybeans_all`不符行 | 0 |
| 大豆像元大于0的县行 | 2,631 |
| 大豆像元明确为0的县行 | 478 |
| 大豆未知县行 | 0 |
| 原6类合计像元数 | 349,151,244 |

这是2010土地覆盖分类的**原像元计数**，不是2010/2019/2020官方面积或产量；没有乘面积、作单产/产量估计或计算天气权重。0像元县与正像元县全部保留，未为提高覆盖率删除小数值县，也不将像元大于0解释成该县一定有显著真实大豆经济暴露。

## 唯一请求与原字节校验

原通路是393官方实际anchor所得[County_Pixel_Count.zip](https://www.nass.usda.gov/Research_and_Science/Cropland/docs/County_Pixel_Count.zip)。只发**一个**请求：

```text
GET Range: bytes=5671161-5969284
If-Match: "a5b488-64dcab7ab0d75"
Accept-Encoding: identity
```

实际HTTP206，Content-Range与393固定总大小/偏移一致；ETag一致；正文298,124B。不跟随重定向、自动重试0、整ZIP下载0。获取进程session94890已真实terminal、exit0，未因观察超时重启。

原local header校验：签名PK0304、文件名`CDL_Cnty_Pixel_2010_30m.csv`、名称27B、extra0、compression8/DEFLATE、flags2（无加密/无data descriptor）；头部后的压缩体恰为298,067B，无多余或缺少字节。有限解压得到1,141,625B，CRC32=`70bfc98e`与393中央目录及root协议一致。

- `original_member_envelope.bin`：298,124B，SHA256 `521bba960a294fec5d8dc348b0e2d588ca0552f764fc50196041a797edb32864`。
- `CDL_Cnty_Pixel_2010_30m.csv`：1,141,625B，SHA256 `6138836a066da3be7120e3578f7602403ddc76a82c2c7d329a432a4c43b4abf4`。
- 完整headers、实际请求时钟、393前件及395协议绑定、local header和CRC证据在`actual_run1/acquisition_receipt.json`与`original_headers.json`。当前ETag/服务器时间只绑定这次取得的现代分发实体，不被称为2011首见。

## 按实际宽表解析，不预造schema

先实际解压原件回报schema后才加离线解析。实际开头为`StPostal,Fips,Category_001,…,Category_254,…,Soybeans_all,…`，不假设它是此前期望的长表。完整原列名保存在`actual_full_schema.json`，未为不存在的类别造列。

依root协议与393已解压README，只取以下六个实际列求和，并逐行比原汇总：

```text
Category_005 + Category_026 + Category_239
+ Category_240 + Category_241 + Category_254
== Soybeans_all
```

所有3,109行相等；其余原计数列同样逐单元检查为非负整数，132列总共410,388个单元格，原CSV始终不改。没有空值填0、负值clip、科学类别修改或按金融结果过滤。各州原像元小计仅是原字段算术汇总，未用于州间经济权重；391的Q2019、w、g均未改。

原`Fips`首行是`1001`，原值原样保留。规范匹配身份只左补零成`01001`，没有县界crosswalk、改县名或按现代行政区替代历史县。已核语法、唯一性、县码非000、同一邮政州只出现一个州FIPS前缀且不同州不共享前缀；**尚未与Census2010原地理实体逐县对账**，因此“3,109有效语法身份”不等于每个县界/编号年代已获外部确认。root另行取得官方Census地理，再检查差异，不能先在本阶段偷偷修正。

## 输出与可追溯性

唯一工具为`tools/stage395_fixed2010_county_source.py`。输出全部位于`outputs/stage395_fixed2010_county_source/actual_run1/`：

- `actual_csv_schema_preview.json`：真实原头与首两行；`actual_full_schema.json`：全134列与身份规范说明。
- `validated_all_count_columns.jsonl`：全部3,109行、全部原132计数列解析值，保留原Fips/规范5位FIPS、原行号、缺失/非法字段及原行SHA256。原行hash定义为UTF8文本去行尾后的单条记录；完整源CSV另有原字节hash，不混同。
- `county_soy_rows.csv`：全部县身份、原6类、原`Soybeans_all`、复算合计、正/零/未知状态、原行号/hash；3,109行全部保留。
- `state_count_summary.json`：原行数、正/零/未知县计数、像元算术和、邮政州—观察到的FIPS前缀。
- `parse_manifest.json`：上述原件、协议、获取收据、脚本和解析产物绑定；状态`all_original_rows_parsed_with_no_detected_core_defect`仅表示本阶段已列数据规则未发现缺陷，未颁独立复审通过或金融资格。

实际只运行：

```text
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage395_fixed2010_county_source.py acquire
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage395_fixed2010_county_source.py parse
```

获取一次、离线解析一次、无旧suite或通用ZIP SDK；未安装任何依赖。root后续独立review应从原CSV重算6类、核FIPS与原件绑定，本作者不自己颁发独立review结论。

## 边界与反思

这关闭“固定2010县级空间结构小表尚未取得/解析”的缺项，但不关闭县界年代、县内田块位置或天气网格映射。当前ZIP属于现代分发的2010分类统计；作为金融结果前固定的**历史结构重建先验**有明确用途，不要求伪造原2011字节，也不把后来重新打包隐瞒成严格PIT。固定2010与2020轮作、扩种及分类误差仍在；如后续效果不好，不得换年份/类别/地图救结果。

代码新增仅本单用途获取/解析脚本，未修改模型/策略参数、回测入口或旧结果。HTTP=1、298,124B；fit=0、cash=0、行情API/SQL/生产/Git/账户变更=0。收益、权益、回撤、Sharpe、滑点、交易次数和胜率均N/A。

结束判断：未依据收益择源或调参，本轮直接过拟合否；长期研究选择偏差不能消除。继续由root与独立Census几何核对并做唯一2020样本物理合成**有价值**。本阶段不越界做天气映射、全国供给指标或金融验证；尚未找到已验证的全市场高质量做多alpha，更无极小止损加注资格。
