# Stage489：两fold宏观残差头实现就绪，尚未真实运行

- 时间：2026-10-21 01:00 CST；line_id=`futures_full_market_long_signal_ai`；非突破。本阶段只实现root487已冻结的候选；源码未改正式C9、旧研究入口或任何生产/CTP/调度。
- 冻结协议：`outputs/stage487_fomc_residual_protocol/protocol.json`，SHA `e8bd8f4029170a56aaf5513ce43e2bfaa931def02369f252edae5a6228066582`。本记录不签发actual授权。源488正在由root单独执行，作者未读取其未完成文件。

## 本次改动

新增`tools/stage489_fomc_residual_experiment.py`，只提供`fit`子命令；现金由491薄wrapper负责，不在此重复实现。新增参数仅为已冻结的事前流动性校准/匿名FF4、SP500主项及交互低维头；.25N止损、20low、anchor、自愿K、费用、风险、容量均不修改。六个52维底座模型与完整原score不重训。

全部141个事件的54089子身份从已接受484新请求读取；source488精确字段读一次，以原raw_request_id+epoch+pre_date三键校验。读取477原数值一次，ordinal/start双键校验。mask只用source数值、rawjoint、事前u资格和155 D<K；两个候选共享mask，不按标签/分数过滤。事件L先在完整可行动事前域按family/child等权中心；其后各scope/cutoff成熟训练统计标准化。B=`[1,Lz]`，C=`[1,Lz,Fz,Sz,LzFz,LzSz]`，constant不罚、其他alpha1，常量scale1，交互不另scale。

原129 actions只有一次白名单流，同时保留事件标签和完整2020+966740行16列因果现金projection，现金只读新projection。COMMON仅一次提取事件行，写新小COMMON sidecar供独审；每个cutoff/scope用其原portable模型计算训练残差，不宣称交叉拟合。12个微型解每完成一个就保存系数/normal equations/训练身份权重，attempt/completed明确计数，不因导出错误再fit。

完整161014个forward母从156 choices文件七身份列取得，不以旧selected准入，不再读129/470全母或227 metadata。原1,933,480条main+held score只流一次，非事件/缺字段/事前资格不合域的B/C逐值复制A；有值事件加新头，写事件overlay及全scope choices，不杜撰完整新score文件。在线argmax复用156的calendar boundary、rank和family winner，原A main重建的选中ID必须与接受156一致。新boundaries覆盖所有forward score epoch和训练事件epoch，不限旧已选动作。

三组held对照B−A/C−A/C−B保留完整family-u非事件日和未知；相同行动增量消去，不需要重读它的未来Y；不同动作的未知不填0。已知未参与为0，已闭原stress first-exit R保持，K cash与原first-exit诊断的含义不混同。handoff明确绑定B/C完整main choices、forward母、16列完整因果动作、全部边界、原calendar和三组held gate，供491一次8新账，A157自身四账只读。

## 新验证与授权接口

先写6新fixture；首次运行缺实现，失败原因仅`FileNotFoundError`，不是行为反证。实现后6项通过，最后一次0.018秒；覆盖source数值与rule未知分离、事前中心不按label过滤、free constant和constant scale1、严格cutoff/成熟/held、精确fallback、完整未选母以及在线selector与156纯函数等价。CLI help正常；未运行旧suite、真实source、COMMON、score、fit或cash。

- implementation：38014B，SHA `3943c99fc2e29ec7fbf53c8eade99bf1b65d0481b873599a5fc7ed9a553aff24`。
- tests：5107B，SHA `7dda519dd32fbec6f3790f70289d0246020c74ac271be860315a60a415ac359c`。
- `outputs/stage489_fomc_residual_experiment/implementation_binding.json`：3134B，SHA `616b8c82140d8994621923a17b276d98a840089cd1bf835d56f9bf6b38211eb1`；含5项source bundle、确切CLI/root授权模板。
- root授权schema `stage489_fomc_fit_authorization_v1`，要求root、fit、exact protocol/source manifest/source bundle、fresh absolute output、12最大fit与actual_run_limit1；协议本身不授权actual。488完成须same protocolSHA、正确schema及其terminal.completed，不能假设源manifest有status。

490正在有限静态预审；后续若发现真实问题，只改明确问题并重新绑定，不跑旧研究或泛扩测试。

## 调研判断、结果与反思

一手方法继承481/482固定作者源与BoE1114原文，当前不新增网络检索或下载。判断仍是一次条件历史数值包检验：C−B同时增加raw主项与异质交互，不能声称纯交互/因果效应；raw首发PIT、跨年代定义和交易资格未认证。数值有效_F不因历史rule未知丢失，原交易资格与cash核保持独立。

本阶段实际新增fit/cash/SQL/下载均0，累计仍481fit/258完成cash及1旧partial。权益、收益、最大回撤、Sharpe、总滑点、交易次数、胜率N/A；新增/修改/删除已回测金融结果均0。开始/结束按新收益调参：否；长期重复历史适应性风险：是且高。继续价值：有，限root冻结的这一包12头/8账及一次独审；重复盘点源/重复旧回测无价值。用户目标未证明，goal保持active，生产与加注资格false。
