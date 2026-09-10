# Source this before building or running the analysis binaries:
#     source scripts/env.sh
#
# SVF lives outside the vault, alongside the other tool artifacts, and is never
# copied into it (see CLAUDE.md).

IRQRACE_ROOT="$(cd -- "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1; pwd -P)"
export IRQRACE_ROOT
export SVF_DIR="${SVF_DIR:-$(cd "$IRQRACE_ROOT/../.." && pwd)/toolchain/SVF}"
export LLVM_DIR="${LLVM_DIR:-/usr/lib/llvm-14}"
export Z3_DIR="${Z3_DIR:-/usr}"
export PYTHONPATH="$IRQRACE_ROOT/src:${PYTHONPATH:-}"
export PATH="$IRQRACE_ROOT/analysis/build/bin:$SVF_DIR/Release-build/bin:$PATH"

echo "SVF_DIR=$SVF_DIR"
echo "LLVM_DIR=$LLVM_DIR"
