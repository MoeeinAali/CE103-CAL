#!/usr/bin/env python3
"""Generate multiplier.circ next to this script.

4x4 shift-and-add binary multiplier built from 74-series TTL chips.
Geometry is derived from Logisim-evolution v4.1.0 sources:
  * AbstractTtlGate.getOffsetBounds / updatePorts  -> DIP pin coordinates
  * SplitterParameters                             -> splitter end coordinates
"""
from __future__ import annotations

import html
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "multiplier.circ")

# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------


def ttl_pin(x: int, y: int, pin_count: int, p: int, facing: str = "south") -> tuple[int, int]:
    """Absolute coordinate of DIP pin ``p`` (1-based) for a TTL chip at (x, y).

    Mirrors AbstractTtlGate.updatePorts().  ``height`` is the default 60, so
    the un-rotated bounds are (0, -30, pin_count*10, 60).
    """
    n = pin_count
    i = p - 1
    if facing == "east":
        w = n * 10
        if i < n // 2:
            return (x + i * 20 + 10, y + 30)
        return (x + w - (i - n // 2) * 20 - 10, y - 30)
    if facing == "south":
        # rotated bounds: width 60, height n*10
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
        # net name -> list of wire indices, for the overlap checker
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
            attrs["output"] = "true"
            attrs["type"] = "output"
        if width != 1:
            attrs["width"] = str(width)
        # keep Logisim's own attribute order tolerant: it parses by name
        attrs.pop("output", None)
        # classic Pin: 20x20 per bus nibble, body opposite the port
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
        # Tunnel.computeBounds: bw = max(10, 6*len), bh = max(10, 12), +3 margin,
        # then union with the port at the origin.
        bw, bh = max(10, 6 * len(label)), 12
        x, y = loc
        if facing == "east":      # body extends west
            self.box(f"tun {label}", (x - bw - 8, y - bh // 2 - 3, x, y + bh // 2 + 3))
        else:                     # body extends east
            self.box(f"tun {label}", (x, y - bh // 2 - 3, x + bw + 8, y + bh // 2 + 3))
        return self.comp("wiring", loc, "Tunnel", attrs)

    def constant(self, loc, value, facing="east", width=1):
        x, y = loc
        self.box(f"const {value}", (x - 20, y - 10, x, y + 10))
        return self.comp("wiring", loc, "Constant",
                         {"facing": facing, "value": value, "width": str(width)})

    def splitter(self, loc, fanout, incoming, facing="east", appear="right", spacing=3):
        self.comp("wiring", loc, "Splitter", {
            "appear": appear, "facing": facing, "fanout": str(fanout),
            "incoming": str(incoming), "spacing": str(spacing)})
        ends = [splitter_end(loc[0], loc[1], i, fanout, facing, appear, spacing)
                for i in range(fanout)]
        xs = [loc[0]] + [e[0] for e in ends]
        ys = [loc[1]] + [e[1] for e in ends]
        self.box("splitter", (min(xs), min(ys) - 5, max(xs), max(ys) + 5))
        return lambda i: splitter_end(loc[0], loc[1], i, fanout, facing, appear, spacing)

    def ttl(self, loc, chip, label, pins, facing="south"):
        self.comp("ttl", loc, chip, {"facing": facing, "label": label})
        x, y = loc
        assert facing == "south"
        self.box(f"{label} {chip}", (x - 30, y, x + 30, y + pins * 10))
        return lambda p: ttl_pin(loc[0], loc[1], pins, p, facing)

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
    <tool lib="7" name="7408"/>
    <tool lib="7" name="74283"/>
    <tool lib="7" name="74194"/>
    <tool lib="7" name="74161"/>
  </toolbar>
'''


# ==========================================================================
# the multiplier circuit
# ==========================================================================

def build_multiplier() -> Circuit:
    c = Circuit("multiplier")

    # ---------------- input column -------------------------------------
    c.text((100, 150), "INPUTS")
    c.pin((100, 200), "A", 4)
    c.wire((100, 200), (180, 200), "A")
    ea = c.splitter((180, 200), 4, 4)
    for i in range(4):
        p = ea(i)
        c.wire(p, (300, p[1]), f"A{i}")
        c.tunnel((300, p[1]), f"A{i}")

    c.pin((100, 400), "B", 4)
    c.wire((100, 400), (180, 400), "B")
    eb = c.splitter((180, 400), 4, 4)
    for i in range(4):
        p = eb(i)
        c.wire(p, (300, p[1]), f"B{i}")
        c.tunnel((300, p[1]), f"B{i}")

    c.pin((100, 600), "start")
    c.wire((100, 600), (300, 600), "ST")
    c.tunnel((300, 600), "ST")

    c.pin((100, 650), "clk")
    c.wire((100, 650), (300, 650), "CLK")
    c.tunnel((300, 650), "CLK")

    c.constant((220, 700), "0x1")
    c.wire((220, 700), (300, 700), "VCC")
    c.tunnel((300, 700), "VCC")

    c.constant((220, 750), "0x0")
    c.wire((220, 750), (300, 750), "GND")
    c.tunnel((300, 750), "GND")

    # ---------------- TTL chips ----------------------------------------
    # pin -> tunnel label; None marks a deliberately open pin
    chips = [
        # (label, chip, pin_count, loc, caption, {pin: net})
        ("U1", "7408", 14, (600, 200), "U1  7408  AND: M = A . Q0", {
            1: "A0", 2: "Q0", 3: "M0",
            4: "A1", 5: "Q0", 6: "M1",
            8: "M2", 9: "A2", 10: "Q0",
            11: "M3", 12: "A3", 13: "Q0",
        }),
        ("U2", "74283", 16, (1000, 200), "U2  74283  ADDER: ACC + M", {
            1: "S1", 2: "M1", 3: "AC1", 4: "S0", 5: "AC0", 6: "M0", 7: "GND",
            9: "CO", 10: "S3", 11: "M3", 12: "AC3", 13: "S2", 14: "AC2", 15: "M2",
        }),
        ("U3", "74194", 16, (1400, 80), "U3  74194  ACC register", {
            1: "nST", 2: "GND", 3: "CO", 4: "S3", 5: "S2", 6: "S1", 7: "GND",
            9: "RUN", 10: "RUN", 11: "CLK", 12: "AC0", 13: "AC1", 14: "AC2", 15: "AC3",
        }),
        ("U4", "74194", 16, (1400, 480), "U4  74194  Q register", {
            1: "VCC", 2: "S0", 3: "B3", 4: "B2", 5: "B1", 6: "B0", 7: "GND",
            9: "RUN", 10: "ST", 11: "CLK", 12: "Q0", 13: "Q1", 14: "Q2", 15: "Q3",
        }),
        ("U6", "7404", 14, (600, 800), "U6  7404  inverters", {
            1: "ST", 2: "nST", 3: "END", 4: "RUN",
            5: "GND", 9: "GND", 11: "GND", 13: "GND",
        }),
        ("U5", "74161", 16, (1000, 800), "U5  74161  cycle counter", {
            1: "nST", 2: "CLK", 3: "GND", 4: "GND", 5: "GND", 6: "GND", 7: "RUN",
            9: "VCC", 10: "RUN", 12: "END",
        }),
    ]

    for label, chip, npins, loc, caption, netmap in chips:
        pin = c.ttl(loc, chip, label, npins)
        cx, y0 = loc
        c.text((cx, y0 - 50), caption, 14)
        left = [p for p in range(1, npins // 2) if p in netmap]           # skip GND
        right = [p for p in range(npins // 2 + 1, npins) if p in netmap]  # skip VCC
        for side, pins in (("L", left), ("R", right)):
            for k, p in enumerate(pins):
                px, py = pin(p)
                stub = 30 if k % 2 == 0 else 90
                tx = px - stub if side == "L" else px + stub
                net = netmap[p]
                c.wire((px, py), (tx, py), net)
                c.tunnel((tx, py), net, facing="east" if side == "L" else "west")

    # ---------------- output column ------------------------------------
    c.text((1700, 250), "OUTPUTS")
    ec = c.splitter((1750, 300), 8, 8, facing="west", appear="left")
    order = ["Q0", "Q1", "Q2", "Q3", "AC0", "AC1", "AC2", "AC3"]
    for i, net in enumerate(order):
        p = ec(i)
        c.tunnel((1650, p[1]), net, facing="east")
        c.wire((1650, p[1]), p, net)
    c.wire((1750, 300), (1830, 300), "C")
    c.pin((1830, 300), "C", 8, output=True)

    c.tunnel((1650, 620), "END", facing="east")
    c.wire((1650, 620), (1830, 620), "END")
    c.pin((1830, 620), "end", output=True)

    return c


# ==========================================================================
# the demo circuit
# ==========================================================================

def build_main() -> Circuit:
    c = Circuit("main")
    c.text((400, 200), "4-bit x 4-bit shift-and-add multiplier  (74-series TTL)", 20)
    c.text((400, 240),
           "start = 1, one clock tick to load, then start = 0 and 4 ticks -> end = 1", 12)

    c.pin((400, 300), "A", 4)
    c.pin((400, 360), "B", 4)
    c.pin((400, 420), "start")
    c.comp("wiring", (400, 480), "Clock", {"facing": "east", "label": "CLK"})

    c.comp(None, (800, 400), "multiplier")

    c.route([(400, 300), (700, 300), (700, 350), (740, 350)], "A")
    c.route([(400, 360), (690, 360), (690, 380), (740, 380)], "B")
    c.route([(400, 420), (680, 420), (680, 410), (740, 410)], "start")
    c.route([(400, 480), (670, 480), (670, 440), (740, 440)], "clk")

    c.wire((860, 370), (1000, 370), "C")
    c.pin((1000, 370), "C", 8, output=True)
    c.wire((860, 430), (1000, 430), "end")
    c.pin((1000, 430), "end", output=True)
    return c


APPEAR = [
    '<rect fill="#ffffff" height="140" stroke="#000000" stroke-width="2" width="120" x="-60" y="-70"/>',
    '<text dominant-baseline="central" font-family="SansSerif" font-size="12" '
    'text-anchor="middle" x="0" y="-52">MUL 4x4</text>',
    '<circ-anchor facing="east" x="0" y="0"/>',
    '<circ-port dir="in" pin="100,200" x="-60" y="-50"/>',
    '<circ-port dir="in" pin="100,400" x="-60" y="-20"/>',
    '<circ-port dir="in" pin="100,600" x="-60" y="10"/>',
    '<circ-port dir="in" pin="100,650" x="-60" y="40"/>',
    '<circ-port dir="out" pin="1830,300" x="60" y="-30"/>',
    '<circ-port dir="out" pin="1830,620" x="60" y="30"/>',
]


# ==========================================================================
# sanity checks
# ==========================================================================

def check(c: Circuit) -> list[str]:
    """Report collinear overlaps and endpoint-on-segment contacts between
    wires that belong to different nets."""
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
            # collinear horizontal
            if y1 == y2 == b1 == b2 and max(x1, a1) < min(x2, a2):
                problems.append(f"collinear H overlap {n1}/{n2} at y={y1}")
            # collinear vertical
            if x1 == x2 == a1 == a2 and max(y1, b1) < min(y2, b2):
                problems.append(f"collinear V overlap {n1}/{n2} at x={x1}")
            # endpoint of j lying inside segment i (T junction between nets)
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
    """Report overlapping component bounding boxes and wires that run through
    a component body."""
    problems = []
    bs = c.boxes
    for i in range(len(bs)):
        n1, (ax1, ay1, ax2, ay2) = bs[i]
        for j in range(i + 1, len(bs)):
            n2, (bx1, by1, bx2, by2) = bs[j]
            if ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2:
                problems.append(f"component overlap: {n1} / {n2}")
    # wires crossing a chip body (tunnels/pins are endpoints, so skip those)
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
    mul = build_multiplier()
    mul.appear = APPEAR
    dem = build_main()

    for c in (mul, dem):
        probs = check(c) + check_boxes(c)
        if probs:
            print(f"!! {c.name}: {len(probs)} wiring problems")
            for p in probs[:20]:
                print("   ", p)
        else:
            print(f"ok  {c.name}: {len(c.wires)} wires, {len(c.comps)} components, no conflicts")

    with open(OUT, "w") as f:
        f.write(HEADER)
        f.write(mul.xml() + "\n")
        f.write(dem.xml() + "\n")
        f.write("</project>\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
