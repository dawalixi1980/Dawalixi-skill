---
name: math-skill
description: Render mathematics as images so the user can actually SEE a formula, function graph, or geometric figure instead of reading raw LaTeX or ASCII art. Renders LaTeX formulas (full LaTeX, including matrices, cases, aligned equations) to PNG via MathJax, and renders function / parametric / multi-panel plots to PNG via matplotlib. Use whenever a reply about math, physics, statistics, engineering, or science would be clearer with a rendered formula or a plotted graph, especially higher math (calculus, limits, derivatives, integrals, series, linear algebra, differential equations, analytic geometry). Triggers include "画一下函数图像", "画出…", "把这个公式渲染成图片", "把它画出来", "plot this", "graph of ...", "render this equation", "visualize", "函数图像", "导数/积分/矩阵/极限/几何图".
---

# math-skill

Turn math into viewable PNG images, then show them to the user. The model cannot draw pixels itself; these scripts render locally.

## Workflow

1. Decide what to draw:
   - **A formula / equation** (no graph) -> `render_formula.js`
   - **A function graph, parametric curve, scatter, or multi-panel figure** -> `render_plot.py`
   - **A geometry/vector figure not covered by the spec** -> write a small custom matplotlib script (see `references/plot-spec.md` §Custom).
2. Run the script; it prints the absolute PNG path on stdout.
3. **Show the image with the Read tool** on that path so the user sees it. Never just write the path and stop.
4. Keep surrounding prose as normal text; let the image carry the math.

Always run the scripts from the skill directory's `scripts/` folder. Node deps auto-install on first run.

## Formulas

```bash
node <skill>/scripts/render_formula.js "LATEX"
node <skill>/scripts/render_formula.js "\\lim_{n\\to\\infty}\\left(1+\\frac{1}{n}\\right)^n = e" --name euler-limit
node <skill>/scripts/render_formula.js "A^{-1} = \\frac{1}{\\det A}\\begin{pmatrix} d & -b \\\\ -c & a \\end{pmatrix}" --bg transparent
```

Options: `-o out.png`, `--name stem`, `--color #hex`, `--bg white|transparent|#hex`, `--scale N`, `--pad px`, `--inline`.

Full LaTeX works: `\frac`, `\int`, `\sum`, `\lim`, `\begin{pmatrix/bmatrix/cases/align}`, `\mathbb`, `\operatorname`, etc. Use `\begin{aligned}...\end{aligned}` inside `$$` for multi-line derivations.

## Function / parametric plots

```bash
python <skill>/scripts/render_plot.py --expr "x**2, sin(x)" --range -5 5 --title "y=x^2 与 y=sin x" --name compare
python <skill>/scripts/render_plot.py spec.json -o ./math-images/geogebra.png
```

The `--expr` shortcut handles quick `y=f(x)` plots. For anything richer (parametric curves, points, annotations, asymptotes, multi-panel, limits of integration, equal aspect), write a JSON spec and pass it. See **`references/plot-spec.md`** for every field and ready-to-copy examples (including a cycloid, a tangent line, and a 2x2 panel grid).

Read `references/plot-spec.md` whenever the figure is more than a plain `y=f(x)` plot.

## Notes

- Python requirements: `numpy` and `matplotlib` (already present on this machine). No LaTeX distribution required.
- Default output dir is `./math-images/` under the current working directory; pass `-o` to control it.
- Verify quality: after rendering, Read the PNG. If the image is broken or clipped, fix the input and re-render before showing the user.
