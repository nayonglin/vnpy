// Run through playwright-cli against the already-open Stage016 stock recap.
async page => {
  const assert = (ok, message) => { if (!ok) throw new Error(message); };
  const state = () => page.locator('#chart').evaluate(el => {
    // Plotly omits legendgroup from hidden _fullData entries; retain input indices.
    const ma = el.data.flatMap((t, i) => /^ma(5|10|20|40)$/.test(t.legendgroup) ? [el._fullData[i]] : []);
    return {ma: ma.length, visibleMA: ma.filter(t => t.visible === true).length,
      bands: el._fullData.filter(t => t.name.startsWith('BB20') && t.visible === true).length,
      signal: el.data.find(t => t.name === '信号日收盘'),
      executions: el.data.find(t => t.name === '同源成交价格'),
      first: [...el._fullLayout.xaxis.range], second: [...el._fullLayout.xaxis2.range]};
  });
  await page.setViewportSize({width: 1680, height: 1400});
  const toggle = page.locator('#movingAverageToggle');
  assert(await toggle.isChecked(), 'MA default enabled');
  const initial = await state();
  assert(initial.ma === 8 && initial.visibleMA === 8 && initial.bands === 3, 'default two panels and overlays');
  const box = await page.locator('#chart .nsewdrag').first().boundingBox();
  assert(box && box.width > 100, 'visible drag surface');
  await page.mouse.move(box.x + box.width * .3, box.y + box.height * .3);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * .7, box.y + box.height * .7, {steps: 12});
  await page.mouse.up();
  await page.waitForFunction(before => JSON.stringify(document.getElementById('chart')._fullLayout.xaxis.range) !== JSON.stringify(before), initial.first, {timeout: 10000});
  const zoomed = await state();
  await toggle.uncheck();
  const hidden = await state();
  assert(hidden.visibleMA === 0 && hidden.ma === 8 && hidden.bands === 3, 'hide only MA, preserve trace order');
  assert(JSON.stringify(hidden.first) === JSON.stringify(zoomed.first) && JSON.stringify(hidden.first) === JSON.stringify(hidden.second), 'toggle retains linked zoom');
  assert(JSON.stringify(hidden.signal) === JSON.stringify(initial.signal) && JSON.stringify(hidden.executions) === JSON.stringify(initial.executions), 'signal and fills unchanged');
  assert(await page.locator('#chart .legendtext').filter({hasText: / MA(5|10|20|40)$/}).count() === 0, 'hidden MA has no stale legend');
  await toggle.check();
  assert((await state()).visibleMA === 8, 'restore all MA');
  await page.locator('#chart g.traces').filter({hasText: /^日K MA5$/}).locator('.legendtoggle').click({timeout: 10000});
  await page.waitForFunction(() => {
    const ma = document.getElementById('chart')._fullData.filter(t => t.legendgroup === 'ma5');
    return ma.length === 2 && ma.every(t => t.visible === 'legendonly');
  }, null, {timeout: 10000});
  await toggle.uncheck();
  await toggle.check();
  assert((await state()).visibleMA === 8, 'global toggle restores individually hidden legend group');
  await toggle.uncheck();
  await page.locator('#next').click();
  assert(!(await toggle.isChecked()) && (await state()).visibleMA === 0, 'next trade keeps off');
  await page.locator('#result').selectOption('loss');
  assert((await state()).visibleMA === 0, 'filter keeps off');
  for (const period of ['day10', 'monthly', 'weekly']) await page.locator(`input[data-period=${period}]`).check();
  const fiveOff = await state();
  assert(fiveOff.ma === 20 && fiveOff.visibleMA === 0 && fiveOff.bands === 3, 'five periods all MA off');
  await page.locator('#bollingerToggle').uncheck();
  assert((await state()).bands === 0 && (await state()).visibleMA === 0, 'both controls independently off');
  await toggle.check();
  assert((await state()).visibleMA === 20 && (await state()).bands === 0, 'MA on does not enable BB');
  await page.locator('#bollingerToggle').check();
  for (const period of ['day10', 'monthly', 'weekly']) await page.locator(`input[data-period=${period}]`).uncheck();
  await page.locator('#result').selectOption('flat');
  await toggle.uncheck();
  await page.locator('#result').selectOption('all');
  assert((await state()).visibleMA === 0, 'empty filter keeps off when data returns');
  await toggle.check();
  await page.getByRole('button', {name: 'Reset axes', exact: true}).click();
  await page.mouse.move(10, 10);
  return {status: 'PASS', episodes: await page.locator('#trade option').count(),
    initialVisibleMA: initial.visibleMA, fivePeriodHiddenMA: fiveOff.ma,
    restoredVisibleMA: (await state()).visibleMA, zoomPreserved: true, legendToggleRestored: true,
    independentBollinger: true, emptyFilterPreserved: true};
}
