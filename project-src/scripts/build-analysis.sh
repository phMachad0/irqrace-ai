#!/usr/bin/env bash
# Build the C++ analysis binaries (currently just irqrace-probe) against SVF.
set -euo pipefail

HERE="$(cd -- "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1; pwd -P)"
SVF_DIR="${SVF_DIR:-$(cd "$HERE/../.." && pwd)/toolchain/SVF}"
LLVM_DIR="${LLVM_DIR:-/usr/lib/llvm-14}"
Z3_DIR="${Z3_DIR:-/usr}"

[[ -f "$SVF_DIR/Release-build/svf/libSvfCore.a" ]] || {
  echo "SVF not built at $SVF_DIR -- run scripts/setup-svf.sh first" >&2; exit 1; }

SVF_DIR="$SVF_DIR" Z3_DIR="$Z3_DIR" cmake -GNinja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER="${CC:-gcc-11}" \
  -DCMAKE_CXX_COMPILER="${CXX:-g++-11}" \
  -DLLVM_DIR="$LLVM_DIR/lib/cmake/llvm" \
  -DSVF_DIR="$SVF_DIR" \
  -S "$HERE/analysis" -B "$HERE/analysis/build"

ninja -C "$HERE/analysis/build"
echo "built: $HERE/analysis/build/bin/irqrace-probe"
