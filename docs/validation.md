# Engineering Validation Methodology — Imad

Status: peer-review ready · Scope: structural analysis core (`OpenSeesEngine`)
Tolerance policy: **5 %** hard limit · **Conservative warnings** within 10 % of code limits.

## 1. Purpose

Imad issues quantities, costs and compliance statements derived from its own
analysis engine. Before any of that output is trusted commercially, the engine
must demonstrate agreement with closed-form solutions. This document defines
the benchmark suite, hand-calculation references, formulas, assumptions and
acceptance criteria used by `services/validation_engine.py`.

## 2. Benchmark cases

Each case is solved twice: once with textbook hand calculations (reference)
and once by driving `OpenSeesEngine.analyze()` with an equivalent synthetic
model (candidate). Results compared: bending moment, shear force, tip/interstorey
drift, fundamental period.

### 2.1 Simply supported beam — UDL

```
span L = 6 m, w = 20 kN/m (uniformly distributed, factored)
M_max = wL²/8 = 20 × 6² / 8 = 90.0 kN·m   (at midspan)
V_max = wL/2  = 60.0 kN                   (at supports)
δ_max = 5wL⁴/(384EI), E = 30 GPa,
I = bh³/12 with b = 0.30 m, h = 0.60 m → I = 5.4e-3 m⁴
δ_max = 5×20e3×6⁴/(384×30e9×5.4e-3) = 6.25e-3 m ≈ 6.25 mm
```

### 2.2 Axially loaded short column

```
section 0.40 × 0.40 m, height 3.0 m, N = 1500 kN concentric
σ = N/A = 1500e3 / 0.16 = 9.375 MPa
Axial shortening δ = NL/(EA) = 1500e3×3/(30e9×0.16) = 9.375e-4 m ≈ 0.94 mm
```

### 2.3 Single-bay 2D portal frame — lateral point load

```
bays 6 m, storey 3.5 m, H = 100 kN applied at roof level
Columns 0.40 × 0.40 (I = 2.133e-3 m⁴), beam 0.30 × 0.55 (I = 4.159e-3 m⁴)
Fixed-base sway frame (moderate beam/column stiffness ratio):
K_c = 12EI_c/h³ per column; Δ = H / ΣK_eff
Engineer reference computed independently with the slope-deflection method;
engine must reproduce within tolerance.
```

### 2.4 Two-storey frame — modal + equivalent lateral force

```
Storey mass ≈ tributary area × (slab self-weight + SDL + live-reduction),
γ_concrete = 25 kN/m³ (matches engine unit weight)
Period estimate used by the engine: T₁ = 0.085 × H^0.75   (H in metres)
Base shear: V = C_s · W with C_s from the engine's ELF implementation
Storey shear distribution: F_i ∝ w_i·h_i (linear mode-shape assumption)
```

## 3. Assumptions locked in the engine (must stay in sync)

| Parameter | Value | Where enforced |
|---|---|---|
| Concrete modulus | E = 30 GPa (C30) | `structural_engine.py` materials |
| Unit weight | γ = 25 kN/m³ | gravity load builder |
| Section inertia | uncracked gross | member stiffness matrix |
| Supports | fixed at base nodes | constraint definitions |
| Diaphragm behaviour | rigid (tributary load distribution) | mass assembly |

Any change to these values invalidates the benchmark references above and
requires re-running the full suite before release.

## 4. Comparison procedure

1. `POST /api/v1/validation/run` executes every case sequentially.
2. Each quantity is scored: `pass` if `|candidate − reference| / reference ≤ 0.05`,
   otherwise `fail`; values within 10 % of code limits additionally raise a
   *conservative warning* flag surfaced in the UI and PDF.
3. Accuracy score = passed checks ÷ total checks × 100.
4. `GET /api/v1/validation/report` returns the persisted comparison table;
   the PDF export embeds the same tables with the Imad report template.

## 5. References

- ACI 318-19 *Building Code Requirements for Structural Concrete* — deflection
  and reinforcement limits used for proximity warnings.
- ASCE 7-16 §12.8 — equivalent lateral force procedure mirrored by the ELF loader.
- Hibbeler, *Structural Analysis*, 10th ed. — slope-deflection reference solutions.
- OpenSees documentation — element formulations (elasticBeamColumn, zero-length springs).

## 6. Limitations

Linear-elastic, small-deformation analysis; no P-Δ, no cracking redistribution,
no foundation flexibility. Benchmarks validate the elastic core only — seismic
detailing and capacity-design rules remain the responsible engineer's duty.
