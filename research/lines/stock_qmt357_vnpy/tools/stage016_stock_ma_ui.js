// Presentation only: retain trace order and data so other overlays stay stable.
function stockMovingAverageVisibility(traces, enabled) {
  const groups = new Set(['ma5', 'ma10', 'ma20', 'ma40']);
  return traces.map(trace => groups.has(trace.legendgroup)
    && trace.type === 'scatter' && trace.mode === 'lines'
    ? {...trace, visible: enabled} : trace);
}

function installStockMovingAverages() {
  const picker = document.getElementById('periodPicker');
  const label = document.createElement('label');
  label.className = 'period-chip';
  label.title = '统一显示或隐藏所有周期的 MA5/10/20/40，不影响布林通道';
  const toggle = document.createElement('input');
  toggle.type = 'checkbox';
  toggle.id = 'movingAverageToggle';
  toggle.checked = true;
  const text = document.createElement('span');
  text.textContent = '显示均线 MA5/10/20/40';
  label.append(toggle, text);
  picker.insertBefore(label, document.getElementById('bollingerToggle').parentElement);
  const originalPanelTraces = panelTraces;
  panelTraces = function(record, option, panelIndex) {
    return stockMovingAverageVisibility(originalPanelTraces(record, option, panelIndex), toggle.checked);
  };
  toggle.addEventListener('change', () => render());
  render();
}
