# Stage030 运行前独立审查

- 结论：**PASS_STAGE030_PREFLIGHT_OFFLINE_RESEARCH_WITH_DECLARED_LIMITATIONS**；P0=0、P1=0、P2=0。允许按冻结合同串行执行daily与weekly两臂，R003只读复用。本人金融回放0、下载0、全仓测试重跑0，不认证金融结果或生产资格。
- adapter/test、runner及report工具五份最终SHA已逐项验证，详见同名JSON；独立重跑20项行为测试全部通过，日志保存于outputs/stage030_preflight_review/。

## 实现与入口

真实Stage827成交成本同步、严格>5%及等值不触发、多空对称、实际层数量加权成本、奇数向下/1手不减、每原生合约轮一次和新开/移仓重置均通过。部分退出保留余层原成本/stop/极值，不重算为现价或扣除已实现利润；RSI flag=False且不复用RSI done。D仅新profit条款读daily close，W仅fresh完整周close；其它指标/技术止损仍周线。

原prev2/layer全平和产品循环内每日账户减仓保持早返回；纯MA20_prev检查在同fresh周全平应成立时defer，保留原MA全平。disabled与原v2行为一致。非法成本、实际数量不符、缺失episode/epoch/错误日期等硬失败，不回退计划价。

runner旧setting/actual/effective与R003直接全字典相等，无放宽归一化。金融前DATA目录严格等于R003实际DB绑定，daily.sqlite/source_manifest/receipt三SHA已由本审查独立重算匹配R003。原19/15万/max19、formal identity、source closure、全AI/HalfR/C2/RSI关闭、epoch、正量日K与次交易日同约open等原闸门保留。输出及completed pointer独立Stage030命名，不覆盖旧pointer；四新诊断、actual config、pending和失败诊断保留。

## 后置保证金安全澄清

原Core在产品循环/rebalance之后仍运行forced margin，再次rebalance。故半仓目标可被后置强减进一步覆盖，一个净close成交可以大于半仓；这是保留原账户安全的实现澄清，没有修改交易规则。行为fixture真实调用原强减方法，验证4手先止盈2手、再明确强减1手、最后留1手，实际净close3手；audit只接受精确3=2+1，删除forced事件即拒验。

execution_allocations/reason_volumes分别保存半仓止盈与forced数量；不得把全净订单都算止盈。核心trade_reason只保留首个pending reason的局限显式标注，归因应使用该分摊凭证。trigger、实际filled和末期真实active pending分别计数，不能混称成交笔数。

## 报告与边界

只读审阅report builder，acceptance schema/配置/字段与新adapter和runner一致；旧参数精确比较、trigger=executed+pending、源绑定、R003快照、实际1.65保证金、已实现/末仓拆分与排他发布符合合同。本审查未独立重跑report测试，根负责本线回归；未绑定根稍后runlog。

每臂金融完成后仍需独立会计、所用源close/实际成本、余仓、执行及SHA复审。旧全仓1652测试5fail/45error边界保留，不称全仓通过。重复历史、原19、零手续费、固定滑点、静态规格、有效观察周跳周、旧源/main/PIT及容量边界不变。

本次未新增拟合或扫描，D/W两臂同时预声明，仍有重复样本选择风险，必须并排保留两臂结果。继续一次固定对照有价值，用于检验兑现频率与趋势右尾的交换，不表示晋级或允许救参。
