// Additive daily-indicator layer. The canonical renderer still owns every chart,
// candle, axis, selector, execution marker and zoom interaction.
function stockBollingerTraces(record, option, panelIndex, enabled) {
  if (option.id !== 'daily') return [];
  const daily = record.daily;
  const signal = record.meta.entry_signal;
  const axes = {
    xaxis: panelIndex === 0 ? 'x' : `x${panelIndex + 1}`,
    yaxis: panelIndex === 0 ? 'y' : `y${panelIndex * 2 + 1}`
  };
  const traces = [];
  if (enabled) {
    const common = {type: 'scatter', mode: 'lines', x: daily.x,
      customdata: daily.date, connectgaps: false, legendgroup: 'stock-bollinger', ...axes};
    traces.push({...common, y: daily.bb_lower, name: 'BB20 下轨',
      line: {color: '#c084b4', width: 1.2}, showlegend: false,
      hovertemplate: '%{customdata}<br>布林下轨=%{y:.3f}<extra></extra>'});
    traces.push({...common, y: daily.bb_upper, name: 'BB20 上轨',
      line: {color: '#c084b4', width: 1.2}, fill: 'tonexty', fillcolor: 'rgba(219,39,119,0.06)',
      showlegend: false, hovertemplate: '%{customdata}<br>布林上轨=%{y:.3f}<extra></extra>'});
    traces.push({...common, y: daily.bb_middle, name: 'BB20 中轨 / ±2σ通道',
      line: {color: '#db2777', width: 2.6}, showlegend: true,
      hovertemplate: '%{customdata}<br>布林中轨=%{y:.3f}<extra></extra>'});
  }
  traces.push({type: 'scatter', mode: 'markers', name: '信号日收盘',
    x: [signal.x], y: [signal.raw_close], ...axes,
    marker: {symbol: 'diamond', size: 12, color: '#0891b2', line: {color: '#fff', width: 1}},
    customdata: [signal.date], showlegend: true,
    hovertemplate: '%{customdata}<br>信号日收盘=%{y:.3f}<br>不是实际买入价<extra></extra>'});
  return traces;
}

function installStockBollinger() {
  const picker = document.getElementById('periodPicker');
  const toggleLabel = document.createElement('label');
  toggleLabel.className = 'period-chip stock-bb-toggle';
  toggleLabel.innerHTML = '<input id="bollingerToggle" type="checkbox" checked><span>布林 BB(20,2) · 日K</span>';
  picker.appendChild(toggleLabel);
  const toggle = document.getElementById('bollingerToggle');
  const box = document.getElementById('stockSignalInfo');
  const originalPanelTraces = panelTraces;
  panelTraces = function(record, option, panelIndex) {
    return originalPanelTraces(record, option, panelIndex).concat(
      stockBollingerTraces(record, option, panelIndex, toggle.checked));
  };
  const originalRender = render;
  render = function() {
    originalRender();
    box.replaceChildren();
    if (!filtered.length) return;
    const meta = filtered[active].meta;
    const signal = meta.entry_signal;
    const dates = document.createElement('strong');
    dates.textContent = `信号 ${signal.date} 收盘 → 买入 ${meta.entry_date} 开盘`;
    box.appendChild(dates);
    for (const [key, label] of [['bollinger', '布林中轨反转'], ['rsi', 'RSI'], ['macd', 'MACD']]) {
      const badge = document.createElement('span');
      badge.className = `stock-condition ${signal[key] ? 'hit' : 'miss'}`;
      badge.dataset.condition = key;
      badge.textContent = `${label} ${signal[key] ? '✓ 已触发' : '— 未触发'}`;
      box.appendChild(badge);
    }
    const count = document.createElement('span');
    count.textContent = `${signal.condition_count}/3 条件满足（至少2项）`;
    box.appendChild(count);
    const note = document.createElement('div');
    note.className = 'stock-signal-note';
    const dailyVisible = selectedPeriods.has('daily');
    note.textContent = (dailyVisible
      ? '青色菱形=信号日收盘；蓝色三角=次日实际买入。布林通道使用各日当时的历史复权因子，换算到该日原价尺度；普通MA仍为原价展示。'
      : '当前未选日K：日线布林与信号菱形不绘制，勾选日K即可查看。')
      + (signal.bollinger ? ' 本笔布林条件成立。' : ' 本笔布林条件未成立，实际由 RSI + MACD 触发。');
    box.appendChild(note);
  };
  toggle.addEventListener('change', () => render());
  render();
}
