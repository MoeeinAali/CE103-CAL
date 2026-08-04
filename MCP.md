# Logisim MCP Setup (CE103-CAL)

این فایل برای **سشن‌های بعدی Cursor** است تا بدون حدس زدن، MCP لاجسییم را راه بیندازند و مدارهای آزمایشگاه را بسازند/تست کنند.

## پیش‌نیازها (همین ماشین)

| ابزار | مسیر / نسخه |
|--------|-------------|
| logisim-mcp | `/Users/moeein/Desktop/logisim-mcp` |
| venv Python | `/Users/moeein/Desktop/logisim-mcp/.venv` |
| Logisim Evolution | `/Applications/Logisim-evolution.app` |
| JAR | `/Applications/Logisim-evolution.app/Contents/app/logisim-evolution-4.1.0-all.jar` |
| Java | **۲۱ یا بالاتر** — `/opt/homebrew/opt/openjdk@21/bin/java` |

> Logisim Evolution 4.1 به **Java 21** نیاز دارد (class file 65). Java 17 باعث `UnsupportedClassVersionError` می‌شود.

بررسی سریع:

```bash
/opt/homebrew/opt/openjdk@21/bin/java -version
ls "/Applications/Logisim-evolution.app/Contents/app/"*.jar
test -x /Users/moeein/Desktop/logisim-mcp/.venv/bin/python && echo ok
```

## نصب اولیه (اگر از صفر)

```bash
# 1) Logisim Evolution از سایت / Homebrew cask
# 2) Java 21
brew install openjdk@21

# 3) MCP server
git clone https://github.com/virsi/logisim-mcp.git ~/Desktop/logisim-mcp
cd ~/Desktop/logisim-mcp
python3 -m venv .venv
.venv/bin/pip install -e .
```

## کانفیگ Cursor

فایل: `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "logisim": {
      "command": "/Users/moeein/Desktop/logisim-mcp/.venv/bin/python",
      "args": ["-m", "logisim_mcp"],
      "env": {
        "LOGISIM_JAR": "/Applications/Logisim-evolution.app/Contents/app/logisim-evolution-4.1.0-all.jar",
        "JAVA": "/opt/homebrew/opt/openjdk@21/bin/java",
        "LOGISIM_LOCALE": "en"
      }
    }
  }
}
```

بعد از تغییر: Cursor را ری‌استارت کنید (یا MCP server را Reload کنید) تا `JAVA` اعمال شود.

در چت، سرور معمولاً با نام `user-logisim` دیده می‌شود.

## ابزارهای مهم برای آزمایشگاه

| کار | ابزار |
|-----|--------|
| فایل جدید `.circ` | `create_circuit_file` |
| ساب‌مدار خالی | `add_subcircuit` |
| تمام‌جمع‌کننده ۱ بیت | `build_full_adder` |
| پین / گیت / قطعه | `add_pin`, `add_gate`, `add_component` |
| سیم | `connect`, `add_wire`, `add_tunnel` |
| توصیف نت‌لیست | `describe_circuit`, `describe_project` |
| تست جدول درستی | `verify_truth_table` |
| تست بردار `.vec` | `run_test_vector` |

`type_key`های رایج `add_component`: `Adder`, `Comparator`, `Multiplexer`, `Constant`, `Clock`, `Register`, `Counter`.

## تست بدون MCP (CLI مستقیم)

اگر `verify_truth_table` داخل MCP به خاطر Java قدیمی fail شد، همین را در ترمینال بزنید (**بدون** `_JAVA_OPTIONS=-Djava.awt.headless=true` — Logisim headless را دوست ندارد):

```bash
export JAVA=/opt/homebrew/opt/openjdk@21/bin/java
JAR="/Applications/Logisim-evolution.app/Contents/app/logisim-evolution-4.1.0-all.jar"
CIRC="Assignments/Lab01-BCD-Adder/bcd_adder.circ"

"$JAVA" -jar "$JAR" --no-splash --locale en \
  --test-vector main Assignments/Lab01-BCD-Adder/tests_main_smoke.vec "$CIRC"
```

همچنین می‌توان از venv خود MCP با env درست import کرد:

```bash
export JAVA=/opt/homebrew/opt/openjdk@21/bin/java
export LOGISIM_JAR="/Applications/Logisim-evolution.app/Contents/app/logisim-evolution-4.1.0-all.jar"
/Users/moeein/Desktop/logisim-mcp/.venv/bin/python -c "
from logisim_mcp.tools.sim_tools import verify_truth_table
print(verify_truth_table(
  'Assignments/Lab01-BCD-Adder/bcd_adder.circ',
  'full_adder',
  ['A','B','Cin'], ['Sum','Cout'],
  [[str(a),str(b),str(c), str((a+b+c)&1), str((a+b+c)>>1)]
   for a in (0,1) for b in (0,1) for c in (0,1)],
))
"
```

## الگوی کار برای هر Lab

1. پوشه: `Assignments/LabNN-Name/`
2. `create_circuit_file(.../lab.circ)`
3. ساخت سلسله‌مراتبی (مثلاً `full_adder` → بلوک میانی → `main`)
4. `describe_circuit` برای چک اتصال کوتاه / نت شناور
5. `verify_truth_table` یا فایل `.vec` + CLI با Java 21
6. README کوتاه داخل همان پوشه

### تله‌های رایج (از Lab01)

- **Comparator** پیش‌فرض `twosComplement` است؛ برای BCD حتماً `mode=unsigned`.
- سیم‌کشی Lشکل می‌تواند ورودی‌ها را short کند؛ مسیر Cin را جدا از باس A/B بکشید.
- هندسه پورت `Multiplexer` در MCP تقریبی است؛ برای انتخاب ۰/۶ گاهی `Bit Extender` (sign) + `AND` مطمئن‌تر است.
- قرار دادن ساب‌مدار سفارشی با ظاهر پیش‌فرض سخت است؛ تونل‌های هم‌نام یا کپی منطق طبقه جایگزین خوبی است.
- تست CLI را با مجوز کامل / نمایشگر بزنید؛ sandbox یا headless اغلب abort می‌شود.

### تله‌های رایج (از Lab02)

- **مدار ساخته‌شده با `build_full_adder`** (یا هر ابزار اتوماتیک مشابه) بدون `<appear>` سفارشی است. اگر بعداً بخواهید همان مدار را به‌عنوان ساب‌مدار در جای دیگری Instantiate کنید، فرمول مکان پورت‌های خارجی که از یک مدار *دیگر* (با appear دستی) استخراج کرده‌اید **کار نمی‌کند** — چون Logisim برای مدار بدون appear از layout پیش‌فرض دیگری استفاده می‌کند. راه‌حل: مدار پایه (مثل `full_adder`) را از یک فایل کاری قبلی (با appear ثابت‌شده) کپی کنید، نه با ابزار خودکار بسازید.
- **گیت `NOT` که با `add_gate` ساخته می‌شود** (با `<a name="size" val="50"/>`) به‌طور خاموش از مدار حذف می‌شود؛ در stats شمارش نمی‌شود و هیچ خطایی هم چاپ نمی‌شود. علتش نامعلوم ماند (AND/OR/XOR با همان attributeها مشکلی ندارند). راه‌حل: NOT را با `XOR(x, Constant(1))` جایگزین کنید.
- **دو سیم هم‌راستا (افقی یا عمودی) که در مختصات هم‌پوشانی دارند** — حتی بدون اشتراک نقطه‌ی پایانی دقیق — به‌صورت فیزیکی به هم متصل می‌شوند و بین دو نت کاملاً نامرتبط short ایجاد می‌کنند. علامت مشخصه: خروجی تست به‌جای `0`/`1` مقدار `E` (خطا/تعارض) نشان می‌دهد، حتی وقتی منطق روی کاغذ درست است. قبل از نهایی‌سازی یک مدار بزرگ، تمام segmentهای سیم را برای هم‌پوشانی collinear (نه فقط تطابق نقطه‌ای) بررسی کنید؛ اسکریپت پایتون ساده (بر پایه‌ی `x1==x2==x` یا `y1==y2==y` و تداخل بازه) این کار را سریع انجام می‌دهد.
- برای مدارهای بزرگ با چند طبقه‌ی مستقل (مثل Carry Select)، بین بلوک‌های مختلف حداقل ۵۰۰-۷۰۰ واحد فاصله‌ی عمودی/افقی بگذارید تا احتمال برخورد مختصاتی این‌چنینی پایین بیاید.
- برای اعتبارسنجی سریع یک زیرمدار قبل از سیم‌کشی همه‌جا: یک نسخه‌ی مینیمال با چند Pin ورودی/خروجی بسازید و `verify_truth_table` را روی چند سطر دستی بزنید — این روش، باگ‌های appear/gate را خیلی زودتر از تست کامل نشان می‌دهد.
- **فایلی که با `create_circuit_file` ساخته می‌شود، تگ `<mappings/>` خالی دارد** — یعنی هیچ نگاشتی بین دکمه‌های ماوس و ابزارها وجود ندارد، و مشخصاً کلیک راست (`Button3`) به `Menu Tool` وصل نیست. نتیجه: داخل GUI واقعی Logisim، راست‌کلیک روی قطعات هیچ منویی (Rotate/Delete/...) باز نمی‌کند، هرچند فایل از نظر شبیه‌سازی و تست headless کاملاً سالم است. بلافاصله بعد از `create_circuit_file`، این بلوک را جایگزین `<mappings/>` کنید:
  ```xml
  <mappings>
    <tool lib="6" map="Button2" name="Poke Tool"/>
    <tool lib="6" map="Button3" name="Menu Tool"/>
    <tool lib="6" map="Ctrl Button1" name="Menu Tool"/>
  </mappings>
  ```
  همچنین بهتر است `source="4.0.0"` در خط اول به نسخه‌ی نصب‌شده (اینجا `4.1.0`) تغییر کند تا با فایل‌های واقعاً ذخیره‌شده توسط برنامه هم‌خوان باشد.

## فرمت بردار تست (`.vec`)

```text
A[4] B[4] Cin S[4] Cout
0x5 0x3 0 0x8 0
0x9 0x9 1 0x9 1
```

برای باس‌ها از `0xN` استفاده کنید؛ رقم هگز خام گاهی parse error می‌دهد.

## مدار آماده Lab01

- فایل: [`Assignments/Lab01-BCD-Adder/bcd_adder.circ`](Assignments/Lab01-BCD-Adder/bcd_adder.circ)
- مدارها: `full_adder`, `bcd_digit`, `main`
- جزئیات: [`Assignments/Lab01-BCD-Adder/README.md`](Assignments/Lab01-BCD-Adder/README.md)

## مدار آماده Lab02

- فایل: [`Assignments/Lab02-Carry-Select-Adder/carry_select_adder.circ`](Assignments/Lab02-Carry-Select-Adder/carry_select_adder.circ)
- مدارها: `full_adder`, `adder2`, `main`
- جزئیات: [`Assignments/Lab02-Carry-Select-Adder/README.md`](Assignments/Lab02-Carry-Select-Adder/README.md)

## لینک‌ها

- [logisim-mcp](https://github.com/virsi/logisim-mcp)
- [Logisim Evolution releases](https://github.com/logisim-evolution/logisim-evolution/releases)
