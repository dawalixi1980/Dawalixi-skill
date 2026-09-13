#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Render mathematical plots/figures to PNG from a JSON spec or simple expressions.

Examples:
    python render_plot.py spec.json -o out.png
    python render_plot.py --expr "x**2, sin(x)" --range -5 5 -o out.png
"""
import argparse
import json
import os
import sys
from datetime import datetime

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "PingFang SC",
    "Noto Sans CJK SC",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False

_NS = {
    "np": np,
    "pi": np.pi,
    "e": np.e,
    "exp": np.exp,
    "log": np.log,
    "ln": np.log,
    "log10": np.log10,
    "sqrt": np.sqrt,
    "abs": np.abs,
    "sin": np.sin,
    "cos": np.cos,
    "tan": np.tan,
    "asin": np.arcsin,
    "acos": np.arccos,
    "atan": np.arctan,
    "sinh": np.sinh,
    "cosh": np.cosh,
    "tanh": np.tanh,
    "floor": np.floor,
    "ceil": np.ceil,
    "sign": np.sign,
    "minimum": np.minimum,
    "maximum": np.maximum,
}


def _eval(expr, extra=None):
    env = dict(_NS)
    if extra:
        env.update(extra)
    with np.errstate(all="ignore"):
        return eval(expr, {"__builtins__": {}}, env)


def _curve_x(spec, xlim):
    if "domain" in spec:
        return np.linspace(float(spec["domain"][0]), float(spec["domain"][1]), int(spec.get("samples", 1000)))
    lo, hi = xlim
    return np.linspace(lo, hi, int(spec.get("samples", 1000)))


def draw_panel(ax, spec):
    xlim = spec.get("xlim", [-5, 5])
    ax.set_xlim(xlim)

    for c in spec.get("curves", []):
        x = _curve_x(c, xlim)
        y = _eval(c["expr"], {"x": x})
        ax.plot(
            x,
            y,
            label=c.get("label"),
            color=c.get("color"),
            linestyle=c.get("linestyle", "-"),
            linewidth=float(c.get("lw", 1.8)),
            alpha=float(c.get("alpha", 1.0)),
        )

    for p in spec.get("parametric", []):
        t = np.linspace(float(p["t"][0]), float(p["t"][1]), int(p.get("samples", 1000)))
        xs = _eval(p["x"], {"t": t})
        ys = _eval(p["y"], {"t": t})
        ax.plot(xs, ys, label=p.get("label"), color=p.get("color"),
                linestyle=p.get("linestyle", "-"), linewidth=float(p.get("lw", 1.8)))

    for pt in spec.get("points", []):
        ax.plot([pt["x"]], [pt["y"]], marker=pt.get("marker", "o"),
                color=pt.get("color", "#d62728"), markersize=float(pt.get("size", 6)),
                label=pt.get("label"), zorder=5)
        if pt.get("text"):
            ax.annotate(pt["text"], (pt["x"], pt["y"]),
                        textcoords="offset points", xytext=(6, 6), fontsize=float(pt.get("textsize", 11)))

    for a in spec.get("annotate", []):
        ax.annotate(
            a["text"],
            xy=(a["xy"][0], a["xy"][1]),
            xytext=(a.get("xytext", [0, 0])[0], a.get("xytext", [0, 0])[1]),
            fontsize=float(a.get("size", 11)),
            color=a.get("color", "#111111"),
            arrowprops=({"arrowstyle": "->", "color": a.get("color", "#111111")} if a.get("arrow", True) else None),
        )

    for y in spec.get("hlines", []):
        ax.axhline(float(y), color=spec.get("axis_color", "#999999"),
                   linestyle=spec.get("axis_style", "--"), linewidth=0.8)
    for x in spec.get("vlines", []):
        ax.axvline(float(x), color=spec.get("axis_color", "#999999"),
                   linestyle=spec.get("axis_style", "--"), linewidth=0.8)

    if spec.get("axes", False):
        ax.axhline(0, color="#888888", linewidth=0.8)
        ax.axvline(0, color="#888888", linewidth=0.8)

    if spec.get("ylim"):
        ax.set_ylim(spec["ylim"])
    if spec.get("title"):
        ax.set_title(spec["title"], fontsize=float(spec.get("title_size", 15)))
    if spec.get("xlabel"):
        ax.set_xlabel(spec["xlabel"])
    if spec.get("ylabel"):
        ax.set_ylabel(spec["ylabel"])
    if spec.get("grid", True):
        ax.grid(True, alpha=0.3)
    if spec.get("legend", True) and (spec.get("curves") or spec.get("parametric") or spec.get("points")):
        handles, labels = ax.get_legend_handles_labels()
        if any(l for l in labels):
            ax.legend(fontsize=float(spec.get("legend_size", 11)))
    if spec.get("equal_aspect"):
        ax.set_aspect("equal", adjustable="box")


def render(spec, out_path):
    dpi = int(spec.get("dpi", 160))
    figsize = spec.get("figsize", [7, 4.5])

    panels = spec.get("panels")
    if panels:
        n = len(panels)
        ncols = int(spec.get("ncols", 2))
        nrows = int((n + ncols - 1) / ncols)
        fig, axes = plt.subplots(nrows, ncols, figsize=figsize, dpi=dpi)
        axes_flat = np.atleast_1d(axes).ravel()
        for i, p in enumerate(panels):
            draw_panel(axes_flat[i], p)
        for j in range(n, len(axes_flat)):
            axes_flat[j].axis("off")
    else:
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        draw_panel(ax, spec)

    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fig.savefig(out_path, dpi=dpi, facecolor=spec.get("bg", "white"))
    plt.close(fig)


def default_out(name):
    d = os.path.join(os.getcwd(), "math-images")
    os.makedirs(d, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return os.path.join(d, f"{name or 'plot-' + ts}.png")


def main():
    ap = argparse.ArgumentParser(description="Render math plots to PNG.")
    ap.add_argument("spec", nargs="?", help="Path to JSON spec file")
    ap.add_argument("--expr", help="Comma-separated y=f(x) expressions (shortcut)")
    ap.add_argument("--range", nargs=2, type=float, metavar=("LO", "HI"), help="x range for --expr")
    ap.add_argument("--title", help="Title for --expr shortcut")
    ap.add_argument("-o", "--output", help="Output PNG path")
    ap.add_argument("--name", help="Filename stem when -o not given")
    args = ap.parse_args()

    if args.expr:
        xlim = args.range if args.range else [-5, 5]
        spec = {
            "xlim": xlim,
            "axes": True,
            "title": args.title,
            "curves": [{"expr": e.strip(), "label": f"y = {e.strip()}"} for e in args.expr.split(",")],
        }
    elif args.spec:
        with open(args.spec, "r", encoding="utf-8") as fh:
            spec = json.load(fh)
    else:
        spec = json.load(sys.stdin)

    out = os.path.abspath(args.output) if args.output else default_out(args.name)
    render(spec, out)
    print(out)


if __name__ == "__main__":
    main()
