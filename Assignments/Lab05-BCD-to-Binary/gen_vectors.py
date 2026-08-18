#!/usr/bin/env python3
"""Generate Logisim sequential test vectors for the converter circuit.

Each conversion is one <Set>; Logisim resets the circuit at the start of a
<Set> and preserves state between <Seq> steps.  A conversion needs
  step 1 : Start=1, clk=0   (present A)
  step 2 : Start=1, clk=1   -> rising edge loads A, clears counter+result
  then 10 rising edges with Start=0.
Each rising edge is a (clk=0, clk=1) pair, so the whole run is 2 + 20 steps.
"""
import sys

HDR = "<Set> <Seq> A[12] Start clk B[10] End"


def bcd(n):
    return (n // 100) << 8 | ((n // 10) % 10) << 4 | (n % 10)


def conversion(setno, n, out):
    a = f"0x{bcd(n):03X}"
    seq = 1

    def row(start, clk, b, end):
        nonlocal seq
        out.append(f"{setno} {seq} {a} {start} {clk} {b} {end}")
        seq += 1

    # present A with Start high, then one rising edge to load it
    row(1, 0, "<DC>", "<DC>")
    row(1, 1, "<DC>", "0")
    # ten iterations; End must stay low until the very last edge
    for i in range(10):
        last = (i == 9)
        row(0, 0, "<DC>", "1" if last and i == 9 and False else "<DC>")
        row(0, 1, f"0x{n:03X}" if last else "<DC>", "1" if last else "0")


def build(values, path):
    out = [
        "# 3-digit BCD -> 10-bit binary converter",
        "# reverse double-dabble: shift right, subtract 3 from any digit whose MSB is set",
        "# one <Set> per conversion; <Seq> steps keep the circuit state",
        HDR,
    ]
    for i, n in enumerate(values, 1):
        out.append(f"# {n} -> {n:010b}")
        conversion(i, n, out)
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
    print(f"wrote {path}: {len(values)} conversions, "
          f"{sum(1 for l in out if l and not l.startswith('#') and not l.startswith('<'))} steps")


def build_main(values, path):
    """Vectors for the demo wrapper.

    ``main`` contains a real Clock component, and Logisim toggles every Clock
    once per vector row -- so there is no clk column here and each row is half
    a clock period (a rising edge lands on every second row).
    """
    out = [
        "# demo wrapper: Logisim ticks the Clock component itself (no clk column)",
        "<Set> <Seq> A2[4] A1[4] A0[4] Start B[10] End",
    ]
    for setno, n in enumerate(values, 1):
        a = f"0x{n // 100:X} 0x{(n // 10) % 10:X} 0x{n % 10:X}"
        seq = 1

        def row(start, b, end):
            nonlocal seq
            out.append(f"{setno} {seq} {a} {start} {b} {end}")
            seq += 1

        out.append(f"# {n} -> {n:010b}")
        row(1, "<DC>", "<DC>")          # present A, clock low
        row(1, "<DC>", "<DC>")          # rising edge loads A
        for i in range(10):
            last = (i == 9)
            row(0, "<DC>", "<DC>")
            row(0, f"0x{n:03X}" if last else "<DC>", "1" if last else "0")
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
    steps = sum(1 for l in out if l and l[0].isdigit())
    print(f"wrote {path}: {len(values)} conversions, {steps} steps")


if __name__ == "__main__":
    rep = [0, 1, 5, 9, 10, 42, 99, 100, 255, 500, 512, 767, 999]
    build(rep, "tests_converter.vec")
    build(list(range(1000)), "tests_converter_exhaustive.vec")
    build_main([0, 7, 42, 99, 100, 405, 999, 123, 256, 500], "tests_main.vec")
