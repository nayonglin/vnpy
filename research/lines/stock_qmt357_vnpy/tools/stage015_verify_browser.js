// Verification on the already-open stock-only recap, with real user interactions.
async page => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const result = {};
  await page.setViewportSize({width: 1680, height: 1500});
  const state = () => page.locator('#chart').evaluate(el => ({
    bands: el.data.filter(t => t.name.startsWith('BB20')).map(t => ({name: t.name, xaxis: t.xaxis, yaxis: t.yaxis})),
    signal: el.data.find(t => t.name === '信号日收盘'),
    executions: el.data.find(t => t.name === '同源成交价格'),
    candles: el.data.filter(t => t.type === 'candlestick').map(t => t.name)
  }));
  await page.locator('#result').selectOption('all');
  await page.locator('#year').selectOption('');
  await page.locator('#product').selectOption('');
  result.count = await page.locator('#trade option').count();
  assert(result.count === 226, 'all episodes available');
  assert(await page.locator('#bollingerToggle').isChecked(), 'Bollinger on by default');
  result.initial = await state();
  assert(result.initial.bands.length === 3 && result.initial.bands.every(t => t.xaxis === 'x2' && t.yaxis === 'y3'), 'BB only on daily panel');
  assert(result.initial.signal.x[0] < result.initial.executions.x[0], 'signal precedes execution');
  await page.locator('#bollingerToggle').uncheck();
  const hidden = await state();
  assert(hidden.bands.length === 0 && hidden.signal.name === '信号日收盘', 'toggle hides only bands');
  assert(JSON.stringify(hidden.executions.y) === JSON.stringify(result.initial.executions.y), 'toggle preserves fills');
  await page.locator('#next').click({timeout: 10000});
  assert((await state()).bands.length === 0, 'toggle persists when changing trade');
  await page.locator('#bollingerToggle').check();
  await page.locator('#product').selectOption('600183.SSE');
  const falseValue = await page.locator('#trade option').evaluateAll(opts => opts.find(o => o.textContent.includes('2020-01-03→2020-01-09')).value);
  await page.locator('#trade').selectOption(falseValue);
  result.falseSignal = await page.locator('#stockSignalInfo').innerText();
  assert(result.falseSignal.includes('信号 2020-01-02 收盘 → 买入 2020-01-03 开盘'), 'signal date vs fill date');
  assert(result.falseSignal.includes('布林中轨反转 — 未触发') && result.falseSignal.includes('RSI ✓ 已触发') && result.falseSignal.includes('MACD ✓ 已触发'), 'actual false/true flags');
  const falseChart = await state();
  assert(falseChart.signal.y[0] === 22.74 && falseChart.executions.y[0] === 22.81, 'raw signal close vs slipped actual entry');
  // Select a source-verified BB=true record through the existing trade selector.
  await page.locator('#product').selectOption('');
  const trueIndex = await page.evaluate(() => String(filtered.findIndex(r => r.meta.entry_signal.bollinger)));
  assert(trueIndex !== '-1', 'BB-triggered trade exists');
  await page.locator('#trade').selectOption(trueIndex);
  result.trueSignal = await page.locator('#stockSignalInfo').innerText();
  assert(result.trueSignal.includes('布林中轨反转 ✓ 已触发'), 'true Bollinger flag rendered');
  await page.locator('input[data-period=daily]').uncheck();
  result.dailyHidden = await state();
  assert(result.dailyHidden.bands.length === 0 && !result.dailyHidden.signal, 'non-daily panel has no daily-only indicators');
  assert((await page.locator('#stockSignalInfo').innerText()).includes('当前未选日K'), 'daily-only disclosure');
  await page.locator('input[data-period=daily]').check();
  await page.locator('#result').selectOption('flat');
  assert((await page.locator('#stockSignalInfo').innerText()) === '', 'empty filter does not leave stale signal');
  await page.locator('#result').selectOption('all');
  result.restoredBands = (await state()).bands.length;
  assert(result.restoredBands === 3, 'bands restored after empty filter');
  result.status = 'PASS';
  return result;
}
