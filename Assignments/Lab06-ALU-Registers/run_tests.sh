#!/usr/bin/env bash
# Run every Logisim test vector for Lab 06.
#
# Logisim-evolution 4.1 needs Java 21; do NOT set -Djava.awt.headless=true.
set -uo pipefail

JAVA="${JAVA:-/opt/homebrew/opt/openjdk@21/bin/java}"
JAR="${LOGISIM_JAR:-/Applications/Logisim-evolution.app/Contents/app/logisim-evolution-4.1.0-all.jar}"
DIR="$(cd "$(dirname "$0")" && pwd)"
CIRC="$DIR/alu_regfile.circ"

for tool in "$JAVA" "$JAR" "$CIRC"; do
    [ -e "$tool" ] || { echo "missing: $tool" >&2; exit 127; }
done

fail=0
run() {
    local circuit="$1" vec="$2" label="$3"
    printf '%-52s' "$label"
    local out summary
    out="$("$JAVA" -jar "$JAR" --no-splash --locale en \
             --test-vector "$circuit" "$DIR/$vec" "$CIRC" 2>&1)"
    summary="$(printf '%s\n' "$out" | grep -E '^Passed:' | tail -1)"
    if printf '%s\n' "$summary" | grep -q 'Failed: 0'; then
        echo "OK   $summary"
    else
        echo "FAIL ${summary:-<no summary>}"
        printf '%s\n' "$out" | grep -E 'Error on test vector' -A4 | head -20
        fail=1
    fi
}

run datapath tests_datapath.vec            "datapath - directed scenarios"
run datapath tests_datapath_random.vec     "datapath - randomised programs"
run datapath tests_datapath_exhaustive.vec "datapath - all 56 instructions"
run main     tests_main.vec                "main - demo wrapper with Clock"

echo
if [ "$fail" -eq 0 ]; then echo "All test vectors passed."
else echo "Some test vectors FAILED." >&2; fi
exit "$fail"
