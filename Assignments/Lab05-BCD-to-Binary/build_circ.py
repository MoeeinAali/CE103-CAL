#!/usr/bin/env python3
"""Generate bcd_to_binary.circ next to this script.

3-digit BCD -> 10-bit binary converter (reverse double-dabble:
shift right, then subtract 3 from any digit whose MSB is set).

Built entirely from 74-series TTL chips.  Geometry is derived from
Logisim-evolution v4.1.0 sources:
  * AbstractTtlGate.getOffsetBounds / updatePorts  -> DIP pin coordinates
  * SplitterParameters                             -> splitter end coordinates
"""
from __future__ import annotations

import html
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bcd_to_binary.circ")

# --------------------------------------------------------------------------
# geometry helpers  (verified in Lab03)
# --------------------------------------------------------------------------


def ttl_pin(x: int, y: int, pin_count: int, p: int, facing: str = "south") -> tuple[int, int]:
    """Absolute coordinate of DIP pin ``p`` (1-based) for a TTL chip at (x, y)."""
    n = pin_count
    i = p - 1
    if facing == "east":
        w = n * 10
        if i < n // 2:
            return (x + i * 20 + 10, y + 30)
        return (x + w - (i - n // 2) * 20 - 10, y - 30)
    if facing == "south":
        h = n * 10
        if i < n // 2:
            return (x - 30, y + i * 20 + 10)
        return (x + 30, y + h - (i - n // 2) * 20 - 10)
    raise ValueError(facing)


def splitter_end(x: int, y: int, i: int, fanout: int, facing: str, appear: str, spacing: int):
    """Absolute coordinate of split end ``i``.  Mirrors SplitterParameters."""
    gap = spacing * 10
    width = 20
    justify = {"center": 0, "legacy": 0, "right": 1, "left": -1}[appear]
    if facing in ("north", "south"):
        raise NotImplementedError
    m = -1 if facing == "west" else 1
    dx_end0 = m * width
    if justify == 0:
        dy_end0 = -gap * (fanout // 2)
    elif m * justify > 0:
        dy_end0 = 10
    else:
        dy_end0 = -(10 + gap * (fanout - 1))
    return (x + dx_end0, y + dy_end0 + gap * i)


# --------------------------------------------------------------------------
# circuit builder
# --------------------------------------------------------------------------

LIB = {"wiring": "0", "gates": "1", "plexers": "2", "arith": "3",
       "mem": "4", "io": "5", "base": "6", "ttl": "7"}


class Circuit:
    def __init__(self, name: str):
        self.name = name
        self.comps: list[str] = []
        self.wires: list[tuple[tuple[int, int], tuple[int, int]]] = []
        self.wire_net: list[str] = []
        self.appear: list[str] = []
        self.boxes: list[tuple[str, tuple[int, int, int, int]]] = []

    # -- raw ---------------------------------------------------------------
    def comp(self, lib: str | None, loc: tuple[int, int], name: str, attrs: dict | None = None):
        libattr = "" if lib is None else f'lib="{LIB[lib]}" '
        attrs = attrs or {}
        if not attrs:
            self.comps.append(f'    <comp {libattr}loc="({loc[0]},{loc[1]})" name="{name}"/>')
        else:
            body = "".join(
                f'\n      <a name="{k}" val="{html.escape(str(v), quote=True)}"/>'
                for k, v in attrs.items()
            )
            self.comps.append(
                f'    <comp {libattr}loc="({loc[0]},{loc[1]})" name="{name}">{body}\n    </comp>'
            )
        return loc

    def box(self, name: str, bb: tuple[int, int, int, int]):
        self.boxes.append((name, bb))

    def wire(self, a: tuple[int, int], b: tuple[int, int], net: str = "?"):
        if a == b:
            return
        assert a[0] == b[0] or a[1] == b[1], f"diagonal wire {a}->{b}"
        self.wires.append((a, b))
        self.wire_net.append(net)

    def route(self, pts: list[tuple[int, int]], net: str = "?"):
        for a, b in zip(pts, pts[1:]):
            self.wire(a, b, net)

    # -- library shorthands ------------------------------------------------
    def pin(self, loc, label, width=1, output=False):
        attrs = {"appearance": "classic"}
        if output:
            attrs["facing"] = "west"
        attrs["label"] = label
        if output:
            attrs["type"] = "output"
        if width != 1:
            attrs["width"] = str(width)
        w = 20 if width == 1 else 30
        x, y = loc
        if output:
            self.box(f"pin {label}", (x, y - 10, x + w, y + 10))
        else:
            self.box(f"pin {label}", (x - w, y - 10, x, y + 10))
        return self.comp("wiring", loc, "Pin", attrs)

    def tunnel(self, loc, label, facing="west", width=1):
        attrs = {}
        if facing != "west":
            attrs["facing"] = facing
        attrs["label"] = label
        if width != 1:
            attrs["width"] = str(width)
        bw, bh = max(10, 6 * len(label)), 12
        x, y = loc
        if facing == "east":      # body extends west
            self.box(f"tun {label}", (x - bw - 8, y - bh // 2 - 3, x, y + bh // 2 + 3))
        else:                     # body extends east
            self.box(f"tun {label}", (x, y - bh // 2 - 3, x + bw + 8, y + bh // 2 + 3))
        return self.comp("wiring", loc, "Tunnel", attrs)

    def constant(self, loc, value, facing="east", width=1):
        x, y = loc
        self.box(f"const {value}@{loc}", (x - 20, y - 10, x, y + 10))
        return self.comp("wiring", loc, "Constant",
                         {"facing": facing, "value": value, "width": str(width)})

    def splitter(self, loc, fanout, incoming, facing="east", appear="right",
                 spacing=3, groups=None):
        """Splitter.  ``groups`` maps each incoming bus bit to a split end.

        Logisim only defaults to "one bit per end" when fanout == incoming;
        for any wider grouping the bitN attributes are mandatory, otherwise
        the ends come out 1 bit wide and Logisim reports "incompatible widths".
        """
        attrs = {"appear": appear, "facing": facing, "fanout": str(fanout),
                 "incoming": str(incoming), "spacing": str(spacing)}
        if groups is None and fanout != incoming:
            per = incoming // fanout
            groups = [b // per for b in range(incoming)]
        if groups is not None:
            assert len(groups) == incoming, "groups must cover every bus bit"
            for b, g in enumerate(groups):
                attrs[f"bit{b}"] = str(g)
        self.comp("wiring", loc, "Splitter", attrs)
        ends = [splitter_end(loc[0], loc[1], i, fanout, facing, appear, spacing)
                for i in range(fanout)]
        xs = [loc[0]] + [e[0] for e in ends]
        ys = [loc[1]] + [e[1] for e in ends]
        self.box(f"splitter@{loc}", (min(xs), min(ys) - 5, max(xs), max(ys) + 5))
        return lambda i: splitter_end(loc[0], loc[1], i, fanout, facing, appear, spacing)

    def ttl(self, loc, chip, label, pins, facing="south"):
        self.comp("ttl", loc, chip, {"facing": facing, "label": label})
        x, y = loc
        assert facing == "south"
        self.box(f"{label} {chip}", (x - 30, y, x + 30, y + pins * 10))
        return lambda p: ttl_pin(loc[0], loc[1], pins, p, facing)


    def hexdigit(self, loc, label=None):
        """Hex Digit Display from #I/O.  4-bit input at ``loc``; the body is
        14 wide by 20 tall and sits up-and-left of the port."""
        attrs = {}
        if label:
            attrs["label"] = label
        x, y = loc
        self.box(f"hex@{loc}", (x - 14, y - 20, x, y))
        return self.comp("io", loc, "Hex Digit Display", attrs)

    def led(self, loc, label=None):
        attrs = {"facing": "west"}
        if label:
            attrs["label"] = label
        x, y = loc
        self.box(f"led@{loc}", (x, y - 10, x + 20, y + 10))
        return self.comp("io", loc, "LED", attrs)

    def text(self, loc, s, size=18):
        self.comp("base", loc, "Text", {"font": f"SansSerif plain {size}", "text": s})

    # -- emit --------------------------------------------------------------
    def xml(self) -> str:
        out = [f'  <circuit name="{self.name}">']
        if self.appear:
            out.append('    <a name="appearance" val="custom"/>')
        out.append(f'    <a name="circuit" val="{self.name}"/>')
        out.append('    <a name="simulationFrequency" val="1.0"/>')
        if self.appear:
            out.append("    <appear>")
            out.extend("      " + a for a in self.appear)
            out.append("    </appear>")
        out.extend(sorted(self.comps))
        for (a, b) in sorted(self.wires):
            out.append(f'    <wire from="({a[0]},{a[1]})" to="({b[0]},{b[1]})"/>')
        out.append("  </circuit>")
        return "\n".join(out)


HEADER = '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<project source="4.1.0" version="1.0">
  This file is intended to be loaded by Logisim-evolution v4.1.0(https://github.com/logisim-evolution/).

  <lib desc="#Wiring" name="0">
    <tool name="Pin">
      <a name="appearance" val="classic"/>
    </tool>
  </lib>
  <lib desc="#Gates" name="1"/>
  <lib desc="#Plexers" name="2"/>
  <lib desc="#Arithmetic" name="3"/>
  <lib desc="#Memory" name="4"/>
  <lib desc="#I/O" name="5"/>
  <lib desc="#Base" name="6"/>
  <lib desc="#TTL" name="7"/>
  <main name="main"/>
  <options>
    <a name="gateUndefined" val="ignore"/>
    <a name="simlimit" val="1000"/>
    <a name="simrand" val="0"/>
  </options>
  <mappings>
    <tool lib="6" map="Button2" name="Poke Tool"/>
    <tool lib="6" map="Button3" name="Menu Tool"/>
    <tool lib="6" map="Ctrl Button1" name="Menu Tool"/>
  </mappings>
  <toolbar>
    <tool lib="6" name="Poke Tool"/>
    <tool lib="6" name="Edit Tool"/>
    <tool lib="6" name="Wiring Tool"/>
    <tool lib="6" name="Text Tool"/>
    <sep/>
    <tool lib="0" name="Pin"/>
    <tool lib="0" name="Pin">
      <a name="facing" val="west"/>
      <a name="type" val="output"/>
    </tool>
    <sep/>
    <tool lib="0" name="Tunnel"/>
    <tool lib="0" name="Splitter"/>
    <tool lib="0" name="Clock"/>
    <sep/>
    <tool lib="7" name="74283"/>
    <tool lib="7" name="74194"/>
    <tool lib="7" name="74161"/>
    <tool lib="7" name="7404"/>
  </toolbar>
'''


def wire_chip(c: Circuit, pin, npins: int, netmap: dict):
    """Wire every mapped pin of a south-facing DIP to a like-named tunnel.

    Stub lengths alternate 30/90 so that the bodies of tunnels sitting on the
    same column never touch (Lab03 lesson).  ``None`` marks a deliberately
    open pin.  GND (npins//2) and VCC (npins) are skipped: with the default
    VccGndPorts attribute they have no port.
    """
    left = [p for p in range(1, npins // 2) if netmap.get(p)]
    right = [p for p in range(npins // 2 + 1, npins) if netmap.get(p)]
    for side, pins in (("L", left), ("R", right)):
        for k, p in enumerate(pins):
            px, py = pin(p)
            stub = 30 if k % 2 == 0 else 90
            tx = px - stub if side == "L" else px + stub
            net = netmap[p]
            c.wire((px, py), (tx, py), net)
            c.tunnel((tx, py), net, facing="east" if side == "L" else "west")

# ==========================================================================
# the converter circuit
# ==========================================================================
#
# Algorithm (reverse double-dabble), one clock per iteration, 10 iterations:
#
#   (a) shift the whole 12-bit BCD register right by one bit; the bit that
#       falls out of the least-significant digit enters the binary register
#       from its MSB side.
#   (b) every digit whose MSB is now 1 gets 3 subtracted from it.
#   (c) repeat 10 times -> all digits are 0 and the binary register holds
#       the answer.
#
# Hardware formulation used here.  The registers always store the *corrected*
# digit; the shift is done by wiring and the correction by a 74283:
#
#       shifted_k = (D_k >> 1) | (serial_in_k << 3)
#       D_k(next) = shifted_k + (shifted_k.msb ? 13 : 0)        [ -3 mod 16 ]
#
# Because the MSB of the shifted value *is* the incoming serial bit, the
# 74283 addend is driven straight from another register's Q output:
#
#       B3 = B2 = B0 = serial_in_k,   B1 = GND,   Cin = GND
#
# so the whole "subtract 3 if MSB set" costs zero gates.
#
# 74194 note (Logisim): QA is the MOST significant bit, QD the least, and the
# shift-right serial input SR enters at QA.  Here every clock is a parallel
# LOAD (S1=S0=1), so the QA..QD ordering only matters for the wiring below.

# digit register k holds bits [QA QB QC QD] = [b3 b2 b1 b0]
#   next_b3..b0 come from the 74283 sum S4..S1
#   the 74283 A inputs are the shifted bits: A4=serial_in, A3=b3, A2=b2, A1=b1
#   (i.e. the digit's own bits 3..1 move down one place)

DIGITS = [
    # (name, reg_label, reg_loc, add_label, add_loc, mux_label, mux_loc, serial_in)
    # serial_in is the bit shifted into the digit's MSB: 0 for the hundreds
    # digit, otherwise the LSB of the next-more-significant digit.
    ("D2", "U1", (600, 140), "U4", (1050, 140), "U7", (1500, 140), "GND"),
    ("D1", "U2", (600, 620), "U5", (1050, 620), "U8", (1500, 620), "D2b0"),
    ("D0", "U3", (600, 1100), "U6", (1050, 1100), "U9", (1500, 1100), "D1b0"),
]


def build_converter() -> Circuit:
    c = Circuit("converter")

    # ---------------- input column -------------------------------------
    c.text((120, 60), "INPUTS", 16)
    c.text((150, 90), "A = 3-digit BCD, 12 bits: A[11:8]=hundreds A[7:4]=tens A[3:0]=units", 12)

    c.pin((100, 160), "A", 12)
    c.wire((100, 160), (180, 160), "A")
    ea = c.splitter((180, 160), 12, 12)
    # splitter end i -> bus bit i (LSB first) -> A0..A11
    #   units  = A3..A0   -> D0 b3..b0
    #   tens   = A7..A4   -> D1 b3..b0
    #   hund   = A11..A8  -> D2 b3..b0
    for i in range(12):
        p = ea(i)
        digit = ["D0", "D1", "D2"][i // 4]
        net = f"{digit}i{i % 4}"          # initial (parallel-load) value
        c.wire(p, (330, p[1]), net)
        c.tunnel((330, p[1]), net)

    c.pin((100, 620), "Start")
    c.wire((100, 620), (330, 620), "ST")
    c.tunnel((330, 620), "ST")

    c.pin((100, 670), "clk")
    c.wire((100, 670), (330, 670), "CLK")
    c.tunnel((330, 670), "CLK")

    c.constant((250, 720), "0x1")
    c.wire((250, 720), (330, 720), "VCC")
    c.tunnel((330, 720), "VCC")

    c.constant((250, 770), "0x0")
    c.wire((250, 770), (330, 770), "GND")
    c.tunnel((330, 770), "GND")


    # ---------------- digit slices -------------------------------------
    #
    # Each digit needs three chips:
    #
    #   74194  D_k     the digit register (always in parallel-load mode)
    #   74283  ADD_k   shift + subtract-3 corrector (combinational)
    #   74157  MUX_k   selects  Start ? A_digit : corrected_sum
    #
    # 74194 pin map (Logisim, 16-pin DIP):
    #   1 nCLR  2 SR  3 A  4 B  5 C  6 D  7 SL  8 GND
    #   9 S0   10 S1  11 CLK  12 QD  13 QC  14 QB  15 QA  16 VCC
    #   QA = MSB (b3), QD = LSB (b0);  S1=S0=1 -> parallel load
    #
    # 74283 pin map (Logisim, 16-pin DIP):
    #   1 S2  2 B2  3 A2  4 S1  5 A1  6 B1  7 Cin  8 GND
    #   9 Cout 10 S4 11 B4 12 A4 13 S3 14 A3 15 B3 16 VCC
    #   (index 1..4 = LSB..MSB)
    #
    # 74157 pin map (Logisim, 16-pin DIP):
    #   1 SEL  2 A1 3 B1 4 Y1  5 A2 6 B2 7 Y2  8 GND
    #   9 Y3  10 B3 11 A3  12 Y4 13 B4 14 A4  15 nEN  16 VCC
    #   Y = A when SEL=0, B when SEL=1
    #
    # Corrector wiring for digit k, with s = serial-in bit:
    #   A4 = s   A3 = b3  A2 = b2  A1 = b1        (the right-shifted digit)
    #   B4 = s   B3 = s   B2 = GND  B1 = s        (adds 1101 = 13 when s=1)
    #   Cin = GND
    # Because the MSB of the shifted digit *is* s, "subtract 3 when the MSB is
    # set" becomes "add 13 when s is set" -- and s is just another register's
    # Q output, so the correction costs no gates at all.

    for name, rl, rloc, al, aloc, ml, mloc, sin in DIGITS:
        # ---- shift/hold register ---------------------------------------
        reg = c.ttl(rloc, "74194", rl, 16)
        c.text((rloc[0], rloc[1] - 40), f"{rl}  74194  {name} digit register", 13)
        wire_chip(c, reg, 16, {
            1: "VCC",           # nCLR inactive: the mux+load sets the value
            2: "GND",           # SR unused (never in shift mode)
            3: f"{name}m3",     # A <- mux out b3
            4: f"{name}m2",     # B <- mux out b2
            5: f"{name}m1",     # C <- mux out b1
            6: f"{name}m0",     # D <- mux out b0
            7: "GND",           # SL unused
            9: "LD",            # S0
            10: "LD",           # S1  (S1=S0=LD -> 1 = load, 0 = hold)
            11: "CLK",
            12: f"{name}b0",    # QD = LSB
            13: f"{name}b1",    # QC
            14: f"{name}b2",    # QB
            15: f"{name}b3",    # QA = MSB
        })

        # ---- shift + subtract-3 corrector ------------------------------
        add = c.ttl(aloc, "74283", al, 16)
        c.text((aloc[0], aloc[1] - 40), f"{al}  74283  {name}: shift right, -3 if MSB", 13)
        wire_chip(c, add, 16, {
            1: f"{name}n1",     # S2 -> corrected b1
            2: "GND",           # B2 = 0
            3: f"{name}b2",     # A2 = b2
            4: f"{name}n0",     # S1 -> corrected b0
            5: f"{name}b1",     # A1 = b1
            6: sin,             # B1 = s
            7: "GND",           # Cin
            9: None,            # Cout unused
            10: f"{name}n3",    # S4 -> corrected b3
            11: sin,            # B4 = s
            12: sin,            # A4 = s
            13: f"{name}n2",    # S3 -> corrected b2
            14: f"{name}b3",    # A3 = b3
            15: sin,            # B3 = s
        })

        # ---- source mux: Start ? A_digit : corrected --------------------
        mux = c.ttl(mloc, "74157", ml, 16)
        c.text((mloc[0], mloc[1] - 40), f"{ml}  74157  {name}: Start ? A : corrected", 13)
        wire_chip(c, mux, 16, {
            1: "ST",            # SEL = Start  (0 -> A inputs, 1 -> B inputs)
            2: f"{name}n0", 3: f"{name}i0", 4: f"{name}m0",
            5: f"{name}n1", 6: f"{name}i1", 7: f"{name}m1",
            9: f"{name}m2", 10: f"{name}i2", 11: f"{name}n2",
            12: f"{name}m3", 13: f"{name}i3", 14: f"{name}n3",
            15: "GND",          # nEN active low -> always enabled
        })

    # ---------------- binary result register ---------------------------
    #
    # 10 bits of shift-right storage fed at the MSB end by D0's LSB -- the bit
    # that falls out of the least-significant BCD digit on every iteration.
    # Three 74194s in shift-right mode (S1=0, S0=RUN): data moves
    # QA -> QB -> QC -> QD, so QD of one chip drives SR of the next.
    #
    # After 10 shifts the first bit out has travelled to B0 and the register
    # holds the answer.  RUN goes low at that point and freezes it.
    #
    # U12's QC/QD are past the end of the 10-bit result; they are left
    # unconnected rather than tunnelled, so nothing else can see them.

    BINREGS = [
        ("U10", (1950, 140), "D0b0", ["B9", "B8", "B7", "B6"]),
        ("U11", (1950, 620), "B6",   ["B5", "B4", "B3", "B2"]),
        ("U12", (1950, 1100), "B2",  ["B1", "B0", None, None]),
    ]
    for lbl, loc, sin, qs in BINREGS:
        reg = c.ttl(loc, "74194", lbl, 16)
        tail = f"{qs[0]}..{qs[1]}" if qs[2] is None else f"{qs[0]}..{qs[3]}"
        c.text((loc[0], loc[1] - 40), f"{lbl}  74194  binary result {tail}", 13)
        wire_chip(c, reg, 16, {
            1: "nCLR",       # async clear while Start = 1
            2: sin,          # SR: serial input, enters at QA
            3: "GND", 4: "GND", 5: "GND", 6: "GND",   # parallel inputs unused
            7: "GND",        # SL unused
            9: "RUN",        # S0 = RUN
            10: "GND",       # S1 = 0   -> 01 = shift right, 00 = hold
            11: "CLK",
            12: qs[3],       # QD
            13: qs[2],       # QC
            14: qs[1],       # QB
            15: qs[0],       # QA
        })

    # ---------------- control unit -------------------------------------
    #
    #   nCLR = NOT(Start)      clears the binary register and the counter
    #   RUN  = NOT(End)        high until the counter reaches 10
    #   LD   = Start OR RUN    digit registers load every cycle until done
    #   End  = Cq3 AND Cq1     the 74161 reached 1010 = 10
    #
    # The 74161 counts 0..10.  Its pins run Qd Qc Qb Qa from pin 11 upward
    # (verified against Logisim's Ttl74161 portNames), so pin 14 is bit 0.
    # It is held cleared while Start is high, so the iterations are exact.

    cnt = c.ttl((1050, 1580), "74161", "U13", 16)
    c.text((1050, 1540), "U13  74161  iteration counter, stops at 10", 13)
    wire_chip(c, cnt, 16, {
        1: "nCLR",       # async clear while Start = 1
        2: "CLK",
        3: "GND", 4: "GND", 5: "GND", 6: "GND",   # load inputs unused
        7: "RUN",        # ENP
        9: "VCC",        # nLOAD inactive
        10: "RUN",       # ENT
        11: "Cq3",       # Qd = bit 3   (Logisim order on this DIP is Qd Qc Qb Qa)
        12: "Cq2",       # Qc = bit 2
        13: "Cq1",       # Qb = bit 1
        14: "Cq0",       # Qa = bit 0
    })

    inv = c.ttl((600, 1580), "7404", "U14", 14)
    c.text((600, 1540), "U14  7404  nCLR = !Start,  RUN = !End", 13)
    wire_chip(c, inv, 14, {
        1: "ST",  2: "nCLR",
        3: "END", 4: "RUN",
        5: "GND", 9: "GND", 11: "GND", 13: "GND",   # unused inputs tied low
    })

    andg = c.ttl((1500, 1580), "7408", "U15", 14)
    c.text((1500, 1540), "U15  7408  End = Cq3 . Cq1  (count = 10)", 13)
    wire_chip(c, andg, 14, {
        1: "Cq1", 2: "Cq3", 3: "END",
        4: "GND", 5: "GND",
        9: "GND", 10: "GND",
        12: "GND", 13: "GND",
    })

    org = c.ttl((1950, 1580), "7432", "U16", 14)
    c.text((1950, 1540), "U16  7432  LD = Start + RUN", 13)
    wire_chip(c, org, 14, {
        1: "ST", 2: "RUN", 3: "LD",
        4: "GND", 5: "GND",
        9: "GND", 10: "GND",
        12: "GND", 13: "GND",
    })

    # ---------------- output column ------------------------------------
    c.text((2500, 100), "OUTPUTS", 16)
    eb = c.splitter((2450, 400), 10, 10, facing="west", appear="left")
    for i in range(10):
        p = eb(i)
        c.tunnel((2330, p[1]), f"B{i}", facing="east")
        c.wire((2330, p[1]), p, f"B{i}")
    c.wire((2450, 400), (2560, 400), "B")
    c.pin((2560, 400), "B", 10, output=True)

    c.tunnel((2330, 800), "END", facing="east")
    c.wire((2330, 800), (2560, 800), "END")
    c.pin((2560, 800), "End", output=True)

    return c


# ==========================================================================
# the demo circuit
# ==========================================================================

def build_main() -> Circuit:
    """Demo wrapper: three 4-bit BCD digit inputs, each shown on its own
    seven-segment display, and the 10-bit binary result shown both as four
    hex digits and as ten individual LEDs."""
    c = Circuit("main")
    c.text((520, 120), "3-digit BCD to 10-bit binary converter  (74-series TTL)", 20)
    c.text((520, 155),
           "Start = 1 for one clock to load, then Start = 0; "
           "after 10 clocks End = 1 and B is valid.", 12)

    # ---- three BCD digit inputs, each with its own display ---------------
    c.text((250, 230), "BCD INPUT", 14)
    digits = [("A2", 300, "hundreds"), ("A1", 480, "tens"), ("A0", 660, "units")]
    for label, x, caption in digits:
        c.text((x - 10, 260), caption, 11)
        c.pin((x, 300), label, 4)
        # the pin drives both the display and the merge splitter
        c.wire((x, 300), (x, 340), label)
        c.hexdigit((x + 14, 400), label)
        c.wire((x, 340), (x + 14, 340), label)
        c.wire((x + 14, 340), (x + 14, 400), label)

    # ---- merge the three nibbles into the 12-bit A bus -------------------
    # splitter end i carries bus bits [4i .. 4i+3]:  0 = units, 1 = tens,
    # 2 = hundreds -- matching A[3:0], A[7:4], A[11:8] in the converter.
    # The splitter faces east, so its combined end is on the loc itself and the
    # three split ends stick out to the EAST at x = loc.x + 20.  The merged bus
    # therefore has to leave from the loc, and the nibbles have to come in from
    # further east -- so the digits are routed out past the splitter and back.
    em = c.splitter((820, 560), 3, 12, facing="west", appear="right", spacing=3)
    for i, (label, x) in enumerate([("A0", 660), ("A1", 480), ("A2", 300)]):
        p = em(i)
        lane = 500 + i * 20
        col = 700 + i * 16
        c.route([(x, 300), (x, lane), (col, lane), (col, p[1]), p], label)
    c.wire((820, 560), (900, 560), "A")

    # ---- control inputs --------------------------------------------------
    c.pin((300, 640), "Start")
    c.comp("wiring", (300, 700), "Clock", {"facing": "east", "label": "CLK"})

    # ---- the converter ---------------------------------------------------
    c.comp(None, (960, 610), "converter")

    c.route([(300, 640), (870, 640), (870, 590), (900, 590)], "Start")
    c.route([(300, 700), (845, 700), (845, 620), (900, 620)], "clk")

    # ---- binary result on three hex digits -------------------------------
    #
    # 10 bits split as 4 + 4 + 2, so the result reads as three hex digits:
    #   end 0 = B[3:0]  end 1 = B[7:4]  end 2 = B[9:8]
    # End 0 is the least significant group and drives the right-most display.
    # Each group gets its own lane and riser so no two share a coordinate.
    c.text((1180, 210), "BINARY RESULT (hex)", 14)
    c.text((1180, 240), "B[9:8] B[7:4] B[3:0]  -- most significant on the left", 11)
    c.wire((1020, 580), (1100, 580), "B")
    groups = [0, 0, 0, 0, 1, 1, 1, 1, 2, 2]
    eb = c.splitter((1100, 580), 3, 10, facing="east", appear="right",
                    spacing=3, groups=groups)
    for i in range(3):
        p = eb(i)
        lane = 300 + i * 20             # separate horizontal lane per group
        col = 1160 + i * 16             # separate vertical riser per group
        hx = 1400 - i * 70              # end 0 (LSB group) -> right-most display
        net = f"Bg{i}"
        c.route([p, (col, p[1]), (col, lane), (hx, lane), (hx, 380)], net)
        c.hexdigit((hx + 14, 440), None)
        c.wire((hx, 380), (hx + 14, 380), net)
        c.wire((hx + 14, 380), (hx + 14, 440), net)

    # ---- raw outputs -----------------------------------------------------
    c.wire((1020, 640), (1180, 640), "End")
    c.pin((1180, 640), "End", output=True)
    c.text((1200, 615), "End = conversion finished", 11)

    c.wire((1100, 580), (1100, 700), "B")
    c.wire((1100, 700), (1180, 700), "B")
    c.pin((1180, 700), "B", 10, output=True)

    return c


APPEAR = [
    '<rect fill="#ffffff" height="140" stroke="#000000" stroke-width="2" '
    'width="120" x="-60" y="-70"/>',
    '<text dominant-baseline="central" font-family="SansSerif" font-size="11" '
    'text-anchor="middle" x="0" y="-52">BCD-&gt;BIN</text>',
    '<circ-anchor facing="east" x="0" y="0"/>',
    '<circ-port dir="in" pin="100,160" x="-60" y="-50"/>',
    '<circ-port dir="in" pin="100,620" x="-60" y="-20"/>',
    '<circ-port dir="in" pin="100,670" x="-60" y="10"/>',
    '<circ-port dir="out" pin="2560,400" x="60" y="-30"/>',
    '<circ-port dir="out" pin="2560,800" x="60" y="30"/>',
]


# ==========================================================================
# sanity checks  (the geometric DRC that saved Lab02/Lab03)
# ==========================================================================

def check(c: Circuit) -> list[str]:
    """Collinear overlaps and endpoint-on-segment contacts between wires of
    different nets -- the silent short that produces 'E' in a test vector."""
    problems = []
    segs = []
    for (a, b), net in zip(c.wires, c.wire_net):
        (x1, y1), (x2, y2) = sorted([a, b])
        segs.append((x1, y1, x2, y2, net))

    for i in range(len(segs)):
        x1, y1, x2, y2, n1 = segs[i]
        for j in range(i + 1, len(segs)):
            a1, b1, a2, b2, n2 = segs[j]
            if n1 == n2:
                continue
            if y1 == y2 == b1 == b2 and max(x1, a1) < min(x2, a2):
                problems.append(f"collinear H overlap {n1}/{n2} at y={y1}")
            if x1 == x2 == a1 == a2 and max(y1, b1) < min(y2, b2):
                problems.append(f"collinear V overlap {n1}/{n2} at x={x1}")
            for (px, py) in ((a1, b1), (a2, b2)):
                if y1 == y2 and py == y1 and x1 <= px <= x2:
                    problems.append(f"T-contact {n2} endpoint ({px},{py}) on {n1}")
                if x1 == x2 and px == x1 and y1 <= py <= y2:
                    problems.append(f"T-contact {n2} endpoint ({px},{py}) on {n1}")
            for (px, py) in ((x1, y1), (x2, y2)):
                if b1 == b2 and py == b1 and a1 <= px <= a2:
                    problems.append(f"T-contact {n1} endpoint ({px},{py}) on {n2}")
                if a1 == a2 and px == a1 and b1 <= py <= b2:
                    problems.append(f"T-contact {n1} endpoint ({px},{py}) on {n2}")
    return sorted(set(problems))


def check_boxes(c: Circuit) -> list[str]:
    """Overlapping component bodies and wires running through a chip."""
    problems = []
    bs = c.boxes
    for i in range(len(bs)):
        n1, (ax1, ay1, ax2, ay2) = bs[i]
        for j in range(i + 1, len(bs)):
            n2, (bx1, by1, bx2, by2) = bs[j]
            if ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2:
                problems.append(f"component overlap: {n1} / {n2}")
    chips = [(n, b) for n, b in bs if b[2] - b[0] == 60]
    for (a, b), net in zip(c.wires, c.wire_net):
        (x1, y1), (x2, y2) = sorted([a, b])
        for n, (cx1, cy1, cx2, cy2) in chips:
            if y1 == y2:
                if cy1 < y1 < cy2 and x1 < cx2 and cx1 < x2:
                    inside = max(x1, cx1 + 1), min(x2, cx2 - 1)
                    if inside[0] < inside[1]:
                        problems.append(f"wire {net} crosses {n}")
            else:
                if cx1 < x1 < cx2 and y1 < cy2 and cy1 < y2:
                    inside = max(y1, cy1 + 1), min(y2, cy2 - 1)
                    if inside[0] < inside[1]:
                        problems.append(f"wire {net} crosses {n}")
    return sorted(set(problems))


def main():
    conv = build_converter()
    conv.appear = APPEAR
    dem = build_main()

    bad = False
    for c in (conv, dem):
        probs = check(c) + check_boxes(c)
        if probs:
            bad = True
            print(f"!! {c.name}: {len(probs)} wiring problems")
            for p in probs[:25]:
                print("   ", p)
        else:
            print(f"ok  {c.name}: {len(c.wires)} wires, "
                  f"{len(c.comps)} components, no conflicts")

    with open(OUT, "w") as f:
        f.write(HEADER)
        f.write(conv.xml() + "\n")
        f.write(dem.xml() + "\n")
        f.write("</project>\n")
    print("wrote", OUT)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
