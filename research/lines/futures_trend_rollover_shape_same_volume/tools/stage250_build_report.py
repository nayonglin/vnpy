"""Build a portable Chinese attribution report from frozen diagnostics."""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/stage250_20261015_no_signal_report"
D = json.loads((OUT / "diagnostics.json").read_text())
ROWS = D["rows"]
e = html.escape


def num(x):
    return f"{x:,.4f}".rstrip("0").rstrip(".")


def relation(r):
    pairs = [("ma5", "ma10"), ("ma10", "ma20"), ("ma20", "ma40")]
    return " ".join([num(r["ma5"])] + [f"{'>' if r[a]>r[b] else '<' if r[a]<r[b] else '='} {num(r[b])}" for a,b in pairs])


def failures(r, direction):
    c = r["checks"]
    cross = ("golden" if direction == "long" else "death")
    higher = any(c[k] for k in ["golden_10_20", "death_10_20", "golden_20_40", "death_20_40"])
    lower = c["golden_5_10"] or c["death_5_10"]
    case = "case2" if higher else "case1a" if lower else "case3"
    triggered = (c[cross+"_10_20"] or c[cross+"_20_40"]) if higher else c[cross+"_5_10"] if lower else c["macd_"+cross]
    issues = []
    if not triggered:
        issues.append(f"当前走{case}分支，没有当日{'金叉' if direction=='long' else '死叉'}触发")
    if not c["bullish_alignment" if direction == "long" else "bearish_alignment"]:
        pairs = [("ma5","ma10"),("ma10","ma20"),("ma20","ma40")]
        bad = [f"{a.upper()} {num(r[a])} {'≤' if direction=='long' else '≥'} {b.upper()} {num(r[b])}" for a,b in pairs if not (r[a]>r[b] if direction=='long' else r[a]<r[b])]
        issues.append("排列失败：" + "；".join(bad))
    if not c["allow_long" if direction=="long" else "allow_short"]:
        issues.append(f"MACD柱 {num(r['macd_hist'])} 未满足{'大于0' if direction=='long' else '小于0'}")
    return issues


def card(r):
    checks = r["checks"]
    pairs = [("MA5/10", "golden_5_10", "death_5_10"), ("MA10/20", "golden_10_20", "death_10_20"), ("MA20/40", "golden_20_40", "death_20_40"), ("MACD", "macd_golden", "macd_death")]
    trigger = " · ".join(f"{label}：{'金叉' if checks[g] else '死叉' if checks[d] else '无新交叉'}" for label,g,d in pairs)
    averages = "".join(f"<tr><td>{k.upper()}</td><td>{num(r[k+'_prev'])}</td><td>{num(r[k])}</td><td>{num(r[k]-r[k+'_prev'])}</td></tr>" for k in ["ma5","ma10","ma20","ma40"])
    blocks = "".join(f"<div><h4>{label}</h4><ul>"+"".join(f"<li>{e(v)}</li>" for v in failures(r, side))+"</ul></div>" for label,side in [("为何不能触发多头", "long"),("为何不能触发空头", "short")])
    other = f"影线计数 {r['wick_count']}/10（上限5）；RSI6 {num(r['rsi6'])}（入场过滤关闭）；20日通道 [{num(r['donchian_lower'])}, {num(r['donchian_upper'])}]，收盘 {num(r['close'])}。这些数值仅供复核，今天基础信号为空，未成为实际初筛拦截原因。"
    return f'''<details class="product" data-pool="{'in' if r['in_ai_pool'] else 'out'}" data-search="{e(r['name']+' '+r['product']+' '+r['contract'])}">
<summary><span class="symbol">{e(r['name'])} <small>{e(r['contract'])}</small></span><span class="badge {'inside' if r['in_ai_pool'] else ''}">{'池内' if r['in_ai_pool'] else '池外'}</span><span class="reason">{e(r['reason'])}</span></summary>
<div class="detail"><p class="lead">{e(r['reason'])}。</p><p class="muted">{e(r['eligibility_note'])}。当日主力合约；41条真实日线暖机齐全；理论空仓。</p>
<p class="triggers">{trigger}</p><div class="two"><div><table><thead><tr><th>指标</th><th>10月14日</th><th>10月15日</th><th>变化</th></tr></thead><tbody>{averages}</tbody></table><p class="mono">MA5 → MA10 → MA20 → MA40<br>{relation(r)}</p></div>
<div><table><thead><tr><th>MACD</th><th>10月14日</th><th>10月15日</th></tr></thead><tbody><tr><td>DIF</td><td>{num(r['dif_prev'])}</td><td>{num(r['dif'])}</td></tr><tr><td>DEA</td><td>{num(r['dea_prev'])}</td><td>{num(r['dea'])}</td></tr><tr><td>柱=2(DIF−DEA)</td><td>{num(2*(r['dif_prev']-r['dea_prev']))}</td><td>{num(r['macd_hist'])}</td></tr></tbody></table><p class="muted">前一日MACD值取当天同一41条数组的倒数第二点；这是冻结策略实际采用的交叉比较口径。</p></div></div>
<div class="two logic">{blocks}</div><p class="note">{e(other)}</p></div></details>'''


overview = "".join(f"<tr><td><b>{e(r['name'])}</b><br><small>{e(r['contract'])}</small></td><td>{'是' if r['in_ai_pool'] else '否'}</td><td>{num(r['close'])}</td><td>{e(r['reason'])}</td></tr>" for r in ROWS)
review = json.loads((OUT / "independent_review.json").read_text()) if (OUT / "independent_review.json").exists() else None
review_text = "独立审查已完成；详见独立审查文件。" if review else "独立审查进行中。"
page = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>2026-10-15 C9正式策略 · 逐品种无信号归因</title><style>
:root{--bg:#f4f6f9;--ink:#142337;--muted:#647185;--line:#dce3ec;--blue:#164d83;--pale:#eaf2fa}*{box-sizing:border-box}body{font:15px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;margin:0;background:var(--bg);color:var(--ink)}main{max-width:1280px;padding:40px 26px 80px;margin:auto}h1{font-size:34px;line-height:1.35;letter-spacing:-.6px;margin:6px 0 14px}h2{font-size:23px;margin:0 0 15px}h3{margin:22px 0 8px}h4{margin:0 0 5px}p{margin:9px 0}.eyebrow{color:var(--blue);font-size:12px;letter-spacing:2px;font-weight:700}.subtitle,.muted,small{color:var(--muted)}small{font-size:12px}.section{background:white;border:1px solid var(--line);border-radius:16px;padding:26px;margin-top:22px}.hero{padding:30px;background:var(--ink);color:white;border-radius:18px}.hero .muted{color:#c1cfdf}.hero b{color:#8fd6ff}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}.metric{padding:17px 20px;border:1px solid #cdddea;background:white;border-radius:12px}.metric strong{display:block;font-size:29px;color:var(--blue);line-height:1.3}.metric span{font-size:13px;color:var(--muted)}.note{background:#f0f4f8;border-left:3px solid #7198b9;padding:12px 16px;font-size:13px}.two{display:grid;grid-template-columns:1fr 1fr;gap:24px}table{width:100%;border-collapse:collapse;font-size:14px}th{text-align:left;background:#edf2f8;font-weight:600}td,th{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}td:nth-child(2),td:nth-child(3){font-variant-numeric:tabular-nums}a{color:var(--blue)}.scroll{overflow-x:auto}.badge{font-size:12px;white-space:nowrap;padding:2px 10px;background:#edf0f4;border-radius:16px;color:#586577;align-self:start}.badge.inside{background:#e4f1fc;color:var(--blue)}.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}input,select,button{font:inherit;border:1px solid #ccd7e3;border-radius:8px;padding:8px 12px;background:white;color:var(--ink)}input{min-width:230px;flex:1}button{cursor:pointer}.product{border:1px solid var(--line);border-radius:10px;margin:10px 0;overflow:hidden}.product summary{cursor:pointer;display:grid;grid-template-columns:180px 48px 1fr;gap:12px;padding:16px;background:#fafcfe;align-items:start}.product[open] summary{background:var(--pale)}.symbol{font-weight:650}.symbol small{display:block}.reason{font-size:14px}.detail{padding:12px 22px 22px}.lead{font-weight:600;color:var(--blue)}.triggers{font-size:13px;background:#f5f8fb;padding:9px 12px}.mono{font:12px/1.7 ui-monospace,SFMono-Regular,monospace}.logic{margin:18px 0}.logic ul{font-size:13px;padding-left:20px;margin:5px 0}.timeline{font-size:13px;color:var(--muted)}code{font-size:12px;overflow-wrap:anywhere}footer{font-size:12px;color:var(--muted);margin-top:28px} @media(max-width:750px){main{padding:20px 12px}h1{font-size:26px}.section,.hero{padding:18px}.metrics{grid-template-columns:1fr 1fr}.two{grid-template-columns:1fr}.product summary{grid-template-columns:1fr 48px}.reason{grid-column:1/-1}td,th{padding:8px;font-size:12px}}@media print{body{background:white}main{max-width:none;padding:10px}.toolbar{display:none}.section{break-inside:avoid}.product{break-inside:avoid}a{color:inherit}.metrics{grid-template-columns:repeat(4,1fr)}}
</style></head><body><main>
<div class="eyebrow">C9 / 15万 · m0008 · 2026年10月15日</div><h1>为什么今天每个品种都没有交易信号？</h1>
<p class="subtitle">逐品种日线归因报告 · 对应16:35收盘任务、16:42:59服务器接受的邮件 · 行情截至2026-10-15</p>
<div class="hero"><h2>没有满足“新交叉 + 同向排列 + MACD方向”的基础信号</h2><p><b>16个品种没有新的交叉触发；3个品种虽有交叉，但方向与均线排列不匹配。</b>所以19个品种的基础信号都是空，尚未形成入场候选。</p><p class="muted">11个在10月准入池内，8个在池外。池外身份是额外的资格限制，今天并没有8笔信号实际被AI池过滤。组合风险快照为normal，待处理委托和理论持仓均为0。</p></div>
<div class="metrics"><div class="metric"><strong>19 / 19</strong><span>当日主力日线齐全</span></div><div class="metric"><strong>11 + 8</strong><span>池内品种 / 池外品种</span></div><div class="metric"><strong>0</strong><span>基础信号 · 入场候选 · 待处理</span></div><div class="metric"><strong>6 / 6</strong><span>历史候选指标复算一致</span></div></div>
<section class="section"><h2>最容易误解的三个地方</h2><div class="two"><div><h3>趋势持续，不等于每天重新开仓</h3><p>生猪、黄金、纯碱、螺纹钢、纸浆、玻璃已经是空头排列，燃料油已经是多头排列；但策略需要今天刚发生符合条件的交叉事件。昨天已有的排列、MACD柱的正负，不会每天重新发出同一信号。</p><h3>铜出现死叉，仍然不能做空</h3><p>铜的DIF从高于DEA变成低于DEA，但MA5 &gt; MA10 &gt; MA20 &gt; MA40仍是多头排列。空头排列条件失败；多头同时因MACD柱转负失败。</p></div><div><h3>锰硅金叉，还差完整的均线排列</h3><p>MA10从5832.8升至5837，高于MA20的5834.6，形成金叉；但MA20仍低于MA40的5898.3，多头排列没有完成。其近10根长影线有7根也是额外观察项，但今天没有走到影线过滤，不能把它说成实际拦截原因。</p><p class="note">RSI入场过滤关闭。燃料油RSI6约86.54、苹果约6.02，都不是今天没有入场信号的原因。Donchian突破只改变信号的breakout标记，不是独立开仓触发器。</p></div></div></section>
<section class="section"><h2>全部19个品种的结论</h2><p class="muted">池内按本期池列表顺序展示，随后为池外品种。下表的原因来自同一冻结源码和41条真实合约日线的只读重算。</p><div class="scroll"><table><thead><tr><th>品种 / 当前主力</th><th>池内</th><th>收盘价</th><th>今天未形成信号的具体原因</th></tr></thead><tbody>__OVERVIEW__</tbody></table></div></section>
<section class="section"><h2>逐品种数值与多空条件</h2><p class="muted">点击品种展开。列出未通过的基础条件；辅助过滤指标不等于今天实际被执行的拦截。比较采用未舍入值，展示保留至4位小数。</p><div class="toolbar"><input id="search" placeholder="搜索品种、代码或合约" aria-label="搜索品种"><select id="pool" aria-label="筛选池内外"><option value="all">全部19个</option><option value="in">仅池内11个</option><option value="out">仅池外8个</option></select><button id="expand">全部展开</button><button id="collapse">全部收起</button></div><div id="cards">__CARDS__</div></section>
<section class="section"><h2>本次采用的准确判定顺序</h2><ol><li>读取当日映射到的真实主力合约；先将10月15日日线放入AM41，再算指标。全部19合约最近41条记录日期一致：8月12日至10月15日。不是主连拼接，不用下一天数据。</li><li>均线为MA5/10/20/40。多头必须5&gt;10&gt;20&gt;40，空头必须5&lt;10&lt;20&lt;40。多头还需MACD柱&gt;0，空头需&lt;0。</li><li>若10/20或20/40今天发生交叉，走case2；否则若5/10今天发生交叉，走case1a；否则才检查MACD交叉走case3。金叉要求前点短线≤长线、当前短线&gt;长线；死叉镜像。</li><li>基础信号成立后才进行MA5连续逆向、空头MA5斜率、影线等初筛，随后才有品种准入、方向约束、Stage037 ATR形态限制、仓位/保证金等候选与下单路径。今天第一步基础信号已全部为空。</li></ol><p class="note">MACD按冻结实现，在当前41条收盘序列上用EMA12、EMA26、DEA9（adjust=False）计算，柱=2(DIF−DEA)。这里的“前点”是当天窗口倒数第二点，不是另跑昨天窗口得到的终点；因此可能与交易软件的长历史MACD略有不同。报告严格复现邮件程序口径。</p><p>实现细节核查：MA5三日“极值”过滤实际拦截连续两步逆向，并非要求严格创新高/低；影线豁免函数需要45条历史，而AM长度是41，当前配置下该豁免无法触发。这些均没有造成今天的0基础信号，本次未改动实现。</p></section>
<section class="section"><h2>邮件来源、证据与结论边界</h2><p class="timeline">16:35:06 开始 → 日线更新457.48秒，exit=0 → 离线影子计算13.44秒，exit=0 → 16:42:57生成decision → 16:42:59邮件服务器接受。</p><p>实际主题：<b>[本机 C9/15w] 收盘影子报告 2026-10-15</b>。发件来源为本机fian-mail，源码HEAD <code>77538e394167c290d5f2923f4d08931b9bbd7c4f</code>；策略为C9/15万，Stage037规则，AI物料 <code>m0008_20261008T204054+0800_2a7420a9f955</code>，评估日2026-09-30。</p><p>本批次cohort：<code>__COHORT__</code>。原始五文件及候选附加封印用于核对同批数据。没有当日候选、没有委托抑制记录、没有理论持仓需要平仓/换月；风险快照normal不能被解读为实盘下单许可。</p><p>本报告证明上述本机邮件的日线信号归因。原生产stable checkout及资格/激活daily receipt在本机未取得；本机只读邮件服务不等同于已验证的生产环境。Stage861分钟源仍只覆盖至2026-04-24，冷启动窗口缺少完整分钟行情，C2/0.5R止损重试路径仍未完整验证；不能把本报告外推为完整盘中策略或真实收益验收。</p><p>本次没有新跑组合回测、没有调整参数、没有连接CTP或发送邮件。数据只读采集，冻结至本报告目录；纯函数重算保留原信号逻辑。近期6条候选的信号类型、MA10、MA20及RSI6全部一致，数值差为0。__REVIEW__</p><p><a href="per_product.csv">下载逐品种CSV</a> · <a href="diagnostics.json">完整数值JSON</a> · <a href="source_manifest.json">来源与SHA清单</a> · <a href="independent_review.json">独立审查</a> · <a href="evidence/bars_65.csv">冻结日线</a> · <a href="evidence/mail_strategy_summary.json">脱敏邮件摘要</a></p></section>
<footer><p>调研与判断：对照<a href="https://github.com/vnpy/vnpy/blob/master/docs/community/app/portfolio_strategy.md">vn.py组合策略文档</a>与<a href="https://github.com/vnpy/vnpy_portfoliostrategy">官方组合策略实现</a>，沿批量on_bars、信号生成和候选路径定位原因；最终以本机冻结实现和该日证据为准，不能仅用空订单列表推断原因。</p><p>过拟合反思：否，本次未搜索参数、训练模型或按收益筛选规则。继续价值：有，补齐可审计的逐品种解释；下一步应优先完善分钟覆盖和运行资格证据，不因今天没有信号而放宽策略条件。</p></footer>
</main><script>const cards=[...document.querySelectorAll('.product')];function filter(){const q=document.querySelector('#search').value.toLowerCase().trim(),p=document.querySelector('#pool').value;cards.forEach(c=>c.hidden=!(c.dataset.search.toLowerCase().includes(q)&&(p==='all'||c.dataset.pool===p)))}document.querySelector('#search').addEventListener('input',filter);document.querySelector('#pool').addEventListener('change',filter);document.querySelector('#expand').onclick=()=>cards.filter(c=>!c.hidden).forEach(c=>c.open=true);document.querySelector('#collapse').onclick=()=>cards.forEach(c=>c.open=false);window.addEventListener('beforeprint',()=>cards.forEach(c=>c.open=true));</script></body></html>'''
page = page.replace("__OVERVIEW__", overview).replace("__CARDS__", "".join(card(r) for r in ROWS)).replace("__COHORT__", e(D["source_cohort_id"])).replace("__REVIEW__", review_text)
(OUT / "index.html").write_text(page)
print(f"Wrote {OUT / 'index.html'} ({len(page.encode())} bytes)")
