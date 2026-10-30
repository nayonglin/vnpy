from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,hashlib
import pandas as pd
L=Path(__file__).resolve().parents[1];S=L/'stages';A=L/'artifacts/stage005_comparison';C=L/'outputs/stage005_C_attempt001'
def load(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for x in iter(lambda:f.read(4194304),b''):h.update(x)
 return h.hexdigest()
def main():
 review=S/'stage005_independent_final.json';r=load(review);assert r['status']=='PASS_WITH_LIMITATIONS' and r['P0']==r['P1']==0
 assert (S/'stage005_independent_review.md').is_file()
 visual=load(S/'stage005_reviewed_visual_receipt.json')
 assert visual['independent_review_sha256']==sha(review)
 pic=L/'artifacts/stage005_nav_drawdown_reviewed.png'
 assert sha(pic)==visual['reviewed_figure_sha256']
 doc=load(A/'comparison.json');t=load(C/'terminal.json');assert t['status']=='completed_pending_independent_review' and t['error'] is None
 rows=pd.read_csv(A/'summary.csv').set_index('role');a,c=[rows.loc[k] for k in ['original','price_range']]
 gates=doc['fixed_candidate_gates'];now=datetime.now(ZoneInfo('Asia/Shanghai'))
 q=S/(now.strftime('%Y%m%d_%H%M')+'_stage005_short_bottom20_result.md');assert not q.exists()
 annual=pd.read_csv(A/'annual.csv');annual=annual.loc[annual.role.eq('price_range')]
 at='；'.join(f"{int(x.year)}年{x.total_return_pct:+.4f}%" for x in annual.itertuples())
 event=load(C/'short_price_range_acceptance.json');diags=load(C/'short_price_range_decisions.json')
 table='\n'.join(f"| {label} | {x.end_equity:,.0f} | {x.total_return_pct:.4f}% | {x.max_dd_pct:.4f}% | {x.sharpe:.6f} | {x.total_slippage:,.0f} | {int(x.modeled_fill_count)} | {x.round_win_rate_pct:.4f}% | {x.round_payoff_ratio:.6f} | {x.round_profit_factor:.6f} |" for label,x in [('原始无斜率/无区间门A',a),('Stage005历史底20%拒开空C',c)])
 body=f"""# Stage005：历史区间底部20%禁止新开空

- line_id=futures_weekly_short_ma_slope_gate；记录{now.isoformat()}；day；仅离线研究。改动及唯一新回放时间{t['started_at']}—{t['completed_at']}。
- 本窗重要改善，尚非正式突破或跨周期有效性证明；版本全部保留，旧失败研究不删除，不改LINE/registry/根总账/44品种线/正式物料。
- 用户已明确选择“该合约截至信号时的全部历史”。新增独立Stage005版本，两侧新增MA斜率过滤完全关闭，原MA5/10/20信号/周线技术退出保持。

## 规则与参数

- 新增：同真实合约同physical epoch截至信号日已有有效真实日线high最高H、low最低L；信号日收盘P<=L+20%*(H-L)则不新开空。含等号和信号日，不看未来/次日开盘。
- 参数新增threshold_fraction=0.20；history_scope=all_available_same_physical_epoch_daily_through_signal；price_field=signal_day_close；flat range拒开，缺源/非有限输入失败。
- 修改：从最新斜率版本切回原始无斜率基底，再只加上述空头价格门。short_case1a flat/env_probe/reverse入场适用；long_case1a/long_case2没有新增过滤；换月/平仓/风险退出不滤。
- 删除：只从新版本删除多空MA斜率拦截，不删除旧源码/账本/证据。新增回测仅C001，修改/删除历史回测结果无。
- 新类先调用完整父级sizing，再仅对已选正手数归零；不改父级结果/target/保证金预占；final open guard防旁路。
- 19品种、15万、2020独立空仓起点，实际2020-01-02—2026-10-29，1652日。当前10/30中午日线未完成，复用同冻结DATA，A为Stage001 A003；不截断2015老曲线。动态底仓、不加仓，原滑点/手续费0/静态margin×1.65、41storage/21ready均保持；AI/MACD/半R/C2/RSI退出/short_case2关闭。

## 同源完整回测

| 版本 | 期末权益元 | 总收益 | 最大回撤 | Sharpe | 总滑点元 | 成交笔数 | 完整平仓周期胜率 | 平均盈亏比 | Profit Factor |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{table}

- C净值终值{c.nav_end:.6f}，净盈亏{c.net_pnl:,.0f}元=已平完整周期{c.round_closed_net_pnl:,.0f}+未平净盯市{c.open_round_net_mtm:,.0f}；未平占净收益{c.open_round_net_mtm/c.net_pnl*100:.4f}%。不是已全部实现的收益。
- 已平完整周期{int(c.round_count)}个，{int(c.round_wins)}赢/{int(c.round_losses)}亏/{int(c.round_flat)}平；平均赢{c.round_average_win:.4f}、平均亏绝对额{c.round_average_loss_abs:.4f}，平均盈亏比{c.round_payoff_ratio:.6f}；总赢{c.round_total_winning_pnl:.4f}/总亏绝对额{c.round_total_losing_pnl_abs:.4f}，Profit Factor{c.round_profit_factor:.6f}。
- C-A期末权益{c.end_equity-a.end_equity:+,.0f}元，收益{c.total_return_pct-a.total_return_pct:+.6f}个百分点，DD{c.max_dd_pct-a.max_dd_pct:+.6f}个百分点，Sharpe{c.sharpe-a.sharpe:+.6f}。预声明门{gates}；本窗结论{doc['strategy_verdict']}，NO_PROMOTION。
- 年度连续路径收益：{at}。2026仅到10/29；年度切片不是独立起点/OOS。
- 配置静态交易所保证金×1.65占权益峰{c.actual_margin_to_equity_max_pct:.6f}%，超过100% {int(c.actual_margin_over100_days)}天。legacy broker10=1.1倍率，不能当作真实历史券商保证金或风险可部署证明。
- 新区间诊断{event['decision_count']}条，位于底部/平区间would_block {event['would_block_count']}条，原有正手数实际归零{event['applied_block_count']}条。这是候选门控事实，不是{event['applied_block_count']}笔必然可成交的固定反事实交易。
- 区间数据源392197行已验证，动态资金/整数手/风险路径共同变化；账户权益提升不能直接称这条过滤器独立alpha。

## 数据、图表与独审

- 只用本地已有已准入真实日线，绝不把它称作完整上市首日以来历史。预审旧65候选覆盖105—220有效日，中位185；其中7个缓存首日晚于已知上市日（不等同其余全部已证无缺口）；新C每条单独审查，详见独审。
- 不用仅accepted完成周子集；不跨合约/复用代码年代，不拼主连、不复权伪造历史。prefix按(symbol,epoch)累计，每条source_date<=signal_date，close与实际信号日真实close一致。
- 独立结果{r['status']}，P0={r['P0']}/P1={r['P1']}/P2={r.get('P2',0)}；源文件/实际配置、全部新区间事件、周信号、实际新开与换月、逐笔/逐日/持仓和终值会计、报表与净值逐点重建见stage005_independent_review.md/final.json。
- 根39项相关测试通过，旧文件未修改；report窄AST仅替换一个旧斜率身份检查，仍真实armC且两侧MAFalse，全部会计函数不变、不伪造preflight。
- 图NAV=权益/150000；DD高水位含初资。原待审图保留，已审图stage005_nav_drawdown_reviewed.png及收据绑定最终定稿独审，不修改报告旧字节。
- 新金融回放1次、行情下载0、分钟/proxy/AI读取0、订单API0、生产访问0；与44品种独立。

## 调研、过拟合和后续

- 调研：Backtrader官方https://github.com/mementum/backtrader/blob/master/backtrader/indicators/stochastic.py 及https://github.com/mementum/backtrader/blob/master/backtrader/indicators/basicops.py 。只采用高低区间位置表达，本次全同约缓存历史，无14周期或K/D平滑。低位追空可能遇反弹，也可能抓住新低趋势，没有先验保证。
- 运行前/后过拟合：有。同一历史样本多次改规则，即使本窗改善也非新OOS；固定20%、未扫描窗口/阈值/年份/品种，不能据此声称穿越周期。
- 继续价值：有，固定规则获得本窗改善，值得未来预声明独立起点/样本外及实际成本/保证金压力验证；本次不自动增加回测或扫参，更不自动正式采用。
- 局限：本地已有历史而非上市首日完整历史、历史主力非完整PIT、零手续费、静态规格/保证金、无分钟/盘口/容量/真实成交资格；保留未平盯市会计口径（本候选末0仓、基准有未平），完整财务一致不等于数据绝对全准。
- TODO：冻结本候选、账本、逐条拦截与净值；如用户继续，再先固定独立起点/OOS与成本压力合同。不可只凭本窗收益立即采用。
"""
 q.write_text(body)
 files={}
 for p in [*S.glob('*stage005*'),*L.joinpath('tools').glob('*stage005*'),*A.rglob('*'),L/'artifacts/stage005_nav_drawdown.png',pic,*C.iterdir(),S/'stage004_delivery_manifest_v2.json']:
  if p.is_file():files[str(p.resolve())]=sha(p)
 files.update(load(C/'input_manifest.json'));files.update(doc['source_files_sha256'])
 assert all(sha(p)==h for p,h in files.items())
 out=S/'stage005_delivery_manifest.json';assert not out.exists()
 out.write_text(json.dumps(dict(schema='stage005_delivery_v1',accepted=True,review_status=r['status'],strategy_verdict=doc['strategy_verdict'],promotion_decision='NO_PROMOTION',financial_replays=1,market_downloads=0,production_qualified=False,files_sha256=files,self_hash_excluded=True),ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(stage=str(q),bound_files=len(files),manifest_sha256=sha(out))))
if __name__=='__main__':main()
