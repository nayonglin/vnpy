from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,hashlib
import pandas as pd
L=Path(__file__).resolve().parents[1];S=L/'stages';A=L/'artifacts/stage007_comparison';C=L/'outputs/stage007_C_attempt001'
def load(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for x in iter(lambda:f.read(4194304),b''):h.update(x)
 return h.hexdigest()
def main():
 review=S/'stage007_independent_final.json';r=load(review);assert r['status']=='PASS_WITH_LIMITATIONS' and r['P0']==r['P1']==0
 assert (S/'stage007_independent_review.md').is_file()
 visual=load(S/'stage007_reviewed_visual_receipt.json');pic=L/'artifacts/stage007_nav_drawdown_reviewed.png'
 assert visual['independent_review_sha256']==sha(review) and visual['reviewed_figure_sha256']==sha(pic)
 doc=load(A/'comparison.json');terminal=load(C/'terminal.json');assert terminal['status']=='completed_pending_independent_review' and terminal['error'] is None
 df=pd.read_csv(A/'summary.csv').set_index('role');old=df.loc['short_only'];new=df.loc['long_top20'];original=df.loc['original'];gates=doc['fixed_candidate_gates_vs']['short_only']
 now=datetime.now(ZoneInfo('Asia/Shanghai'));out=S/(now.strftime('%Y%m%d_%H%M')+'_stage007_long_top20_result.md');assert not out.exists()
 table='\n'.join(f"| {label} | {x.end_equity:,.0f} | {x.total_return_pct:.4f}% | {x.max_dd_pct:.4f}% | {x.sharpe:.6f} | {x.total_slippage:,.0f} | {int(x.modeled_fill_count)} | {x.round_win_rate_pct:.4f}% | {x.round_payoff_ratio:.6f} | {x.round_profit_factor:.6f} |" for label,x in [('原始无价格门',original),('Stage006仅空头底20%',old),('Stage007加多头顶部20%/新高豁免',new)])
 annual=pd.read_csv(A/'annual.csv');at='；'.join(f"{int(x.year)}年{x.total_return_pct:+.4f}%" for x in annual.loc[annual.role.eq('long_top20')].itertuples())
 long=load(C/'long_price_range_acceptance.json');short=load(C/'short_price_range_acceptance.json');decisions=load(C/'long_price_range_decisions.json')
 continuation='有继续进行固定独立起点/OOS与成本压力验证价值，本窗通过仍不等于正式有效。' if all(gates.values()) else '未通过固定窗口三门，不建议直接采用。继续扫附近阈值或挑年份救参没有价值；若继续，应先固定归因合同，而不搜索参数。'
 body=f"""# Stage007 多头历史顶部20%拦截＋严格新高豁免

- line_id=futures_weekly_short_ma_slope_gate；记录{now.isoformat()}；day；是否重要突破：否，固定结构实验。唯一新增金融回放{terminal['started_at']}—{terminal['completed_at']}。
- 用户明确“多头加顶部20%拦截，超过历史最高价依然可以开仓”。新C在Stage006 C仅空头底20%上新增长门，两侧新增MA斜率门仍关闭；原MA信号、资金/止损/风险和换月/退出保持。

## 变更参数与精确定义

- 多头P=信号日收盘；L/H为同约同physical epoch严格date<signal_date的全部本地已有有效真实日线low最低/high最高。历史不含信号日，当前日与未来极值不能影响此前区间。
- L+0.8*(H-L)<=P<=H拒开新long_case1a/long_case2（顶部20%含两端）；P>H严格突破豁免本门，P==H仍拦；P<顶部下界，包括P<L，均不被此长门拦。
- flat prior H=L：P==H拦，P>H新高豁免，P<H允许；缺prior/非有限数据失败。新高豁免只不应用本门，不能把父级0手变为可开，不能绕过原信号或风险，也不保证有成交。
- 只flat_entry/env_probe/reverse_entry；先完整父级sizing，再仅对正量拷贝归零，不改target/预占；final open guard防旁路。换月续仓、平仓和风险退出不加本门。
- 空头保持原Stage005源码原字节、包含信号日的全日线历史底20%规则，不暗改成prior。多空区间时间口径有意不同，源于本轮只增加带严格新高豁免的多头条件。
- 新增参数long_price_range_gate_enabled=True，long_price_range_threshold=.8/top_fraction=.2，history_scope=all_available_same_physical_epoch_daily_strictly_before_signal，breakout_rule=signal_close_strictly_gt_prior_high。修改其他策略参数：无；删除参数：无；旧回测修改/删除：无。
- 新增回测仅stage007_C_attempt001；对照复用Stage006 C001仅空头、A001原版的同源已审完整账本，不再重跑未变控制。三臂各15万空仓独立2015起点，2015-01-05—2026-10-29共2871日；原19、动态底仓、不加仓、原滑点、手续费0、静态margin×1.65、21周ready/41storage保持。
- 原MA5/10/20交易信号保留；AI/MACD/半R/C2/RSI退出/short_case2仍关闭。所有新文件stage007；旧版本/LINE/registry/根总账/44品种/正式物料/生产不改。

## 同源结果

| 版本 | 期末权益元 | 总收益 | 最大回撤 | Sharpe | 滑点元 | 成交笔数 | 完整周期胜率 | 平均盈亏比 | Profit Factor |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{table}

- 新C净值{new.nav_end:.6f}，净利润{new.net_pnl:,.0f}=已平完整周期{new.round_closed_net_pnl:,.0f}+未平净盯市{new.open_round_net_mtm:,.0f}，末未平{int(new.open_round_count)}周期。
- 已平{int(new.round_count)}周期，{int(new.round_wins)}胜/{int(new.round_losses)}负/{int(new.round_flat)}平；均赢{new.round_average_win:.4f}、均亏绝对额{new.round_average_loss_abs:.4f}，平均盈亏比{new.round_payoff_ratio:.6f}；总赢{new.round_total_winning_pnl:.4f}/总亏{new.round_total_losing_pnl_abs:.4f}，PF{new.round_profit_factor:.6f}。
- 相比仅空头基准：权益{new.end_equity-old.end_equity:+,.0f}元，收益{new.total_return_pct-old.total_return_pct:+.6f}个百分点，DD{new.max_dd_pct-old.max_dd_pct:+.6f}个百分点，Sharpe{new.sharpe-old.sharpe:+.6f}。预声明门{gates}；策略{doc['strategy_verdict_vs_short_only']}，NO_PROMOTION。
- 末值桥：已平差{new.round_closed_net_pnl-old.round_closed_net_pnl:+,.0f}+未平差{new.open_round_net_mtm-old.open_round_net_mtm:+,.0f}=总权益差{new.end_equity-old.end_equity:+,.0f}。共享资本/整数手/保证金/风控与后续机会反馈改变全账户路径，不能将总差直接叫被拦多头的独立alpha。
- 新C年度连续路径：{at}。2026仅到10/29，年度不是独立起点或OOS。
- 新C配置静态margin×1.65/权益峰{new.actual_margin_to_equity_max_pct:.6f}%，{int(new.actual_margin_over100_days)}日>100%；legacy broker10=1.1倍，不是实际历史券商保证金证明。

## 门控与独审

- 多头诊断{long['decision_count']}，would拦截{long['would_block_count']}，父级正量实际归零{long['applied_block_count']}；strict新高诊断豁免{long['breakout_exempt_count']}，不等于这么多笔一定成交。case1a/case2/实际开多与换月、breakout/lower区间fill由独审逐个连接订单anchor验证。
- 空头诊断{short['decision_count']}、命中{short['would_block_count']}、正量拦截{short['applied_block_count']}；规则源码不变，不意味共享资本路径下数量/手数必须等于旧版。
- 独审{r['status']}，P0={r['P0']}/P1={r['P1']}/P2={r.get('P2',0)}；源/参数/数据/实际开仓/strict prior日期与epoch/新高豁免/空头原规则/逐笔逐日/库存终值/三控制及报告曲线逐点重建见stage007_independent_review.md/final.json。
- root62项新旧相关单元测试通过；额外独审测试见final。真实持仓日数据与next-open执行验收通过；新金融回放1次、行情下载/分钟/proxy/AI/订单API/生产访问0。
- 图NAV=权益/150000，DD高水位含初资；原pending图/报告不修改，reviewed图及receipt绑定最终锁定review SHA。历史仅本地已有有效行情，不证明上市首日起完整；原PIT/生命周期/结构缺口、零手续费、静态保证金和无盘口容量限制继续。

## 调研、反思和后续

- 参考Backtrader维护者Donchian代码https://gist.github.com/mementum/1adc2aea1102f222bfa8b93ef892aae8 ：排除当根bar才可判定当前价突破此前边界。本轮不是其默认窗口，而是同约全部已有历史；信号close、next-open模型保持https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/ 。
- 运行前/后过拟合风险：有。在已看过的历史上新增门，2015—2026不是新OOS；固定顶部20%和strict breakout、不扫参数只能避免进一步搜索，不能消除既有选择。
- 继续价值：本次一次固定验证有价值。{continuation} 不自动开展额外窗口或部署。
- TODO：冻结本版本与对照、账本、独审、图和哈希；完整保留结果，无结果后改规则/删交易。下一步需用户共同确定研究方向。
"""
 out.write_text(body)
 files={}
 for p in [*S.glob('*stage007*'),*L.joinpath('tools').glob('*stage007*'),*A.rglob('*'),L/'artifacts/stage007_nav_drawdown.png',pic,*C.iterdir(),S/'stage006_delivery_manifest.json']:
  if p.is_file():files[str(p.resolve())]=sha(p)
 files.update(load(C/'input_manifest.json'));files.update(doc['source_files_sha256'])
 assert all(sha(p)==h for p,h in files.items())
 manifest=S/'stage007_delivery_manifest.json';assert not manifest.exists();manifest.write_text(json.dumps(dict(schema='stage007_delivery_v1',accepted=True,review_status=r['status'],strategy_verdict=doc['strategy_verdict_vs_short_only'],promotion_decision='NO_PROMOTION',financial_replays=1,market_downloads=0,production_qualified=False,files_sha256=files,self_hash_excluded=True),ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(stage=str(out),bound_files=len(files),manifest_sha256=sha(manifest))))
if __name__=='__main__':main()
