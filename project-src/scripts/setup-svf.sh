#!/usr/bin/env bash
# Build SVF against the SYSTEM LLVM 14 rather than downloading SVF's own
# prebuilt LLVM.
#
# Two reasons. The prebuilt LLVM release is several gigabytes unpacked, and the
# development machine has under 4 GB free; and the subjects are compiled with
# the distribution's clang-14, so using the same LLVM for the analysis keeps the
# bitcode version and the analysis in step. Built this way SVF costs about 64 MB
# and roughly ten minutes on four cores.
#
# SVF 2.7 is the release that targets LLVM 14.0.0 (its setup.sh names
# llvm-14.0.0.obj). SVF 3.x requires LLVM 16 and would reintroduce the download.
set -euo pipefail

SVF_TAG="${SVF_TAG:-SVF-2.7}"
LLVM_DIR="${LLVM_DIR:-/usr/lib/llvm-14}"
Z3_DIR="${Z3_DIR:-/usr}"
HERE="$(cd -- "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1; pwd -P)"
SVF_DIR="${SVF_DIR:-$(cd "$HERE/../.." && pwd)/toolchain/SVF}"

for f in "$LLVM_DIR/lib/cmake/llvm/LLVMConfig.cmake" "$LLVM_DIR/include/llvm/IR/Module.h"; do
  [[ -e "$f" ]] || { echo "missing $f -- apt install llvm-14-dev clang-14" >&2; exit 1; }
done

if [[ ! -d "$SVF_DIR/.git" ]]; then
  mkdir -p "$(dirname "$SVF_DIR")"
  git clone --depth 1 --branch "$SVF_TAG" https://github.com/SVF-tools/SVF.git "$SVF_DIR"
fi

# SVF is built -fno-rtti to match LLVM. clang-14 on this machine defaults to the
# GCC 12 installation, which ships no libstdc++.so, so use g++-11 explicitly.
cmake -GNinja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER="${CC:-gcc-11}" \
  -DCMAKE_CXX_COMPILER="${CXX:-g++-11}" \
  -DCMAKE_CXX_FLAGS=-Wno-error \
  -DLLVM_DIR="$LLVM_DIR/lib/cmake/llvm" \
  -DZ3_DIR="$Z3_DIR" \
  -S "$SVF_DIR" -B "$SVF_DIR/Release-build"

ninja -C "$SVF_DIR/Release-build" -j"${JOBS:-3}"
echo "SVF built: $SVF_DIR/Release-build/bin"
