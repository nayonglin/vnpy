from pathlib import Path
import json,hashlib,subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
ROOT=Path.cwd();L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';S=L/'stages';A=L/'artifacts/stage004_comparison';C=L/'outputs/stage004_C_attempt001'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(4194304),b''):h.update(chunk)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
r=load(S/'stage004_independent_final.json');assert r['status']=='PASS_WITH_LIMITATIONS'
assert not any(r.get(k,0) for k in ['P0','P1'])
assert load(C/'terminal.json')['status']=='completed_pending_independent_review'
assert load(C/'terminal.json')['error'] is None
assert (L/'artifacts/stage004_nav_drawdown_reviewed.png').is_file()
summary=pd.read_csv(A/'summary.csv');d=load(A/'comparison.json');terminal=load(C/'terminal.json');metrics=summary.set_index('role');new=metrics.loc['long_ma5']
now=datetime.now(ZoneInfo('Asia/Shanghai'));p=S/(now.strftime('%Y%m%d_%H%M')+'_stage004_long_ma5_result.md')
assert not p.exists()
rows=[]
for role,label in [('original','原始无斜率门'),('short_only','仅空头MA5/10'),('symmetric','多空均MA5/10'),('long_ma5','Stage004多头仅MA5，空头MA5/10')]:
 x=metrics.loc[role];rows.append(f"| {label} | {x.end_equity:,.0f} | {x.total_return_pct:.4f}% | {x.max_dd_pct:.4f}% | {x.sharpe:.6f} | {x.total_slippage:,.0f} | {int(x.modeled_fill_count)} | {x.round_win_rate_pct:.4f}% | {x.round_payoff_ratio:.6f} | {x.round_profit_factor:.6f} |")
years=pd.read_csv(A/'annual.csv');years=years.loc[years.role.eq('long_ma5')]
yeartext='；'.join(f"{int(x.year)}年{x.total_return_pct:+.4f}%" for x in years.itertuples())
text=f"""# Stage004 多头仅MA5斜率门：回测与净值交付

- line_id=futures_weekly_short_ma_slope_gate；记录时间{now.isoformat()}；模式day；非重要突破，研究结果未支持整体优化。
- 真实完整回测时间：{terminal['started_at']} 至 {terminal['completed_at']}（Asia/Shanghai）。设计文件首行手填01:03是记录时间误写；它实际在run前创建且被输入清单冻结，不修改其字节；回测起止以本terminal为准。
- 用户明确要求改完直接回测；独立新版本Stage004，仅研究，不晋级/不部署。四条净值均从同一15万元独立空仓起点开始，1652个交易日，实际2020-01-02—2026-10-29；不把2015老曲线截断。
- 当前为2026-10-30凌晨，当日日线未完成，本次最新完整日为29日。同一已验收数据/19品种，与44品种代码、数据、产物完全解耦；仅本线新增stage004文件。

## 版本及参数变更

- 新增：Stage004独立类、入口、测试、输出、四版报告与净值图、独审和哈希；多头参数long_ma_slope_periods=[5]，MA_periods=[5]，operator=SINGLE。
- 修改：long_case1a/long_case2从任一MA5或MA10负斜率拦截，改为仅MA5严格负斜率拦截；零允许。MA10仍记录供审计，不参与多头判断；sizing与final open guard一致。
- 删除：只删除新版本多头MA10拦截条件，不删除旧版本源码、结果或记录。
- 空头：仍MA5>0 OR MA10>0拦截；采用同约已接受完成周相邻均线差。换月续仓不当作新信号，平仓、风险减仓、动态手数、原止损、完成周/同约下一日开盘执行、41存储/21ready及其余原策略设置不变。不加仓，AI/MACD/半R/C2/RSI退出/short_case2仍关闭。
- 起始资金150000，19品种，原滑点、手续费0、配置静态交易所保证金×1.65。未新增分钟数据，未下载/补行情，订单API0。
- 新增回测结果：唯一新C001；三份同源已审控制直接复用。修改/删除历史回测结果：无。此前Stage001/002/003交付绑定均无漂移，LINE/registry/总账不改。

## 同窗结果

| 版本 | 期末权益元 | 总收益 | 最大回撤 | Sharpe | 滑点元 | 成交笔数 | 完整平仓周期胜率 | 平均盈亏比 | Profit Factor |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

- Stage004净值终值2.3119；净利润196785=已平周期49005+末未平净盯市147780，未平占净利润{147780/196785*100:.4f}%；不是已全部落袋。
- 182个已平完整周期：75赢/106亏/1平；平均盈利9580.6667，平均亏损绝对额6316.4623，平均盈亏比1.516777；总赢718550/总亏669545，PF1.073191。
- 新版相较双MA多头版：期末权益少1410元，收益少0.94个百分点，最大回撤改善13.742204个百分点，Sharpe降低0.002896。成交增加37笔、滑点增加4500元；两版末未平净额同为147780，净差来自已平净额。不将共享资金路径差叫过滤器独立alpha。
- 新版相较仅空头版：期末权益少1343280元，收益少895.52个百分点，最大回撤恶化0.406000个百分点，Sharpe降低0.516902。
- 三个预声明门（相较symmetric权益更高、DD不更差、Sharpe不更低）仅DD通过；MIXED_OR_FAIL_NO_RESCUE_TUNING，NO_PROMOTION。
- 新版年度连续路径收益：{yeartext}。2026只是截止10/29，不是全年；这些年度切片不等同独立起点/OOS验证。
- 配置静态margin×1.65占权益峰值106.445575%，1天超过100%；不能把legacy broker10约70.96%误称实际券商风险通过。

## 门控与复核

- 多头202条诊断，MA5负21次，父级原有正手数而实际归零8次：case1a 2次、case2 6次；空头65条诊断，任一正21次，实际归零16次。诊断并不都等于一定会成交的交易。
- 实际新多头开仓126次（case1a65/case2 61），另12次换月；其中14次MA5非负、MA10为负的实际新开多已放行，证明MA10不再参与。空头43次新开+4次换月。所有真实新开均符合各自方向门，换月不滤。
- 独立复核结果{r['status']}，P0={r.get('P0',0)}/P1={r.get('P1',0)}/P2={r.get('P2',0)}，细节见stage004_independent_review.md及final.json。独立重建周源/同约epoch、逐笔成交/订单锚、逐日持仓和现金会计、源与输出哈希、同源控制及报告。根30项相关单元测试通过；旧对称逻辑在MA10单独向下特例失败、新逻辑通过。
- 真实持仓/成交所需日线无缺口、无零成交持仓日、无bar失败；minute/proxy/AI加载0。模型是日线下一真实开盘，不具有分钟或盘口成交证明。
- 原图stage004_nav_drawdown.png保留待审字样，最终已审图stage004_nav_drawdown_reviewed.png；净值=权益/150000，回撤高水位包含初始资金；完整原始日线/逐笔/持仓在新C001，不伪造覆盖。

## 调研、过拟合反思和后续

- 调研：已查Backtrader官方指标文档https://www.backtrader.com/docu/indautoref/ 与官方GitHub均线/订单示例https://github.com/mementum/backtrader/blob/master/samples/order-execution/order-execution.py 。本次采用相邻完成周MA方向，不引入新回归窗口；取消MA10慢门在逻辑上可能保留转折早期，也可能增加逆势入场，没有先验收益保证。
- 运行前/后过拟合判断：有。看到失败结果后减少条件仍属同一历史样本内选择。本次没有扫参，不代表无过拟合；若继续逐个移除过滤追最高净值会增加风险。
- 运行后继续价值：不建议继续沿同一失败多头门做参数搜索；保存结果和复盘有价值。即使回撤改善，权益/Sharpe未过固定门，整体仍明显弱于仅空头版，不能称优化成功。不自动开展后续回测。
- 局限：手续费为0、历史主力回溯/非完整PIT、静态保证金、容量/盘口/涨跌停/真实执行未证、末仓盯市集中，独审为带限制的离线会计认可，不是全数据绝对真实或正式资格。
- TODO：保留固定Stage004及全部对照与哈希，停止本次搜索。若未来评估采用，需独立起点/OOS和真实成本/保证金验证，另行固定实验；不自动晋级或触碰生产。
"""
p.write_text(text)
files={}
for parent in ['stage001','stage002','stage003']:
 q=S/(parent+'_delivery_manifest.json');files[str(q)]=sha(q)
for q in [*S.glob('*stage004*'),*L.joinpath('tools').glob('*stage004*'),*A.rglob('*'),L/'artifacts/stage004_nav_drawdown.png',L/'artifacts/stage004_nav_drawdown_reviewed.png',*C.iterdir()]:
 if q.is_file():files[str(q)]=sha(q)
files.update(load(C/'input_manifest.json'))
files.update(d['source_files_sha256'])
for q,h in files.items():assert sha(q)==h,q
manifest=S/'stage004_delivery_manifest.json'
assert not manifest.exists()
manifest.write_text(json.dumps(dict(schema='stage004_delivery_v1',accepted=True,review_status=r['status'],production_qualified=False,financial_replays=1,market_downloads=0,files_sha256=files,self_hash_excluded=True),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(stage=str(p),bound_files=len(files),manifest_sha256=sha(manifest))))
