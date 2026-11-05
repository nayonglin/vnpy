"""Publish the loss atlas and reconcile all manual notes to the frozen ledger."""
import base64
from html import escape

import pandas as pd

from stage027_s44_loss_forensics import OUT, RULES


def render():
    features = pd.read_csv(OUT / "trade_features.csv")
    losses = features.loc[features.entry_year.eq(2022) & features.net_pnl.lt(0)]
    visual = pd.read_csv(OUT / "visual_review.tsv", sep="\t")
    chart_inputs = pd.read_json(OUT / "chart_inputs.json")
    assert list(visual.cycle) == list(chart_inputs.cycle) == list(losses.cycle)
    assert len(visual) == 206 and visual.cycle.is_unique and visual.visual_note.str.len().min() > 10
    audited = losses.merge(visual, on="cycle", validate="one_to_one")
    audited["chart_sheet"] = audited.index // 20 + 1
    audited.to_csv(OUT / "loss_review.csv", index=False, encoding="utf-8-sig")

    attribution = pd.read_csv(OUT / "filter_attribution.csv")
    summary = attribution.loc[attribution.direction.eq("all")].set_index(["period", "rule"])
    overlap = summary.loc[("2022", "two_bars_overlap")]
    other_overlap_pnl = sum(
        summary.loc[(period, "two_bars_overlap"), "selected_net_pnl"]
        for period in ("2015–2021", "2023–2026")
    )
    overlap_loss_rate = overlap.loss_selected / overlap.selected
    other_loss_rate = (overlap.loss_all - overlap.loss_selected) / (overlap.total - overlap.selected)
    comparisons = []
    for key, label in RULES.items():
        before, current, after = (summary.loc[(period, key)] for period in ("2015–2021", "2022", "2023–2026"))
        comparisons.append(
            f"<tr><td>{escape(label)}</td><td>{current.loss_selected}/{current.loss_eligible}</td>"
            f"<td>{current.win_selected}/{current.win_eligible}</td>"
            f"<td>{current.unknown}</td><td>{current.selected_net_pnl:+,.0f}</td>"
            f"<td>{before.selected_net_pnl:+,.0f}</td><td>{after.selected_net_pnl:+,.0f}</td></tr>"
        )

    def number(value, percent=False):
        if pd.isna(value):
            return "缺历史"
        return f"{value:.1%}" if percent else f"{value:,.2f}"

    rows = []
    for row in audited.itertuples(index=False):
        active = "、".join(RULES[key] for key in RULES if pd.notna(getattr(row, key)) and getattr(row, key))
        rows.append(
            f'<tr id="trade-{row.cycle}"><td><a href="#sheet-{row.chart_sheet}">{row.cycle}</a></td>'
            f"<td>{escape(row.contract)}</td><td>{'多' if row.direction == 'long' else '空'}</td>"
            f"<td>{row.signal_date}</td><td>{row.entry_date} → {row.exit_date}</td>"
            f"<td>{'周线止损' if row.exit_reason == 'weekly_stop' else '到期保护'}</td>"
            f'<td class="loss">{row.net_pnl:,.0f}</td><td>{escape(row.visual_note)}</td>'
            f"<td>{number(row.overlap_shorter_range, percent=True)}</td>"
            f"<td>{number(row.directional_3w_break_distance)}</td>"
            f"<td>{number(row.ma5_slope)} / {number(row.ma10_slope)} / {number(row.ma20_slope)}</td>"
            f"<td>{escape(active or '无')}</td></tr>"
        )
    atlas = []
    for page in range(1, 12):
        path = OUT / f"sheet_{page:02d}.png"
        picture = base64.b64encode(path.read_bytes()).decode("ascii")
        atlas.append(
            f'<details id="sheet-{page}"><summary>图组 {page:02d} · '
            f'第 {(page-1)*20+1}–{min(page*20, len(audited))} 笔</summary>'
            f'<img loading="lazy" src="data:image/png;base64,{picture}" alt="第 {page} 组逐笔信号周图"></details>'
        )
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>S44 双向 · 2022 年亏损逐笔形态复盘</title>
<style>
body{{font:15px/1.55 system-ui,sans-serif;color:#17252f;background:#f2f6f8;margin:0}}
main{{max-width:1470px;margin:auto;padding:24px}} h1,h2{{line-height:1.2}}
section{{background:white;padding:18px;border:1px solid #d9e1e6;border-radius:12px;margin-bottom:16px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} td,th{{border-bottom:1px solid #d9e1e6;text-align:left;padding:8px}}
th{{background:#eaf1f5}} .loss{{color:#9b312b}} .scroll{{overflow:auto}} img{{width:100%;height:auto}}
details{{border-bottom:1px solid #d9e1e6;padding:9px}} summary{{cursor:pointer}} input{{padding:8px;width:18em}}
</style></head><body><main>
<h1>S44 双向 · 2022 年亏损逐笔形态复盘</h1>
<section>
<p>以 Stage025 双向 S44 为准，按开仓年筛选。逐笔核对了全部 206 笔亏损，其中多单 116 笔、空单 90 笔，累计亏损 584,515 元。同年 115 笔盈利交易合计 542,150 元。</p>
<p>每笔视觉检查用信号当时的实际交割合约，窗口为截至信号周的最近 14 个日历交易周。均线用可用的更早同合约周收盘预热。图中空单价格方向翻转，绿色表示顺拟开仓方向。浅黄色标示两根确认周 K，空白表示当周缺足够的同合约日线。</p>
<p>2022 年最常见且相对集中的特征是两根确认周 K 高低区间重叠较大。多空统一用两根周 K 的区间交集长度除以较短的一根振幅，重叠达到 50% 时记为命中。2022 年命中 {overlap.loss_selected} 笔亏损和 {overlap.win_selected} 笔盈利，命中组实际亏损率 {overlap_loss_rate:.1%}，其余为 {other_loss_rate:.1%}。命中组当年净亏 {-overlap.selected_net_pnl:,.0f} 元，其他年份合计净赚 {other_overlap_pnl:,.0f} 元。适合保留观察，当前没有跨期证据支持把它设为硬过滤。</p>
</section>
<section><h2>八条形态假设的账本核算</h2>
<p>净盈亏是该条件命中的原交易最终盈亏，正值表示直接剔除会丢掉该批交易的净盈利。跨年度仍按开仓年归属。2026 数据截至 11 月 3 日，样本只含已结束周期。缺历史独立计数。这里未重跑开平仓路径。</p>
<div class="scroll"><table><thead><tr><th>形态</th><th>2022 命中亏损／可判</th><th>2022 命中盈利／可判</th><th>缺数据</th><th>2022 命中净盈亏</th><th>2015–2021</th><th>2023–2026</th></tr></thead>
<tbody>{"".join(comparisons)}</tbody></table></div>
</section>
<section><h2>206 笔逐笔记录</h2>
<p>点击周期编号查看对应图组。MA 斜率按实际价格列示，方向过滤时对空头取反。前三周突破距离大于零表示顺方向突破。</p>
<label>搜索 <input id="search" placeholder="周期、合约或形态"></label> <span id="count">206 笔</span>
<div class="scroll"><table><thead><tr><th>周期</th><th>合约</th><th>方向</th><th>信号日</th><th>开仓 → 平仓</th><th>退出</th><th>净盈亏</th><th>逐笔视觉记录</th><th>两周区间重叠</th><th>前三周突破距离</th><th>MA5 / 10 / 20 斜率</th><th>量化命中</th></tr></thead>
<tbody id="review">{"".join(rows)}</tbody></table></div>
</section>
<section><h2>逐笔周 K 图册</h2>{"".join(atlas)}</section>
</main><script>
const query=document.getElementById('search');
const rows=[...document.querySelectorAll('#review tr')];
query.addEventListener('input',()=>{{
  const word=query.value.trim().toLowerCase();
  rows.forEach(row=>row.hidden=!row.textContent.toLowerCase().includes(word));
  document.getElementById('count').textContent=rows.filter(row=>!row.hidden).length+' 笔';
}});
document.querySelectorAll('#review a').forEach(link=>link.addEventListener('click',()=>{{
  document.querySelector(link.getAttribute('href')).open=true;
}}));
</script></body></html>"""
    (OUT / "index.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    render()
