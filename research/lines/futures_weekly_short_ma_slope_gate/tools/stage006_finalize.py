from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,hashlib
import pandas as pd
L=Path(__file__).resolve().parents[1];S=L/'stages';A=L/'artifacts/stage006_comparison';C=L/'outputs/stage006_C_attempt001';B=L/'outputs/stage006_A_attempt001'
def load(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for x in iter(lambda:f.read(4194304),b''):h.update(x)
 return h.hexdigest()
def main():
 review=S/'stage006_independent_final.json';r=load(review);assert r['status']=='PASS_WITH_LIMITATIONS' and r['P0']==r['P1']==0
 assert (S/'stage006_independent_review.md').is_file()
 visual=load(S/'stage006_reviewed_visual_receipt.json')
 assert visual['independent_review_sha256']==sha(review)
 pic=L/'artifacts/stage006_nav_drawdown_reviewed.png'
 assert sha(pic)==visual['reviewed_figure_sha256']
 doc=load(A/'comparison.json');t=load(C/'terminal.json');ta=load(B/'terminal.json');assert ta['status']=='completed_pending_independent_review' and ta['error'] is None;assert t['status']=='completed_pending_independent_review' and t['error'] is None
 rows=pd.read_csv(A/'summary.csv').set_index('role');a,c=[rows.loc[k] for k in ['original','price_range']]
 gates=doc['fixed_candidate_gates'];continuation='固定长窗三门均通过，后续独立验证有价值，但仍不自动采用。' if all(gates.values()) else '权益与Sharpe门未通过，不建议直接采用。继续扫20%附近阈值来救结果没有价值；若继续，应先做被拦交易与共享资本路径归因。';now=datetime.now(ZoneInfo('Asia/Shanghai'))
 q=S/(now.strftime('%Y%m%d_%H%M')+'_stage006_2015_short_bottom20_result.md');assert not q.exists()
 annual=pd.read_csv(A/'annual.csv');annual=annual.loc[annual.role.eq('price_range')]
 at='；'.join(f"{int(x.year)}年{x.total_return_pct:+.4f}%" for x in annual.itertuples())
 event=load(C/'short_price_range_acceptance.json');diags=load(C/'short_price_range_decisions.json')
 table='\n'.join(f"| {label} | {x.end_equity:,.0f} | {x.total_return_pct:.4f}% | {x.max_dd_pct:.4f}% | {x.sharpe:.6f} | {x.total_slippage:,.0f} | {int(x.modeled_fill_count)} | {x.round_win_rate_pct:.4f}% | {x.round_payoff_ratio:.6f} | {x.round_profit_factor:.6f} |" for label,x in [('原始无斜率/无区间门A',a),('Stage005历史底20%拒开空C',c)])
 body=f"""# Stage006 固定Stage005历史底20%规则：2015独立起点回测

- line_id=futures_weekly_short_ma_slope_gate；记录{now.isoformat()}；day；本轮只扩展财务起点，不修改策略。是否重要突破：否，结果为固定历史窗口验证，非正式资格。
- A完整回放时间{ta['started_at']}—{ta['completed_at']}；C完整回放时间{t['started_at']}—{t['completed_at']}。两臂各15万元、空仓独立从2015-01-01开始，实际2015-01-05—2026-10-29，2871交易日；不是2020曲线拼接或反向截断。
- 固定C=Stage005：关闭多空新增MA斜率拦截，只拒绝处于同约已有历史高低区间底部20%的新开空信号；A为关闭range门的原始对照。旧range核心stage005_short_bottom20.py保持原字节。

## 变更与合同

- 新增：Stage006独立A/C入口、2015窗口测试、数据范围预审、报告/曲线/独审与交付。新增回测A001/C001两次；没有其他候选扫描。
- 修改参数：financial/trade_start_date从2020-01-01改2015-01-01；历史安全account_start同步，初资仍150000。删除参数：无；原历史回测结果修改/删除：无。
- 数据原receipt.financial_start仍2020，本轮明确记录用户2015授权、Stage006合同及数据预审扩展财务范围；源日线2014起，实际暖机由原引擎处理，不能在2015前交易或承接外部旧仓。此前已有冻结R2015对照可交叉检查。
- 19品种、动态底仓、不加仓、成本/风控/原信号/退出均不变：手续费0、原滑点、静态margin×1.65、21周ready/41storage；原MA5/10/20信号保留，AI/MACD/半R/C2/RSI退出/short_case2关闭。
- P为信号日close；L/H为本地已有同真实合约同physical epoch、日期<=信号日全部有效真实日线low/high极值；P<=L+0.20*(H-L)拦截short_case1a新flat/env/reverse；含等号/信号日；flat range拒开、缺源失败。long/换月续仓/平仓不加新门，不跨合约、不拼主连、不用未来。
- A range.enabledFalse但保留诊断would，applied0；两侧MA斜率证书都False/0diag。C range.enabledTrue。两版实际配置/有效参数/数据相同，仅类开关不同。
- 写入仅本研究线新stage006文件；Stage001—005/LINE/registry/总账/44品种/正式物料/生产不改。已存在offline HTML未跟踪副本不动。

## 完整同窗结果

| 版本 | 期末权益元 | 总收益 | 最大回撤 | Sharpe | 总滑点元 | 成交笔数 | 完整周期胜率 | 平均盈亏比 | Profit Factor |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{table}

- C净值终值{c.nav_end:.6f}；净盈亏{c.net_pnl:,.0f}=已平完整周期{c.round_closed_net_pnl:,.0f}+未平净盯市{c.open_round_net_mtm:,.0f}；末未平周期{int(c.open_round_count)}个，未平占净收益{c.open_round_net_mtm/c.net_pnl*100:.4f}%。
- C完整已平{int(c.round_count)}周期：{int(c.round_wins)}赢/{int(c.round_losses)}亏/{int(c.round_flat)}平，均赢{c.round_average_win:.4f}、均亏绝对额{c.round_average_loss_abs:.4f}；平均盈亏比{c.round_payoff_ratio:.6f}；总赢{c.round_total_winning_pnl:.4f}/总亏{c.round_total_losing_pnl_abs:.4f}，PF{c.round_profit_factor:.6f}。
- C-A权益{c.end_equity-a.end_equity:+,.0f}元，收益{c.total_return_pct-a.total_return_pct:+.6f}个百分点，DD{c.max_dd_pct-a.max_dd_pct:+.6f}个百分点，Sharpe{c.sharpe-a.sharpe:+.6f}。预声明门{gates}；{doc['strategy_verdict']}，NO_PROMOTION。
- 末值桥：A已平{a.round_closed_net_pnl:,.0f}+未平净盯市{a.open_round_net_mtm:,.0f}=净利润{a.net_pnl:,.0f}；C已平{c.round_closed_net_pnl:,.0f}+未平净盯市{c.open_round_net_mtm:,.0f}=净利润{c.net_pnl:,.0f}。C已平比A多{c.round_closed_net_pnl-a.round_closed_net_pnl:+,.0f}，未平差{c.open_round_net_mtm-a.open_round_net_mtm:+,.0f}，合计{c.end_equity-a.end_equity:+,.0f}。统一收盘估值比较总权益，不能只取已平或未平一边判断优劣，也不能把已平差当过滤器直接alpha。
- C年度连续路径收益：{at}。2026为截至10/29；年度切片不是各自15万独立起点，也不是OOS。
- 配置margin×1.65占权益峰{c.actual_margin_to_equity_max_pct:.6f}%，{int(c.actual_margin_over100_days)}天>100%；legacy broker10=1.1倍不能冒称实际券商历史保证金或生产承载。
- C价格区间诊断{event['decision_count']}，would命中{event['would_block_count']}，父级正手数实际归零{event['applied_block_count']}；不等于这么多笔必然成交的反事实。所有实际开仓、源日期与epoch见独审。
- 2020独立起点Stage005的A/C结果仍为1304010/2435920，DD-55.0429%/-44.4543%，Sharpe0.966500/1.161661；这些是另一个15万空仓起点，不能用本2015曲线的2020段替代。起点改变会通过资本/整数手/风险预算/后续机会反馈影响整条路径，账户差不叫过滤器独立alpha。具体继承状态：2019-12-31 A权益311920、FG005多11/OI005多5/cu2002多2；C权益330325、FG005多11/OI005多6/cu2002多2。两者进入2020已带不同权益和OI手数，与2020各15万元空仓起跑不同。

## 验收与边界

- 独立结论{r['status']}，P0={r['P0']}/P1={r['P1']}/P2={r.get('P2',0)}；数据/实际2015起点/预热/首日资金和库存、全部区间事件前缀、实际多空新开/换月、逐笔逐日/持仓/终值、旧2015 A等价及报告净值逐点检查见stage006_independent_review.md/final.json。
- 原2014早期行情和上市初期历史覆盖未证，已知不交易/结构不可用日期未补造。历史区间只指已有有效本地同合约行情，不是上市首日起完整性保证。所有旧交付源哈希检查无漂移。
- 报告窄AST只改旧gate身份和2015窗口常量，保留arm/数据/执行/全部纯会计检查；不伪造实际flags/账本。首日15万、预热无财务状态必须实际验证。
- 图NAV=权益/150000，DD含初资高水位，原pending图保留，reviewed图及receipt绑定最终锁定独审SHA。
- 2次金融回放；行情下载/补价/分钟/proxy/AI读取/订单API/生产访问均0；没有尝试附近阈值、窗口或品种。

## 调研、反思与TODO

- 参考官方https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/ 和https://github.com/mementum/backtrader/blob/master/backtrader/indicators/stochastic.py 。固定相邻执行时序与历史区间规则，只延长起点；不因本次结果更换20%定义。
- 运行前/后过拟合风险：有。2015—2026包含之前已看过的2020—2026，本轮不是严格新样本外；固定扩展无扫描不能消除既有选择偏差。
- 继续价值：这一次早起点完整验证有价值。{continuation} 失败完整保留，不救参；即便其他窗口通过，也不自动正式采用。
- 原主力/生命周期/PIT、零手续费、静态规格/保证金、没有真实分钟/盘口/容量/涨跌停执行资格等限制继续。完整财务一致不是全数据绝对真实或生产资格。
- TODO：冻结本次A/C和独审、图与账本，向用户报告；若继续，再共同固定独立起点/真实成本验证合同，不自动扩展研究。
"""
 q.write_text(body)
 files={}
 for p in [*S.glob('*stage006*'),*L.joinpath('tools').glob('*stage006*'),*A.rglob('*'),L/'artifacts/stage006_nav_drawdown.png',pic,*C.iterdir(),*B.iterdir(),S/'stage005_delivery_manifest.json']:
  if p.is_file():files[str(p.resolve())]=sha(p)
 files.update(load(C/'input_manifest.json'));files.update(load(B/'input_manifest.json'));files.update(doc['source_files_sha256'])
 assert all(sha(p)==h for p,h in files.items())
 out=S/'stage006_delivery_manifest.json';assert not out.exists()
 out.write_text(json.dumps(dict(schema='stage006_delivery_v1',accepted=True,review_status=r['status'],strategy_verdict=doc['strategy_verdict'],promotion_decision='NO_PROMOTION',financial_replays=2,market_downloads=0,production_qualified=False,files_sha256=files,self_hash_excluded=True),ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(stage=str(q),bound_files=len(files),manifest_sha256=sha(out))))
if __name__=='__main__':main()
