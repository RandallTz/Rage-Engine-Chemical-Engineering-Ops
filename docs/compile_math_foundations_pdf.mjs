import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import katex from '../frontend/node_modules/katex/dist/katex.mjs';

const DOCS_DIR = path.resolve('docs');
const MD_PATH = path.resolve(DOCS_DIR, 'MATHEMATICAL_FOUNDATIONS.md');
const PDF_PATH = path.resolve(DOCS_DIR, 'MATHEMATICAL_FOUNDATIONS.pdf');
const TEMP_HTML_PATH = path.resolve(DOCS_DIR, '.temp_math_foundations_render.html');
const KATEX_CSS_PATH = path.resolve('frontend/node_modules/katex/dist/katex.min.css');

if (!fs.existsSync(MD_PATH)) {
  console.error('Error: Markdown file not found:', MD_PATH);
  process.exit(1);
}

const mdContent = fs.readFileSync(MD_PATH, 'utf-8');

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
  text = text.replace(/\$([^\$\n]+?)\$/g, (_, math) => safeKatex(math, false));
  text = text.replace(/`([^`]+?)`/g, (_, code) => `<code>${escapeHtml(code)}</code>`);
  text = text.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/\*([^*]+?)\*/g, '<em>$1</em>');
  text = text.replace(/\[([^\]]+?)\]\(([^)]+?)\)/g, '<a href="$2">$1</a>');
  return text;
}

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
      const cells = row.split('|').slice(1, -1).map(c => c.trim());
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

    if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
      inTable = true;
      tableBuf.push(line.trim());
      continue;
    } else if (inTable) {
      flushTable();
    }

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

    if (line.trim() === '---' || line.trim() === '***') {
      out.push('<hr />');
      continue;
    }

    if (line.trim().startsWith('>')) {
      out.push(`<blockquote>${formatInline(line.trim().slice(1).trim())}</blockquote>`);
      continue;
    }

    const ulMatch = line.match(/^(\s*)[-*]\s+(.*)$/);
    if (ulMatch) {
      const indent = ulMatch[1].length;
      out.push(`<li class="indent-${indent}">${formatInline(ulMatch[2])}</li>`);
      continue;
    }

    const olMatch = line.match(/^(\s*)([0-9]+)\.\s+(.*)$/);
    if (olMatch) {
      out.push(`<li class="ol-item"><strong>${olMatch[2]}.</strong> ${formatInline(olMatch[3])}</li>`);
      continue;
    }

    if (line.trim().length > 0) {
      out.push(`<p>${formatInline(line.trim())}</p>`);
    }
  }

  if (inTable) flushTable();
  return out.join('\n');
}

const htmlBody = mdToHtml(mdContent);

const fullHtml = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mathematical, Physical, and Algorithmic Foundations of the Simulation Engine</title>
  <style>
    ${fs.existsSync(KATEX_CSS_PATH) ? fs.readFileSync(KATEX_CSS_PATH, 'utf-8') : ''}
    
    @page {
      size: A4;
      margin: 20mm 18mm 22mm 18mm;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      font-size: 9.5pt;
      line-height: 1.55;
      color: #1e293b;
      background: #ffffff;
      margin: 0;
      padding: 0;
    }

    h1 {
      font-size: 18pt;
      font-weight: 800;
      color: #0f172a;
      border-bottom: 2.5px solid #2563eb;
      padding-bottom: 8px;
      margin-top: 18px;
      margin-bottom: 12px;
      letter-spacing: -0.4px;
    }

    h2 {
      font-size: 13.5pt;
      font-weight: 700;
      color: #1e3a8a;
      border-bottom: 1.5px solid #cbd5e1;
      padding-bottom: 5px;
      margin-top: 18px;
      margin-bottom: 10px;
    }

    h3 {
      font-size: 11pt;
      font-weight: 600;
      color: #0369a1;
      margin-top: 14px;
      margin-bottom: 6px;
    }

    h4 {
      font-size: 10pt;
      font-weight: 600;
      color: #334155;
      margin-top: 10px;
      margin-bottom: 4px;
    }

    p {
      margin-top: 0;
      margin-bottom: 8px;
      text-align: justify;
    }

    .display-math {
      margin: 10px 0;
      padding: 6px 12px;
      background: #f8fafc;
      border-left: 3px solid #3b82f6;
      border-radius: 3px;
      overflow-x: auto;
      text-align: center;
    }

    code {
      font-family: "JetBrains Mono", Consolas, "Courier New", monospace;
      font-size: 8.5pt;
      background-color: #f1f5f9;
      color: #0f172a;
      padding: 1.5px 4px;
      border-radius: 3px;
      border: 1px solid #e2e8f0;
    }

    pre {
      background-color: #0f172a;
      color: #f8fafc;
      padding: 10px 14px;
      border-radius: 5px;
      overflow-x: auto;
      font-size: 8pt;
      line-height: 1.45;
      margin: 10px 0;
    }

    pre code {
      background: transparent;
      color: inherit;
      border: none;
      padding: 0;
    }

    blockquote {
      margin: 10px 0;
      padding: 6px 14px;
      border-left: 3.5px solid #64748b;
      background-color: #f8fafc;
      color: #334155;
      font-style: italic;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 8.5pt;
      margin: 8px 0;
    }

    th, td {
      border: 1px solid #cbd5e1;
      padding: 6px 8px;
      text-align: left;
    }

    th {
      background-color: #f1f5f9;
      color: #0f172a;
      font-weight: 600;
    }

    tr:nth-child(even) td {
      background-color: #f8fafc;
    }

    li {
      margin-bottom: 3px;
      font-size: 9.5pt;
    }

    li.indent-2 { margin-left: 14px; }
    li.indent-4 { margin-left: 28px; }

    hr {
      border: 0;
      border-top: 1px solid #e2e8f0;
      margin: 16px 0;
    }

    .doc-header {
      font-size: 8pt;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      margin-bottom: 14px;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 4px;
      display: flex;
      justify-content: space-between;
    }
  </style>
</head>
<body>
  <div class="doc-header">
    <span>Simulation Engine · Rigorous Mathematical Specification</span>
    <span>Version 1.0.0 · Applied Mathematics Reference</span>
  </div>
  ${htmlBody}
</body>
</html>`;

fs.writeFileSync(TEMP_HTML_PATH, fullHtml, 'utf-8');

const STAGING_PDF_PATH = path.resolve(DOCS_DIR, '.temp_math_foundations_build.pdf');
const edgeCandidates = [
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe'
];
const edgePath = edgeCandidates.find(p => fs.existsSync(p));

if (!edgePath) {
  console.error('Error: msedge.exe not found on system.');
  process.exit(1);
}

console.log('Compiling vector PDF via headless Microsoft Edge...');
try {
  execSync(`"${edgePath}" --headless --disable-gpu --print-to-pdf-no-header --print-to-pdf="${STAGING_PDF_PATH}" "${TEMP_HTML_PATH}"`);
  
  let primarySuccess = false;
  try {
    fs.copyFileSync(STAGING_PDF_PATH, PDF_PATH);
    primarySuccess = true;
  } catch (copyErr) {
    if (copyErr.code === 'EBUSY' || copyErr.code === 'EPERM') {
      console.log(`Notice: Primary PDF is currently open in a viewer. Skipping direct overwrite of ${PDF_PATH}`);
    } else {
      throw copyErr;
    }
  }

  const latestPath = path.resolve(DOCS_DIR, 'MATHEMATICAL_FOUNDATIONS_LATEST.pdf');
  try {
    fs.copyFileSync(STAGING_PDF_PATH, latestPath);
  } catch (latestErr) {
    console.log(`Notice: Could not write to ${latestPath}: ${latestErr.message}`);
  }

  fs.unlinkSync(STAGING_PDF_PATH);

  const reportPath = primarySuccess ? PDF_PATH : latestPath;
  const stats = fs.statSync(reportPath);
  const pdfRaw = fs.readFileSync(reportPath, 'latin1');
  const pageMatches = pdfRaw.match(/\/Type\s*\/Page[^s]/g);
  const pageCount = pageMatches ? pageMatches.length : 'unknown';

  console.log(`✓ PDF successfully generated: ${reportPath}`);
  console.log(`✓ Total Pages: ${pageCount}`);
  console.log(`✓ Document size: ${(stats.size / 1024).toFixed(1)} KB`);
} catch (err) {
  console.error('Error compiling PDF with Edge:', err.message);
  process.exit(1);
} finally {
  if (fs.existsSync(TEMP_HTML_PATH)) {
    fs.unlinkSync(TEMP_HTML_PATH);
  }
  if (fs.existsSync(STAGING_PDF_PATH)) {
    fs.unlinkSync(STAGING_PDF_PATH);
  }
}
