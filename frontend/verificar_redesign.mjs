import assert from 'node:assert/strict';
import { lanzarNavegador } from './navegador.mjs';

// UI regression check with synthetic HTTP responses; no physical validation.
const browser = await lanzarNavegador();
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1000 });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.setRequestInterception(true);
  page.on('request', request => {
    const url = request.url();
    if (request.method() === 'OPTIONS') {
      request.respond({ status: 204, headers: { 'access-control-allow-origin': '*', 'access-control-allow-methods': 'GET, POST, OPTIONS', 'access-control-allow-headers': 'content-type' } });
    } else if (url.includes('/diagrama/resolver')) {
      const data = JSON.parse(request.postData());
      request.respond({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: JSON.stringify({ pool: { ...data.valores, 'col1.N': 12 }, completo: true, diagnostico: [], incognitas_restantes: [], inconsistencias: [], diagramas: {}, masas_molares_mezcla: {} }) });
    } else if (url.includes('/diagrama/grados-libertad')) {
      request.respond({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: JSON.stringify({ grados_de_libertad: 0, ecuaciones: 1, incognitas: 1, redundancias: [] }) });
    } else if (/\/unidades(?:\?|$)/.test(url)) {
      request.respond({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: JSON.stringify({ magnitudes: {}, variables: {} }) });
    } else if (/\/componentes\/buscar|\/modelos-termodinamicos/.test(url)) {
      request.respond({ status: 503, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: '{}' });
    } else { request.continue(); }
  });
  async function clickText(text) {
    const clicked = await page.evaluate(text => {
      const el = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === text);
      el?.click(); return !!el;
    }, text);
    assert(clicked, `Missing button: ${text}`);
  }
  await page.goto('http://localhost:3000', { waitUntil: 'networkidle0', timeout: 120000 });
  assert(await page.$('h1'));
  await page.click('.minimal-methods summary');
  assert((await page.evaluate(() => document.body.innerText)).includes('MESH'));
  await page.click('.minimal-methods summary');
  await page.screenshot({ path: 'preview-home.png', fullPage: true });
  await page.goto('http://localhost:3000/simulaciones', { waitUntil: 'networkidle0' });
  await page.type('input[aria-label="Nombre de la nueva simulación"]', 'Verificación de interfaz');
  await clickText('Crear y abrir');
  await page.waitForSelector('.react-flow__node');
  await page.click('.equipment-library summary');
  await page.type('input[aria-label="Buscar equipo"]', 'bomba');
  assert.equal(await page.$$eval('.equipment-list button', bs => bs.length), 1);
  await clickText('+ Bomba');
  assert.equal(await page.$eval('.equipment-library', e => e.open), false);
  await clickText('Resolver');
  await page.waitForFunction(() => document.body.innerText.includes('Resuelto por completo'));
  await clickText('Editar');
  await page.click('.react-flow__node-corriente');
  await page.waitForSelector('.properties-panel input[id]');
  await page.$eval('.properties-panel input[id]', input => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(input, '123'); input.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.waitForFunction(() => document.body.innerText.includes('Resultados pendientes de actualizar'));
  await clickText('Reporte');
  assert(await page.$('fieldset[disabled]'));
  await clickText('Editar');
  await page.screenshot({ path: 'preview-workbench.png', fullPage: true });
  await clickText('Resolver');
  await page.waitForFunction(() => !document.body.innerText.includes('Resultados pendientes de actualizar'));
  await clickText('Reporte');
  assert.equal(await page.$('fieldset[disabled]'), null);
  await page.screenshot({ path: 'preview-report.png', fullPage: true });
  await page.setViewport({ width: 390, height: 844 });
  await page.goto('http://localhost:3000', { waitUntil: 'networkidle0' });
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({ path: 'preview-mobile.png', fullPage: true });
  assert.deepEqual(errors, []);
  console.log('OK: navigation, templates, equipment search, result freshness, export protection, mobile layout and runtime.');
} finally { await browser.close(); }
