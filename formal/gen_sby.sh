#!/usr/bin/env bash
# Generate a runnable SymbiYosys file from the formal/orbit_demo.sby template.
#
#   gen_sby.sh <template.sby> <out.sby> <harness.sv> <rtl.v>...
#
# The RTL file names replace the @RTL_FILES@ placeholder in [script], and the
# absolute paths of the RTL files and the harness are appended to [files],
# which must be the last section of the template. Used by mk/formal.mk for
# $(RTL) and by formal/vacuity.sh for the broken RTL copies.

set -euo pipefail

if [ $# -lt 4 ]; then
    echo "usage: $0 <template.sby> <out.sby> <harness.sv> <rtl.v>..." >&2
    exit 2
fi

tmpl=$1
out=$2
tb=$3
shift 3

if [ "$(grep -E '^\[[a-z]+\]' "$tmpl" | tail -n 1)" != "[files]" ]; then
    echo "$0: [files] must be the last section of $tmpl" >&2
    exit 1
fi

names=""
for f in "$@"; do
    names="$names $(basename "$f")"
done
names=${names# }

mkdir -p "$(dirname "$out")"
tmp=$(mktemp "$out.XXXXXX")
{
    sed "s|@RTL_FILES@|$names|" "$tmpl"
    for f in "$@" "$tb"; do
        realpath "$f"
    done
} > "$tmp"
mv "$tmp" "$out"
