# -*- coding: utf-8 -*-
"""
理正岩土·挡土墙 计算内核（重力式）
====================================
依据：理正岩土《挡土墙设计软件》编制原理（DangTu.pdf）
      + 《公路路基设计规范》JTG D30-2015 + 《公路设计手册·路基》

土压力：库仑理论，数值扫描破裂面（复现理正 5.1.3 节）
稳定性：滑动 Kc、倾覆 K0、地基应力/偏心距（复现 7.1.1~7.1.3）

用法：  python dantu_calc.py input.json [-o result.json]
输入：  见 references/parameters.md / assets/input_template.json
"""
import json
import sys
import math

DEG = math.pi / 180.0


def num(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


f3 = lambda x: "%.3f" % x


# ============================================================================
# 地面线（自墙顶背角点向填土内侧延伸的折线）+ 超载
# ============================================================================
class Ground:
    def __init__(self, segments, start_x=0.0, cross_slope=0.0):
        self.segments = segments or []
        self.start_x = start_x
        self.cross_slope = cross_slope

    def _abs_segments(self, x_origin, y_origin):
        out = []
        x = x_origin + self.start_x
        y = y_origin
        for s in self.segments:
            x1 = x + num(s.get("dx"))
            y1 = y + num(s.get("dy"))
            out.append((x, x1, y, y1, num(s.get("q")) if s.get("q") else 0.0))
            x, y = x1, y1
        return out

    def y_at(self, x, x_origin, y_origin):
        segs = self._abs_segments(x_origin, y_origin)
        if not segs or x <= segs[0][0]:
            return y_origin
        for (x0, x1, y0, y1, q) in segs:
            if x0 <= x <= x1:
                if abs(x1 - x0) < 1e-12:
                    return max(y0, y1)
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        x0, x1, y0, y1, q = segs[-1]
        return y1 + (x - x1) * math.tan(self.cross_slope * DEG)

    def q_at(self, x, x_origin, y_origin):
        for (x0, x1, y0, y1, q) in self._abs_segments(x_origin, y_origin):
            if x0 <= x <= x1:
                return q
        return 0.0


# ============================================================================
# 库仑主动土压力：数值扫描破裂面
# ============================================================================
def _bisect(f, lo, hi, it=90):
    for _ in range(it):
        mid = (lo + hi) / 2.0
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def coulomb_active(m_back, delta_deg, phi_deg, gamma, ground, H, xtb=None, ytb=None):
    """返回 {Ea,Ea_soil,theta,Hcalc,Ex,Ey,Ze}. 墙踵在原点(0,0)。
    墙顶背角 = (xtb, ytb) = (-m_back*H, H)。"""
    if xtb is None:
        xtb, ytb = -m_back * H, H
    alpha = math.atan(m_back)
    delta = delta_deg * DEG
    phi = phi_deg * DEG

    # 计算高度：延伸墙背 x = -m_back*y 与地面交点
    def f_hc(y):
        return y - ground.y_at(-m_back * y, xtb, ytb)
    if m_back > 1e-9:
        Hcalc = _bisect(f_hc, H, H + 40.0)
    else:
        Hcalc = H
    # 破裂面与水平夹角 θ；破裂面 x = y/tanθ
    def f_exit(y, tan_th):
        return y - ground.y_at(y / tan_th, xtb, ytb)

    n = 1600
    best = None
    for k in range(n + 1):
        th = (2.0 + 86.0 * k / n) * DEG
        tan_th = math.tan(th)
        if tan_th <= 1e-6:
            continue
        denom = math.cos(th - phi - alpha - delta)
        if denom <= 1e-6:
            continue
        y_exit = _bisect(lambda y: f_exit(y, tan_th), 1e-6, Hcalc + 30.0)
        if y_exit <= 0:
            continue
        area = (1.0 / tan_th + m_back) * y_exit * y_exit / 2.0
        # 超载 ∫∫q
        Q = 0.0
        m = 400
        dy = y_exit / m
        for i in range(m):
            y = (i + 0.5) * dy
            xl = -m_back * y
            xr = y / tan_th
            qa = ground.q_at(xl, xtb, ytb)
            qb = ground.q_at(xr, xtb, ytb)
            Q += (qa + qb) / 2.0 * (xr - xl) * dy
        Ws = gamma * area
        Ea = (Ws + Q) * math.sin(th - phi) / denom
        if Ea < 0:
            continue
        if best is None or Ea > best["Ea"]:
            Es = Ws * math.sin(th - phi) / denom
            best = {"Ea": Ea, "Ea_soil": Es, "theta": th / DEG,
                    "Hcalc": Hcalc, "A": area}
    if best is None:
        best = {"Ea": 0.0, "Ea_soil": 0.0, "theta": 45.0, "Hcalc": Hcalc, "A": 0.0}
    incl = alpha + delta
    best["Ex"] = best["Ea"] * math.cos(incl)
    best["Ey"] = best["Ea"] * math.sin(incl)
    Hc = best["Hcalc"]
    Eq = best["Ea"] - best["Ea_soil"]
    best["Ze"] = (best["Ea_soil"] * Hc / 3.0 + Eq * Hc / 2.0) / best["Ea"] if best["Ea"] else 0.0
    return best


# ============================================================================
# 重力式挡土墙几何（多边形 + 面积/重心）
# ============================================================================
class GravityWall:
    def __init__(self, H, b_top, m_face, m_back, base_slope=0.0,
                 step_b=0.0, step_h=0.0, step_follows_face=True):
        self.H, self.b_top, self.m_face, self.m_back = H, b_top, m_face, m_back
        self.base_slope, self.step_b, self.step_h = base_slope, step_b, step_h
        self.step_follows_face = step_follows_face

    def widths(self):
        H, mf, mb, h1 = self.H, self.m_face, self.m_back, self.step_h
        B1 = self.b_top + mf * (H - h1) + mb * (H - h1)   # 台顶宽
        B = self.step_b + self.b_top + mb * H + mf * (H - (0 if self.step_follows_face else h1))
        return B1, B

    def polygon(self):
        """以墙趾(前下角)为(0,0)、x 向背坡为正、y 向上。返回顶点列表。"""
        H, mf, mb, h1, sb = self.H, self.m_face, self.m_back, self.step_h, self.step_b
        if self.step_follows_face:
            p = [
                (0.0, 0.0),
                (sb, 0.0),
                (sb + mf * H, H),
            ]
        else:
            p = [
                (0.0, 0.0),
                (0.0, h1),
                (sb, h1),
                (sb + mf * (H - h1), H),
            ]
        # 墙顶
        xtopF = p[-1][0]
        p.append((xtopF + self.b_top, H))
        # 背坡至墙踵
        p.append((xtopF + self.b_top + mb * H, 0.0))
        return p

    def area_centroid(self):
        p = self.polygon()
        A = 0.0
        cx = cy = 0.0
        for i in range(len(p)):
            x0, y0 = p[i]
            x1, y1 = p[(i + 1) % len(p)]
            cr = x0 * y1 - x1 * y0
            A += cr
            cx += (x0 + x1) * cr
            cy += (y0 + y1) * cr
        A /= 2.0
        if abs(A) < 1e-12:
            return 0.0, 0.0, 0.0
        cx /= (6 * A)
        cy /= (6 * A)
        return abs(A), cx, cy

    def back_top(self):
        p = self.polygon()
        # 墙顶背角 = 倒数第二个点
        return p[-2]


# ============================================================================
# 稳定性验算
# ============================================================================
def sliding(wall, W, Ex, Ey, f_base, extra_resist=0.0, extra_force=0.0):
    if abs(wall.base_slope) < 1e-9:
        resist = f_base * (W + Ey) + extra_resist
        force = Ex + extra_force
        Kc = resist / force if force else 0
        return {"kind": "level", "f": f_base, "slide_force": force, "resist": resist,
                "Kc": Kc, "pass": Kc >= 1.30}
    eta = math.atan(wall.base_slope)
    s, c = math.sin(eta), math.cos(eta)
    Wn, Wt = W * c, W * s
    En, Et = Ey * c - Ex * s, Ex * c + Ey * s
    force = Et - Wt + extra_force
    resist = f_base * (Wn + En) + extra_resist
    Kc = resist / force if force else 0
    return {"kind": "inclined", "eta": eta / DEG, "Wn": Wn, "Wt": Wt, "En": En,
            "Et": Et, "slide_force": force, "resist": resist, "Kc": Kc,
            "pass": Kc >= 1.30}


def overturning(B, W, xc, Ey, Ex, Ze, M_front=0.0):
    Mo = Ex * Ze
    Mr = W * xc + Ey * B + M_front        # M_front: 墙前被动土压力等提供的抗倾覆力矩
    K0 = Mr / Mo if Mo else 0
    return {"K0": K0, "M_overturn": Mo, "M_resist": Mr, "Zw": xc, "Zx": B,
            "Zy": Ze, "pass": K0 >= 1.50}


def bearing(B, W, Ey, xc, Ex, Ze, fa, k_toe, k_heel, k_avg, M_front=0.0):
    Wall = W + Ey
    Mall = W * xc + Ey * B - Ex * Ze + M_front
    Zn = Mall / Wall if Wall else 0
    e = B / 2.0 - Zn
    if abs(e) <= B / 6.0:
        s_toe = Wall / B * (1 + 6 * e / B)
        s_heel = Wall / B * (1 - 6 * e / B)
    else:
        s_toe = 2 * Wall / (3 * Zn) if Zn else 0.0
        s_heel = 0.0
    s_avg = (s_toe + s_heel) / 2.0
    return {"Wall": Wall, "Mall": Mall, "Zn": Zn, "e": e, "B": B, "s_toe": s_toe,
            "s_heel": s_heel, "s_avg": s_avg, "fa": fa, "allow_toe": fa * k_toe,
            "allow_heel": fa * k_heel, "allow_avg": fa * k_avg,
            "e_pass": abs(e) <= B / 6.0, "toe_pass": s_toe <= fa * k_toe,
            "heel_pass": s_heel <= fa * k_heel, "avg_pass": s_avg <= fa * k_avg}


# ============================================================================
def calc_gravity(inp):
    g = inp["geometry"]
    wall = GravityWall(num(g["H"]), num(g["b_top"]), num(g.get("m_face")),
                       num(g.get("m_back")), num(g.get("base_slope")),
                       num(g.get("step_b")), num(g.get("step_h")),
                       g.get("step_follows_face", True))
    mate, soil = inp["materials"], inp["soil"]
    fnd = inp.get("foundation", {})
    surf = inp.get("surface", {})
    gamma_m = num(mate.get("gamma_masonry"), 23.0)
    gamma_s = num(soil.get("gamma"), 19.0)
    phi = num(soil.get("phi"), 35.0)
    delta = num(soil.get("delta"), phi / 2.0)

    B1, B = wall.widths()
    A, xc, yc = wall.area_centroid()
    W = gamma_m * A
    xtb, ytb = wall.back_top()
    heel_x = wall.polygon()[-1][0]
    ground = Ground(surf.get("segments", []), num(surf.get("start_x")),
                    num(surf.get("cross_slope")))
    # 墙顶背角相对墙踵的坐标（墙踵 = 背坡底端点）
    ep = coulomb_active(wall.m_back, delta, phi, gamma_s, ground, wall.H,
                        xtb - heel_x, wall.H)
    Ex, Ey = ep["Ex"], ep["Ey"]

    f_base = num(fnd.get("f_base"), 0.5)
    # 附加集中荷载：是否为被动土压力为真时，水平分量计入抗滑力
    extra_resist = extra_force = 0.0
    Wload = 0.0
    load_M = 0.0
    for pl in inp.get("point_loads", []) or []:
        P = num(pl.get("P"))
        ang = num(pl.get("angle")) * DEG
        Ph, Pv = P * math.cos(ang), P * math.sin(ang)
        if pl.get("passive"):
            extra_force -= Ph          # 被动向：减小滑移力（理正口径）
        else:
            extra_force += abs(Ph)     # 非被动：增大滑移力
        Wload += Pv
        load_M += Pv * num(pl.get("x")) - Ph * num(pl.get("y"))
    Wtot = W + max(0.0, Wload)
    # 墙前被动土压力（可选，含折减系数；默认不计）
    fp = inp.get("front_passive")
    Ep = 0.0
    M_front = 0.0
    if fp and fp.get("enabled"):
        h1 = num(fp.get("H1"))
        phi_f = num(fp.get("phi"), 30.0)
        gam_f = num(fp.get("gamma"), 19.0)
        lam = num(fp.get("lambda"), 1.0)
        kp = math.tan((45.0 + phi_f / 2.0) * DEG) ** 2
        ep_full = 0.5 * gam_f * h1 * h1 * kp
        if fp.get("count_sliding", True):
            Ep = lam * ep_full
        if fp.get("count_overturning", True):
            M_front = lam * ep_full * (h1 / 3.0)
    sl = sliding(wall, Wtot, Ex, Ey, f_base, extra_resist + Ep, extra_force)
    ov = overturning(B, W, xc, Ey, Ex, ep["Ze"], M_front)
    fa = num(fnd.get("fa"), 200.0)
    be = bearing(B, Wtot, Ey, xc, Ex, ep["Ze"], fa,
                 num(fnd.get("fa_toe_coef"), 1.2), num(fnd.get("fa_heel_coef"), 1.3),
                 num(fnd.get("fa_avg_coef"), 1.0), M_front)
    return {"standard": inp.get("standard", "general"),
            "front_passive": {"Ep": Ep, "M_front": M_front} if fp else None,
            "geometry": {"B1": B1, "B": B, "A": A, "xc": xc, "W": W,
                         "alpha": math.degrees(math.atan(wall.m_back))},
            "earth_pressure": ep, "sliding": sl, "overturning": ov, "bearing": be}


# ============================================================================
def report_text(inp, r):
    st = "公路" if r["standard"] == "highway" else "通用"
    g = inp["geometry"]
    R, ep, sl, ov, be = r["geometry"], r["earth_pressure"], r["sliding"], r["overturning"], r["bearing"]
    soil = inp["soil"]
    L = []
    A = L.append
    A("重力式挡土墙验算[执行标准：%s]" % st)
    A("")
    A("计算项目： %s" % inp.get("project_name", "重力式挡土墙"))
    A("")
    A("原始条件:")
    A("")
    A("墙身尺寸:")
    A("  墙身高: %s(m)" % f3(g["H"]))
    A("  墙顶宽: %s(m)" % f3(g["b_top"]))
    A("  面坡倾斜坡度: 1:%s" % f3(g.get("m_face", 0)))
    A("  背坡倾斜坡度: 1:%s" % f3(g.get("m_back", 0)))
    if num(g.get("step_b")):
        A("  采用1个扩展墙址台阶:")
        A("  墙趾台阶b1: %s(m)" % f3(g["step_b"]))
        A("  墙趾台阶h1: %s(m)" % f3(g["step_h"]))
    A("  墙底倾斜坡率: %s:1" % f3(g.get("base_slope", 0)))
    A("")
    A("物理参数:")
    A("  圬工砌体容重: %s(kN/m3)" % f3(inp["materials"].get("gamma_masonry", 23)))
    A("  墙后填土内摩擦角: %s(度)" % f3(soil.get("phi")))
    A("  墙后填土粘聚力: %s(kPa)" % f3(soil.get("c", 0)))
    A("  墙后填土容重: %s(kN/m3)" % f3(soil.get("gamma")))
    A("  墙背与墙后填土摩擦角: %s(度)" % f3(soil.get("delta")))
    A("  土压力计算方法: 库仑")
    A("")
    A("墙底宽度 B = %s(m)   台顶宽度 = %s(m)" % (f3(R["B"]), f3(R["B1"])))
    A("墙身截面积 = %s(m2)   重量 = %s (kN)" % (f3(R["A"]), f3(R["W"])))
    A("")
    A("=" * 69)
    A("")
    A("第 1 种情况: 一般情况")
    A("")
    A("[土压力计算] 计算高度为 %s(m)处的库仑主动土压力" % f3(ep["Hcalc"]))
    A("")
    A("按实际墙背计算得到:")
    A("")
    A("第1破裂角： %s(度)" % f3(90.0 - ep["theta"]))
    A("")
    A("Ea=%s(kN) Ex=%s(kN) Ey=%s(kN) 作用点高度 Zy=%s(m)"
      % (f3(ep["Ea"]), f3(ep["Ex"]), f3(ep["Ey"]), f3(ep["Ze"])))
    A("")
    A("(一) 滑动稳定性验算")
    A("")
    A("基底摩擦系数 = %s" % f3(inp.get("foundation", {}).get("f_base", 0.5)))
    A("滑移力= %s(kN) 抗滑力= %s(kN)" % (f3(sl["slide_force"]), f3(sl["resist"])))
    A("滑移验算%s: Kc = %s %s 1.300" % ("满足" if sl["pass"] else "不满足",
      f3(sl["Kc"]), ">" if sl["pass"] else "<="))
    A("")
    A("(二) 倾覆稳定性验算")
    A("")
    A("相对于墙趾点，墙身重力的力臂 Zw = %s (m)" % f3(ov["Zw"]))
    A("相对于墙趾点，Ey的力臂 Zx = %s (m)" % f3(ov["Zx"]))
    A("相对于墙趾点，Ex的力臂 Zy = %s (m)" % f3(ov["Zy"]))
    A("倾覆力矩= %s(kN-m) 抗倾覆力矩= %s(kN-m)" % (f3(ov["M_overturn"]), f3(ov["M_resist"])))
    A("倾覆验算%s: K0 = %s %s 1.500" % ("满足" if ov["pass"] else "不满足",
      f3(ov["K0"]), ">" if ov["pass"] else "<="))
    A("")
    A("(三) 地基应力及偏心距验算")
    A("")
    A("作用于基础底的总竖向力 = %s(kN) 作用于墙趾下点的总弯矩=%s(kN-m)" % (f3(be["Wall"]), f3(be["Mall"])))
    A("基础底面宽度 B = %s (m) 偏心距 e = %s(m)" % (f3(be["B"]), f3(be["e"])))
    A("基础底面合力作用点距离基础趾点的距离 Zn = %s(m)" % f3(be["Zn"]))
    A("基底压应力: 趾部=%s 踵部=%s(kPa)" % (f3(be["s_toe"]), f3(be["s_heel"])))
    A("作用于基底的合力偏心距验算%s: e=%s %s 0.167*%s = %s(m)" % (
        "满足" if be["e_pass"] else "不满足", f3(be["e"]),
        "<=" if be["e_pass"] else ">", f3(be["B"]), f3(be["B"] / 6)))
    A("墙趾处地基承载力验算%s: 压应力=%s %s %s(kPa)" % (
        "满足" if be["toe_pass"] else "不满足", f3(be["s_toe"]),
        "<=" if be["toe_pass"] else ">", f3(be["allow_toe"])))
    A("墙踵处地基承载力验算%s: 压应力=%s %s %s(kPa)" % (
        "满足" if be["heel_pass"] else "不满足", f3(be["s_heel"]),
        "<=" if be["heel_pass"] else ">", f3(be["allow_heel"])))
    A("地基平均承载力验算%s: 压应力=%s %s %s(kPa)" % (
        "满足" if be["avg_pass"] else "不满足", f3(be["s_avg"]),
        "<=" if be["avg_pass"] else ">", f3(be["allow_avg"])))
    A("")
    A("=" * 49)
    A("各组合最不利结果")
    A("=" * 49)
    A("")
    A("(一) 滑移验算")
    A("滑移验算%s: Kc = %s %s 1.300" % ("满足" if sl["pass"] else "不满足",
      f3(sl["Kc"]), ">" if sl["pass"] else "<="))
    A("")
    A("(二) 倾覆验算")
    A("倾覆验算%s: K0 = %s %s 1.500" % ("满足" if ov["pass"] else "不满足",
      f3(ov["K0"]), ">" if ov["pass"] else "<="))
    A("")
    A("(三) 地基验算")
    A("地基平均承载力验算%s: 压应力=%s %s %s(kPa)" % (
        "满足" if be["avg_pass"] else "不满足", f3(be["s_avg"]),
        "<=" if be["avg_pass"] else ">", f3(be["allow_avg"])))
    A("")
    return "\n".join(L)


def main():
    if len(sys.argv) < 2:
        print("用法: python dantu_calc.py input.json [-o result.json]")
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8-sig") as fp:
        inp = json.load(fp)
    r = calc_gravity(inp)
    print(report_text(inp, r))
    if "-o" in sys.argv:
        with open(sys.argv[sys.argv.index("-o") + 1], "w", encoding="utf-8") as fp:
            json.dump(r, fp, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    main()
