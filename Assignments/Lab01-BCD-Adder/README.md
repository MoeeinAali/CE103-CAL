# Lab 01 — جمع‌کننده دهدهی سه‌رقمی (BCD Adder)

پیاده‌سازی آزمایش اول دستور کار در **Logisim Evolution**، با ساخت سلسله‌مراتبی و نمایش خروجی روی **Hex Digit Display** (۷-segment).

## ساختار

| مدار | نقش |
|------|-----|
| `full_adder` | تمام‌جمع‌کننده ۱ بیتی (گیت‌های XOR/AND/OR) |
| `adder4` | جمع‌کننده ۴ بیتی ripple از **چهار** `full_adder` |
| `bcd_digit` | جمع‌کننده دهدهی یک‌رقمی با دو `adder4` (+ تصحیح BCD) |
| `main` | **سه نمونه** از `bcd_digit` زنجیره‌شده + Hex Digit برای `S100`/`S10`/`S1` و LED برای `Cout` |

چیدمان `main` از پایین به بالا: واحدها → دهگان → صدگان. رقم نقلی بین طبقات با Tunnel (`Cout1`, `Cout10`) منتقل می‌شود.

## منطق `bcd_digit`

1. جمع باینری ۴ بیت با `adder4` (از `full_adder`): \(Z = A + B + C_{in}\)
2. تصحیح BCD: \(C_{out} = C_1 \lor (Z > 9)\) — Comparator در حالت **unsigned**
3. اگر تصحیح لازم باشد، ۶ به \(Z\) با `adder4` دوم اضافه می‌شود (`Bit Extender` + `AND` با ثابت `0x6`)

## پایه‌های `main`

**ورودی:** `A100`, `A10`, `A1`, `B100`, `B10`, `B1` (هر کدام ۴ بیت BCD)، `Cin`  
**خروجی:** `S100`, `S10`, `S1` (۴ بیت)، `Cout`  
**نمایش:** Hex Digit روی هر رقم مجموع؛ LED روی `Cout`

مثال: \(123 + 456 = 579\)

## تست

```bash
export JAVA=/opt/homebrew/opt/openjdk@21/bin/java
JAR="/Applications/Logisim-evolution.app/Contents/app/logisim-evolution-4.1.0-all.jar"

"$JAVA" -jar "$JAR" --no-splash --locale en \
  --test-vector full_adder tests_full_adder.vec bcd_adder.circ

"$JAVA" -jar "$JAR" --no-splash --locale en \
  --test-vector bcd_digit tests_bcd_digit.vec bcd_adder.circ

"$JAVA" -jar "$JAR" --no-splash --locale en \
  --test-vector main tests_main_smoke.vec bcd_adder.circ
```

نتایج تأییدشده: `full_adder` ۸/۸، `bcd_digit` ۲۰۰/۲۰۰، `main` ۶/۶.
