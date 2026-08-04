# Lab 01 — جمع‌کننده دهدهی سه‌رقمی (BCD Adder)

پیاده‌سازی آزمایش اول دستور کار در **Logisim Evolution**، با ساخت سلسله‌مراتبی و نمایش خروجی روی **Hex Digit Display** (۷-segment).

## ساختار

فقط **۳ ماژول**، بدون هیچ لایه‌ی واسط اضافه:

| مدار | نقش |
|------|-----|
| `full_adder` | تمام‌جمع‌کننده ۱ بیتی (گیت‌های XOR/AND/OR) |
| `bcd_digit` | جمع‌کننده دهدهی یک‌رقمی؛ مستقیماً از **۸ نمونه** `full_adder` ساخته شده (بدون ماژول واسط ۴بیتی) |
| `main` | **سه نمونه** از `bcd_digit` زنجیره‌شده + Hex Digit برای `S100`/`S10`/`S1` و LED برای `Cout` |

چیدمان `main` از پایین به بالا: واحدها → دهگان → صدگان. رقم نقلی بین طبقات با Tunnel (`Cout1`, `Cout10`) منتقل می‌شود.

## منطق `bcd_digit`

1. جمع باینری ۴ بیت با زنجیره‌ی اول از ۴ `full_adder`: \(Z = A + B + C_{in}\)، رقم نقلی باینری آن را `C4` می‌نامیم.
2. تصحیح BCD: باید بفهمیم آیا \(Z > 9\) است یا نه (چون رقم دهدهی حداکثر ۹ است، ولی جمع باینری خام می‌تواند تا ۱۹ برود). قبلاً این کار با یک `Comparator` آماده انجام می‌شد؛ چون رقم نقلی باینری (`C4`) فقط سرریز ≥۱۶ را نشان می‌دهد و مقادیر ۱۰ تا ۱۵ را نه، Comparator جداگانه لازم بود.
   حالا به‌جای Comparator، از فرمول کمینه‌ی استاندارد BCD adder استفاده شده که با ۲ گیت کافی است:
   \[C_{out} = C_4 \lor (Z_3 \land Z_2) \lor (Z_3 \land Z_1)\]
   (پیاده‌سازی: `OR(Z2,Z1)` → `AND(Z3, ·)` → `OR(C4, ·)`)
3. اگر تصحیح لازم باشد (`Cout=1`)، باید ۶ (=`0110`) به \(Z\) اضافه شود. چون بیت ۰ و ۳ عدد ۶ صفرند، این کار با زنجیره‌ی دوم از ۴ `full_adder` انجام می‌شود که ورودی دومش فقط در بیت‌های ۱ و ۲ برابر `Cout` است (بقیه صفر) — نیازی به جمع‌کننده یا AND ۴بیتی جداگانه نیست.

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
