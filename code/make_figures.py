#!/usr/bin/env python3
"""Phase 5 分析图生成（pgfplots/TikZ，IEEE 规格）。

三张图各回答一个问题：
  F1  CTAT 在两条扰动臂下的退化 —— "对测量噪声稳健、对 jitter + cumulative drift 脆弱"
      (Arm B 含累积漂移, Arm C 为非累积抖动; B/C 对比不隔离漂移)
  F2  CTAT 16 个强判别文件在 Arm B 下的逐文件轨迹 —— 崩溃是断崖且异质
  F3  ROAD oracle 在 Arm B 下向"全判攻击"退化解收敛 —— 弱信号归零
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "results" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
D = pd.read_csv(ROOT / "results" / "jitter_sensitivity.csv")

BASE = D[D.arm == "none"].set_index(["benchmark", "file"])
AGG = (D[D.arm != "none"]
       .groupby(["benchmark", "file", "arm", "level"])[["trivial_f1", "oracle_f1"]]
       .mean().reset_index())

PREAMBLE = r"""\documentclass[border={4pt 4pt 34pt 4pt}]{standalone}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\usepgfplotslibrary{groupplots,fillbetween}
\definecolor{plotblue}{HTML}{2166AC}
\definecolor{plotred}{HTML}{D6604D}
\definecolor{plotgreen}{HTML}{4DAC26}
\definecolor{plotorange}{HTML}{F4A582}
\definecolor{plotgray}{HTML}{878787}
\begin{document}
"""


def coords(xs, ys) -> str:
    return " ".join(f"({x:g},{y:.4f})" for x, y in zip(xs, ys))


def band(xs, lo, hi) -> str:
    """误差带：先正向再逆向闭合。"""
    fwd = " ".join(f"({x:g},{v:.4f})" for x, v in zip(xs, hi))
    bwd = " ".join(f"({x:g},{v:.4f})" for x, v in zip(reversed(xs), reversed(lo)))
    return fwd + " " + bwd


# ---------------------------------------------------------------- F1
def fig1() -> Path:
    b = BASE.loc["ctat"]
    out = []
    for arm, xs in [("A", [1, 10, 100, 1000]), ("B", [0.05, 0.10, 0.20, 0.50, 1.00])]:
        s = AGG[(AGG.benchmark == "ctat") & (AGG.arm == arm)]
        rec = {}
        for m in ["trivial_f1", "oracle_f1"]:
            mu = [s[s.level == x][m].mean() for x in xs]
            sd = [s[s.level == x][m].std(ddof=1) / np.sqrt(len(s[s.level == x])) for x in xs]
            rec[m] = (mu, [a - c for a, c in zip(mu, sd)], [a + c for a, c in zip(mu, sd)])
        out.append((arm, xs, rec))

    (armA, xa, ra), (armB, xb, rb) = out
    bt, bo = float(b.trivial_f1.mean()), float(b.oracle_f1.mean())

    tex = PREAMBLE + r"""
\begin{tikzpicture}
\begin{groupplot}[
  group style={group size=2 by 1, horizontal sep=1.5cm},
  width=7.6cm, height=5.2cm,   % IEEE double column 18.2cm / 2 panels
  ymin=0, ymax=0.80, grid=major, grid style={plotgray!25},
  label style={font=\small}, tick label style={font=\footnotesize},
  legend style={font=\footnotesize, draw=plotgray!60},
]
\nextgroupplot[
  xlabel={Arm A: timestamp noise $s$ ($\mu$s)}, ylabel={F1 (mean over 40 CTAT files)},
  xmode=log, log basis x=10, xtick={1,10,100,1000},
  title={\small (a) measurement noise}, title style={yshift=-1pt},
  legend style={at={(0.5,-0.30)}, anchor=north, legend columns=1, cells={anchor=west}},
]
\addplot[draw=none, fill=plotblue, fill opacity=0.15, forget plot] coordinates {""" + band(xa, ra["oracle_f1"][1], ra["oracle_f1"][2]) + r"""} \closedcycle;
\addplot[draw=none, fill=plotred, fill opacity=0.15, forget plot] coordinates {""" + band(xa, ra["trivial_f1"][1], ra["trivial_f1"][2]) + r"""} \closedcycle;
\addplot[plotgray, dashed, thick, forget plot] coordinates {(1,""" + f"{bo:.4f}" + r""") (1000,""" + f"{bo:.4f}" + r""")};
\addplot[plotgray, dotted, thick, forget plot] coordinates {(1,""" + f"{bt:.4f}" + r""") (1000,""" + f"{bt:.4f}" + r""")};
\addplot[plotblue, thick, mark=*, mark size=1.5pt] coordinates {""" + coords(xa, ra["oracle_f1"][0]) + r"""};
\addlegendentry{oracle (signal bound)}
\addplot[plotred, thick, mark=square*, mark size=1.5pt] coordinates {""" + coords(xa, ra["trivial_f1"][0]) + r"""};
\addlegendentry{trivial (zero-learning)}

\nextgroupplot[
  xlabel={Arm B: jitter + cumulative drift $\sigma$}, ylabel={},
  xtick={0.05,0.2,0.5,1.0}, xticklabels={$0.05$,$0.2$,$0.5$,$1.0$},
  xmin=-0.02, xmax=1.08,
  title={\small (b) Arm B: jitter + cumulative drift}, title style={yshift=-1pt},
  legend style={at={(0.5,-0.30)}, anchor=north, legend columns=1, cells={anchor=west}},
]
\addplot[draw=none, fill=plotblue, fill opacity=0.15, forget plot] coordinates {""" + band(xb, rb["oracle_f1"][1], rb["oracle_f1"][2]) + r"""} \closedcycle;
\addplot[draw=none, fill=plotred, fill opacity=0.15, forget plot] coordinates {""" + band(xb, rb["trivial_f1"][1], rb["trivial_f1"][2]) + r"""} \closedcycle;
\addplot[plotgray, dashed, thick] coordinates {(0,""" + f"{bo:.4f}" + r""") (1.05,""" + f"{bo:.4f}" + r""")};
\addlegendentry{oracle baseline ($\sigma{=}0$)}
\addplot[plotgray, dotted, thick] coordinates {(0,""" + f"{bt:.4f}" + r""") (1.05,""" + f"{bt:.4f}" + r""")};
\addlegendentry{trivial baseline ($\sigma{=}0$)}
\addplot[plotblue, thick, mark=*, mark size=1.5pt, forget plot] coordinates {""" + coords(xb, rb["oracle_f1"][0]) + r"""};
\addplot[plotred, thick, mark=square*, mark size=1.5pt, forget plot] coordinates {""" + coords(xb, rb["trivial_f1"][0]) + r"""};
\end{groupplot}
\end{tikzpicture}
\end{document}
"""
    p = FIG / "fig_p5_ctat_degradation.tex"
    p.write_text(tex)
    return p


# ---------------------------------------------------------------- F2
def fig2() -> Path:
    b = BASE.loc["ctat"]
    strong = b[b.trivial_f1 > 0.3].index.tolist()
    xs = [0.05, 0.10, 0.20, 0.50, 1.00]
    lines, hi = [], {}
    for f in strong:
        g = AGG[(AGG.benchmark == "ctat") & (AGG.file == f) & (AGG.arm == "B")]
        ys = [float(g[g.level == x].trivial_f1.iloc[0]) for x in xs]
        ys = [float(b.loc[f, "trivial_f1"])] + ys          # 把 σ=0 基线接到最左
        if "rpm-3" in f or "force-neutral-3" in f:
            hi[f] = ys
        else:
            lines.append(ys)
    xf = [0.0] + xs

    body = "".join(
        r"\addplot[plotgray, opacity=0.45, line width=0.5pt, forget plot] coordinates {"
        + coords(xf, ys) + "};\n" for ys in lines)

    tex = PREAMBLE + r"""
\begin{tikzpicture}
\begin{axis}[
  width=15cm, height=6.2cm,     % IEEE double column
  xlabel={Arm B: jitter + cumulative drift $\sigma$}, ylabel={trivial F1},
  xmin=-0.02, xmax=1.06, ymin=0, ymax=1.02,
  xtick={0,0.05,0.2,0.5,1.0}, xticklabels={$0$,,$0.2$,$0.5$,$1.0$},
  grid=major, grid style={plotgray!25},
  label style={font=\small}, tick label style={font=\footnotesize},
  % 数据整体下行且 14 条灰线铺满画布 -> 图例一律放绘图区外下方, 禁止 inside
  legend style={font=\footnotesize, at={(0.5,-0.26)}, anchor=north,
                legend columns=3, cells={anchor=west}, draw=plotgray!60},
]
""" + body
    for f, ys in hi.items():
        col = "plotred" if "rpm-3" in f else "plotblue"
        name = "rpm-3 (collapses at $\\sigma{=}0.5$)" if "rpm-3" in f else "force-neutral-3 (holds to $\\sigma{=}0.5$)"
        tex += (r"\addplot[" + col + r", very thick, mark=*, mark size=1.6pt] coordinates {"
                + coords(xf, ys) + "};\n" + r"\addlegendentry{" + name + "}\n")
    tex += r"""\addplot[plotgray, opacity=0.45, line width=0.5pt] coordinates {(0,-1) (0.05,-1)};
\addlegendentry{other 14 strong-discrimination files}
\end{axis}
\end{tikzpicture}
\end{document}
"""
    p = FIG / "fig_p5_ctat_perfile.tex"
    p.write_text(tex)
    return p


# ---------------------------------------------------------------- F3
def fig3() -> Path:
    b = BASE.loc["road"]
    xs = [0.05, 0.10, 0.20, 0.50, 1.00]
    s = AGG[(AGG.benchmark == "road") & (AGG.arm == "B")]
    mu = [s[s.level == x].oracle_f1.mean() for x in xs]
    sd = [s[s.level == x].oracle_f1.std(ddof=1) / np.sqrt(13) for x in xs]
    xf = [0.0] + xs
    muf = [float(b.oracle_f1.mean())] + mu
    lo = [muf[0]] + [a - c for a, c in zip(mu, sd)]
    hiv = [muf[0]] + [a + c for a, c in zip(mu, sd)]
    deg = float(b.degenerate_f1.mean())

    tex = PREAMBLE + r"""
\begin{tikzpicture}
\begin{axis}[
  width=8.6cm, height=5.4cm,    % IEEE single column
  xlabel={Arm B: jitter + cumulative drift $\sigma$}, ylabel={ROAD masquerade oracle F1},
  xmin=-0.02, xmax=1.06, ymin=0, ymax=0.26,
  xtick={0,0.05,0.2,0.5,1.0}, xticklabels={$0$,,$0.2$,$0.5$,$1.0$},
  grid=major, grid style={plotgray!25},
  label style={font=\small}, tick label style={font=\footnotesize},
  legend style={font=\footnotesize, at={(0.5,-0.26)}, anchor=north,
                legend columns=1, cells={anchor=west}, draw=plotgray!60},
]
\addplot[draw=none, fill=plotblue, fill opacity=0.15, forget plot] coordinates {""" + band(xf, lo, hiv) + r"""} \closedcycle;
\addplot[plotblue, very thick, mark=*, mark size=1.6pt] coordinates {""" + coords(xf, muf) + r"""};
\addlegendentry{oracle F1 (mean of 13 files)}
\addplot[plotred, dashed, very thick] coordinates {(0,""" + f"{deg:.4f}" + r""") (1.05,""" + f"{deg:.4f}" + r""")};
\addlegendentry{all-positive degenerate F1}
\end{axis}
\end{tikzpicture}
\end{document}
"""
    p = FIG / "fig_p5_road_oracle.tex"
    p.write_text(tex)
    return p


if __name__ == "__main__":
    for fn in (fig1, fig2, fig3):
        print("wrote", fn())
