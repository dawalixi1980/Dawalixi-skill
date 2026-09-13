#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const SKILL_DIR = path.resolve(__dirname, '..');

function ensureDeps() {
  const mods = ['mathjax-full', '@resvg/resvg-js'];
  const missing = mods.filter((m) => {
    try {
      require.resolve(m);
      return false;
    } catch (e) {
      return true;
    }
  });
  if (missing.length) {
    process.stderr.write(`Installing math-render deps (${missing.join(', ')}) ...\n`);
    execSync('npm install --no-audit --no-fund --loglevel=error', {
      cwd: SKILL_DIR,
      stdio: 'inherit',
    });
  }
}

function parseArgs(argv) {
  const opts = {
    scale: 3,
    pad: 12,
    color: '#111111',
    bg: 'white',
    display: true,
    out: null,
    name: null,
    latex: '',
  };
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '-o' || a === '--output') opts.out = argv[++i];
    else if (a === '--name') opts.name = argv[++i];
    else if (a === '--color') opts.color = argv[++i];
    else if (a === '--bg') opts.bg = argv[++i];
    else if (a === '--scale') opts.scale = Number(argv[++i]);
    else if (a === '--pad') opts.pad = Number(argv[++i]);
    else if (a === '--inline') opts.display = false;
    else if (a === '-h' || a === '--help') opts.help = true;
    else rest.push(a);
  }
  opts.latex = rest.join(' ').trim();
  return opts;
}

function usage() {
  process.stdout.write(
    [
      'Usage: node render_formula.js "<latex>" [-o out.png] [options]',
      '',
      'Options:',
      '  -o, --output <path>   Output PNG path (default: ./math-images/formula-<ts>.png)',
      '  --name <name>         Filename stem when -o not given',
      '  --color <hex>         Formula color (default #111111)',
      '  --bg <white|transparent|#hex>  Background (default white)',
      '  --scale <n>           Pixel zoom factor (default 3)',
      '  --pad <px>            Padding around formula (default 18)',
      '  --inline              Render in inline (text) style instead of display style',
      '',
      'Example: node render_formula.js "\\int_0^1 x^2\\,dx = \\frac{1}{3}"',
    ].join('\n') + '\n'
  );
}

function defaultOut(name) {
  const dir = path.join(process.cwd(), 'math-images');
  fs.mkdirSync(dir, { recursive: true });
  const ts = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
  const stem = name ? name : `formula-${ts}`;
  return path.join(dir, `${stem}.png`);
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help || !opts.latex) {
    usage();
    process.exit(opts.latex ? 0 : 1);
  }
  ensureDeps();

  const { mathjax } = require('mathjax-full/js/mathjax.js');
  const { TeX } = require('mathjax-full/js/input/tex.js');
  const { SVG } = require('mathjax-full/js/output/svg.js');
  const { liteAdaptor } = require('mathjax-full/js/adaptors/liteAdaptor.js');
  const { RegisterHTMLHandler } = require('mathjax-full/js/handlers/html.js');
  const { AllPackages } = require('mathjax-full/js/input/tex/AllPackages.js');
  const { Resvg } = require('@resvg/resvg-js');

  const adaptor = liteAdaptor();
  RegisterHTMLHandler(adaptor);
  const tex = new TeX({ packages: AllPackages });
  const svg = new SVG({ fontCache: 'local' });
  const doc = mathjax.document('', { InputJax: tex, OutputJax: svg });

  const node = doc.convert(opts.latex, {
    display: opts.display,
    em: 16,
    ex: 8,
    containerWidth: 100000,
  });

  const html = adaptor.outerHTML(node);
  const match = html.match(/<svg[\s\S]*<\/svg>/);
  if (!match) {
    process.stderr.write('Failed to render LaTeX (no SVG produced).\n');
    process.exit(2);
  }

  let s = match[0].replace(/currentColor/g, opts.color);

  const EM = 16;
  const UNITS_PER_PX = 1000 / EM;

  s = s.replace(/<svg([^>]*)>/, (full, attrs) => {
    const vbMatch = attrs.match(/viewBox="([^"]+)"/);
    const vb = (vbMatch ? vbMatch[1] : '0 0 100 100')
      .trim()
      .split(/\s+/)
      .map(Number);
    const [x, y, w, h] = vb;
    const padUnits = opts.pad * UNITS_PER_PX;
    const nwUnits = w + 2 * padUnits;
    const nhUnits = h + 2 * padUnits;
    const nwPx = Math.ceil(nwUnits / UNITS_PER_PX);
    const nhPx = Math.ceil(nhUnits / UNITS_PER_PX);
    let a = attrs
      .replace(/\sviewBox="[^"]*"/, ` viewBox="${x - padUnits} ${y - padUnits} ${nwUnits} ${nhUnits}"`)
      .replace(/\sstyle="[^"]*"/, '')
      .replace(/\s(width|height)="[^"]*"/g, '');
    return `<svg${a} width="${nwPx}" height="${nhPx}" style="color:${opts.color}">`;
  });

  const out = opts.out ? path.resolve(opts.out) : defaultOut(opts.name);
  fs.mkdirSync(path.dirname(out), { recursive: true });

  const transparent = opts.bg === 'transparent' || opts.bg === 'none';
  const resvgOpts = { fitTo: { mode: 'zoom', value: opts.scale } };
  if (!transparent) resvgOpts.background = opts.bg;

  const png = new Resvg(s, resvgOpts).render().asPng();
  fs.writeFileSync(out, png);
  process.stdout.write(out + '\n');
}

main();
