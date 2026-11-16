import assert from 'node:assert/strict';
import { lanzarNavegador, urlBase } from './navegador.mjs';

// Browser check of the current product pages: home, the model library (/models), blank model creation and the
// Checklist, at desktop and phone width, with no runtime page errors. It replaces the check of the retired
// /simulaciones flowsheet workbench, deleted with Process Simulation (ad8c90a). Pages are awaited by their own
// elements, not by network idle: a page that keeps a request open never reaches network idle (CI run 43843155286
// timed out on page.goto with waitUntil networkidle0). No physical validation.
// Usage: node verificar_redesign.mjs [base URL]   (default URL_PRUEBAS, then http://localhost:3000)
const BASE = urlBase().replace(/\/$/, '');
const TIMEOUT = 120000;
const browser = await lanzarNavegador();
try {
  const page = await browser.newPage();
  page.setDefaultTimeout(TIMEOUT);
  await page.setViewport({ width: 1440, height: 1000 });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const open = async (path, selector) => {
    await page.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: TIMEOUT });
    await page.waitForSelector(selector);
  };
  const text = () => page.evaluate(() => document.body.innerText);

  await open('/', 'h1#hero-title');
  assert.deepEqual(await page.$$eval('a[href="/models"], a[href="/checklist"]', as => [...new Set(as.map(a => a.getAttribute('href')))].sort()),
    ['/checklist', '/models']);
  await page.click('.minimal-methods summary');
  assert((await text()).includes('Model, Transform, Solve and Results'));
  await page.screenshot({ path: 'preview-home.png', fullPage: true });

  await open('/models', 'h1');
  assert.equal(await page.$eval('h1', h => h.textContent.trim()), 'Your models');
  await page.waitForFunction(() => !document.querySelector('[aria-label="Loading models"]'));
  const create = await page.$$('button');
  let clicked = false;
  for (const button of create) {
    if ((await button.evaluate(b => b.textContent.trim())).startsWith('Create model')) { await button.click(); clicked = true; break; }
  }
  assert(clicked, 'Missing button: Create model');
  await page.waitForSelector('#new-model-name');
  await page.type('#new-model-name', 'Interface check');
  await page.$eval('#new-model-name', input => input.form.requestSubmit());
  await page.waitForFunction(() => /^\/models\/[^/]+/.test(location.pathname));
  // The model workspace opens on Model and shows the name in its editable name field.
  await page.waitForFunction(() => document.querySelector('h1')?.textContent.trim() === 'Model'
    && [...document.querySelectorAll('input')].some(i => i.value === 'Interface check'));
  await page.screenshot({ path: 'preview-model.png', fullPage: true });

  await open('/checklist', 'h1');
  assert.equal(await page.$eval('h1', h => h.textContent.trim()), 'Engine capabilities');

  await page.setViewport({ width: 390, height: 844 });
  for (const path of ['/', '/models']) {
    await open(path, 'h1');
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `horizontal scroll at 390 px on ${path}`);
  }
  await page.screenshot({ path: 'preview-mobile.png', fullPage: true });
  assert.deepEqual(errors, []);
  console.log('OK: home, model library, blank model creation, Checklist, phone layout and runtime errors.');
} finally { await browser.close(); }
