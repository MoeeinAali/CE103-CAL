#!/usr/bin/env bash
# Run every *.vec next to this script against the matching circuit in *.circ.
#
# Naming: tests_<circuit>.vec  or  tests_<circuit>_<tag>.vec
#   tests_full_adder.vec      → full_adder
#   tests_bcd_digit.vec       → bcd_digit
#   tests_main_smoke.vec      → main
#
# Override with env:
#   JAVA=/path/to/java
#   LOGISIM_JAR=/path/to/logisim-evolution-*-all.jar
#   CIRC=bcd_adder.circ

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

JAVA="${JAVA:-/opt/homebrew/opt/openjdk@21/bin/java}"
if [[ ! -x "$JAVA" ]]; then
  JAVA="$(command -v java || true)"
fi

if [[ -z "${LOGISIM_JAR:-}" ]]; then
  LOGISIM_JAR="$(ls /Applications/Logisim-evolution.app/Contents/app/logisim-evolution-*-all.jar 2>/dev/null | head -n1 || true)"
fi

CIRC="${CIRC:-}"
if [[ -z "$CIRC" ]]; then
  CIRC="$(ls -1 *.circ 2>/dev/null | head -n1 || true)"
fi

die() { echo "error: $*" >&2; exit 1; }

[[ -n "$JAVA" && -x "$JAVA" ]] || die "java not found (set JAVA=...)"
[[ -n "$LOGISIM_JAR" && -f "$LOGISIM_JAR" ]] || die "Logisim jar not found (set LOGISIM_JAR=...)"
[[ -n "$CIRC" && -f "$CIRC" ]] || die "no .circ file found (set CIRC=...)"

shopt -s nullglob
vecs=(*.vec)
[[ ${#vecs[@]} -gt 0 ]] || die "no .vec files next to this script"

# Circuit names from the .circ XML: <circuit name="...">
CIRCUITS=()
while IFS= read -r c; do
  [[ -n "$c" ]] && CIRCUITS+=("$c")
done < <(grep -oE 'circuit name="[^"]+"' "$CIRC" | sed -E 's/circuit name="//; s/"$//' | sort -u)

circuit_from_vec() {
  local stem="$1" # without .vec / without tests_ prefix
  stem="${stem#tests_}"

  local best="" c
  for c in "${CIRCUITS[@]}"; do
    if [[ "$stem" == "$c" || "$stem" == "$c"_* ]]; then
      if [[ ${#c} -gt ${#best} ]]; then
        best="$c"
      fi
    fi
  done

  if [[ -n "$best" ]]; then
    printf '%s\n' "$best"
    return
  fi

  # Fallback: drop a single trailing _tag (e.g. _smoke).
  if [[ "$stem" == *_* ]]; then
    printf '%s\n' "${stem%_*}"
  else
    printf '%s\n' "$stem"
  fi
}

pass=0
fail=0
total=${#vecs[@]}

echo "circ : $CIRC"
echo "java : $JAVA"
echo "jar  : $LOGISIM_JAR"
echo "vecs : $total"
echo

for vec in "${vecs[@]}"; do
  stem="${vec%.vec}"
  circuit="$(circuit_from_vec "$stem")"
  echo "=== $vec  →  circuit '$circuit' ==="
  if "$JAVA" -jar "$LOGISIM_JAR" --no-splash --locale en \
      --test-vector "$circuit" "$vec" "$CIRC"; then
    echo "PASS: $vec"
    pass=$((pass + 1))
  else
    echo "FAIL: $vec"
    fail=$((fail + 1))
  fi
  echo
done

echo "summary: $pass/$total passed, $fail failed"
[[ "$fail" -eq 0 ]]
