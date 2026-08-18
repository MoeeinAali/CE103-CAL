#!/usr/bin/env bash
# Run every Logisim test vector for Lab 05.
#
# Logisim-evolution 4.1 needs Java 21 (class file 65); Java 17 aborts with
# UnsupportedClassVersionError.  Do NOT set -Djava.awt.headless=true --
# Logisim aborts when it cannot reach a display.
set -uo pipefail

JAVA="${JAVA:-/opt/homebrew/opt/openjdk@21/bin/java}"
JAR="${LOGISIM_JAR:-/Applications/Logisim-evolution.app/Contents/app/logisim-evolution-4.1.0-all.jar}"
CIRC="$(cd "$(dirname "$0")" && pwd)/bcd_to_binary.circ"

for tool in "$JAVA" "$JAR"; do
    [ -e "$tool" ] || { echo "missing: $tool" >&2; exit 127; }
done

fail=0

run() {
    local circuit="$1" vec="$2" label="$3"
    printf '%-46s' "$label"
    local out
    out="$("$JAVA" -jar "$JAR" --no-splash --locale en \
             --test-vector "$circuit" "$(dirname "$CIRC")/$vec" "$CIRC" 2>&1)"
    local summary
    summary="$(printf '%s\n' "$out" | grep -E '^Passed:' | tail -1)"
    if printf '%s\n' "$summary" | grep -q 'Failed: 0'; then
        echo "OK   $summary"
    else
        echo "FAIL ${summary:-<no summary>}"
        printf '%s\n' "$out" | grep -E 'Error on test vector' -A3 | head -20
        fail=1
    fi
}

run converter tests_converter.vec             "converter - 13 representative values"
run converter tests_converter_exhaustive.vec  "converter - all 1000 values (000..999)"
run main      tests_main.vec                  "main - demo wrapper with Clock"

echo
if [ "$fail" -eq 0 ]; then
    echo "All test vectors passed."
else
    echo "Some test vectors FAILED." >&2
fi
exit "$fail"
