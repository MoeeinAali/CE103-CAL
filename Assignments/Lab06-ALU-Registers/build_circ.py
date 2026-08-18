#!/usr/bin/env python3
"""Generate alu_regfile.circ next to this script.

Lab 06 -- arithmetic unit with selectable source and destination registers.

Instruction format (6 bits), from the lab handout:

      [ F | D1 D0 | S2 S1 S0 ]
        5   4  3    2  1  0

  F  : 0 = add, 1 = subtract
  D  : destination register, 00..11 -> R0..R3
  S  : source operand
         000..011 -> R0..R3
         100 -> constant 0
         101 -> constant 1
         110 -> constant -1  (0xFF)
         111 -> reserved for the next session

Datapath:      Rd  <-  R0  (+/-)  src

One ALU operand is always R0; the other is the selected source.  The result is
written into exactly one destination register on the rising clock edge.

Component geometry below was measured against Logisim-evolution v4.1.0 with
real test vectors (see README) -- the plexer offsets in particular are not
what the obvious guess would give.
"""
from __future__ import annotations

import html
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alu_regfile.circ")

# --------------------------------------------------------------------------
# verified component geometry (offsets relative to a component's loc)
# --------------------------------------------------------------------------
#
# Adder      A(-40,-10) B(-40,+10) Sum(0,0) Cin(-20,-20) Cout(-20,+20)
# Register   D(0,30) Q(60,30) clk(0,70) en(0,50) rst(30,90); body 60x90
# Mux n=2    in0(-30,-10) in1(-30,+10) sel(-20,+20) out(0,0)
# Mux n>2    in_i(-40, -(n/2)*10 + 10*i)  sel(-20, +(n/2)*10)  out(0,0)
# Gate       in0(-30,-10) in1(-30,+10) out(0,0)   -- requires size=30


def adder_ports(x: int, y: int) -> dict:
    return {"A": (x - 40, y - 10), "B": (x - 40, y + 10), "S": (x, y),
            "Cin": (x - 20, y - 20), "Cout": (x - 20, y + 20)}


def register_ports(x: int, y: int) -> dict:
    return {"D": (x, y + 30), "Q": (x + 60, y + 30), "clk": (x, y + 70),
            "en": (x, y + 50), "rst": (x + 30, y + 90)}


def mux_ports(x: int, y: int, n: int) -> dict:
    """Data-input / select / output coordinates for an n-input multiplexer."""
    if n == 2:
        return {"in": [(x - 30, y - 10), (x - 30, y + 10)],
                "sel": (x - 20, y + 20), "out": (x, y)}
    dy0 = -(n // 2) * 10
    return {"in": [(x - 40, y + dy0 + 10 * i) for i in range(n)],
            "sel": (x - 20, y - dy0), "out": (x, y)}


def gate_ports(x: int, y: int, inputs: int = 2) -> dict:
    """Gate with size=30.  Inputs are stacked on 10-unit centres."""
    if inputs == 2:
        return {"in": [(x - 30, y - 10), (x - 30, y + 10)], "out": (x, y)}
    dy0 = -((inputs - 1) * 10) // 2
    return {"in": [(x - 30, y + dy0 + 10 * i) for i in range(inputs)],
            "out": (x, y)}


def splitter_end(x: int, y: int, i: int, fanout: int, facing: str,
                 appear: str, spacing: int):
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
       "mem": "4", "io": "5", "base": "6"}


class Circuit:
    def __init__(self, name: str):
        self.name = name
        self.comps: list[str] = []
        self.wires: list[tuple[tuple[int, int], tuple[int, int]]] = []
        self.wire_net: list[str] = []
        self.appear: list[str] = []
        self.boxes: list[tuple[str, tuple[int, int, int, int]]] = []

    # -- raw ---------------------------------------------------------------
    def comp(self, lib: str | None, loc: tuple[int, int], name: str,
             attrs: dict | None = None):
        libattr = "" if lib is None else f'lib="{LIB[lib]}" '
        attrs = attrs or {}
        if not attrs:
            self.comps.append(
                f'    <comp {libattr}loc="({loc[0]},{loc[1]})" name="{name}"/>')
        else:
            body = "".join(
                f'\n      <a name="{k}" val="{html.escape(str(v), quote=True)}"/>'
                for k, v in attrs.items())
            self.comps.append(
                f'    <comp {libattr}loc="({loc[0]},{loc[1]})" name="{name}">'
                f'{body}\n    </comp>')
        return loc

    def box(self, name: str, bb: tuple[int, int, int, int]):
        self.boxes.append((name, bb))

    def wire(self, a, b, net: str = "?"):
        if a == b:
            return
        assert a[0] == b[0] or a[1] == b[1], f"diagonal wire {a}->{b}"
        self.wires.append((a, b))
        self.wire_net.append(net)

    def route(self, pts, net: str = "?"):
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
        if facing == "east":
            self.box(f"tun {label}", (x - bw - 8, y - bh // 2 - 3, x, y + bh // 2 + 3))
        else:
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

        When fanout != incoming the bitN attributes are mandatory, otherwise
        Logisim makes every end 1 bit wide and reports "incompatible widths".
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
        return lambda i: splitter_end(loc[0], loc[1], i, fanout, facing,
                                      appear, spacing)

    # -- the parts this lab needs -----------------------------------------
    def adder(self, loc, label=None, width=8):
        attrs = {"width": str(width)}
        self.comp("arith", loc, "Adder", attrs)
        x, y = loc
        self.box(f"adder {label or ''}@{loc}", (x - 40, y - 20, x, y + 20))
        return adder_ports(x, y)

    def register(self, loc, label, width=8):
        self.comp("mem", loc, "Register", {
            "width": str(width), "trigger": "rising",
            "appearance": "logisim_evolution", "label": label})
        x, y = loc
        self.box(f"reg {label}", (x, y, x + 60, y + 90))
        return register_ports(x, y)

    def mux(self, loc, select_bits, width=8, label=None):
        n = 1 << select_bits
        self.comp("plexers", loc, "Multiplexer", {
            "width": str(width), "select": str(select_bits)})
        x, y = loc
        p = mux_ports(x, y, n)
        # bound the drawn body only: the select pin protrudes from the bottom
        # edge, so including it would flag every legitimate select wire
        ys = [q[1] for q in p["in"]] + [y]
        xs = [q[0] for q in p["in"]] + [x]
        self.box(f"mux {label or ''}@{loc}",
                 (min(xs), min(ys) - 5, max(xs), max(ys) + 5))
        return p

    def gate(self, loc, kind, inputs=2, label=None, negate=None):
        """kind: 'AND Gate', 'OR Gate', 'XOR Gate', 'NOT Gate'."""
        attrs = {"size": "30"}
        if inputs != 2 and kind != "NOT Gate":
            attrs["inputs"] = str(inputs)
        if negate:
            for i, neg in enumerate(negate):
                if neg:
                    attrs[f"negate{i}"] = "true"
        self.comp("gates", loc, kind, attrs)
        x, y = loc
        self.box(f"gate {label or kind}@{loc}", (x - 30, y - 20, x, y + 20))
        return gate_ports(x, y, inputs)

    def text(self, loc, s, size=18):
        self.comp("base", loc, "Text",
                  {"font": f"SansSerif plain {size}", "text": s})

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
    <tool lib="3" name="Adder"/>
    <tool lib="4" name="Register"/>
    <tool lib="2" name="Multiplexer"/>
  </toolbar>
'''


# ==========================================================================
# the datapath
# ==========================================================================

REGS = ["R0", "R1", "R2", "R3"]


def build_datapath() -> Circuit:
    c = Circuit("datapath")

    # ---------------- instruction input ---------------------------------
    c.text((100, 60), "INSTRUCTION", 16)
    c.text((100, 90),
           "IR[5] = F (0 add, 1 sub)   IR[4:3] = destination   IR[2:0] = source", 12)

    c.pin((100, 160), "IR", 6)
    c.wire((100, 160), (180, 160), "IR")
    # split the 6-bit instruction into its three fields
    ir = c.splitter((180, 160), 3, 6, groups=[0, 0, 0, 1, 1, 2])
    c.wire(ir(0), (330, ir(0)[1]), "SRC")     # bits 2:0
    c.tunnel((330, ir(0)[1]), "SRC", width=3)
    c.wire(ir(1), (330, ir(1)[1]), "DST")     # bits 4:3
    c.tunnel((330, ir(1)[1]), "DST", width=2)
    c.wire(ir(2), (330, ir(2)[1]), "F")       # bit 5
    c.tunnel((330, ir(2)[1]), "F")

    c.pin((100, 340), "clk")
    c.wire((100, 340), (330, 340), "CLK")
    c.tunnel((330, 340), "CLK")

    c.pin((100, 390), "WE")
    c.text((110, 415), "write enable: 1 = execute the instruction", 11)
    c.wire((100, 390), (330, 390), "WE")
    c.tunnel((330, 390), "WE")

    c.pin((100, 440), "rst")
    c.wire((100, 440), (330, 440), "RST")
    c.tunnel((330, 440), "RST")

    # constants used as source operands and for tie-offs
    c.constant((250, 500), "0x0", width=8)
    c.wire((250, 500), (330, 500), "K0")
    c.tunnel((330, 500), "K0", width=8)

    c.constant((250, 570), "0x1", width=8)
    c.wire((250, 570), (330, 570), "K1")
    c.tunnel((330, 570), "K1", width=8)

    c.constant((250, 640), "0xff", width=8)
    c.wire((250, 640), (330, 640), "KM1")
    c.tunnel((330, 640), "KM1", width=8)
    c.text((360, 645), "constant -1 (two's complement 0xFF)", 11)

    c.constant((250, 710), "0x0", width=1)
    c.wire((250, 710), (330, 710), "GND")
    c.tunnel((330, 710), "GND")

    # ---------------- source multiplexer --------------------------------
    #
    # 8-to-1, 8 bits wide.  Inputs 0..3 are the four registers, 4..6 are the
    # constants 0, 1 and -1.  Input 7 is reserved by the handout for the next
    # session, so it is tied to 0 rather than left floating.
    c.text((700, 60), "SOURCE SELECT", 16)
    smux = c.mux((900, 300), 3, label="SRC")
    src_nets = ["R0Q", "R1Q", "R2Q", "R3Q", "K0", "K1", "KM1", "K0"]
    # the mux data inputs are on a 10-unit pitch, so the tunnel bodies would
    # overlap if they all sat at the same x -- stagger the stub lengths
    for i, net in enumerate(src_nets):
        p = smux["in"][i]
        stub = 60 + (i % 2) * 90
        c.tunnel((p[0] - stub, p[1]), net, facing="east", width=8)
        c.wire((p[0] - stub, p[1]), p, net)
    # select comes from IR[2:0]
    # the select port sits on the lower edge of the mux body, so step down
    # clear of the body before running the tunnel stub
    sel = smux["sel"]
    c.route([sel, (sel[0], sel[1] + 30), (sel[0] - 120, sel[1] + 30),
             (sel[0] - 120, sel[1] + 120)], "SRC")
    c.tunnel((sel[0] - 120, sel[1] + 120), "SRC", facing="north", width=3)
    c.wire(smux["out"], (smux["out"][0] + 90, smux["out"][1]), "SRCV")
    c.tunnel((smux["out"][0] + 90, smux["out"][1]), "SRCV", width=8)
    c.text((760, 420), "input 7 is reserved (tied to 0)", 11)

    # ---------------- ALU: add / subtract --------------------------------
    #
    # One 8-bit adder does both operations.  Subtraction is A + (~B) + 1, so
    # each source bit is XORed with F and F is fed into the carry-in:
    #
    #     F = 0 :  R0 + src
    #     F = 1 :  R0 + ~src + 1  =  R0 - src
    #
    # The eight XOR gates are driven from one splitter and merged by another.
    c.text((700, 700), "ALU  (add / subtract)", 16)
    c.text((700, 730),
           "subtract = add the one's complement with carry-in 1", 11)

    # fan the source value out to eight XOR gates
    c.tunnel((700, 820), "SRCV", facing="east", width=8)
    c.wire((700, 820), (760, 820), "SRCV")
    sp = c.splitter((760, 820), 8, 8, spacing=5)
    mg = c.splitter((1180, 820), 8, 8, facing="west", appear="left", spacing=5)
    for i in range(8):
        a = sp(i)          # split end i, carries source bit i
        b = mg(i)          # merge end i, carries the XORed bit
        # gate output must line up with the merge end, so anchor the gate on it
        g = c.gate((b[0] - 100, b[1]), "XOR Gate", label=f"x{i}")
        # source bit into the first input (both sit on the same row as `a`)
        c.route([a, (a[0] + 40, a[1]), (a[0] + 40, g["in"][0][1]),
                 g["in"][0]], f"sv{i}")
        # the function bit F drives the second input of every XOR
        c.wire((g["in"][1][0] - 40, g["in"][1][1]), g["in"][1], "F")
        c.tunnel((g["in"][1][0] - 40, g["in"][1][1]), "F", facing="east")
        c.wire(g["out"], b, f"bx{i}")

    c.wire((1180, 820), (1240, 820), "BX")
    c.tunnel((1240, 820), "BX", width=8)

    alu = c.adder((1500, 300), label="ALU")
    c.tunnel((alu["A"][0] - 60, alu["A"][1]), "R0Q", facing="east", width=8)
    c.wire((alu["A"][0] - 60, alu["A"][1]), alu["A"], "R0Q")
    c.tunnel((alu["B"][0] - 60, alu["B"][1]), "BX", facing="east", width=8)
    c.wire((alu["B"][0] - 60, alu["B"][1]), alu["B"], "BX")
    # carry-in = F
    c.route([(alu["Cin"][0], alu["Cin"][1] - 60), alu["Cin"]], "F")
    c.tunnel((alu["Cin"][0], alu["Cin"][1] - 60), "F", facing="south")
    # result
    c.wire(alu["S"], (alu["S"][0] + 90, alu["S"][1]), "RES")
    c.tunnel((alu["S"][0] + 90, alu["S"][1]), "RES", width=8)
    # carry out is exposed for observation only
    c.route([alu["Cout"], (alu["Cout"][0], alu["Cout"][1] + 60)], "COUT")
    c.tunnel((alu["Cout"][0], alu["Cout"][1] + 60), "COUT", facing="north")

    # ---------------- destination decode ---------------------------------
    #
    # A 2-to-4 decode built from AND gates.  Register k is enabled when
    # DST == k and the write-enable input WE is high:
    #
    #     EN_k = WE . (D1 == k1) . (D0 == k0)
    #
    # The two destination bits are taken straight off the instruction, and
    # their complements come from two XOR gates driven by a constant 1
    # (XOR(x,1) = NOT x -- Lab02 found that plain NOT gates are silently
    # dropped from a generated file, so they are avoided here).
    c.text((1700, 700), "DESTINATION DECODE", 16)
    c.tunnel((1700, 780), "DST", facing="east", width=2)
    c.wire((1700, 780), (1760, 780), "DST")
    ds = c.splitter((1760, 780), 2, 2, spacing=3)
    c.wire(ds(0), (1900, ds(0)[1]), "D0")
    c.tunnel((1900, ds(0)[1]), "D0")
    c.wire(ds(1), (1900, ds(1)[1]), "D1")
    c.tunnel((1900, ds(1)[1]), "D1")

    c.constant((1700, 900), "0x1", width=1)
    c.wire((1700, 900), (1760, 900), "VCC")
    c.tunnel((1760, 900), "VCC")

    # complements
    for bit, y in (("D0", 980), ("D1", 1060)):
        g = c.gate((2000, y), "XOR Gate", label=f"n{bit}")
        c.tunnel((g["in"][0][0] - 60, g["in"][0][1]), bit, facing="east")
        c.wire((g["in"][0][0] - 60, g["in"][0][1]), g["in"][0], bit)
        c.tunnel((g["in"][1][0] - 60, g["in"][1][1]), "VCC", facing="east")
        c.wire((g["in"][1][0] - 60, g["in"][1][1]), g["in"][1], "VCC")
        c.wire(g["out"], (g["out"][0] + 60, g["out"][1]), f"n{bit}")
        c.tunnel((g["out"][0] + 60, g["out"][1]), f"n{bit}", width=1)

    # one 3-input AND per register: WE . d1 . d0
    for k in range(4):
        y = 1200 + k * 120
        d1 = "D1" if (k >> 1) & 1 else "nD1"
        d0 = "D0" if k & 1 else "nD0"
        g = c.gate((2100, y), "AND Gate", inputs=3, label=f"en{k}")
        for j, (src_net, port) in enumerate(zip(("WE", d1, d0), g["in"])):
            stub = 60 + j * 70          # keep the three tunnel bodies apart
            c.tunnel((port[0] - stub, port[1]), src_net, facing="east")
            c.wire((port[0] - stub, port[1]), port, src_net)
        c.wire(g["out"], (g["out"][0] + 60, g["out"][1]), f"EN{k}")
        c.tunnel((g["out"][0] + 60, g["out"][1]), f"EN{k}")

    # ---------------- register file --------------------------------------
    #
    # Four 8-bit registers.  Every register sees the same ALU result on its D
    # input and the same clock; only the one whose enable is high loads on the
    # rising edge, so exactly one destination is written per instruction.
    c.text((2600, 60), "REGISTER FILE", 16)
    for k, name in enumerate(REGS):
        x, y = 2700, 140 + k * 260
        r = c.register((x, y), name)
        c.text((x, y - 30), f"{name}  (8 bits)", 13)
        c.tunnel((r["D"][0] - 90, r["D"][1]), "RES", facing="east", width=8)
        c.wire((r["D"][0] - 90, r["D"][1]), r["D"], "RES")
        c.tunnel((r["en"][0] - 60, r["en"][1]), f"EN{k}", facing="east")
        c.wire((r["en"][0] - 60, r["en"][1]), r["en"], f"EN{k}")
        c.tunnel((r["clk"][0] - 130, r["clk"][1]), "CLK", facing="east")
        c.wire((r["clk"][0] - 130, r["clk"][1]), r["clk"], "CLK")
        c.route([r["rst"], (r["rst"][0], r["rst"][1] + 40)], "RST")
        c.tunnel((r["rst"][0], r["rst"][1] + 40), "RST", facing="north")
        # Q feeds the source mux and, for R0, the ALU's fixed operand
        c.wire(r["Q"], (r["Q"][0] + 80, r["Q"][1]), f"{name}Q")
        c.tunnel((r["Q"][0] + 80, r["Q"][1]), f"{name}Q", width=8)

    # ---------------- outputs --------------------------------------------
    c.text((3200, 60), "OUTPUTS", 16)
    for k, name in enumerate(REGS):
        y = 200 + k * 260
        c.tunnel((3200, y), f"{name}Q", facing="east", width=8)
        c.wire((3200, y), (3320, y), f"{name}Q")
        c.pin((3320, y), name, 8, output=True)

    c.tunnel((3200, 1180), "RES", facing="east", width=8)
    c.wire((3200, 1180), (3320, 1180), "RES")
    c.pin((3320, 1180), "ALUout", 8, output=True)

    c.tunnel((3200, 1240), "COUT", facing="east")
    c.wire((3200, 1240), (3320, 1240), "COUT")
    c.pin((3320, 1240), "Cout", output=True)

    return c


# ==========================================================================
# demo wrapper
# ==========================================================================

def build_main() -> Circuit:
    """Demo: the instruction is entered as three separate fields and each
    register value is shown on a pair of hex digits."""
    c = Circuit("main")
    c.text((400, 120), "Arithmetic unit with selectable source and destination", 20)
    c.text((400, 155),
           "set F / DST / SRC, raise WE, then one clock edge executes the instruction", 12)

    # instruction fields as separate inputs, merged into the 6-bit IR
    c.pin((400, 260), "F", 1)
    c.pin((400, 320), "DST", 2)
    c.pin((400, 380), "SRC", 3)
    c.text((300, 235), "instruction", 13)

    # merge: bit0..2 = SRC, bit3..4 = DST, bit5 = F
    im = c.splitter((760, 340), 3, 6, facing="west", appear="right",
                    spacing=3, groups=[0, 0, 0, 1, 1, 2])
    for i, (x, y) in enumerate([(400, 380), (400, 320), (400, 260)]):
        p = im(i)
        lane = 440 + i * 30       # each field descends on its own row
        col = 600 + i * 40        # and rises on its own column
        c.route([(x, y), (x + 60 + i * 30, y), (x + 60 + i * 30, lane),
                 (col, lane), (col, p[1]), p], ["SRC", "DST", "F"][i])
    c.wire((760, 340), (860, 340), "IR")

    c.pin((400, 560), "WE")
    c.pin((400, 620), "rst")
    c.comp("wiring", (400, 680), "Clock", {"facing": "east", "label": "CLK"})

    c.comp(None, (920, 400), "datapath")

    c.route([(400, 560), (840, 560), (840, 370), (860, 370)], "WE")
    c.route([(400, 620), (825, 620), (825, 400), (860, 400)], "rst")
    c.route([(400, 680), (810, 680), (810, 430), (860, 430)], "clk")

    # register outputs
    for k, name in enumerate(REGS):
        y = 340 + k * 40
        c.wire((980, y), (1120, y), name)
        c.pin((1120, y), name, 8, output=True)

    c.wire((980, 500), (1120, 500), "ALUout")
    c.pin((1120, 500), "ALUout", 8, output=True)
    c.wire((980, 540), (1120, 540), "Cout")
    c.pin((1120, 540), "Cout", output=True)
    return c


APPEAR = [
    '<rect fill="#ffffff" height="160" stroke="#000000" stroke-width="2" '
    'width="120" x="-60" y="-80"/>',
    '<text dominant-baseline="central" font-family="SansSerif" font-size="11" '
    'text-anchor="middle" x="0" y="-62">ALU + REGS</text>',
    '<circ-anchor facing="east" x="0" y="0"/>',
    '<circ-port dir="in" pin="100,160" x="-60" y="-60"/>',
    '<circ-port dir="in" pin="100,390" x="-60" y="-30"/>',
    '<circ-port dir="in" pin="100,440" x="-60" y="0"/>',
    '<circ-port dir="in" pin="100,340" x="-60" y="30"/>',
    '<circ-port dir="out" pin="3320,200" x="60" y="-60"/>',
    '<circ-port dir="out" pin="3320,460" x="60" y="-20"/>',
    '<circ-port dir="out" pin="3320,720" x="60" y="20"/>',
    '<circ-port dir="out" pin="3320,980" x="60" y="60"/>',
    '<circ-port dir="out" pin="3320,1180" x="60" y="100"/>',
    '<circ-port dir="out" pin="3320,1240" x="60" y="140"/>',
]


# ==========================================================================
# geometric checks
# ==========================================================================

def check(c: Circuit) -> list[str]:
    """Collinear overlaps and endpoint-on-segment contacts between wires of
    different nets -- the silent short that shows up as 'E' in a test."""
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
    """Overlapping component bodies and wires running through a component."""
    problems = []
    bs = c.boxes
    for i in range(len(bs)):
        n1, (ax1, ay1, ax2, ay2) = bs[i]
        for j in range(i + 1, len(bs)):
            n2, (bx1, by1, bx2, by2) = bs[j]
            if ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2:
                problems.append(f"component overlap: {n1} / {n2}")
    big = [(n, b) for n, b in bs if (b[2] - b[0]) >= 40 and (b[3] - b[1]) >= 40]
    for (a, b), net in zip(c.wires, c.wire_net):
        (x1, y1), (x2, y2) = sorted([a, b])
        for n, (cx1, cy1, cx2, cy2) in big:
            if y1 == y2:
                if cy1 < y1 < cy2 and x1 < cx2 and cx1 < x2:
                    lo, hi = max(x1, cx1 + 1), min(x2, cx2 - 1)
                    if lo < hi:
                        problems.append(f"wire {net} crosses {n}")
            else:
                if cx1 < x1 < cx2 and y1 < cy2 and cy1 < y2:
                    lo, hi = max(y1, cy1 + 1), min(y2, cy2 - 1)
                    if lo < hi:
                        problems.append(f"wire {net} crosses {n}")
    return sorted(set(problems))


def main():
    dp = build_datapath()
    dp.appear = APPEAR
    dem = build_main()

    bad = False
    for c in (dp, dem):
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
        f.write(dp.xml() + "\n")
        f.write(dem.xml() + "\n")
        f.write("</project>\n")
    print("wrote", OUT)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
