import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import katex from 'katex';

const SCRIPT_DIR = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([a-zA-Z]:)/, '$1'));
const MD_PATH = fs.existsSync(path.resolve(SCRIPT_DIR, 'ARQUITECTURA_INTEGRACION_MULTIFISICA.md'))
  ? path.resolve(SCRIPT_DIR, 'ARQUITECTURA_INTEGRACION_MULTIFISICA.md')
  : path.resolve('ARQUITECTURA_INTEGRACION_MULTIFISICA.md');
const PDF_PATH = path.resolve(SCRIPT_DIR, 'ARQUITECTURA_INTEGRACION_MULTIFISICA.pdf');
const TEMP_HTML_PATH = path.resolve(SCRIPT_DIR, '.temp_articulo_render.html');
const KATEX_CSS_PATH = fs.existsSync(path.resolve(SCRIPT_DIR, 'node_modules/katex/dist/katex.min.css'))
  ? path.resolve(SCRIPT_DIR, 'node_modules/katex/dist/katex.min.css')
  : path.resolve('node_modules/katex/dist/katex.min.css');

if (!fs.existsSync(MD_PATH)) {
  console.error('Error: No se encuentra el archivo Markdown:', MD_PATH);
  process.exit(1);
}

const mdContent = fs.readFileSync(MD_PATH, 'utf-8');

// Renderizador KaTeX seguro
function safeKatex(tex, displayMode = false) {
  try {
    return katex.renderToString(tex.trim(), {
      displayMode,
      throwOnError: false,
      output: 'html'
    });
  } catch (err) {
    return `<code class="math-error">${escapeHtml(tex)}</code>`;
  }
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function formatInline(text) {
  // Primero procesar fórmulas inline $...$
  text = text.replace(/\$([^\$\n]+?)\$/g, (_, math) => {
    return safeKatex(math, false);
  });

  // Código inline `...`
  text = text.replace(/`([^`]+?)`/g, (_, code) => {
    return `<code>${escapeHtml(code)}</code>`;
  });

  // Negrita **...**
  text = text.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>');

  // Cursiva *...*
  text = text.replace(/\*([^*]+?)\*/g, '<em>$1</em>');

  // Enlaces [texto](url)
  text = text.replace(/\[([^\]]+?)\]\(([^)]+?)\)/g, '<a href="$2">$1</a>');

  return text;
}

// Convertidor Markdown a HTML
function mdToHtml(md) {
  const lines = md.split(/\r?\n/);
  const out = [];
  let inCode = false;
  let codeLang = '';
  let codeBuf = [];
  let inTable = false;
  let tableBuf = [];

  function flushTable() {
    if (!inTable || tableBuf.length === 0) return;
    let html = '<div class="table-container"><table>\n';
    let isHeader = true;
    for (const row of tableBuf) {
      if (row.trim().match(/^\|(?:\s*:?-+:?\s*\|)+$/)) {
        isHeader = false;
        continue;
      }
      const cells = row
        .split('|')
        .slice(1, -1)
        .map(c => c.trim());
      
      html += '  <tr>\n';
      for (const c of cells) {
        const tag = isHeader ? 'th' : 'td';
        html += `    <${tag}>${formatInline(c)}</${tag}>\n`;
      }
      html += '  </tr>\n';
    }
    html += '</table></div>\n';
    out.push(html);
    tableBuf = [];
    inTable = false;
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Manejo de bloques de código
    if (line.trim().startsWith('```')) {
      if (inTable) flushTable();
      if (inCode) {
        out.push(`<pre><code class="language-${codeLang}">${escapeHtml(codeBuf.join('\n'))}</code></pre>`);
        codeBuf = [];
        inCode = false;
      } else {
        inCode = true;
        codeLang = line.trim().slice(3).trim();
      }
      continue;
    }
    if (inCode) {
      codeBuf.push(line);
      continue;
    }

    // Manejo de fórmulas en bloque $$...$$
    if (line.trim().startsWith('$$')) {
      if (inTable) flushTable();
      let mathBuf = [line.trim().slice(2)];
      if (line.trim().endsWith('$$') && line.trim().length > 2) {
        const formula = line.trim().slice(2, -2);
        out.push(`<div class="display-math">${safeKatex(formula, true)}</div>`);
        continue;
      }
      i++;
      while (i < lines.length && !lines[i].trim().endsWith('$$')) {
        mathBuf.push(lines[i]);
        i++;
      }
      if (i < lines.length) {
        mathBuf.push(lines[i].trim().replace(/\$\$$/, ''));
      }
      out.push(`<div class="display-math">${safeKatex(mathBuf.join('\n'), true)}</div>`);
      continue;
    }

    // Tablas Markdown
    if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
      inTable = true;
      tableBuf.push(line.trim());
      continue;
    } else if (inTable) {
      flushTable();
    }

    // Encabezados
    const h4 = line.match(/^####\s+(.*)$/);
    if (h4) {
      out.push(`<h4>${formatInline(h4[1])}</h4>`);
      continue;
    }
    const h3 = line.match(/^###\s+(.*)$/);
    if (h3) {
      out.push(`<h3>${formatInline(h3[1])}</h3>`);
      continue;
    }
    const h2 = line.match(/^##\s+(.*)$/);
    if (h2) {
      out.push(`<h2>${formatInline(h2[1])}</h2>`);
      continue;
    }
    const h1 = line.match(/^#\s+(.*)$/);
    if (h1) {
      out.push(`<h1>${formatInline(h1[1])}</h1>`);
      continue;
    }

    // Regla horizontal
    if (line.trim() === '---' || line.trim() === '***') {
      out.push('<hr />');
      continue;
    }

    // Blockquotes
    if (line.trim().startsWith('>')) {
      const bqText = line.trim().slice(1).trim();
      out.push(`<blockquote>${formatInline(bqText)}</blockquote>`);
      continue;
    }

    // Listas no ordenadas
    const ulMatch = line.match(/^(\s*)[-*]\s+(.*)$/);
    if (ulMatch) {
      const indent = ulMatch[1].length;
      out.push(`<li class="indent-${indent}">${formatInline(ulMatch[2])}</li>`);
      continue;
    }

    // Listas ordenadas
    const olMatch = line.match(/^(\s*)([0-9]+)\.\s+(.*)$/);
    if (olMatch) {
      out.push(`<li class="ol-item"><strong>${olMatch[2]}.</strong> ${formatInline(olMatch[3])}</li>`);
      continue;
    }

    // Párrafos normales
    if (line.trim().length > 0) {
      out.push(`<p>${formatInline(line.trim())}</p>`);
    }
  }

  if (inTable) flushTable();

  return out.join('\n');
}

const htmlBody = mdToHtml(mdContent);

const fullHtml = `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Arquitectura Técnica: Integración del Módulo de Adimensionalización en el Motor de Multifísica</title>
  <style>
    ${fs.existsSync(KATEX_CSS_PATH) ? fs.readFileSync(KATEX_CSS_PATH, 'utf-8') : ''}
    
    @page {
      size: A4;
      margin: 20mm 16mm 22mm 16mm;
      @bottom-right {
        content: counter(page);
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 8pt;
        color: #64748b;
      }
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      font-size: 10pt;
      line-height: 1.55;
      color: #1e293b;
      background: #ffffff;
      margin: 0;
      padding: 0;
    }

    h1 {
      font-size: 19pt;
      font-weight: 800;
      color: #0f172a;
      border-bottom: 2.5px solid #2563eb;
      padding-bottom: 8px;
      margin-top: 0;
      margin-bottom: 14px;
      line-height: 1.25;
    }

    h2 {
      font-size: 14pt;
      font-weight: 700;
      color: #1e3a8a;
      border-bottom: 1px solid #cbd5e1;
      padding-bottom: 5px;
      margin-top: 24px;
      margin-bottom: 10px;
      break-after: avoid;
    }

    h3 {
      font-size: 11.5pt;
      font-weight: 600;
      color: #0369a1;
      margin-top: 18px;
      margin-bottom: 6px;
      break-after: avoid;
    }

    h4 {
      font-size: 10.5pt;
      font-weight: 600;
      color: #334155;
      margin-top: 14px;
      margin-bottom: 4px;
      break-after: avoid;
    }

    p {
      margin-top: 0;
      margin-bottom: 8px;
      text-align: justify;
    }

    blockquote {
      margin: 10px 0;
      padding: 8px 14px;
      background-color: #f1f5f9;
      border-left: 4px solid #3b82f6;
      border-radius: 4px;
      color: #334155;
      font-size: 9pt;
      line-height: 1.45;
    }

    blockquote p {
      margin: 2px 0;
    }

    pre {
      background-color: #0f172a;
      color: #e2e8f0;
      padding: 10px 12px;
      border-radius: 6px;
      font-family: Consolas, "Courier New", monospace;
      font-size: 8pt;
      line-height: 1.4;
      overflow-x: auto;
      margin: 10px 0;
      border: 1px solid #334155;
      break-inside: avoid;
    }

    code {
      font-family: Consolas, "Courier New", monospace;
      font-size: 8.5pt;
      background: #f1f5f9;
      color: #0f172a;
      padding: 1px 4px;
      border-radius: 3px;
      border: 1px solid #e2e8f0;
    }

    pre code {
      background: transparent;
      color: inherit;
      padding: 0;
      border: none;
    }

    .display-math {
      margin: 12px 0;
      padding: 8px 0;
      text-align: center;
      break-inside: avoid;
      overflow-x: auto;
    }

    .table-container {
      margin: 12px 0;
      break-inside: avoid;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 8.5pt;
      margin: 6px 0;
    }

    th, td {
      border: 1px solid #cbd5e1;
      padding: 6px 8px;
      text-align: left;
    }

    th {
      background-color: #e2e8f0;
      color: #0f172a;
      font-weight: 600;
    }

    tr:nth-child(even) td {
      background-color: #f8fafc;
    }

    li {
      margin-bottom: 4px;
      font-size: 9.5pt;
    }

    li.indent-2 { margin-left: 14px; }
    li.indent-4 { margin-left: 28px; }

    hr {
      border: 0;
      border-top: 1px solid #e2e8f0;
      margin: 18px 0;
    }

    .watermark-header {
      font-size: 7.5pt;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      margin-bottom: 12px;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 4px;
      display: flex;
      justify-content: space-between;
    }
  </style>
</head>
<body>
  <div class="watermark-header">
    <span>Plataforma Multifísica · Pre-Acondicionamiento Canónico</span>
    <span>Documento Técnico de Integración</span>
  </div>
  ${htmlBody}
</body>
</html>`;

fs.writeFileSync(TEMP_HTML_PATH, fullHtml, 'utf-8');

const edgePath = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
console.log('Compilando PDF vectorial vía Microsoft Edge Headless...');
try {
  execSync(`"${edgePath}" --headless --disable-gpu --print-to-pdf-no-header --print-to-pdf="${PDF_PATH}" "${TEMP_HTML_PATH}"`);
  const stats = fs.statSync(PDF_PATH);
  console.log(`✓ PDF generado exitosamente: ${PDF_PATH}`);
  console.log(`✓ Tamaño del documento: ${(stats.size / 1024).toFixed(1)} KB`);
} catch (err) {
  console.error('Error al compilar el PDF con Edge:', err.message);
  process.exit(1);
} finally {
  if (fs.existsSync(TEMP_HTML_PATH)) {
    fs.unlinkSync(TEMP_HTML_PATH);
  }
}
