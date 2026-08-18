#!/usr/bin/env python3
"""Generate Logisim sequential test vectors for the Lab06 datapath.

Each <Set> is one scenario: Logisim resets the circuit at the start of a <Set>
and keeps state between <Seq> steps.  A step pair (clk=0, clk=1) is one rising
edge, i.e. one executed instruction.
"""
import itertools
import random

MASK = 0xFF
REGS = ["R0", "R1", "R2", "R3"]
HDR = "<Set> <Seq> IR[6] WE rst clk R0[8] R1[8] R2[8] R3[8]"


def encode(f, d, s):
    return (f << 5) | (d << 3) | s


def src_value(s, R):
    return R[s] if s < 4 else (0 if s == 4 else 1 if s == 5 else MASK)


def execute(R, f, d, s):
    b = src_value(s, R)
    res = (R[0] - b) & MASK if f else (R[0] + b) & MASK
    return [res if i == d else R[i] for i in range(4)]


class Prog:
    """Builds one <Set>: a reset, some seeding, then the instructions."""

    def __init__(self, out, setno):
        self.out, self.setno, self.seq = out, setno, 1
        self.R = [0, 0, 0, 0]

    def row(self, ir, we, rst, clk, expect=True):
        vals = " ".join(f"0x{v:02X}" for v in self.R) if expect else " ".join(["<DC>"] * 4)
        self.out.append(f"{self.setno} {self.seq} 0x{ir:02X} {we} {rst} {clk} {vals}")
        self.seq += 1

    def reset(self):
        # asynchronous clear: rst high, one step, then release
        self.R = [0, 0, 0, 0]
        self.out.append(f"{self.setno} {self.seq} 0x00 0 1 0 <DC> <DC> <DC> <DC>")
        self.seq += 1
        self.row(0, 0, 0, 0)

    def step(self, f, d, s):
        """One instruction = one rising edge."""
        ir = encode(f, d, s)
        self.row(ir, 1, 0, 0)              # setup, clock low
        self.R = execute(self.R, f, d, s)  # the edge writes the destination
        self.row(ir, 1, 0, 1)              # rising edge -> new state visible

    def hold(self, f, d, s):
        """WE = 0: the instruction must NOT change any register."""
        ir = encode(f, d, s)
        self.row(ir, 0, 0, 0)
        self.row(ir, 0, 0, 1)

    def seed(self, values):
        """Load R0..R3 using only the instruction set itself.

        R0 is built by repeatedly adding 1 to itself; the others are then
        produced as R0 + 0 after R0 has been set to the wanted value.
        """
        # R0 <- 0 (R0 - R0)
        self.step(1, 0, 0)
        for k in (1, 2, 3):
            # make R0 hold values[k], then copy R0 into Rk via Rk <- R0 + 0
            self._set_r0(values[k])
            self.step(0, k, 4)
        self._set_r0(values[0])

    def _set_r0(self, target):
        cur = self.R[0]
        # cheapest path: clear then add 1s, or add/subtract 1 repeatedly
        if abs(((target - cur) & MASK) if target >= cur else -((cur - target) & MASK)) > 40:
            self.step(1, 0, 0)             # R0 <- 0
            cur = 0
        while cur != target:
            up = (target - cur) & MASK
            down = (cur - target) & MASK
            if up <= down:
                self.step(0, 0, 5)         # R0 <- R0 + 1
                cur = (cur + 1) & MASK
            else:
                self.step(1, 0, 5)         # R0 <- R0 - 1
                cur = (cur - 1) & MASK


def build(path, scenarios):
    out = ["# Lab06 -- ALU with selectable source and destination",
           "# one <Set> per scenario; <Seq> steps keep the circuit state",
           HDR]
    for i, fn in enumerate(scenarios, 1):
        p = Prog(out, i)
        p.reset()
        fn(p)
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
    steps = sum(1 for l in out if l and l[0].isdigit())
    print(f"wrote {path}: {len(scenarios)} scenarios, {steps} steps")


# ---- scenarios ------------------------------------------------------------

def basic(p):
    """Every source with a fixed destination, plus both ALU functions."""
    p.seed([5, 9, 3, 1])
    for s in range(7):
        p.step(0, 1, s)
        p.step(1, 2, s)


def all_destinations(p):
    p.seed([7, 0, 0, 0])
    for d in range(4):
        p.step(0, d, 5)      # Rd <- R0 + 1
    for d in range(4):
        p.step(1, d, 6)      # Rd <- R0 - (-1)


def write_enable(p):
    """WE = 0 must leave every register untouched."""
    p.seed([4, 4, 4, 4])
    for f, d, s in itertools.product((0, 1), range(4), range(7)):
        p.hold(f, d, s)


def wraparound(p):
    """8-bit wrap in both directions."""
    p.seed([0xFF, 1, 0, 0])
    p.step(0, 2, 1)          # 0xFF + 1 -> 0x00
    p.step(1, 3, 5)          # 0xFF - 1
    p._set_r0(0)
    p.step(1, 1, 5)          # 0 - 1 -> 0xFF


def self_target(p):
    """Destination == source: the OLD value must be used as the operand."""
    p.seed([3, 0, 0, 0])
    p.step(0, 0, 0)          # R0 <- R0 + R0 = 6
    p.step(0, 0, 0)          # R0 <- 12
    p.step(1, 0, 0)          # R0 <- R0 - R0 = 0


def randomised(p, rng):
    p.seed([rng.randrange(256) for _ in range(4)])
    for _ in range(30):
        p.step(rng.randrange(2), rng.randrange(4), rng.randrange(7))



def exhaustive(p, seed_vals):
    """Every one of the 56 valid instructions (2 F x 4 D x 7 S) executed from
    the same seeded state, re-seeding between instructions so each is checked
    against a known register file."""
    for f, d, s in itertools.product((0, 1), range(4), range(7)):
        p.seed(seed_vals)
        p.step(f, d, s)



def build_main_vectors(path, scenarios=6):
    """Vectors for the demo wrapper.

    ``main`` takes the instruction as three separate fields and contains a real
    Clock component, which Logisim toggles once per vector row -- so there is
    no clk column and each rising edge spans two rows.
    """
    out = ["# demo wrapper: Logisim ticks the Clock component itself (no clk column)",
           "<Set> <Seq> F DST[2] SRC[3] WE rst R0[8] R1[8] R2[8] R3[8]"]
    for setno in range(1, scenarios + 1):
        seq, R = 1, [0, 0, 0, 0]

        def row(f, d, s, we, rst, expect=True):
            nonlocal seq
            v = " ".join(f"0x{x:02X}" for x in R) if expect else " ".join(["<DC>"] * 4)
            out.append(f"{setno} {seq} {f} 0x{d:X} 0x{s:X} {we} {rst} {v}")
            seq += 1

        out.append(f"{setno} {seq} 0 0x0 0x0 0 1 <DC> <DC> <DC> <DC>")
        seq += 1
        row(0, 0, 0, 0, 0)
        prog = [(0, 0, 5)] * setno + [(0, 1, 0), (1, 2, 5), (0, 3, 6), (0, 2, 1)]
        for (f, d, s) in prog:
            row(f, d, s, 1, 0)
            R = execute(R, f, d, s)
            row(f, d, s, 1, 0)
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
    steps = sum(1 for l in out if l and l[0].isdigit())
    print(f"wrote {path}: {scenarios} scenarios, {steps} steps")


if __name__ == "__main__":
    rng = random.Random(20260818)
    build("tests_datapath.vec", [
        basic, all_destinations, write_enable, wraparound, self_target,
    ])
    build("tests_datapath_random.vec",
          [lambda p, r=rng: randomised(p, r) for _ in range(12)])
    build("tests_datapath_exhaustive.vec",
          [lambda p: exhaustive(p, [6, 10, 200, 1])])
    build_main_vectors("tests_main.vec")
