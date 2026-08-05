# Lab 03 — 4×4 Binary Multiplier (Shift & Add), TTL 74-series

**Date:** 2026-08-05
**Target:** `Assignments/Lab03-Binary-Multiplier/multiplier.circ`
**Tooling:** Logisim-evolution 4.1.0, TTL library (`#TTL`), hand-written `.circ` XML

## 1. Requirements

| Signal | Direction | Width | Notes |
|---|---|---|---|
| `A` | in | 4 | multiplicand |
| `B` | in | 4 | multiplier |
| `start` | in | 1 | level; asserted to initialise |
| `clk` | in | 1 | rising edge |
| `C` | out | 8 | product |
| `end` | out | 1 | asserted when `C` is valid |

The circuit must compute `C = A × B` by shift-and-add over several clock
cycles, then raise `end`.

## 2. Algorithm

Registers: `ACC[3:0]` (accumulator), `Q[3:0]` (multiplier), `M[3:0] = A`
(multiplicand, held on the input pins).

Each iteration performs add **and** shift in a single clock edge:

```
{Cout, S[3:0]} = ACC + (Q0 ? M : 0)
ACC <- {Cout, S3, S2, S1}
Q   <- {S0,   Q3, Q2, Q1}
```

After 4 iterations, `C[7:4] = ACC` and `C[3:0] = Q`.

Hand trace for `A = 3, B = 3`:

| cycle | ACC | Q | Q0 | sum |
|---|---|---|---|---|
| init | 0000 | 0011 | — | — |
| 1 | 0001 | 1001 | 1 | 0_0011 |
| 2 | 0010 | 0100 | 1 | 0_0100 |
| 3 | 0001 | 0010 | 0 | 0_0010 |
| 4 | 0000 | 1001 | 0 | 0_0001 |

Result `0000_1001 = 9` ✓

## 3. Chip list

| Ref | Chip | Role |
|---|---|---|
| U1 | 7408 | quad 2-input AND — `M_i = A_i · Q0` |
| U2 | 74283 | 4-bit adder — `ACC + M`, `CIN = GND` |
| U3 | 74194 | ACC register — parallel load of `{Cout,S3,S2,S1}` |
| U4 | 74194 | Q register — load `B`, then shift right with serial-in `S0` |
| U5 | 74161 | 4-bit counter — counts the 4 iterations, generates `end` |
| U6 | 7404 | hex inverter — two inverters used: `nSTART`, `RUN` |

No discrete gates outside TTL packages. Two `Constant` components supply
logic 1 (`VCC`) and logic 0 (`GND`) for tie-off pins.

## 4. Control unit

The 74194 mode inputs carry the entire control; no extra flip-flop is needed.

```
RUN    = NOT(end)                     U6 gate 2
nSTART = NOT(start)                   U6 gate 1

U3 (ACC):  S1 = S0 = RUN ,  nCLR = nSTART
U4 (Q)  :  S1 = start, S0 = RUN , nCLR = VCC
U5 (cnt):  ENP = ENT = RUN , nLOAD = VCC , nCLR = nSTART
end = U5.QC                           (counter value 4 -> bit 2 set)
```

74194 mode encoding `S1 S0`: `11` = parallel load, `01` = shift right,
`00` = hold, `10` = shift left (unused).

| Phase | start | end | ACC mode | Q mode | counter |
|---|---|---|---|---|---|
| load | 1 | 0 | cleared by `nCLR` | **load B** | cleared by `nCLR` |
| run | 0 | 0 | **load adder result** | **shift right** | counting |
| done | 0 | 1 | hold | hold | frozen at 4 |

**Operating sequence:** assert `start`, apply one clock edge (loads `B` into
`Q`; `ACC` and the counter are held at zero asynchronously), deassert `start`,
apply 4 more clock edges. After the 4th edge the counter reads 4, `end` goes
high, and both registers freeze. Total 5 clock cycles.

`C` is driven continuously from `{ACC, Q}`; intermediate values are visible
during the run, and the final product is present exactly when `end` rises.

## 5. Pin mapping (datasheet pin numbers)

Verified against Logisim-evolution v4.1.0 sources
(`std/ttl/Ttl74283.java`, `Ttl74194.java`, `Ttl74161.java`, `Ttl7408.java`,
`Ttl7404.java`). All follow the real datasheet pinouts.

### U1 — 7408 (14-pin)

| pin | signal | pin | signal |
|---|---|---|---|
| 1 | `A0` | 9 | `A2` |
| 2 | `Q0` | 10 | `Q0` |
| 3 | `M0` (out) | 8 | `M2` (out) |
| 4 | `A1` | 12 | `A3` |
| 5 | `Q0` | 13 | `Q0` |
| 6 | `M1` (out) | 11 | `M3` (out) |

### U2 — 74283 (16-pin)

| pin | signal | pin | signal |
|---|---|---|---|
| 5 (A1) | `ACC0` | 6 (B1) | `M0` |
| 3 (A2) | `ACC1` | 2 (B2) | `M1` |
| 14 (A3) | `ACC2` | 15 (B3) | `M2` |
| 12 (A4) | `ACC3` | 11 (B4) | `M3` |
| 7 (CIN) | `GND` | | |
| 4 (Σ1) | `S0` | 1 (Σ2) | `S1` |
| 13 (Σ3) | `S2` | 10 (Σ4) | `S3` |
| 9 (C4) | `COUT` | | |

### U3 — 74194 as ACC (16-pin)

`QA` is the MSB and `QD` the LSB (Logisim follows the datasheet: shift right
enters at `QA`).

| pin | signal | pin | signal |
|---|---|---|---|
| 1 (nCLR) | `nSTART` | 11 (CLK) | `CLK` |
| 2 (SR) | `GND` | 9 (S0) | `RUN` |
| 3 (A) | `COUT` | 10 (S1) | `RUN` |
| 4 (B) | `S3` | 15 (QA) | `ACC3` |
| 5 (C) | `S2` | 14 (QB) | `ACC2` |
| 6 (D) | `S1` | 13 (QC) | `ACC1` |
| 7 (SL) | `GND` | 12 (QD) | `ACC0` |

### U4 — 74194 as Q

| pin | signal | pin | signal |
|---|---|---|---|
| 1 (nCLR) | `VCC` | 11 (CLK) | `CLK` |
| 2 (SR) | `S0` | 9 (S0) | `RUN` |
| 3 (A) | `B3` | 10 (S1) | `start` |
| 4 (B) | `B2` | 15 (QA) | `Q3` |
| 5 (C) | `B1` | 14 (QB) | `Q2` |
| 6 (D) | `B0` | 13 (QC) | `Q1` |
| 7 (SL) | `GND` | 12 (QD) | `Q0` |

### U5 — 74161 (16-pin)

`QA` is Q0 (LSB), `QD` is Q3 (MSB).

| pin | signal | pin | signal |
|---|---|---|---|
| 1 (nCLR) | `nSTART` | 9 (nLOAD) | `VCC` |
| 2 (CLK) | `CLK` | 10 (ENT) | `RUN` |
| 3–6 (A–D) | `GND` | 12 (QC) | `END` |
| 7 (ENP) | `RUN` | 11,13,14,15 | unused |

### U6 — 7404

| pin | signal |
|---|---|
| 1 in / 2 out | `start` → `nSTART` |
| 3 in / 4 out | `END` → `RUN` |

## 6. Geometry of TTL components in `.circ` XML

From `AbstractTtlGate.getOffsetBounds` / `updatePorts` (facing EAST, default
height 60, `VccGndPorts` false):

- Bounds relative to the `loc` anchor `(x, y)`: `x … x + 10·pinCount`,
  `y − 30 … y + 30`.
- Pin `p` (1-based, DIP numbering: bottom-left = 1, along the bottom, then
  top-right back to top-left):
  - `p ≤ pinCount/2`  →  `(x + 20·(p−1) + 10, y + 30)`
  - `p > pinCount/2`  →  `(x + 10·pinCount − 20·(p − pinCount/2 − 1) − 10, y − 30)`
- GND (`pinCount/2`) and VCC (`pinCount`) have no port when `VccGndPorts` is
  false; the remaining pins keep their physical coordinates.

XML form: `<lib desc="#TTL" name="7"/>` and
`<comp lib="7" loc="(x,y)" name="74283"><a name="label" val="U2"/></comp>`.

## 7. File structure

Two circuits in one file:

- `multiplier` — the design under test. Pins `A[4] B[4] start clk` →
  `C[8] end`. All six TTL chips live here.
- `main` — demonstration wrapper: a `Clock` component, input pins/switches for
  `A`, `B`, `start`, a hex display for `C` and an LED for `end`, wired to a
  `multiplier` subcircuit instance.

## 8. Layout and wiring rules

Left-to-right data flow with ≥300 units between columns:

```
x≈100 inputs | x≈450 U1 | x≈800 U2 | x≈1150 U3/U4 | x≈1500 outputs
control row (U6, U5) placed ≥300 units below the datapath
```

- Short, adjacent connections use real wire segments.
- Long-haul and feedback signals (`CLK`, `A0..A3`, `B0..B3`, `Q0`, `S0..S3`,
  `COUT`, `ACC0..ACC3`, `RUN`, `nSTART`, `END`) use named tunnels, so no wire
  crosses a component or another wire.
- After construction, a script checks every wire segment pair for **collinear
  overlap** (not just shared endpoints) — the Lab02 failure mode that silently
  shorts unrelated nets.

## 9. Verification

1. `describe_circuit` — inspect nets for floating or shorted signals.
2. Collinear wire-overlap script over all segments.
3. `.vec` test vector against `multiplier`, driving `clk` explicitly:
   5 cycles per case, covering `3×3=9`, `15×15=225`, `0×7=0`, `9×6=54`,
   `12×5=60`, `1×1=1`, `8×2=16`.
4. Fallback if Logisim test vectors do not retain state across rows: a Python
   driver that steps the simulation edge by edge via the Logisim CLI.

Acceptance: for every case, `end` is low during the run and high on the same
cycle that `C` holds the correct product.
