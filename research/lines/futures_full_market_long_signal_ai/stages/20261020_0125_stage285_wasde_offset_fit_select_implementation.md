# Stage285：冻结52＋发布当月单scalar offset实现

- line_id=`futures_full_market_long_signal_ai`；2026-10-20 01:25 CST；非重要突破，仅284冻结协议实现，**未启动actual**。本次0实际fit/0cash/0SQL/0网络/0旧大CSV、NPZ、标签或native价格读取，累计439fit/238cash不变。不改LINE/registry/旧source或其他研究线。
- 全文读取284协议，SHA `b604940cf2d43fa504883796a8532a734101a7d2291d7fee225296c384e39193`，并读technical_clarifications `b67e22d679d375d5f4eddd66d53e458a6dcdca2240f2366bcaf575baedc1580f`。沿279接口及283已接受有效期，不更改科学主协议。外网与GitHub依据复用272/277，未重复网络调研：冻结原52才可隔离此次单项修正，但当月脉冲仍可能携带公告期/覆盖代理，不能推作外生因果。

## 本次实现

新增`tools/stage285_wasde_offset_fit_select.py`及对应test。actual入口必须有root精确源bundle/inputs授权、完整282 manifest及独立287已接受算术receipt；287不作为PIT或金融资格。输入source-manifest显式由CLI给出，不依赖284中早期预期目录的词序。282实际目录为`stage282_wasde_incremental_projection/actual_run1`，只消费已合并小projection，不读旧47或新11原件。

- 仅DCE.C可使用有效非V2原报告；r+2自然日NY00转换UTC，完整u日15:00上海close比较，仅r的发布月内启用。跨月主动offset0；月末u可在次月D执行，未新增平仓。相同月、同release/value重复去重；存在不同合格release或value则整月unknown/z0，不选最新或有利报告。缺量/未映射/V2均z0。
- 两个main原训练缓存字符串直接恢复float权重；原成熟身份、目标、权重与原scaler/52coef/intercept不变。actual仅一次COMMON26读取、两份训练CSV读取；只有有限源行需计算冻结s52及残差。训练内原权重加权mean/variance缩放一scalar，至少两报告且正变异；否则unsupported γ0。无新截距、missing或ID，不重归一有源子集权重。保存有限训练q/z/s52/residual/w/source_report、base bindings、scaler和γ。
- 完整130 scores一次分块流读，跳过原held记录；全部966740 main动作包含旧非正分，缺源/零delta严格保留原score浮点位。完整161014母行交原156 D<K前置选择，不复制全score；只额外输出玉米前向delta小表。旧156控制choices只读用于确认DCE.C family外选择身份不变，不重选控制或重跑现金。
- manifest为`stage285_wasde_offset_fit_select_manifest_v1`、新candidate `WASDE_PUBLICATION_MONTH_OFFSET`，artifacts为binding字典，含完整choices_main和boundaries；inputs.mothers/actions原129，另存technical_clarifications。choices内部`VOLUNTARY_RESELECT`只用于157兼容，外部candidate单独保存。

金融前288静态独审发现285边界文档新schema与286期待的旧schema不一致。已将输出调整为**`stage156_voluntary_K_only_v1` / `account_deadline_certified=false` / 原epochs Kmap**，与286完全衔接；只适配序列化身份，不改边界值、科学规则或旧源。286仍按新choices全部selected ID取原129动作，不能只筛旧4365。

## RED → GREEN与交付

先新增真实边界fixture，首次运行因尚无285新模块而exit1；随后实现，最终**9个新fixture全部通过，0.947秒**。覆盖发布前/完整close、NY冬夏令及切换周末、月末/跨月D、release+2跨月、缺源/V2、重复与冲突、固定权重无截距单scalar、冻结52残差、零offset位保持、旧负分翻正、完整score流跳过held和无child母行保留。未跑旧suite；新模块语法compile及`--help`各exit0，未读取金融数据。

[实现收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage285_wasde_offset_fit_select/implementation/implementation_receipt.json)与[供root复核的授权模板](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage285_wasde_offset_fit_select/implementation/authorization_template.json)已写。模板绑定完成282和287收据，**模板写出不是actual已获执行或已运行**。仅root在最终核源后启动一次；失败保留terminal和计数，不自动重试。

- 新源码：29233B，SHA `288188985586cc6a0cfd3bd5bde885236bf8491e056bae8d73d7906f7cf920d8`。
- 新test：8816B，SHA `d36f64baa56625ac57aaa783c6302ec2f08d313fee3dc5660f69959fd2111331`。
- 模板：4820B，SHA `75c965940eec7f687bea884566c08b28698f5d7a25d1cfc014cd1f9e9dad1a38`。

新增仅实现与合成验证，策略科学参数新增/修改/删除0；实际回测结果新增/修改/删除0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易数、胜率、CI全部N/A。本阶段不声称收益改进、held通过、PIT、窄损、加注或晋级资格。

开始/结束新增按本轮收益调参过拟合：**否**，尚无新金融结果且未改冻结政策；长期同史439/238后适应性选题风险：**是**。继续一次固定2main学习/最多4候选现金证伪：**有价值**；重复原基准、来源补洞或按后续结果改符号/有效期/风险：**无价值**。下一步仅root完成金融前最终独审并决定是否实际启动；实际回测后仍须独立agent全面审查数据、逻辑、结果、置信度与bug。
