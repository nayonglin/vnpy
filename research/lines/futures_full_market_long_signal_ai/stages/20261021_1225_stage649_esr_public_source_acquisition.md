# Stage649：USDA新版公开出口销售历史取得

- 时间：2026-10-21 12:25 CST；line_id=futures_full_market_long_signal_ai；重要突破：否，仅新增真实来源。
- 开始新增按结果选参过拟合：否，未读取Y/模型/资金成绩；继续价值：是，取得尚未检验的需求侧观测，不是更换WASDE库存或供给预测的供应商。
- 原旧esrquery 404不作为全源不可用证明。官方2026 ESRQS公开手册指向新/esrqs/，新站HTTP200、公开bundle定位正常公开历史查询GET。Corn id10/code401/MetricTons由实际44商品元数据确认。
- 实际raw834460B，SHAa3175f29bbc4e96a20e029b7f1792609c2e90506efcff9101e36133dbc18ddfa；1951行/1919个weekend，1990-01-04—2026-10-08，38营销年。MY Standard1882/Ending37/Starting32全保留，不合并同周不同行。
- 所有字段按原JSON Decimal字符串规范；current netSales负值73、next year43保留，6数量字段null0不意味着来源完整首发；单位是吨，非千吨。0删行/填补/新特征日历join。
- 范围是美国玉米向所有目的地合计，不是中国目的地数据；签约净变化可含取消、调整/转营销年，未装运订单不等于未来实际出口，更不预设对国内全品种利多。
- period end是前周统计结束日，不是发布日期；通常次周四08:30ET但假日/停摆例外。官方当前历史数据库非逐周首发PIT，修订时钟/每周发布证据尚未证明，不机械+7日回贴中国u。
- 直接HTTP7次：脚本/metadata6、报告1，4次200/3次401，自动retry0；3受保护metadata路由未再试，未用token或登录绕过。先CUA入口30秒超时未返回状态，不重复，其内部网络未知不计作0请求。
- [规范化manifest](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage649_esr_public_source_probe/manifest.json)；[全1951行CSV](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage649_esr_public_source_probe/corn_weekly.csv.gz)；[summary](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage649_esr_public_source_probe/summary.json)。Stage651将独立各读一次复核，root652结案。
- 新增/修改/删除策略参数、回测结果均无；权益/ROI/DD/Sharpe/滑点/交易/胜率N/A。累计551fit/294cash+1旧partial不变；正式/生产/Git未改。
- 结束新增按成绩过拟合：否，长期历史择题风险高；继续有界源检验有价值，直接当首发或交易优势无证据。goal active。
- 原资料：[USDA项目与时钟](https://www.fas.usda.gov/programs/export-sales-reporting-program)、[新版公开手册](https://apps.fas.usda.gov/esrqs/assets/ESRQS_UserManual_PublicUser.pdf)、[原USDA GitHub API issue](https://github.com/USDA/USDA-APIs/issues/9)；旧GitHub提问不证明当前接口，实际依赖2026官方bundle与成功响应。
