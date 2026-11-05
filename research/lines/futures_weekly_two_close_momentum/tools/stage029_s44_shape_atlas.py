"""Publish a local searchable K-line atlas for the frozen Stage029 trade set."""
import base64
import json
from html import escape

import pandas as pd

from stage029_s44_weekly_shapes import OUT, RULES

FOCUS = ("range_expansion", "compression_break", "strong_close", "disjoint_ranges")
NOTES = {
    "range_expansion": "锌多 2750 放大 2.64 倍、收在方向区间 90.3%，并突破前三周，赚 3,600 元。豆一多 3297 放大 2.80 倍、收在 85.7%，但仍在前三周高点内，亏 870 元。液化气多 3260 放大 5.65 倍、收在 73.8%，仅因收盘未达到四分位而落选，赚 26,900 元。",
    "compression_break": "硅铁多 2588 和燃油多 3115 都呈现前三周逐级收窄后收盘突破。前者赚 950 元，后者亏 1,840 元。螺纹多 3323 的信号也有明显推动，但前置区间没有严格逐周缩小。",
    "strong_close": "热卷多 3453 与豆一多 3297 的信号周都收在靠近方向极值的位置。前者是此前回落后的修复，后者是冲高回落后的反抽。实体和收盘位置相似，左侧结构不同。",
    "disjoint_ranges": "苯乙烯多 2865 和白糖多 2736 都出现确认周区间完全分离，结果分别为 +135 元和 -290 元。铜多 3176 的两根周 K 只略有重叠，图上仍明显上移，赚 39,250 元。",
}


def format_rate(value):
    return f"{value:.1%}" if pd.notna(value) else "—"


def publish():
    stats = pd.read_csv(OUT / "shape_stats.csv")
    bounds = pd.read_csv(OUT / "validation_intervals.csv").set_index("rule")
    base = stats.loc[stats.arm.eq("S44") & stats.direction.eq("全部")].set_index(["rule", "phase"])
    filtered = stats.loc[stats.arm.eq("Overlap50") & stats.direction.eq("全部")].set_index(["rule", "phase"])
    dates = ("发现", "2022", "2023–2024", "2025–2026", "核验")
    qualified = []
    table = []
    for rule in sorted(RULES, key=lambda r: -base.loc[(r, "核验"), "win_rate"]):
        cells = [base.loc[(rule, phase)] for phase in dates]
        early, _, first, second, late = cells
        passed = (early.matches >= 80 and late.matches >= 60 and
                  min(early.win_rate, late.win_rate) >= 0.45 and min(early.lift, late.lift) >= 0.07 and
                  min(first.lift, second.lift) > 0 and min(early.average_pnl, late.average_pnl) > 0)
        if passed:
            qualified.append(rule)
        values = "".join(f"<td>{format_rate(c.win_rate)}<small>{c.wins}/{c.matches}</small></td>" for c in cells)
        b = bounds.loc[rule]
        f = filtered.loc[(rule, "核验")]
        table.append(f"<tr><td>{escape(RULES[rule])}</td>{values}"
                     f"<td>{late.lift*100:+.1f} pp<small>[{b.lower*100:+.1f}, {b.upper*100:+.1f}]</small></td>"
                     f"<td>{format_rate(f.win_rate)}<small>{f.wins}/{f.matches}</small></td></tr>")
    data = (OUT / "atlas_data.json").read_text()
    examples = []
    for rule in FOCUS:
        encoded = base64.b64encode((OUT / f"examples_{rule}.png").read_bytes()).decode("ascii")
        examples.append(f'<details{" open" if rule==FOCUS[0] else ""}><summary>{escape(RULES[rule])}</summary>'
                        f'<p>{escape(NOTES[rule])}</p><img loading="lazy" src="data:image/png;base64,{encoded}" alt="12 笔周 K 样例"></details>')
    late_sheets = []
    for page, path in enumerate(sorted(OUT.glob("examples_expansion_late_*.png")), 1):
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        late_sheets.append(f'<details><summary>晚期振幅扩张 · 第 {page} 组</summary>'
                           f'<img loading="lazy" src="data:image/png;base64,{encoded}" alt="晚期振幅扩张逐笔图，第 {page} 组"></details>')
    options = "".join(f'<option value="{key}">{escape(label)}</option>' for key, label in RULES.items())
    html = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>S44 全量交易周 K 形态</title>
<style>
:root{color:#172b3a;background:#eef3f7;font:15px/1.55 system-ui,sans-serif}
main{max-width:1310px;padding:24px;margin:auto} h1{line-height:1.15}
section{background:white;border:1px solid #dbe4eb;border-radius:12px;padding:16px 20px;margin-bottom:16px}
table{width:100%;border-collapse:collapse;text-align:left;font-size:13px;white-space:nowrap}
td,th{padding:7px 9px;border-bottom:1px solid #e0e8ef}th{background:#eaf0f6}small{display:block;color:#526b7e}
.controls{display:flex;flex-wrap:wrap;gap:8px}select,input,button{font:inherit;padding:6px}
#cases{max-width:100%;width:100%;margin-top:9px} svg,img{max-width:100%;width:100%;height:auto}
details{padding:9px 0;border-bottom:1px solid #e1e9f0}summary{cursor:pointer;font-weight:600}
.scroll{overflow:auto}.hint{color:#4d6375} #trade-info{margin:9px 0}
</style></head><body><main>
<h1>S44 全量交易周 K 形态复盘</h1>
<section><p>原 S44 已平仓 3,484 笔，重叠过滤版已平仓 2,347 笔。净盈亏大于零记赢，持平计入分母。所有图按拟开仓方向显示，空单价格方向翻转。形态只读取信号周及之前实际合约的完整周 K。2022 单列，2026 截至 11 月 3 日。</p>
<p>22 个固定形态中，达到事先设定胜率、样本量与跨期要求的有 <b>@@PASS@@ 个</b>。振幅扩张并强收盘在 2023–2026 年胜率最高，但 2015–2021 和 2022 均低于 40%。</p></section>
<section><h2>按形态对照胜率</h2><p>每格下方为胜／命中。胜率差是命中组减去同窗、可判但未命中的交易。方括号是晚期按入场月重抽样、对 22 项比较作 Bonferroni 校正的区间，单位百分点。</p>
<div class="scroll"><table><thead><tr><th>形态</th><th>2015–2021 发现</th><th>2022</th><th>2023–2024</th><th>2025–2026</th><th>2023–2026</th><th>晚期胜率差</th><th>过滤版晚期</th></tr></thead><tbody>@@TABLE@@</tbody></table></div></section>
<section><h2>视觉核查</h2><p>每组展示早期和晚期命中的盈利、亏损案例，以及接近阈值却落选的案例。绿 K 沿开仓方向，黄色区标出两根确认周。</p>@@EXAMPLES@@
<details><summary>展开晚期原 S44 的 76 笔振幅扩张交易</summary><p>按信号收盘是否突破前三周极值分组。突破组 31 胜／61 笔，未突破组 5 胜／15 笔。这个拆分来自看图后的追加观察。</p>@@LATE@@</details></section>
<section><h2>按笔查看周 K</h2>
<div class="controls">
<label>版本 <select id="arm"><option>S44</option><option>Overlap50</option><option value="">全部</option></select></label>
<label>形态 <select id="shape"><option value="">全部</option>@@OPTIONS@@</select></label>
<label>结果 <select id="outcome"><option value="">全部</option><option value="win">盈利</option><option value="loss">亏损</option><option value="flat">持平</option></select></label>
<label>搜索 <input id="query" placeholder="编号、合约或开仓年"></label>
</div>
<select id="cases" aria-label="交易"></select>
<div class="controls"><button id="prev">上一笔</button><button id="next">下一笔</button></div>
<div id="trade-info" aria-live="polite"></div><div id="chart"></div>
<p class="hint">图窗截至信号周。缺实际合约完整周线的历史周留空。上下影线与实体等价格可悬停查看。</p>
</section></main><script>
const trades=@@DATA@@, labels=@@LABELS@@;
const get=id=>document.getElementById(id);
let matches=[];
function update(){
 const q=get("query").value.trim().toLowerCase(), arm=get("arm").value, shape=get("shape").value, outcome=get("outcome").value;
 matches=trades.filter(t=>(!arm||arm===t.arm)&&(!shape||t.rules.includes(shape))&&
 (!outcome||(t.pnl>0?"win":t.pnl<0?"loss":"flat")===outcome)&&
 (!q||String(t.cycle)===q||t.contract.toLowerCase().includes(q)||t.entry.startsWith(q)));
 const list=get("cases");
 list.replaceChildren(...matches.map((t,i)=>new Option(`${i+1}/${matches.length} · ${t.arm} · #${t.cycle} ${t.contract} ${t.direction} · ${t.entry} · ${t.pnl.toLocaleString()} 元`,i)));
 show();
}
function show(){
 const t=matches[Number(get("cases").value)], info=get("trade-info"), chart=get("chart");
 if(!t){info.textContent="没有符合条件的交易";chart.innerHTML="";return}
 info.textContent=`${t.arm} 周期 ${t.cycle} · ${t.contract} ${t.direction} · 信号 ${t.signal} · 开仓 ${t.entry} · 平仓 ${t.exit} · ${t.pnl.toLocaleString()} 元 · ${t.rules.map(k=>labels[k]).join("、")||"无命中形态"}`;
 const known=t.bars.filter(b=>b[0]!==null), floor=Math.min(...known.map(b=>b[2])), top=Math.max(...known.map(b=>b[1]));
 const py=v=>220-185*(v-floor)/(top-floor), x=i=>54+72*i;
 const pretty=v=>Number(v.toFixed(4));
 const candles=t.bars.map(([o,h,l,c],i)=>{
  if(o===null)return `<text x="${x(i)-13}" y="233" fill="#687d8f" font-size="11">缺数据</text>`;
  const xx=x(i), color=c>=o?"#157d72":"#c85c36", price=t.direction==="多"?[o,h,l,c]:[-o,-l,-h,-c];
  return `<g><title>距信号周 ${i-9} 周 | 开 ${pretty(price[0])} 高 ${pretty(price[1])} 低 ${pretty(price[2])} 收 ${pretty(price[3])}</title><line x1="${xx}" x2="${xx}" y1="${py(h)}" y2="${py(l)}" stroke="${color}" stroke-width="2"/><rect x="${xx-10}" y="${Math.min(py(o),py(c))}" width="20" height="${Math.max(Math.abs(py(o)-py(c)),1)}" fill="${color}"/></g>`;
 }).join("");
 chart.innerHTML=`<svg viewBox="0 0 770 260" role="img" aria-label="信号前十周 K 线"><rect width="770" height="260" rx="8" fill="#f3f7fa"/><rect x="594" y="15" width="145" height="220" fill="#fff1cf"/><text x="630" y="29" font-size="12" fill="#785f26">两根确认周 K</text>${candles}<text x="665" y="251" font-size="13" fill="#334c5c">信号周</text></svg>`;
}
for(const id of ["arm","shape","outcome","query"])get(id).addEventListener(id==="query"?"input":"change",update);
get("cases").addEventListener("change",show);
for(const [id,step] of [["prev",-1],["next",1]])get(id).addEventListener("click",()=>{if(matches.length){get("cases").selectedIndex=(get("cases").selectedIndex+step+matches.length)%matches.length;show()}});
update();
</script></body></html>"""
    for tag, replacement in {"@@PASS@@": str(len(qualified)), "@@TABLE@@": "".join(table),
                             "@@EXAMPLES@@": "".join(examples), "@@LATE@@": "".join(late_sheets), "@@OPTIONS@@": options,
                             "@@DATA@@": data, "@@LABELS@@": json.dumps(RULES, ensure_ascii=False)}.items():
        html = html.replace(tag, replacement)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print("Qualified:", qualified)


if __name__ == "__main__":
    publish()
