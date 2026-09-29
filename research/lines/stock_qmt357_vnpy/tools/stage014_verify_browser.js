// Run with playwright-cli -s=stockrecap run-code --filename <this file>.
// Uses the already-open recap; never navigates to an external site.
async page => {
  const result = {};
  const assert = (ok, message) => { if (!ok) throw new Error(message); };
  const count = () => page.locator('#trade option').count();
  const chart = () => page.locator('#chart').evaluate(el => ({
    candles: el.data.filter(x => x.type === 'candlestick').map(x => x.name),
    first: [...el._fullLayout.xaxis.range], second: [...el._fullLayout.xaxis2.range],
    matches: el._fullLayout.xaxis2.matches
  }));
  await page.setViewportSize({width: 1680, height: 1400});
  await page.locator('#result').selectOption('all');
  await page.locator('#year').selectOption('');
  await page.locator('#product').selectOption('');
  result.all = await count();
  assert(result.all === 226, 'all closed trades');
  await page.locator('#result').selectOption('profit');
  result.profit = await count();
  assert(result.profit === 37, 'profit count');
  await page.locator('#next').click({timeout: 10000});
  result.next = await page.locator('#trade').inputValue();
  assert(result.next === '1', 'next navigation');
  await page.locator('#prev').click({timeout: 10000});
  result.previous = await page.locator('#trade').inputValue();
  assert(result.previous === '0', 'previous navigation');
  await page.locator('#result').selectOption('loss');
  result.loss = await count();
  assert(result.loss === 189, 'loss count');
  await page.locator('#result').selectOption('flat');
  result.flat = await count();
  assert(result.flat === 0 && (await page.locator('#metrics').innerText()).includes('没有符合'), 'empty result');
  await page.locator('#result').selectOption('all');
  await page.locator('#year').selectOption('2026');
  result.year2026 = await count();
  assert(result.year2026 > 0 && await page.locator('#trade option').evaluateAll(opts => opts.every(o => /2026-\d\d-\d\d→/.test(o.textContent))), 'entry year filter');
  await page.locator('#year').selectOption('');
  await page.locator('#product').selectOption('000001.SZSE');
  result.symbol000001 = await count();
  assert(result.symbol000001 > 0 && await page.locator('#trade option').evaluateAll(opts => opts.every(o => o.textContent.includes('000001.SZSE'))), 'stock filter');
  await page.locator('#product').selectOption('');
  await page.locator('input[data-period=intraday]').check();
  result.missingMinuteNote = await page.locator('#periodNote').innerText();
  assert((await chart()).candles.length === 2 && result.missingMinuteNote.includes('无15分钟'), 'no fabricated minute panel');
  await page.locator('input[data-period=intraday]').uncheck();
  for (const period of ['day10', 'monthly', 'weekly']) await page.locator(`input[data-period=${period}]`).check();
  result.fivePeriods = await page.locator('#chart').evaluate(el => ({
    candles: el.data.filter(x => x.type === 'candlestick').map(x => x.name),
    axes: [2, 3, 4, 5].map(i => el._fullLayout[`xaxis${i}`].matches)
  }));
  assert(result.fivePeriods.candles.length === 5 && result.fivePeriods.axes.every(x => x === 'x'), 'five linked periods');
  for (const period of ['day10', 'monthly', 'weekly']) await page.locator(`input[data-period=${period}]`).uncheck();
  result.beforeZoom = await chart();
  const box = await page.locator('#chart .nsewdrag').first().boundingBox();
  assert(box && box.width > 100, 'visible drag surface');
  await page.mouse.move(box.x + box.width * .3, box.y + box.height * .3);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * .7, box.y + box.height * .7, {steps: 12});
  await page.mouse.up();
  await page.waitForFunction(before => JSON.stringify(document.getElementById('chart')._fullLayout.xaxis.range) !== JSON.stringify(before), result.beforeZoom.first, {timeout: 10000});
  result.afterZoom = await chart();
  assert(JSON.stringify(result.afterZoom.first) === JSON.stringify(result.afterZoom.second), 'actual drag linked zoom');
  await page.getByRole('button', {name: 'Reset axes', exact: true}).click({timeout: 10000});
  result.defaultPeriods = await page.locator('input[data-period]:checked').evaluateAll(els => els.map(x => x.dataset.period));
  assert(JSON.stringify(result.defaultPeriods) === '["day30","daily"]', 'defaults restored');
  result.status = 'PASS';
  return result;
}
