#!/usr/bin/env bash
# WHY the conv fails, and whether it can be made to work without changing the declared jax spec.
#
# The previous probe established that jax runs and conv does not. It did not capture the cuDNN
# version (pip --quiet | tail -5 ate it) nor the per-algorithm errors (truncated at 1200 chars),
# which are the two things that separate "Volta is uncovered" from "the loaded cuDNN mismatches
# the one XLA was built against". `<unknown cudnn status: 5003>` points at the latter: XLA printing
# UNKNOWN means cuDNN returned a code its build does not know.
#
# It also tries the one lever that would let ctrl run AS DECLARED: xla_gpu_autotune_level=0 skips
# the autotuner and takes cuDNN's default algorithm. If the failure is the autotuner probing
# engines that do not exist on sm_70, that flag avoids it. If the default algorithm fails too, no
# flag saves it and the build itself has to change.
set -uo pipefail
if ! python3 -VV 2>/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq python3 python3-pip >/dev/null 2>&1
  python3 -VV || { echo "FATAL: no interpreter -- measured NOTHING"; exit 90; }
fi
pip3 install --no-input 'jax[cuda12]==0.4.35' 2>&1 | grep -E "Successfully installed|ERROR" | tail -3
[[ ${PIPESTATUS[0]} -eq 0 ]] || { echo "FATAL: install failed -- measured NOTHING"; exit 91; }

export CUDA_ROOT=/usr/local/cuda CUDA_PATH=/usr/local/cuda
echo "=== installed CUDA/cuDNN pip packages ==="
pip3 list 2>/dev/null | grep -iE "nvidia|jax" || true
echo "=== cuDNN shared libraries actually present ==="
find / -name 'libcudnn*.so*' -maxdepth 8 2>/dev/null | head -8

for level in 4 0; do
  echo
  echo "=== conv with xla_gpu_autotune_level=$level ==="
  XLA_FLAGS="--xla_gpu_autotune_level=$level" python3 - "$level" <<'PY'
import sys
lvl = sys.argv[1]
import jax
print("cudnn version as jaxlib sees it:", getattr(jax.lib, "cuda_versions", None) and
      jax.lib.cuda_versions.cudnn_get_version() or "unavailable")
try:
    img = jax.numpy.ones((1, 3, 64, 64), dtype=jax.numpy.float32)
    kern = jax.numpy.ones((32, 3, 3, 3), dtype=jax.numpy.float32)
    out = jax.lax.conv_general_dilated(img, kern, (1, 1), "SAME",
                                       dimension_numbers=("NCHW", "OIHW", "NCHW"))
    out.block_until_ready()
    print(f"CONV OK at autotune_level={lvl}  sum={float(out.sum()):.0f}")
except Exception as error:
    print(f"CONV FAILED at autotune_level={lvl}")
    print(str(error)[:4000])          # FULL per-algorithm errors, not truncated to 1200
PY
done
echo "=== DIAG DONE ==="
