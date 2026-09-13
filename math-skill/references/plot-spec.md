# Plot spec reference (`render_plot.py`)

## Contents
- [Expression namespace](#expression-namespace)
- [Top-level fields](#top-level-fields)
- [curves](#curves)
- [parametric](#parametric)
- [points](#points)
- [annotate](#annotate)
- [hlines / vlines](#hlines--vlines)
- [panels](#panels)
- [Full examples](#full-examples)
- [Custom figures (raw matplotlib)](#custom-figures-raw-matplotlib)

Pass a spec as a JSON file: `python <skill>/scripts/render_plot.py spec.json -o out.png`.
Omit the file and pipe JSON on stdin if you prefer.

## Expression namespace

Expressions are Python/numpy evaluated with `x` (curves) or `t` (parametric) bound. Available:
`np, pi, e, exp, log, ln, log10, sqrt, abs, sin, cos, tan, asin, acos, atan, sinh, cosh, tanh, floor, ceil, sign, minimum, maximum`.
Use `**` for powers, e.g. `x**3 - 3*x`. Use `np.where(...)` for piecewise functions.

## Top-level fields

| Field | Type | Default | Meaning |
|---|---|---|---|
| `title` | str | – | Figure title (Chinese ok) |
| `xlabel` / `ylabel` | str | – | Axis labels |
| `xlim` | [lo, hi] | [-5, 5] | x range (also default domain for curves) |
| `ylim` | [lo, hi] | auto | y range |
| `figsize` | [w, h] | [7, 4.5] | inches |
| `dpi` | int | 160 | resolution |
| `grid` | bool | true | show grid |
| `legend` | bool | true | show legend when labels exist |
| `axes` | bool | false | draw x/y axis lines through the origin |
| `equal_aspect` | bool | false | force 1:1 aspect (geometry) |
| `bg` | str | "white" | figure background |
| `hlines` / `vlines` | list | – | dashed guide lines at y / x values |
| `axis_color`, `axis_style` | str | `#999999`, `--` | style of hlines/vlines |

## curves

`y = f(x)` plots. Each item:

| Field | Default | Meaning |
|---|---|---|
| `expr` | required | e.g. `"x**2"`, `"sin(x)/x"` |
| `label` | – | legend text (LaTeX allowed: `"$\\sin x$"`) |
| `color` | auto | any matplotlib color |
| `linestyle` | `"-"` | `-`, `--`, `-.`, `:` |
| `lw` | 1.8 | line width |
| `domain` | `xlim` | `[lo, hi]` to restrict this curve |
| `samples` | 1000 | number of points |

## parametric

Parametric curves `(x(t), y(t))` — for circles, ellipses, cycloids, Lissajous, etc.

| Field | Default | Meaning |
|---|---|---|
| `x`, `y` | required | expressions in `t` |
| `t` | required | `[t0, t1]` |
| `label`, `color`, `linestyle`, `lw`, `samples` | as above | |

## points

| Field | Default | Meaning |
|---|---|---|
| `x`, `y` | required | coordinates |
| `label` | – | legend text |
| `color` | `#d62728` | marker color |
| `marker` | `o` | marker style |
| `size` | 6 | marker size |
| `text` | – | label drawn next to the point |
| `textsize` | 11 | text size |

## annotate

Arrows with text — for tangent lines, limits, "此处间断", extrema.

| Field | Default | Meaning |
|---|---|---|
| `text` | required | annotation text |
| `xy` | required | `[x, y]` point being annotated |
| `xytext` | [0,0] | `[dx, dy]` text offset |
| `arrow` | true | draw an arrow |
| `color`, `size` | `#111111`, 11 | |

## hlines / vlines

```json
"hlines": [1, -1],
"vlines": [0],
"axis_style": ":"
```

## panels

Render several sub-specs in a grid. Each panel is a normal spec.

```json
{ "panels": [ { "title": "a" }, { "title": "b" } ], "ncols": 2, "figsize": [10, 8] }
```

## Full examples

### 1. `sin x / x` with a horizontal asymptote

```json
{
  "title": "重要极限: y = sin(x)/x",
  "xlim": [-15, 15],
  "ylim": [-0.4, 1.2],
  "axes": true,
  "curves": [{ "expr": "sin(x)/x", "label": "$\\frac{\\sin x}{x}$", "color": "#1f77b4" }],
  "hlines": [0],
  "points": [{ "x": 0, "y": 1, "marker": "o", "text": "极限 = 1" }]
}
```

### 2. Parametric cycloid

```json
{
  "title": "摆线 x=t-sin t, y=1-cos t",
  "equal_aspect": true,
  "parametric": [
    { "x": "t - sin(t)", "y": "1 - cos(t)", "t": [0, 12.566370614], "label": "cycloid", "color": "#d62728" }
  ],
  "axes": true
}
```

### 3. Tangent line with annotation

```json
{
  "title": "f(x)=x^2 在 x=1 处的切线",
  "xlim": [-1, 3],
  "curves": [
    { "expr": "x**2", "label": "$f(x)=x^2$" },
    { "expr": "2*x - 1", "label": "切线 y=2x-1", "linestyle": "--", "color": "#d62728" }
  ],
  "axes": true,
  "points": [{ "x": 1, "y": 1, "text": "(1, 1)" }]
}
```

### 4. 2x2 panels

```json
{
  "figsize": [10, 8],
  "ncols": 2,
  "panels": [
    { "title": "$y=x^2$", "curves": [{ "expr": "x**2" }], "axes": true },
    { "title": "$y=e^x$", "curves": [{ "expr": "exp(x)" }], "axes": true },
    { "title": "$y=\\ln x$", "curves": [{ "expr": "log(x)", "domain": [0.05, 5] }], "axes": true },
    { "title": "$y=\\sin x$", "curves": [{ "expr": "sin(x)" }], "axes": true }
  ]
}
```

## Custom figures (raw matplotlib)

When the figure is not a plot (coordinate geometry, vectors, Riemann rectangles, solids of revolution, Venn-like diagrams), write a throwaway Python script to `math-images/`, run it, and Read the resulting PNG. Template:

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

fig, ax = plt.subplots(figsize=(6, 6), dpi=160)
# ... draw with ax.plot / ax.fill / ax.arrow / ax.text ...
ax.set_aspect("equal")
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig("math-images/custom.png")
print("math-images/custom.png")
```

Common helpers for math figures:
- Riemann sum: `ax.bar(..., width=..., alpha=0.4, align="edge")` + `ax.plot(func)`.
- Vectors: `ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->"))`.
- Filled area under a curve: `ax.fill_between(x, y, alpha=0.3)`.
- Unit circle + trig: plot `cos(t)`, `sin(t)`, draw the angle arc and the reference triangle.
