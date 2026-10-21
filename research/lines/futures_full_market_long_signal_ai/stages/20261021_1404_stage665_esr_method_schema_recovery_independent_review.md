# Stage665：ESR固定数量实验方法、格式恢复与独立全审

记录时间：2026-10-21 14:04 CST；研究线 `futures_full_market_long_signal_ai`。本阶段不是重要突破；全市场98历史代码/95家族目标仍active，正式C9未改。未等今天日线，历史END固定2026-10-16。

## 结论

独立验收通过：唯一review session53512到exit0/chunk dc97b7，106.750759秒，2,890项检查、0失败，Critical0/Important0。671已实际完成24个新增残差头，独审0解方程/重训/策略现金重跑/旧538金融载荷读取。六个经济筛选门均false，真实训练与前向支持门true；按冻结合同关闭这个ESR精确包，不扫lag、商品、符号、尺度、季节、模型或风险救参。

[验收收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage665_esr_method_review/actual_review1/acceptance_receipt.json)，20,099字节，SHA256 `0a6094a56ffce2a4fd16e4cd139bd8bb2bc4de6b5ac15ee5dddd7c63519e23e2`。完整数值与策略裁决由root的Stage672统一报告，独审不重写LINE/registry或根总账。

## 方法与唯一格式恢复

先完整审666；固定5直接族（C/B/M/Y/CF）、3经济组（corn/soy_complex/upland_cotton），其余90族逐位回原A。原6fold的B/C12头，加3经济组×2部署期×B/C12头，最大24；训练经济组排除先于尺度和权重。原52基线只用冻结Ahat/score，0原A重训。B含Ahat、MY季节sin/cos及其A交互，C只增加有符号 `asinh(netSales/prefix_median_abs)` 和A交互，Ridge1、截距不惩罚、共同列train-only scaler保持。

源clock单一统计期末+14日纽约00:00，含真实DST；国内u日15:00截面，四段固定黑窗/MYCO共同无效，latest invalid不回找旧有效期。每reportweek总训练权1，经济组等权、组内源等权、源内继承旧weight；共同52周循环块2,000次/seed20261021。季节phase使用真实365/366长度，前缀尺度不读Y或未来年度最终值。

668初次运行181.389547秒、0attempt/0completed，原因是方法合同假定myDefinition开头四位年，真实字段为 `Sep 1989/Aug 1990`。本agent此前方法预审未核实真实格式，已在[无效运行确认](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage665_esr_method_review/stage668_invalid_run_confirmation.json)明确登记；只核源新缓存前2行、原parser和小terminal/stub，未对无经济实验的53产物扩审。原668完整保留，其全A结果不能用来判断数量信息是否有效。

root669另冻唯一操作修正：严格英文月年/月年、起月/末月/次年校验；不变经济MY日期公式或任何特征/尺度/权重/clock/门。670仅新增1真实格式RED/GREEN回归，旧6fixture不重跑；671金融只读668完整缓存原列白名单268,527,025压缩字节，0重读538大表，5小源各透明再读一次，无新GET。源GO前已核AST：kernel只MY解析变化；统计/target/validation函数保持。666/667/668和旧审查/GO均未改写。

## 独审覆盖与置信度

完整读54个新产物各一次并同读取算hash，独立重构：9,755源行的MY/clock/黑窗、27,935个calendar×source映射、两cutoff前缀尺度；六全训练域和三层权重；全部24头正规方程/共同scaler；1,933,480条前向预测；161,014原母体与990,729原/transfer选择、原156日历和family/tie规则；own未知及same-action配对代数零；4,224周统计、共享155/197事件grid和全部CI/七门；252年度、11,970族年、378经济组年零格；4,881源MSE与1,973周MSE。全部新manifest绑定和14原输入IO收据一致。

原A与held源单位尺度不是全管线未见该经济组，transfer只代表新增头的监督结果组排除。当前源为修订档案，14日lag不是完整首发上界证明；known条件CI不等于fullE未知被识别，历次大量同史择题仍有高适应性风险。PIT、正式生产、极窄止损与加注资格均否。

## 调研判断

本次重查[USDA ERS MY定义](https://www-tx.ers.usda.gov/data-products/oil-crops-yearbook/documentation)及USDA/NASS原定义，起月用于共同季节控制。[原作者SDK源码](https://github.com/chhayly/usda-fas-sdk/blob/main/usda_fas/api/esr.py)支持商品/MY/周身份与缓存实践，不能提供首发vintage或alpha证明。数量是美国全部目的地净合同变化，保留负值，不能命名为中国需求surprise。666/669前后没有依据新收益更改规则。

## 版本参数、指标与后续

- 新增：24个预定数量残差头的实际结果及独立审查；操作层新增真实MY字符串解析与恢复IO路由。
- 修改：MY输入语法解释；经济参数、目标、成本、风险、止损和7个经济/支持门均0修改。
- 删除：参数0、旧结果0；668无效运行完整保留。
- 历史实际fit：563→587；研究完成cash294及1旧partial不变；独审新增fit/cash均0。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均N/A，本轮没有资金回测。
- 开始/结束新增按成绩调参过拟合：否；长期同史研究选择风险：高。
- 继续此精确ESR包：否；继续原完整全市场做多目标：是，但需要不同且可证伪的信息/机制。极窄止损与加注仍待稳定信号和独立账户证据。

本agent仅写665输出与本唯一中文stage，不改其他研究线、LINE/registry、根memory/back_log、Git/远端、CTP、邮件、launchd或正式配置。
