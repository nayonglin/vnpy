# Stage397：固定县代表点合成单个历史高温预报修订

- line_id：`futures_full_market_long_signal_ai`；记录 2026-10-20 14:06 CST。
- 当前模式：独立全市场做多研究；沿用当前分支，无分支/工作树/提交/生产修改。
- 阶段性质：单个历史新信息源合成，不是金融回测或重要策略突破，不触发正式A/B。

## 调研与判断

沿用386的独立农学先验和390/391/392已接受的同未来窗口及原报告；新空间输入来自[NASS官方县级CDL像元表](https://www.nass.usda.gov/Research_and_Science/Cropland/docs/County_Pixel_Count.zip)和[Census官方2010县级Gazetteer](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.2010.html)。395和396记录了实际获取、原schema与限制。2010县像元只分配州内相对空间权重，不能替代2019原州产量；县代表点也不是田块位置。GitHub层面沿用388核实的ECMWF官方eccodes-python解码说明，不增加GIS库或重解旧GRIB。

判断：先完成粗近似的一个可检查物理量有价值；没有理由把天气异常直接等同于可盈利多头信号。库存、需求、南美供给、市场已定价程度及保守滞后仍可能使它没有交易价值。

## 变更与冻结参数

仅新增 `tools/stage397_county_heat_single_case.py`、1个小数值合同测试及397独立输出；不改390/391/395/396输入或任何模型、账户。收益前协议实际冻结于2026-10-20 14:02 CST，SHA `2a1fb053a09c6faf4601084cb6064ebea7f5fe5839779ea33c44b7e5c52cb19d`。

- 原例不变：旧run2020-08-30 00Z、新run08-31 00Z，asof2020-09-01 21:00 CST；未来V为09-02 00Z至09-09 00Z，29个六小时节点/7日，单控制预报，30℃以上梯形积分（℃·日）。
- 精确五位FIPS联结，原州postal一致才可用；不猜县名、不自动crosswalk。最近原生1°格点用球面haversine距离，经度周期、相等取原数组首index。
- 每州县权重=县原soy pixels/该州**全部**395县soy pixels。缺失正质量留在分母，不填零、不重新缩放。old/new/revision共用已知mask。
- 州间仍用391原2019州产量/全美产量，乘2020当周 `(pods−leaves)/100`。
  `X_covered=Σ_s w_s*g_s*Σ_c(pixel_c/totalpixel_s)*ΔH(nearest_point_c)`。
- 18州外进度未知，完整全美指数保持null；全98产品/95family母域不改，m仅有预声明豆粕映射，其余源未建模而非收益零。

新增的是物理映射参数；金融参数新增/修改/删除0，旧回测结果修改/删除0。

## 实际运行与结果

一个合成fixture先RED（文件尚不存在）再GREEN，核经度周期、重复格点确定性与缺失质量不重归一；未跑旧suite。唯一实际handle47005终态exit0，3.836555秒；0网络、0SQL、0预测、0fit、0现金回测、0行情API。代码SHA `e0e6a755e4ed1588218e8cb10d5c318697454d704d2fc0fee4f8f833dbec026b`。

| 项目 | 数值 |
| --- | ---: |
| 全县保留 | 3109 |
| 原始soy为零且保留 | 478 |
| 正soy县 | 2631 |
| 精确代表点匹配 | 3108 |
| 正质量未知 | SD46102，28像元 |
| 原18州生产覆盖/US | 96.4475543106% |
| 18州外未知进度的生产份额 | 3.5524456894% |
| 原w×g质量 | 0.846006077091719 |
| 实际已映射w×g质量 | 0.846006031703037 |
| 覆盖旧热量component | 1.107559789679993 ℃·日 |
| 覆盖新热量component | 0.426145995844799 ℃·日 |
| 覆盖修订component | -0.681413793835194 ℃·日 |
| new−old与revision算术差 | 1.11e-16 |
| 正质量点到最近格点最远角距 | 0.627278° |

主下修贡献NE/KS/IA约−0.286786/−0.151557/−0.140728；ND与NC反而上修约+0.019197/+0.006056。没有挑正值点或调整日期。未匹配的极小质量保留unknown，不为此修码重跑。上述覆盖量不是完整全美观测平均值，更不是减产吨数、价格预测或收益。

期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全部N/A。累计仍454fit/246完整现金回测及1旧金融partial，本阶段新增均0。

## 输出、审查与反思

- 输出：`outputs/stage397_county_heat_single_case/actual_run1/`中的summary/state_heat_components/county_heat_rows/receipt；summary SHA `e79c4dd0df47d53f992a0ce6b71e13059f8623b8a6ec886e718c6999df866e30`；receipt SHA `45aa6ab9040b60ba98f2ad088b22c58ba918a82c1ba91dffd68f8329b0622e8a`。
- 新源与本次空间数学由独立398另行核查；本记录不预先声称review通过。
- 运行前/后新增选参过拟合：否，没有利用金融成绩、单例符号选地图/日期/阈值。但累计研究择题、回顾性地图、时钟及空间近似风险仍存在。
- 运行前/后继续价值：是，已能形成有来源且可检查的外生指标；下一步应固定历史样本和有对照的增量检验，不能据这一个样本宣称稳定优势或加注。
- 今天完整日线只约束原361单次新增前瞻观察，不阻塞历史新源或策略研究。
- root待398终态后以399整理LINE/registry；不追加根memory/back_log。
