# VERIFIED REGISTRY — can_timing_fidelity

> 本文件是数字的唯一权威来源。paper-writing 用
> `% src:VERIFIED_REGISTRY.md:row=<PK>,col=<header>` 引用。
> ⛔ row PK 与表头一经写入**不得改名或重排**，只能向右追加新列（SKILL_CONTRACT §11.5）。

## Experiment Results — 2026-08-11

来源 CSV：`results/jitter_sensitivity.csv`
⛔ **2026-08-12 更新（registry 漂移修复）**：Arm C 三臂重跑已于 2026-08-11 晚完成落盘，
但本文件当时未同步，仍记两臂版本。现更正——
**当前 sha256 `0f679a21ef9183ce0bcc6045c4125c6a70346805bc5363b20ef2a21e08919de2`，行数 8178，
45 个 (benchmark × arm × level) 组，arm ∈ {A, B, C, none}。**
（旧两臂版本 sha256 `52c007e6bdd02ef4d5eb1aafb942d684fdf6a5bf06540e9c67ab9485b76b1ade` / 5278 行，
其数值为当前文件的子集，下方两臂表格未受影响，仍逐行有效。）
硬件：MacBook M5 Max 本地 18 核 / 12 workers。
seeds：0-9（Arm A/B/C 各 10 个），level=0 无 seed（确定性）。

三臂定义（论文用词以此为准）：
- **Arm A = 加性绝对测量噪声**：`t' = t + N(0,s)`，s ∈ {1, 10, 100, 1000} µs（全部帧）
- **Arm B = gap 比例抖动 + 累积漂移**：cumsum 重建，σ ∈ {0.05, 0.1, 0.2, 0.5, 1.0}
  ⛔ 论文中**必须**称 "jitter + cumulative drift"，不得称纯抖动臂
- **Arm C = 有界 gap 比例抖动（无漂移）**：`t'_i = t_i + ε_i·g_i`，ε~N(0,σ) i.i.d.，同 σ 网格

<!-- src-anchor: row PK = `Condition` 列; col PK = 表头名。二者 LOCKED，仅可向右追加。 -->

| Condition | Baseline trivial F1 | Perturbed trivial F1 | Baseline oracle F1 | Perturbed oracle F1 | n files | Source file |
|-----------|--------------------|--------------------|-------------------|--------------------|---------|-------------|
| CTAT_armA_100us | 0.3076 | 0.3043 | 0.6666 | 0.6638 | 40 | results/jitter_sensitivity.csv |
| CTAT_armA_1000us | 0.3076 | 0.3258 | 0.6666 | 0.5947 | 40 | results/jitter_sensitivity.csv |
| CTAT_armB_sigma020 | 0.3076 | 0.2757 | 0.6666 | 0.5894 | 40 | results/jitter_sensitivity.csv |
| CTAT_armB_sigma050 | 0.3076 | 0.2487 | 0.6666 | 0.4575 | 40 | results/jitter_sensitivity.csv |
| CTAT_armB_sigma100 | 0.3076 | 0.0965 | 0.6666 | 0.2700 | 40 | results/jitter_sensitivity.csv |
| ROAD_armA_100us | 0.0038 | 0.0055 | 0.1978 | 0.1928 | 13 | results/jitter_sensitivity.csv |
| ROAD_armB_sigma020 | 0.0038 | 0.0071 | 0.1978 | 0.0856 | 13 | results/jitter_sensitivity.csv |
| ROAD_armB_sigma100 | 0.0038 | 0.0018 | 0.1978 | 0.0422 | 13 | results/jitter_sensitivity.csv |
| SynCAN_armB_sigma100 | 0.1499 | 0.0741 | 0.3557 | 0.3306 | 5 | results/jitter_sensitivity.csv |

单文件关键格（10-seed 均值±std）：

| Condition | trivial F1 | oracle F1 | Source file |
|-----------|-----------|-----------|-------------|
| rpm3_baseline | 0.8631 | 0.8859 | results/jitter_sensitivity.csv |
| rpm3_armA_100us | 0.8630 ± 0.0013 | 0.8859 ± 0.0000 | results/jitter_sensitivity.csv |
| rpm3_armB_sigma020 | 0.8560 ± 0.0018 | 0.8859 ± 0.0006 | results/jitter_sensitivity.csv |
| rpm3_armB_sigma050 | 0.2255 ± 0.0052 | 0.4296 ± 0.0029 | results/jitter_sensitivity.csv |
| forceneutral3_baseline | 0.8862 | 0.9321 | results/jitter_sensitivity.csv |
| forceneutral3_armB_sigma050 | 0.8631 ± 0.0044 | 0.8822 ± 0.0045 | results/jitter_sensitivity.csv |
| forceneutral3_armB_sigma100 | 0.0387 ± 0.0053 | 0.0567 ± 0.0008 | results/jitter_sensitivity.csv |
| corrsig2masq_baseline | 0.0279 | 0.4522 | results/jitter_sensitivity.csv |
| corrsig2masq_armB_sigma100 | 0.0030 ± 0.0015 | 0.0673 ± 0.0016 | results/jitter_sensitivity.csv |
| corrsig2masq_degenerate | — | 0.0654 | results/jitter_sensitivity.csv |

## Statistical Analysis — 2026-08-11

配对 Wilcoxon signed-rank（先对 10 seed 取均值再与 level=0 配对，seed **不**作独立样本），
Holm 校正（每基准 × 每指标 9 个 level）。effect size = Cohen's dz（配对差的标准化均值）。

<!-- src-anchor: row PK = `Comparison` 列; col PK = 表头名。二者 LOCKED，仅可向右追加。 -->

| Comparison | Test | p-value | p-value (Holm) | Effect size (dz) | Significant? | Floor check |
|---|---|---|---|---|---|---|
| CTAT trivial: armA 100µs vs base | Wilcoxon | 2.06e-03 | 1.24e-02 | −0.509 | ✅ Yes | floor 1.8e-12，未饱和 |
| CTAT trivial: armA 1000µs vs base | Wilcoxon | 3.01e-01 | 6.60e-01 | +0.139 | ❌ No | 未饱和 |
| CTAT trivial: armB σ=0.20 vs base | Wilcoxon | 4.05e-03 | 2.03e-02 | −0.327 | ✅ Yes | 未饱和 |
| CTAT trivial: armB σ=1.00 vs base | Wilcoxon | 2.64e-05 | 2.11e-04 | −0.635 | ✅ Yes | 未饱和 |
| CTAT oracle: armA 100µs vs base | Wilcoxon | 1.55e-02 | 4.64e-02 | −0.371 | ✅ Yes | 未饱和 |
| CTAT oracle: armB σ=1.00 vs base | Wilcoxon | 1.14e-07 | 1.03e-06 | −1.325 | ✅ Yes | 未饱和 |
| ROAD oracle: armA 100µs vs base | Wilcoxon | 2.44e-04 | 2.20e-03 | −1.525 | ⚠️ 方向性 | **floor-saturated**（=2⁻¹², n=13 双侧下界） |
| ROAD oracle: armB σ=0.20 vs base | Wilcoxon | 2.44e-04 | 2.20e-03 | −1.591 | ⚠️ 方向性 | **floor-saturated** |
| ROAD oracle: armB σ=1.00 vs base | Wilcoxon | 2.44e-04 | 2.20e-03 | −1.273 | ⚠️ 方向性 | **floor-saturated** |
| SynCAN trivial: armB σ=1.00 vs base | Wilcoxon | 5.62e-01 | 1.00e+00 | −0.436 | ❌ No | floor 0.0625 > 0.05，**n=5 不可能显著** |

**Phase A.2b 统计健全性三问**（逐条）：

- **floor 检查**：ROAD 全部 14 个"显著"单元格 p_raw = 2.44e-04 = 2⁻¹²，正是 n=13 双侧
  Wilcoxon 在 13 个差值全部同号时的最小可达值 → **饱和**，只报方向 + dz，不作强证据。
  SynCAN n=5 的 floor = 0.0625 > 0.05 → **该基准任何结果都不可能显著**，只报描述性。
  CTAT n=40 floor = 1.8e-12，实测最小 p = 1.14e-07 → **未饱和，可作强证据**。
- **独立性**：10 个 seed 先聚合成每文件均值，再与该文件 level=0 配对 → 样本单位 = 文件
  （各自独立捕获），未把同一 seed 网格的不同 cell 当独立样本。
- **多重比较**：每 (基准 × 指标) 内 9 个 level 做 Holm 校正；表中 p-value 与 p-value (Holm) 并列。

## Derived Computations — 2026-08-11

| Derived value | 值 | 口径 |
|---|---|---|
| CTAT 强判别文件崩溃率 (Arm B) | 13/16 文件在 σ≤1.0 跌破基线一半 | 仅统计基线 trivial>0.3 的文件 |
| CTAT 崩溃点中位 (Arm B) | σ = 0.5（最早 σ = 0.2） | 同上 |
| CTAT 崩溃率 (Arm A) | 1/16，且仅在 1000µs；**100µs 下 0/16** | 同上 |
| level=0 与 Phase 3 一致性 | trivial 最大偏差 **0.0000**（7 文件），oracle 全中 | 基线校准 |

## Three-Arm De-confounding — 2026-08-12（新增，论文主结果）

2026-10-03：标题保留历史命名；旧8178行CSV身份由 `phase5/legacy_result_2026-08-11.json` 校验。
该文件不是补签旧运行契约；历史输入/缓存/代码哈希unknown。SynCAN旧训练缓存漏train_2/3/4首行，
修正后的nominal/tau/F1未重算；当前分析和图仍消费明确标记的历史CSV，不冒充新契约运行。

<!-- src-anchor: row PK = `Arm` 列; col PK = 表头名。LOCKED，仅可向右追加。 -->

| Arm | 扰动语义 | CTAT 强判别文件崩溃数 | 最早崩溃 level | 崩溃点中位 |
|---|---|---|---|---|
| A | 加性绝对测量噪声 (µs) | **1 / 16** | 1000 µs | 1000 µs |
| B | gap 比例抖动 + 累积漂移 (σ) | 13 / 16 | 0.2 | **0.5** |
| C | 有界 gap 比例抖动，无漂移 (σ) | 13 / 16 | **0.05** | **0.2** |

**2026-10-03 判读范围修正（数字不变）**：Arm C 不累积位置误差，也发生崩溃
（中位 0.2 vs Arm B 的0.5），说明累积漂移不是发生崩溃的必要条件。
B/C 的区间噪声幅度、分布与相关结构不同，不能据此隔离漂移的影响，也不能证明漂移掩盖效应。
旧“漂移部分掩盖、可以归因于抖动类型”的确定因果判读撤回；保留各测试扰动下的敏感性读数。

| CTAT 40 文件均值 trivial | 基线 | σ=0.05 | σ=0.1 | σ=0.2 | σ=0.5 | σ=1.0 |
|---|---|---|---|---|---|---|
| Arm B | 0.3076 | 0.2811 | 0.2740 | 0.2757 | 0.2487 | 0.0965 |
| **Arm C** | 0.3076 | **0.2792** | 0.2980 | **0.1930** | **0.0797** | 0.0786 |

| ROAD 13 文件均值 oracle（退化解 0.0411） | 基线 | — |
|---|---|---|
| Arm A | 0.1978 | 1µs 0.1978 / 10µs 0.1976 / 100µs 0.1928 / 1000µs 0.1324 |
| Arm B | 0.1978 | σ0.05 0.1762 / 0.1 0.1436 / 0.2 0.0856 / 0.5 0.0471 / 1.0 0.0422 |
| **Arm C** | 0.1978 | σ0.05 0.1566 / 0.1 0.1009 / 0.2 0.0569 / 0.5 **0.0419** / 1.0 **0.0417** |

→ ROAD 的弱信号在 Arm C 的 σ≥0.5 处落到退化解 0.0411（差 0.0008），即**零判别性**。

⛔ **与真实时钟对照（自我否定 #1，论文必须照写）**：CrySyS 真实良性档实测
σ_real 中位 **0.0187**、p90 0.126、76% < 0.05。在**最小测试点 Arm C σ=0.05**，
CTAT 判别性 0.3076 → 0.2792，下降 **9.2%**；0.05高于真实时钟中位0.0187，
未测试0.0187，不能把9.2%称为该点实测或插值。崩溃点中位为σ=0.2。
**因此"合成钟让判别性虚高、真实钟下会翻转"这一说法被本项目自己的数据否掉，不得写入论文。**

```yaml
compute-anchor:
  value: "Arm A 崩溃 1/16(仅1000µs); Arm B 13/16 中位σ=0.5; Arm C 13/16 中位σ=0.2 最早0.05; CTAT ArmC σ=0.05 → 0.2792 (基线 0.3076, -9.2%); ROAD ArmC σ≥0.5 oracle 0.0419 ≈ 退化解 0.0411"
  script: phase5/three_arm_analysis.py
  cmd: /opt/anaconda3/bin/python3 phase5/three_arm_analysis.py
  stdout: "Arm A: collapsed 1/16  earliest=1000.0  median=1000.0 / Arm B: collapsed 13/16  earliest=0.2  median=0.5 / Arm C: collapsed 13/16  earliest=0.05  median=0.2"
  input_files:
    - results/jitter_sensitivity.csv  # sha256 0f679a21ef9183ce0bcc6045c4125c6a70346805bc5363b20ef2a21e08919de2, 8178 行
  ran_at: 2026-08-12
  note: "⛔ 2026-08-12 claim-verify B.8 修复：原 script 字段写的是「内联 pandas 复算（见 session 记录）」，
         不是可解析路径 → B.8 判 FAIL。已把计算落盘为 phase5/three_arm_analysis.py 并复跑，
         逐位复现本节全部数字。修法是补脚本，不是删 anchor。"
```

```yaml
compute-anchor:
  value: "崩溃率 13/16, 中位崩溃点 σ=0.5, Arm A@100µs 崩溃 0/16"
  script: phase5/analyze.py            # Phase A.4 段
  cmd: /opt/anaconda3/bin/python3 phase5/analyze.py
  stdout: "ctat    n=16  崩溃文件 13/16  最小崩溃 level=0.2  中位=0.5 / ctat n=16 崩溃文件 1/16 最小崩溃 level=1000.0"
  input_files:
    - results/jitter_sensitivity_AB_only.csv.bak  # historical two-arm snapshot; sha256 52c007e6bdd02ef4d5eb1aafb942d684fdf6a5bf06540e9c67ab9485b76b1ade
  ran_at: 2026-08-11
```

---

## Timing-Fidelity Audit (Phase 1-3, 6) — graduated 2026-08-12

> 本节把 Phase 1/2/3/6 的论文级数字从各 summary 收编为权威行，供 paper 用
> `% src:VERIFIED_REGISTRY.md:row=<PK>,col=<header>` 引用。
> 数值来源逐条标注；凡 REVIEW_2026-08-11 撤销过的量（网格/量化/对齐族）一律不入册。

<!-- src-anchor: row PK = `Key` 列; col PK = 表头名。LOCKED，仅可向右追加。 -->

| Key | Value | Unit | Source |
|-----|-------|------|--------|
| road_files_rewritten | 45/45 | files | phase1_summary.md 总判定表 |
| road_dt_median_ambient | 1.000 | µs (exact int) | audit/REVIEW_2026-08-11.md C1 |
| road_dt_median_masquerade | 2.000 | µs (exact int) | audit/REVIEW_2026-08-11.md C1 |
| road_rho_below_floor | 0.6408 | fraction < 47µs, pooled over 45 files (28,244,494 gaps) | ⛔ 2026-08-12 更正，原值 0.6268 是单文件 ambient_dyno_reverse.log 的值，见 audit/CORRECTION_2026-08-12_rho_scope.md。⚠️ 2026-08-14 补记 scope：正文 headline「64.1%」在两处指两个不同总体 —— Table 1 用本行 0.6408（45 文件），Figure 1(b) 与 Table 2 用 0.6409（12 ambient captures，24,149,507 frame pairs）。两者三位有效数字一致，故同印为 64.1%；引用该数时必须先确认指的是哪个总体，不得互相替换。 |
| road_sigext_rho_pooled | 0.6270 | fraction < 47µs，signal_extractions 全树池化（46 文件 / 27,117,377 gaps） | audit/signal_extraction_floor.py（2026-08-16 建，回应 cross-model reviewer 的 MAJOR 2：审计跑在 candump 上，而检测器读 signal extractions，缺陷必须在后者也证明） |
| road_perid_rho_symmetric | 0.004997 | fraction < 47µs，**同标识符区间**（12 ambient captures / 24,148,247 intervals）⛔ 非零 | audit/perid_symmetric_rho.py（2026-08-16 建，回应 cross-model reviewer M5：两个投影用了不对称判据——总线级用 any-gap ρ<，标识符级只用中位数） |
| road_perid_rho_worst_file | 0.00717 | 同上，逐文件最大 | audit/perid_symmetric_rho.py（2026-08-16 建，回应 cross-model reviewer M5：两个投影用了不对称判据——总线级用 any-gap ρ<，标识符级只用中位数） |
| road_projection_ratio | 128 | 同判据下 总线级ρ< / 标识符级ρ< 的倍数 | audit/perid_symmetric_rho.py（2026-08-16 建，回应 cross-model reviewer M5：两个投影用了不对称判据——总线级用 any-gap ρ<，标识符级只用中位数） |
| road_sigext_rho_range | 0.6092-0.6591 | 同上，逐文件区间 | audit/signal_extraction_floor.py（2026-08-16 建，回应 cross-model reviewer 的 MAJOR 2：审计跑在 candump 上，而检测器读 signal extractions，缺陷必须在后者也证明） |
| road_sigext_files_above_half | 46/46 | signal_extraction 文件中 ρ<>0.5 的个数 | audit/signal_extraction_floor.py（2026-08-16 建，回应 cross-model reviewer 的 MAJOR 2：审计跑在 candump 上，而检测器读 signal extractions，缺陷必须在后者也证明） |
| road_sigext_median_us_range | 1.1-2.0 | µs，逐文件中位间隔 | audit/signal_extraction_floor.py（2026-08-16 建，回应 cross-model reviewer 的 MAJOR 2：审计跑在 candump 上，而检测器读 signal extractions，缺陷必须在后者也证明） |
| road_rho_perfile_range | 0.6189-0.6668 | fraction < 47µs, per-file (median 0.6388) | 同上，独立复算 |
| road_dt_eq_1us_ambient | 0.5495 | fraction of gaps in ambient_dyno_exercise_all_bits.log | ⛔ 2026-08-12 claim-verify 更正：分子 2428557 对，**分母错**（旧写 4369841，真值 4419421）→ 0.556 应为 0.5495 |
| road_dt_eq_1us_masquerade | 0.4676 | fraction of gaps in correlated_signal_attack_1_masquerade.log | ⛔ 2026-08-12 更正：分母旧写 78308，真值 79175 → 0.473 应为 0.4676 |
| road_zero_gaps_frac | 0.012319 | fraction of ROAD ambient bus-level gaps that are **exactly 0 µs**（297,500 / 24,149,507，12 files；per-file 0.8940%–1.5645%）—— 两帧共用同一微秒时间戳，单条共享总线上物理不可能 | audit/zero_gap_count.py（2026-08-22 建，回应 cross-check HIGH-1：GLM 把 Figure 4(b) 的柱子加起来得 63.64% 而标注 64.1%） |
| road_hist_visible_below | 0.636410 | Figure 4(b) 柱子**可见**的 <47µs 部分 = (15,477,149−297,500)/(24,149,507−297,500)。与 ρ_<=0.640889 的差额**全部**是 log 轴画不出的零间隔；make_fig_projection.py 的 logbins(lo_exp=0) 把 <1µs 全丢掉 | audit/zero_gap_count.py；与 GLM 手工求和 63.64% 四位小数一致 |
| road_band_46_47_count | 0 | ROAD ambient 24,149,507 个 gap 中落在 **[46,47) µs** 的个数。ISO 11898-1 的 intermission 第 3 位 SOF 例外允许 46 位时间下界；实测该带内**一个都没有**，故 ρ_< 在 47 与 46 两种下界下完全相同（均 0.640889）。⛔ 2026-08-26 扩展：**45 文件全量同样为零**（attack 33 文件 4,094,987 gaps 亦 0），background §2.1 的全称句自此按全量口径引用 | audit/zero_gap_count.py 同源解析；2026-08-25 复算回应 cross-check Claude 席 MEDIUM #8；45 全量 = audit/disputed_band.py 2026-08-26 |
| road_total_gaps_45file | 28244494 | ROAD **45 文件全量** bus-level gaps（ambient 24,149,507 + attack 4,094,987）。background §2.1 争议带句 2026-08-26 起引用此数（旧文误用 ambient 口径 24,149,507 充当 ROAD 全体） | audit/floor_recompute_2026-08-12.json pooled n=28,244,494；独立复算 audit/disputed_band.py 同值 |
| ctat_band_46_47_count | 2546 | can-train-and-test set\_01 全 52 文件 normal-frame 序列的 [46,47) µs 计数。若下界改 46：0.6539 第四位小数动 1，printed 65.4% **不动**。rebuttal 弹药，未入正文 | audit/band_paper_scope.py 2026-08-26（Decimal 精确差分） |
| crysys_benign_band_46_47 | 1 | CrySyS 26 benign 的 12 个 sub-floor gaps 中恰 **1 个 = 46 µs**。下界改 46 时 pooled ρ_< 0.00000218→0.00000200（printed 0.00022%→0.00020%，**会动**）；论文保留 47 = 让对照语料的 ρ_< 显得略高 = 对自身论点保守的方向。rebuttal 弹药，未入正文 | audit/band_paper_scope.py 2026-08-26（整数微秒精确计数） |
| road_ambient_epoch_1e7 | 12/12 | ⛔ 2026-08-26 新增（第四轮 Claude 席实测）：**全部 12 个 ambient 文件起始时间戳为 k×10⁷ 秒整**（1030000000.000000 … 1110000000.000000）——比 integer-second 强 7 个数量级的 per-file canonical rebasing 证据，同时**反证 corpus-wide 单一 scalar**（若单 scalar 则 45 个独立 session 起点不可能全落 10⁷ 网格）。rebuttal 弹药：ROAD 作者若辩"scalar 是 per-file 的"，此数即回应（per-file rebasing 无任何 published statement 覆盖）。未入正文 | 第四轮 _claude_review.md Finding 4；raw logs 首行时间戳直读 |
| syncan_masq_oracle 更正 | — | ⛔ 2026-08-26 更正：本表旧行 `syncan_masq_oracle` 的 suppress/continuous 两值**标签转置**（旧记 suppress=0.2358 / continuous=0.2794）。真值 = **suppress 0.2794 / continuous 0.2358**（phase3/audit_phase3.json test_suppress f1=0.2794, test_continuous f1=0.2358）。⚠️ **论文正文是对的**（playback/plateau/suppression/continuous = 0.2328/0.2806/0.2794/0.2358），转置只在本表——按本表旧行"纠正"论文会把对的改错。转置根因：phase3_summary.md 按 playback/plateau/continuous/suppress 顺序列值，本表换序重标时错位 | 第四轮 _claude_review.md Finding 7；audit_phase3.json 为准 |
| road_span_ratio | 1.000 | ratio vs declared elapsed_sec | phase2_summary.md 任务② |
| road_epoch_integer | 45/45 | files | phase1_summary.md |
| ctat_files_rewritten | 48/52 | files (normal-frame median gap < 47 µs) | ⛔ 2026-08-12 更正，原写 52/52；4 个 train_01 文件正常帧 dt 中位 248-253 µs 物理合理 |
| ctat_files_plausible | 4/52 | files (accessory-1/2, attack-free-1/2, all in train_01) | 同上 |
| ctat_epoch_integer | 52/52 | files start on integer second (incl. the 4 plausible) | 同上 |
| ctat_dt_median_normal | 11.0 | µs, median over the 48 affected files (range 8.8-17.8) | 2026-08-12 独立复算，与 REVIEW C2 的 11.09 一致 |
| ctat_rho_below_floor | 0.6539 | fraction < 47µs, pooled over the 48 affected files (40,505,015 normal-frame gaps) | ⛔ 2026-08-12 两次更正：原值 0.615 是文件级值→0.6544（口径修正）→0.6539（下限修正） | ⛔ 2026-08-12 paper-cross-check Gate 6 更正：下限由 135µs@"500kbps" 改为 **47µs 通用界**（最短合法帧 44 bit + IFS 3 bit @ 1 Mbit/s 上限）。两处错叠加：① 135 是**比特数**不是 µs，且三个语料**都无波特率文档**，"500kbps" 是无来源假设；② 55+10ℓ 是**满位填充最大值**，拿上界推下界方向反了，下界须用最短帧 47+8ℓ。复跑 audit/recompute_floor.py，per-file 全表落 audit/floor_recompute_2026-08-12.json |
| ctat_rho_perfile_range | 0.6143-0.7922 | fraction < 47µs, per-file among the 48 (median 0.6263) | | ⛔ 2026-08-12 paper-cross-check Gate 6 更正：下限由 135µs@"500kbps" 改为 **47µs 通用界**（最短合法帧 44 bit + IFS 3 bit @ 1 Mbit/s 上限）。两处错叠加：① 135 是**比特数**不是 µs，且三个语料**都无波特率文档**，"500kbps" 是无来源假设；② 55+10ℓ 是**满位填充最大值**，拿上界推下界方向反了，下界须用最短帧 47+8ℓ。复跑 audit/recompute_floor.py，per-file 全表落 audit/floor_recompute_2026-08-12.json |
| ctat_plausible_dt_median | 248-253 | µs, the 4 plausible files | 同上 |
| ctat_dt_median_attack | 2943.2 | µs | REVIEW F4（全 CTAT 整体） |
| ctat_attack_cv | 0.1078 | 攻击帧 gap 变异系数，**仅 test_01/rpm-3.csv 单文件**（该文件中位 3003 µs） | ⛔⛔ **2026-08-13 双重更正**。原：与 2943 µs 并列写成「48 文件攻击帧」统计量——**两个数来自两个不同文件**（2943=test_03/speed-3，CV 0.1078=rpm-3），且三种口径无一给出 2943 作为 48 文件值（median-of-medians 11,149 µs / pooled 808 µs）。首次更正把中位归给 speed-3 却把 CV 留在原处 → **变成「点名一个文件、报另一个文件的数」，比原来更糟**（speed-3 实测 CV=0.0877）。现统一用 rpm-3 举例（3003 µs / CV 0.1078 自洽），表格改用真实 48 文件跨度 0.7–1000 ms。由 lane-repro 两次抓出（第二次是实时抓我的修复）|
| ctat_attack_inversion | 0.002315 | fraction (440/190088) | REVIEW F4 精确命中 |
| ctat_sparsification | 2.12 | ms (n=3161) | REVIEW F4 修订值（原 1.17ms 作废） |
| ctat_sparsification_ratio | 189.6 | x, in rpm-3.csv specifically | 2026-08-12 复算：该文件正常帧 dt 中位 11.20µs、跨攻击帧游程间距中位 2.1230ms (n=3161)、比值 189.6（⛔ 原记"恰 190"不成立，论文写的是 "roughly 190" 无碍）|
| ctat_rpm3_normal_dt | 11.20 | µs, rpm-3.csv only (corpus median over the 48 is 11.0) | ⛔ 2026-08-12 claim-verify 补：论文同段并用 11.0 与 11.2 却未写口径 |
| ctat_plausible_rho | 0.00048 | fraction < 47µs, the 4 plausible files pooled (range 0.000209-0.000690) | 2026-08-12 补（lane 指出无对应行）；⛔ 2026-08-12 paper-cross-check Gate 6 更正：下限由 135µs@"500kbps" 改为 **47µs 通用界**（最短合法帧 44 bit + IFS 3 bit @ 1 Mbit/s 上限）。两处错叠加：① 135 是**比特数**不是 µs，且三个语料**都无波特率文档**，"500kbps" 是无来源假设；② 55+10ℓ 是**满位填充最大值**，拿上界推下界方向反了，下界须用最短帧 47+8ℓ。复跑 audit/recompute_floor.py，per-file 全表落 audit/floor_recompute_2026-08-12.json |
| crysys_benign_files | 26 | benign recordings | 2026-08-12 补（lane 指出无对应行）；来源 CrySyS 官方论文与 phase6_summary |
| crysys_ks_wrong_way_D | 0.88 | KS D when pooling all IDs (the WRONG comparison, cited as an anti-pattern) | 2026-08-12 补（lane 指出无对应行）；phase6_summary.md 警示段 |
| syncan_official_synthetic | 10/10 | files | phase1_summary.md（官方 README 明示） |
| crysys_benign_dt_median_lo | 241 | µs | phase6_summary.md（26 段良性录制下界） |
| crysys_benign_dt_median_hi | 599 | µs | phase6_summary.md（上界） |
| crysys_rho_below_floor_max | 0.00005584 | fraction < 47µs, per-file max (S-1-1-benign) | phase6_summary.md 的 0.0004 是按旧 135µs 下限算的；⛔ 2026-08-12 paper-cross-check Gate 6 更正：下限由 135µs@"500kbps" 改为 **47µs 通用界**（最短合法帧 44 bit + IFS 3 bit @ 1 Mbit/s 上限）。两处错叠加：① 135 是**比特数**不是 µs，且三个语料**都无波特率文档**，"500kbps" 是无来源假设；② 55+10ℓ 是**满位填充最大值**，拿上界推下界方向反了，下界须用最短帧 47+8ℓ。复跑 audit/recompute_floor.py，per-file 全表落 audit/floor_recompute_2026-08-12.json |
| crysys_rho_below_floor_pooled | 0.00000218 | fraction < 47µs, pooled over 26 benign (5,500,448 gaps) | audit/recompute_floor.py 2026-08-12 |
| perfile_road_median_below_floor | 45 | files of 45，逐文件中位间隔 < 47µs | floor_recompute_2026-08-12.json per_file，经 make_fig_perfile.py 复算 |
| perfile_ctat_median_below_floor | 48 | files of 52，同上 | floor_recompute_2026-08-12.json per_file，经 make_fig_perfile.py 复算 |
| perfile_crysys_median_below_floor | 0 | files of 26，同上 | floor_recompute_2026-08-12.json per_file，经 make_fig_perfile.py 复算 |
| crysys_files_rho_exactly_zero | 17 | files of 26，ρ< **恰好等于 0**（非四舍五入；每文件约 18,000 个间隔无一低于下界） | floor_recompute_2026-08-12.json per_file，经 make_fig_perfile.py 复算 |
| crysys_zero_files_gaps_total | 1403415 | 该 17 个文件的间隔总数，其中低于下界者为 0 | audit/floor_recompute_2026-08-12.json per_file 求和（2026-08-16 复算）。⛔ 我原先在 caption 写「每文件约 18,000」是看列表头几条外推的，实际逐文件 17,403–334,979（19 倍跨度），cross-model reviewer M4 抓到 |
| perfile_empty_band_lo | 0.00069028 | ρ< of the highest-ρ passing file（CTAT attack-free-1） | floor_recompute_2026-08-12.json per_file，经 make_fig_perfile.py 复算 |
| perfile_empty_band_hi | 0.6143 | ρ< of the lowest-ρ failing file | floor_recompute_2026-08-12.json per_file，经 make_fig_perfile.py 复算 |
| perfile_empty_band_ratio | 890 | hi/lo，空带宽度倍数 | floor_recompute_2026-08-12.json per_file，经 make_fig_perfile.py 复算（derived） |
| perfile_empty_band_inside | 0 | files of 123 落在空带内 | floor_recompute_2026-08-12.json per_file，经 make_fig_perfile.py 复算 |
| crysys_msgmod_trivial_f1 | 0.0000 | F1, all 624 files | phase6_summary.md（range [0,0]） |
| crysys_msgmod_oracle_median | 0.0157 | F1 | phase6_summary.md（range 0.0018-0.1200） |
| crysys_msgmod_degenerate_median | 0.0095 | F1 | phase6_summary.md |
| crysys_oracle_above_degenerate | 192/624 | files (>+0.02) | phase6_summary.md |
| crysys_ks_file1 | S-1-1-malicious-ADD-DECR-msg-mod-0x410-0.4-0.6 | capture name (full) | ⛔ 2026-08-12 claim-verify 补全：原只写 "S-1-1-ADD-DECR"，缺比例后缀致不可复现 |
| crysys_ks_p1 | 0.0591 | p-value (D=0.1866, n=60 modified / 239 benign) | phase6/ks_same_id_test.py 复现 |
| crysys_ks_file2 | S-2-6-malicious-POS_OFFSET-msg-mod-0x410-0.5-0.55 | capture name (full) | ⛔ 2026-08-12 claim-verify 补全：**是 0.5-0.55 变体不是 0.4-0.6**；0.4-0.6 变体给 D=0.0847/p=0.8526，与论文数字不符 |
| crysys_ks_p2 | 0.5875 | p-value (D=0.1884, n=16 modified / 294 benign) | phase6/ks_same_id_test.py 复现 |
| sigma_real_median | 0.0187 | dimensionless | NEXT_SESSION_PROMPT.md（408 file×ID） |
| sigma_real_p90 | 0.126 | dimensionless | 同上 |
| sigma_real_below_005 | 0.76 | fraction | 同上 |
| road_aid_count | 106 | distinct arbitration IDs across the 12 ambient captures | ⛔ 2026-08-12 更正（原 105），独立复算 |
| road_aid_series | 1270 | (capture, ID) series with >=20 samples | 2026-08-12 独立复算 |
| road_aid_median_period | 100 | ms | 同上 |
| road_aid_fastest | 5.36 | ms (single fastest ID) | ⛔ 2026-08-12 更正：原写"最快 8 个 10.00-10.01ms"不准 |
| road_aid_fastest_cluster | 10.00-10.01 | ms (the next seven IDs) | 同上 |
| road_aid_implausible | 0/106 | AIDs (pooled); 0/1270 (capture, ID) series | ⛔ 2026-08-12 更正 |
| road_bus_dt_median | 1 | µs, **精确整数**，12 个 ambient 池化 24,149,507 个 gap | ⛔ 2026-08-12 Gate 6 更正：原值 **1.19 不可能是中位**（整数数据的中位只能是整数或 x.5），来自 NOVELTY_AUDIT.md 的过期口径。deepseek 席指出它与全文「精确整数微秒」自相矛盾 |
| road_bus_dt_mean | 444.2 | µs, 同一池化 | ⛔ 同上更正（原 472）。⚠️ `figure_manifest.md` 里 Figure 1 生成脚本早已记 444.2 —— **图与表长期不一致而无人发现**，与 2026-08-09 TNSM 教训同型（图不在既有 gate 的扫描面内） |
| road_masq_trivial_max | 0.0279 | F1 | phase3_summary.md（13 masquerade 全 ≤此值） |
| road_masq_oracle_range | 0.0577-0.4522 | F1 | phase3_summary.md（全阈值扫描后） |
| road_masq_degenerate_range | 0.055-0.065 | F1 | phase3_summary.md |
| road_masq_best_precision | 0.37-0.48 | precision | phase3_summary.md（最好三个文件） |
| road_masq_best_recall | 0.38-0.43 | recall | 同上 |
| ctat_rpm3_trivial | 0.8631 | F1 | phase3_summary.md |
| ctat_rpm3_oracle | 0.8859 | F1 | phase3_summary.md |
| ctat_fn3_trivial | 0.8862 | F1 | phase3_summary.md |
| ctat_fn3_oracle | 0.9321 | F1 | phase3_summary.md |
| ctat_dos3_trivial | 0.019 | F1 | phase3_summary.md（DoS-3） |
| ctat_dos3_oracle | 0.9576 | F1 (P 0.919 / R 0.9998) | phase3_summary.md（原"DoS 不可检"已推翻） |
| ctat_dos3_degenerate | 0.222 | F1 | phase3_summary.md |
| ctat_unknown_trivial_range | 0.004-0.206 | F1 | phase3_summary.md（test_04 未知车） |
| ctat_unknown_oracle_range | 0.30-0.975 | F1 | phase3_summary.md（speed-3 = 0.9750, P 0.95 / R 1.00） |
| ctat_construction_ratio | 268 | × (攻击帧中位间距 2943.2µs ÷ 正常帧中位 11.0µs = 267.6) | ⛔⛔ **2026-08-13 起已从正文全部撤下，不得再引用作「为什么 per-identifier F1 高」的解释**。数值本身没错，但**两个量都是 bus-level**，而被解释的判别器读的是 same-identifier 间隔——拿 bus-level 比值解释 per-identifier 分数，正是本文自己指控的 projection 混用。改用 `ctat_perid_dev_separation`。（2026-08-12 Gate 3b 那次只更正了 273→268 的跨口径混算，没看出整个量就用错了投影。） |
| ctat_perid_dev_separation | 攻击 dev 中位 0.22 / 良性 1.00；良性 p05 0.92 > 攻击 p95 0.28 | dev = 同 ID 间隔 ÷ nominal（式 5） | `audit/ctat_projection_separation.py`（test_01/rpm-3，train=train_01/rpm-1,2）。同 ID 间隔：攻击 2.9ms vs 良性 12.9ms；nominal 中位 **99.9ms**（51 个 ID）——⛔ 顺带证伪 `phase3/phase3_summary.md` 里「11µs 合成 nominal」那句，正是那句让 bus-level 与 per-identifier 看起来重合、把错误藏了下来 |
| crysys_oracle_degenerate_excess | oracle 中位 0.0157 vs degenerate 中位 0.0095；624/624 文件 oracle>degenerate，超出量中位 +0.0031、最大 +0.0707、192/624 超 0.02 | F1 | `results/crysys_discriminability.csv` 实算（2026-08-13）。⛔ **对一处真实错误的更正**：正文原写「oracle bound sits at the degenerate solution, so no threshold beats flagging every frame」——与本文 Table 4 印的 0.0157/0.0095 直接矛盾，也不满足 method.tex §3.4 自定的 `F1_orc≈F1_deg` 授权条件（相对超出 65%）。对照 SynCAN masquerade 族超出量 ±0.0001，那才是真 degenerate。lane-positive 抓出，主 agent 独立复算 |
| armC_effective_magnitude | Arm C 相对区间抖动 = σ√2（实测 σ=0.2 时 0.2834 vs 名义 0.2），相邻区间自相关 −0.501；Arm B 为 σ（实测 0.2022）、自相关 0 | 无量纲 | 解析+仿真（n=2e5, seed 0）：Arm C 定义 t'=t+ε·δ ⇒ δ'_i = δ_i + ε_i δ_i − ε_{i-1} δ_{i-1}，相邻区间共享扰动项 ⇒ Var ∝ 2σ²。⛔ **论文原写 'the same multiplicative magnitude' 不精确**——C 的等效幅度是 B 的 √2 倍，即 B-vs-C 对比并非等幅。折算：C 崩溃中位 σ=0.2 → B 口径 0.28，仍早于 B 的 0.5，**仅在等间隔近似下作幅度换算，排序余量从 2.5× 收窄到约 1.8×；这不隔离漂移效应**。已在 method.tex 显式披露。由 lane-coldread 提出（δ 改写后仍存活）、lane-repro 从代码确证，主 agent 仿真复核 |
| crysys_subtype_split | 单 ID 312 文件：median(oracle) 0.0054 / median(degenerate) 0.0039；**逐文件之差的中位 0.0010**（注意 ≠ 两个中位数之差 0.0015，两者都对但口径不同）。DOUBLE 312 文件：0.0848 / 0.0411 / 逐文件之差中位 +0.0251 | F1 | `audit/double_split_check.py` + `results/crysys_discriminability.csv` 按文件名子类分组实算。六个单 ID 子类各 52 文件，小数点后四位完全一致。⛔ 池化的 +0.0031 是混合伪影。⛔ **正文曾写「the oracle stands 0.0010 above the degenerate」并同时引用 0.0054/0.0039 → 页面上减不出来**（读者会得 0.0015）。已改为显式标注「per-file excess … median」。由 lane-repro 实时抓出 |
| crysys_oracle_null_excess | 零信号零假设下 oracle 超出量：中位 +0.0015、均值 +0.0030（实测为 +0.0031 / +0.0134）；observed>null 的文件 377/624 | F1 | `audit/null_oracle_check.py`（400 trials/file, seed 0）。⛔ **本行记录一次「我未验证就写进论文」的失误**：曾据 lane-positive 的机制建议写入「an excess of the size label-aware threshold selection yields on noise」，该机制**当时无人验证**。lane-positive 事后自纠并实算：零假设只解释约**一半**中位超出量、约五分之一均值超出量。→ 「超出量**就是**选择噪声」**不成立**；「超出量与选择噪声**同量级**」成立。正文已改回论文中已验证过的措辞 “a margin far too small to support evaluation”，**不再主张任何机制** |
| syncan_masq_oracle | 0.2328/0.2806/0.2358/0.2794 | F1 = degenerate 2p/(1+p) | phase3_summary.md（playback/plateau/suppress/continuous） |
| syncan_flooding | 0.7497 | F1 (trivial = oracle) | phase3_summary.md |
| collapse_model_rho | 0.699 | Spearman，**Arm B**，80 个 (file,σ) 对 (p=5.8e-13) | phase5/collapse_recall_check.py（2026-08-14 建；复算 Arm B，ρ=0.6986 p=5.81e-13 n=80 MAE_med=0.0338 <0.10:13/16）；⛔ MAE 口径 = 逐文件均值再取中位（非 80 点池化中位 0.011） |
| collapse_model_mae_median | 0.034 | 逐文件 MAE 的中位数（16 文件） | phase5/collapse_recall_check.py（2026-08-14 建；复算 Arm B，ρ=0.6986 p=5.81e-13 n=80 MAE_med=0.0338 <0.10:13/16）；⛔ MAE 口径 = 逐文件均值再取中位（非 80 点池化中位 0.011） |
| collapse_model_fit_files | 13/16 | files with per-file MAE<0.10 | phase5/collapse_recall_check.py（2026-08-14 建；复算 Arm B，ρ=0.6986 p=5.81e-13 n=80 MAE_med=0.0338 <0.10:13/16）；⛔ MAE 口径 = 逐文件均值再取中位（非 80 点池化中位 0.011） |
| collapse_model_counterexample_mae | 0.60/0.57 | per-file MAE，**interval-3=0.595、interval-4=0.571**（⛔ 原记 "0.57/0.60 (interval-3/4)" 顺序与文件对反了，2026-08-14 复算更正；正文只写"0.57 和 0.60"未指名，正文无误） | phase5/collapse_recall_check.py（2026-08-14 建；复算 Arm B，ρ=0.6986 p=5.81e-13 n=80 MAE_med=0.0338 <0.10:13/16）；⛔ MAE 口径 = 逐文件均值再取中位（非 80 点池化中位 0.011） |
| audited_files_total | 107 | files (45+52+10) | audit_phase1.json 完整性复验 |
| physical_floor_universal | 47 | µs, **任何合法 classic-CAN 配置**（最短帧 44 bit + IFS 3 bit ÷ 最高标准速率 1 Mbit/s） | 本文 Eq.(1)；audit/recompute_floor.py 逐字段核对⛔ 2026-08-12 paper-cross-check Gate 6 更正：下限由 135µs@"500kbps" 改为 **47µs 通用界**（最短合法帧 44 bit + IFS 3 bit @ 1 Mbit/s 上限）。两处错叠加：① 135 是**比特数**不是 µs，且三个语料**都无波特率文档**，"500kbps" 是无来源假设；② 55+10ℓ 是**满位填充最大值**，拿上界推下界方向反了，下界须用最短帧 47+8ℓ。复跑 audit/recompute_floor.py，per-file 全表落 audit/floor_recompute_2026-08-12.json |
| physical_floor_8byte_1mbit | 111 | µs, 8 字节帧无填充 @1 Mbit/s（更紧的速率相关界，论文不用） | 同上 |
| physical_floor_8byte_worstcase | 135 | µs, 8 字节帧满位填充 @1 Mbit/s = 55+10·8 bit | ⛔ **这是上界不是下界**，旧稿误当下限用，且误标为 "@500 kbit/s"（该速率下应为 270µs） |
| segment_bug_inflation | 0.0279→0.0683 | F1 | phase5/jitter_sensitivity.py:dt_id_of() 自审注释 |

### Three-arm single-value rows (for paper src-markers, 2026-08-12)

> 上方三臂表用"σ0.05 0.1566 / 0.1 …"的串式单元格，不便做 marker 数值比对。
> 此处按单值拆开，值与上表逐一一致。

| Key | Value | Unit | Source |
|-----|-------|------|--------|
| road_oracle_baseline | 0.1978 | F1 | results/jitter_sensitivity.csv (arm=none) |
| road_degenerate | 0.0411 | F1 | results/jitter_sensitivity.csv (degenerate_f1, arm=none) |
| road_armC_sigma050_oracle | 0.0419 | F1 | results/jitter_sensitivity.csv (arm=C, level=0.5) |
| road_armC_sigma100_oracle | 0.0417 | F1 | results/jitter_sensitivity.csv (arm=C, level=1.0) |
| ctat_baseline_trivial | 0.3076 | F1, 40 files | results/jitter_sensitivity.csv (arm=none) |
| ctat_armA_100us_trivial | 0.3043 | F1, 40 files | results/jitter_sensitivity.csv (arm=A, level=100) |
| ctat_armC_sigma005_trivial | 0.2792 | F1, 40 files | results/jitter_sensitivity.csv (arm=C, level=0.05) |
| ctat_armC_sigma020_trivial | 0.1930 | F1, 40 files | results/jitter_sensitivity.csv (arm=C, level=0.2) |
| ctat_armC_drop_sigma005 | 9.2 | percent | tested Arm C sigma=0.05; (0.3076-0.2792)/0.3076; not measured at sigma_real median 0.0187 |
| wilcoxon_floor_ctat | 1.8e-12 | p-value floor, n=40 | VERIFIED_REGISTRY Statistical Analysis 节 |
| wilcoxon_min_observed_ctat | 1.14e-07 | p-value | 同上 |
| wilcoxon_floor_road | 2.44e-04 | p-value floor = 2^-12, n=13 | 同上 |
| wilcoxon_floor_syncan | 0.0625 | p-value floor, n=5 | 同上 |

```yaml
compute-anchor:
  value: "KS same-ID: file1 D=0.1866 p=0.0591 (n=60/239); file2 D=0.1884 p=0.5875 (n=16/294)"
  script: phase6/ks_same_id_test.py
  cmd: /opt/anaconda3/bin/python3 phase6/ks_same_id_test.py
  stdout: "S-1-1-...-0.4-0.6: modified 100.0160ms n=60 / benign 100.0050ms n=239 / KS D=0.1866 p=0.0591 ; S-2-6-...-0.5-0.55: modified 100.0325ms n=16 / benign 100.0100ms n=294 / KS D=0.1884 p=0.5875"
  input_files:
    - ~/Datasets/can_ids/CrySyS/logs/S-1-1-malicious-ADD-DECR-msg-mod-0x410-0.4-0.6.log
    - ~/Datasets/can_ids/CrySyS/logs/S-2-6-malicious-POS_OFFSET-msg-mod-0x410-0.5-0.55.log
  ran_at: 2026-08-12
  note: "⛔ 本脚本因 claim-verify B.5 判定为 phantom experiment 才补写：KS 数字此前只存在于
         phase6_summary.md，无任何脚本可复现。补写后 file1 逐位复现；file2 查出论文引用的
         是 0.5-0.55 变体而非默认的 0.4-0.6，已在论文中写全文件名。"
```

```yaml
compute-anchor:
  value: "Official ROAD archive reproduces the extracted tree bit-for-bit: basic_long rho_<=0.6442 (n=2991271), basic_short 0.6448 (n=1063623), benign_anomaly 0.6280 (n=771518); all start on integer seconds"
  script: audit/verify_official_archive.py
  cmd: /opt/anaconda3/bin/python3 audit/verify_official_archive.py
  stdout: "ambient .log members in archive: 12 / ambient_dyno_drive_basic_long.log first timestamp 1110000000.000000 (integer second: True) gaps n=2991271 median=1 us below 47 us = 0.6442"
  input_files:
    - ~/Datasets/can_ids/ROAD/road.zip   # sha256 0e4fe6ed7f99b5cdabf6b772c91a2025c614a071ba8579c532904d0ef7aea5f6, 556718276 bytes
  ran_at: 2026-08-12 (下限更正后 2026-08-12 复跑，三个 rho 值不变)
  note: "⛔ 因 claim-verify B.5 判定为 phantom experiment 才补写。此前 phase2_summary.md 只写
         『本地 road.zip md5 确认为官方 Zenodo 发行版』而未记 md5 值、无脚本。现改用 sha256
         并直接从 zip 成员流式解析（不解压落盘），三个抽样文件与提取树逐位一致。
         ⚠️ zip 内有 macOS AppleDouble (._*) 资源叉文件，必须过滤，否则 member 数会数成 24。"
```

### tau_0 quantile sensitivity + per-ID threshold sensitivity — 2026-08-12（ieee-reviewer M2 补做）

| Key | Value | Unit | Source |
|-----|-------|------|--------|
| tau_sens_q0005_max | 0.0000 | trivial F1, max over 624 CrySyS masquerade files at q=0.0005 | phase6/tau_sensitivity.py |
| tau_sens_q001_max | 0.0000 | 同上，q=0.001（论文采用值） | 同上 |
| tau_sens_q005_max | 0.0515 | 同上，q=0.005（162/624 文件非零） | 同上 |
| tau_sens_q01_max | 0.0754 | 同上，q=0.01（294/624 非零） | 同上 |
| tau_sens_q05_max | 0.1130 | 同上，q=0.05（312/624 非零），mean 0.0283 | 同上 |
| tau_sens_oracle_median | 0.0156 | oracle F1 中位（tau_sensitivity.py 独立重算 0.015639） | ⚠️ 与主 run 的 0.0157（crysys_discriminability.csv 实算 0.015650）**在第 4 位小数处不同**，两处是同一量的两次独立实现，相对差 0.7%。论文统一采用主 run 的 **0.0157**；此行保留以记录差异 |
| tau_sens_degenerate_median | 0.0095 | 退化解中位 | 同上 |
| aid_threshold_min_median | 3620 | µs，任意门槛(1..100 个间隔)下最短的 per-ID 中位周期，= 47µs 下限的 77 倍 | 2026-08-12 门槛扫描 |
| aid_threshold_below_floor | 0 | 序列数，门槛 1/5/10/20/50/100 下均为 0 | 同上 |
| aid_excluded_pair_medians | 132.6 / 142.5 | ms，被 >=20 门槛剔除的两个 (capture,ID) 对（均远高于下限） | 同上 |

```yaml
compute-anchor:
  value: "CrySyS masquerade trivial F1 在 q<=0.001 时全 624 文件为 0.0000；q=0.05 时 mean 0.0283 / max 0.1130；oracle 中位 0.0156 vs 退化解 0.0095 与 q 无关"
  script: phase6/tau_sensitivity.py
  cmd: /opt/anaconda3/bin/python3 phase6/tau_sensitivity.py
  stdout: "0.0005 -> max 0.0000 mean 0.0000 nonzero 0/624 ; 0.001 -> 0.0000/0.0000/0 ; 0.005 -> 0.0515/0.0028/162 ; 0.01 -> 0.0754/0.0103/294 ; 0.05 -> 0.1130/0.0283/312 ; oracle median 0.0156 (degenerate 0.0095)"
  input_files:
    - ~/Datasets/can_ids/CrySyS/logs/*-malicious-*msg-mod*.log  # 624 个
  ran_at: 2026-08-12
  note: "因 ieee-reviewer Method Detective 判 τ0 分位数无论证且无敏感性而补做。结果修正了一处
         过强的表述：论文原拟写「无任何结论依赖该取值」，实测显示**精确的 0.0000 确实依赖
         q<=0.001**；不依赖 q 的是 oracle 判据（构造上对所有阈值取最大）。论文已按实测改写。"
```

<!-- ⛔ 上面那个 compute-anchor YAML 块把这张表**从中间劈开了**。check_src_markers.py
     一遇到非 `|` 开头的行就把表头置空，于是紧随其后的第一行数据会被当成新表头吃掉。
     2026-08-13 实发：armB_displacement_worst 被当表头、armB_displacement_range 被按错误列名索引，
     两行同时 UNRESOLVABLE，而 sections/method.tex 不在 checker 的 strict 名单里，
     所以这个断裂只有在 flat 化后才暴露。补一行表头即恢复解析。
     ⚠️ 以后往表中间插代码块/说明段，必须在其后重发表头。 -->

| Key | Value | Unit | Source |
|-----|-------|------|--------|
| armB_displacement_worst | 45 | ms, σ=0.05 下良性帧绝对位移中位，**受影响文件中最差的那个** | .omc/decisions/2026-08-11_phase5-framing-and-drift-confound.md（seed 0；同处记 p99 574ms / max 2.03s） |
| armB_displacement_range | 6-63 | ms, 同量跨 12 个文件的中位范围（中位 19.4） | ⛔ 2026-08-12 paper-cross-check Gate 6 补：qwen 质疑 45ms 物理不可能（它按 gap 全为 10µs 算）。实测证伪该质疑——gap 重尾（均值 389µs ≫ 中位 9µs），随机游走方差 ∝ Σg² 由毫秒级大 gap 主导，sqrt(Σg²)·σ=32ms 与实测同量级。但论文原写法未标口径，已补 |

## Bounded numeric gate for floor claims (2026-10-02)

This table declares the three claims checked by `paper/check_src_markers.py --numeric` before packaging. It does not certify other numeric claims. The CTAT pooled-gap median and the median of 48 file medians both happen to equal 11.0 µs; the paper's pooled wording uses the former. The artifact records both estimators and the hashes of all 123 source files read during recomputation.

| Key | Estimator | Denominator | Artifact SHA256 |
|-----|-----------|-------------|-----------------|
| floor_numeric_scope | recorded floor recomputation artifact | 123 input files | d668c28edeeb374d407447e52a9b8c58cbb3288d5216310d1f01581a3d919029 |
| road_rho_below_floor | pooled 45 ROAD files | 28244494 | |
| ctat_dt_median_normal | pooled normal-frame gaps in 48 affected CTAT files | 40505015 | |
| ctat_rho_below_floor | pooled normal-frame gaps in 48 affected CTAT files | 40505015 | |

```yaml
compute-anchor:
  value: "ROAD 0.6408 (28,244,494 gaps); CTAT pooled median 11.0 µs and rho 0.6539 (40,505,015 normal-frame gaps in 48 affected files); CTAT median of file medians 11.0 µs"
  script: audit/recompute_floor.py
  cmd: "python3 audit/recompute_floor.py --output ~/ResearchReports/mechanism-trust/CAN_FLOOR_RECOMPUTE_FINAL_2026-10-02.json"
  stdout: "recomputation completed; exact counts and hashes in audit/floor_recompute_2026-10-02.json"
  input_files: "123 paths and SHA256 digests in audit/floor_recompute_2026-10-02.json:run_contract.inputs"
  ran_at: 2026-10-02
```


## 2026-10-04 新输入契约完整复算（取代对应历史敏感性证据，保留旧记录）

旧结果及上方旧计数/语义记录为历史，运行输入及代码身份仍 unknown。当前正文 Phase5 引用下面带日期的新键。610 行存储字段变化全部在 SynCAN，不能单独归因于首行修正；四位 F1 分组均值一致不等于逐行 F1/阈值/精度一致。数值一致性全量对账为本次离线审计，不是新增运行时或打包前全稿数值门。现有打包前数值门仍只覆盖声明的三项。

| Key | Value | Estimator / Denominator | Source |
|---|---|---|---|
| ctat_baseline_trivial_20261004 | 0.3076 | 40 equal-weight files | ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/full-verification.json |
| ctat_armA_100us_trivial_20261004 | 0.3043 | 40 files;10seeds/file;A100us | ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/full-verification.json |
| ctat_armC_sigma005_trivial_20261004 | 0.2792 | 40 files;10seeds/file;C.05 | ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/full-verification.json |
| ctat_armC_drop_sigma005_20261004 | 9.2 | relative change of exact stored-score aggregates;40files | ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/full-verification.json |
| ctat_armC_collapse_median_20261004 | 0.2 | 16 baseline strong files;also13 collapsed conditional median | ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/full-verification.json |
| road_oracle_baseline_20261004 | 0.1978 | 13 equal-weight files | ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/full-verification.json |
| road_armC_sigma050_oracle_20261004 | 0.0419 | 13files;10seeds/file;C.5 | ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/full-verification.json |
| road_degenerate_20261004 | 0.0411 | 13 equal-weight files; raw attackcounts checked | ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/full-verification.json |
| wilcoxon_floor_ctat_20261004 | 1.8189894035458565e-12 | 40 nonzero differences;two C oracle cells attain floor | ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/full-verification.json |
| ctat_armA_collapse100us_20261004 | 0/16 | strong baseline trivial F1>0.3;A100us | ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/full-verification.json |
| armA_collapse_20261004 | 1/16; earliest1000us; cohort median>1000us | 16 strong files;1collapsed | ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/full-verification.json |
| armB_collapse_20261004 | 13/16; earliest0.2; conditional median0.5; whole-cohort median0.75 | 16strong files;13collapsed | ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/full-verification.json |
| armC_collapse_20261004 | 13/16; earliest0.05; median0.2 | 16strong files;13collapsed | ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/full-verification.json |
| phase5_full_run_20261004 | 8178 | 58 files ×141 configurations;CTAT40/ROAD13/SynCAN5;10seeds each perturbation | ~/ResearchReports/CAN-submission-completion-20261004/phase5-fresh/results/jitter_sensitivity.csv |
| syncan_masq_oracle_20261004 | 0.2328/0.2806/0.2794/0.2358 | playback/plateau/suppress/continuous; rounded F1, positive excess retained | ~/ResearchReports/CAN-submission-completion-20261004/ceo/phase3-corrected/UNROUNDED_COMPUTE_ANCHOR.json |
| syncan_flooding_20261004 | 0.7497 | rounded trivial/oracle, NOT exact equality; oracle excess5.4124913773101468e-6 | ~/ResearchReports/CAN-submission-completion-20261004/ceo/phase3-corrected/UNROUNDED_COMPUTE_ANCHOR.json |
| syncan_positive_excess_20261004 | 5.564557486181787e-7 to1.8800459885615073e-5 | four non-flooding testfiles; unrounded oracle minus all-attack F1; allpositive | ~/ResearchReports/CAN-submission-completion-20261004/ceo/phase3-corrected/UNROUNDED_COMPUTE_ANCHOR.json |

```yaml
compute-anchor:
  value:
    rows: 8178
    changed_stored_rows: 610
    ctat_armC_drop_percent: 9.214263071908707
  script: ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/verify_complete.py
  cmd: /opt/anaconda3/bin/python3 -B ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/verify_complete.py
    --csv ~/ResearchReports/CAN-submission-completion-20261004/phase5-fresh/results/jitter_sensitivity.csv
    --manifest ~/ResearchReports/CAN-submission-completion-20261004/phase5-fresh/results/jitter_sensitivity_manifest.json
    --mode full --output ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/full-verification.json
  stdout: ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/full-stdout.txt
  input_files:
  - ~/ResearchReports/CAN-submission-completion-20261004/phase5-fresh/results/jitter_sensitivity.csv
  - ~/ResearchReports/CAN-submission-completion-20261004/phase5-fresh/results/jitter_sensitivity_manifest.json
  - ~/ResearchReports/CAN-submission-completion-20261004/phase5-fresh/input_contract.json
  ran_at: '2026-10-04T10:26:18.517202+00:00'
  csv_sha256: c9cf9cd4c41de7aebea23a947c17ae853ba9159c7371d070f0eac40c2b53fcfb
  manifest_sha256: 113a17b914dcd7965928f2f85eb9b6e5d2e3adc87e7fffe5d67c916bef8314e3
  contract_id: 73b95995fc2d55c2209318a4a5d7282e2211c19c5cafd45b6567a60c450c80a4
  scope: full stored precision reconciliation and current input hashes;historical runtime
    unknown;not full-paper numeric gate
```

### 当前输入下的经验标度律复算

| Key | Value | Estimator / Denominator | Source |
|---|---|---|---|
| collapse_model_rho_20261004 | 0.699 | 80 B file-sigma pairs | ~/ResearchReports/CAN-submission-completion-20261004/ceo/fresh-figures/collapse-analysis/audit/collapse_recall_check.json |
| collapse_model_mae_median_20261004 | 0.034 | median of16per-file mean absolute errors;not pooled median | ~/ResearchReports/CAN-submission-completion-20261004/ceo/fresh-figures/collapse-analysis/audit/collapse_recall_check.json |
| collapse_model_fit_files_20261004 | 13/16 | per-file MAE<0.10 | ~/ResearchReports/CAN-submission-completion-20261004/ceo/fresh-figures/collapse-analysis/audit/collapse_recall_check.json |
| collapse_model_counterexample_mae_20261004 | 0.595/0.571 | interval-3/interval-4;B;per-file mean absolute error | ~/ResearchReports/CAN-submission-completion-20261004/ceo/fresh-figures/collapse-analysis/audit/collapse_recall_check.json |

```yaml
compute-anchor:
  value:
    n_pairs: 80
    spearman_rho: 0.6986
    p_value: 5.811336000794215e-13
    mae_median: 0.0338
    mae_pooled_median: 0.011
    files_mae_below_0.10: 13
    n_files_scored: 16
    worst_files:
      interval-3: 0.595
      interval-4: 0.571
      standstill-3: 0.13
  script: ~/ResearchReports/CAN-submission-completion-20261004/ceo/fresh-figures/run_collapse_isolated.py
  cmd: /opt/anaconda3/bin/python3 -B ~/ResearchReports/CAN-submission-completion-20261004/ceo/fresh-figures/run_collapse_isolated.py
  stdout: ~/ResearchReports/CAN-submission-completion-20261004/ceo/fresh-figures/collapse-analysis-attempt2-stdout.txt
  input_files:
  - ~/ResearchReports/CAN-submission-completion-20261004/phase5-fresh/results/jitter_sensitivity.csv
  - ~/ResearchReports/CAN-submission-completion-20261004/phase5-fresh/input_contract.json
  ran_at: '2026-10-04T10:29:48.647302+00:00'
  scope: IO-isolated original model body;fresh67cacheSHA and producer bound in collapse-run-record.json;
    first harness attemptfailed beforemain and retained;no Phase5 rerun
```

| Key | Value | Estimator / Denominator | Source |
|---|---|---|---|
| road_armC_excess_20261004 | 0.0007461538461538547 | C.5 mean oracle minus mean baseline all-attack F1;13equal-weight files;difference before display rounding | ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-full-verification/full-verification.json and fresh CSV |

## CrySyS 原始帧计数与存储精度复核（2026-10-05）

此新增证据不重写旧CSV、不追认历史运行身份，也不替代未保存的未舍入oracle结果。

| Key | Value | Estimator / Denominator | Source |
|---|---|---|---|
| crysys_double_raw_degenerate_20261005 | 0.04115788406229173 (display 0.041158) | median of 312 per-file 2A/(N+A), A=attack frames; raw integer counts before rounding | claims/ceo-crysys-final/compute-anchor.json |
| crysys_double_stored_degenerate_20261005 | 0.04115; historical binary64 format4 0.0411 | median of 312 per-file scores stored to four decimals; middle 0.0188/0.0635; not raw-count median | local-cold-review/ceo-crysys-rounding/COMPUTE_ANCHOR.json |
| crysys_nominal_period_ids_20261005 | single 0x410 approx100ms; DOUBLE 0x110 approx10ms plus0x410 | 26benign IDpositive-gap medians,624attack label-ID sets;52base/windowgroups | claims/ceo-crysys-final/REPORT.md and readings.json |

```json
{
  "compute-anchor": {
    "value": {
      "single_rawflagall_median": 0.003867906088760855,
      "double_rawflagall_median": 0.04115788406229173,
      "single_stored_oracle_median": 0.0054,
      "double_stored_oracle_median": 0.08475,
      "double_stored_degenerate_median": 0.04115,
      "double_historical_format4": "0.0411"
    },
    "script": "~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-crysys-final/read_crysys.py",
    "script_sha256": "32d54f9abd27e348f94b54b25b862ea74fb072aa6d85293fdabacb8f99b7383e",
    "cmd": "/usr/bin/time -l /opt/anaconda3/bin/python3 -B ~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-crysys-final/read_crysys.py",
    "stdout": "~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-crysys-final/stdout.txt",
    "raw_counts_output": "~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-crysys-final/readings.json",
    "post_aggregation_outputs": [
      "~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-crysys-final/pair-readings.json",
      "~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-crysys-final/rounding-readings.json",
      "~/ResearchReports/CAN-submission-completion-20261004/claims/ceo-crysys-final/window-readings.json"
    ],
    "input_files": "all624msg-modlogs+624metadata+26benignrawSHA stored individually in readings.json; CSV identity separately recorded",
    "csv_sha256": "e4e428ac580cc88b7603f6aae5ed514043593b9c2bd72a20220cb4da8d1b236c",
    "ran_at": "2026-10-04T18:43:21.280702+00:00",
    "limitations": "no fulloracleclassifier rerun; existingroundedoracle scores independently aggregated; exactcountsflagall computable and kept separate; historicalexperimentruntimeunknown"
  }
}
```
