# Stage012 保留C2后的条件性入场日识别结果

- line_id：futures_ai_monthly_pool_generalization；day；2026-10-20 19:16 CST。
- 实际运行：19:13:23，一次185行参考表构建，0.24秒。重要突破：输入/识别进展，无模型或收益突破。
- 参数继承：训练源halfR/retry=False，C2=True，stop/confirm仍1R/1R。正式配置不改。
- 实验性质：参考信号的下一源交易日识别probe，不是185笔真实交易、持续持仓源或60日经济标签。不创建正式A/C。

## 新增工具及变更

- 新增`tools/stage012_c2_reference_frontier.py`、9项测试；未修改策略alpha/正式源码。
- 初始stop从冻结m0008基础+Stage804 AST提取，逐文件SHA校验；多头tight初始stop与空头基础路径保留。基于信号日及之前2源日，共740条真实日线键读取。
- configured tick来自Stage006静态epoch资料。初始signedR正确侧guard是本研究合法性要求；正式源abs本身并无此guard，不混称修复正式逻辑。
- 新增/修改模型参数：无；删除回测结果：无；本轮没有模型fit/金融回放/60日标签/订单/下载。金融指标全部N/A。
- 小测试9项通过；首个合成adapter probe暴露Stage804类名错误，实际构建前修复并加冻结初始stop整合测试。实际185表只构建一次。

## 实际结果

| 状态 | 事件数 |
| --- | ---: |
| 固定月末fresh参考观察 | 185，68历史产品 |
| 下一源日signedR有效 | 172 |
| 开盘已越过原stop或R为0 | 13 |
| 逆/顺1R均未触达 | 66 |
| 仅逆1R触达 | 51 |
| 仅顺1R触达 | 35 |
| 逆/顺两侧均触达，先后未知 | 20 |

152=66+51+35仅在“entry为真实完整session首open、R有效、日OHLC准确完整”的条件下可识别C2动作类别。canonical_session_first_open_verified=0、exact_fills_identified=0，不能写成152个真实可执行事件。仅逆1R可确认条件触发，但跳空可能使fill更差且tick可达性仍待验证。

13错误侧gap保留原行和原因，不填0收益，不默认它们是正式策略取消委托。20双触达保留两个可能动作，不人为用单根日bar的保守stop取代真实未知顺序。

## 分钟库存交叉

Stage011按已有有界来源检查185条同epoch/下一源日键，全部与本表一致。

| 日线类别 | 有日期证据 | 未见日期证据 |
| --- | ---: | ---: |
| 两侧触达 | 4 | 16 |
| 仅顺1R | 9 | 26 |
| 两侧均未触达 | 5 | 61 |
| 仅逆1R | 8 | 43 |
| 错误侧gap | 1 | 12 |

27条仅是分钟库存日期代理，不是完整session。2010—2017的63条参考事件均无本轮有界来源中的日期证据。旧11个accepted full_session收据不自动授权本线新source。

下一步Stage014只对4个双触达且有日期证据的事件核已有分钟payload；DCE.M不在当前硬编码session支持域则保持unsupported，不扩session规则救覆盖。不会拼不同provider绕过冲突或假造缺分钟。

## 版本与置信边界

- Stage010发现current修复版与frozen m0008 C2可能事件不同：后一分钟open已越过confirm、同一分钟又穿stop时，current先判open而frozen先看high/low。表绑定current repaired helper SHA，初始stop绑定frozen确定性方法，不称完整正式C9回放。
- 日线四分法数学边界由实际helper两条同OHLC不同路径反例验证；来源日历仍是共有代理，非逐所历史PIT。
- 原18池/全市场域未按未来覆盖删池；本185表只针对预声明月末fresh观察，是执行识别诊断，不替代全候选模型母体。

## 复核与反思

独立Stage013已从Stage008原表、740个源键与冻结公式复算185/185，1289断言0失败；9项小测试通过。结果与root一致。后续分钟witness另审，不将本统计当作分钟完整资格。

开始/结束新增按收益选参过拟合：否，未看收益、未改1R或窗口；历史目标选择、source版本和静态经济资料偏差仍存在。继续价值：是，但有效方向是精确已有歧义证据和单品种源合同，不是把未知标签补成点值后立即fit。

调研判断：vnpy与Backtrader官方的时点/撮合区分支持明确后续执行与OHLC假设；本地反例证明日双触达不能恢复先后顺序。链接与结果前范围见Stage012 protocol；无外部资料可替本地session资格证明。
