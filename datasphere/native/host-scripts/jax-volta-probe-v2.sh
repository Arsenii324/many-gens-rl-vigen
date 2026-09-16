#!/usr/bin/env bash
# Does THIS jax build run a convolution on THIS card?
#
# The question ctrl's failure poses is narrow: XLA's autotuner reported that every cuDNN engine
# rejected the first convolution on a Tesla V100 (sm_70), while the same family attested on an
# L4 (sm_89). This probe answers it directly and separates two causes that look alike:
#   - a matmul proves the GPU, the driver and XLA work at all;
#   - a conv immediately after proves whether CONVOLUTION specifically is what fails.
# If matmul passes and conv fails, the sm_70 lead is confirmed and ctrl cannot run on this host
# with this build. If both fail, the cause is broader than cuDNN and the lead is wrong.
#
# The previous version of this probe ran in `ubuntu:24.04`, which has no interpreter: it printed
# `python3: command not found`, measured nothing, and still exited 0. Hence the explicit status
# propagation below -- this script must exit non-zero when it proves nothing.
set -uo pipefail
echo "=== image python ==="
# The pinned image is a CUDA *runtime* image and carries no interpreter. The cells install one at
# job start; the probe does the same rather than assuming, because the last probe's whole failure
# was running somewhere with no python and reporting success anyway.
if ! python3 -VV 2>/dev/null; then
  echo "no interpreter present; installing one (same as a cell does)"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq python3 python3-pip >/dev/null 2>&1
  python3 -VV || { echo "FATAL: could not obtain an interpreter -- the probe measured NOTHING"; exit 90; }
fi

echo "=== installing ctrl's declared jax spec (families.json, unpinned jaxlib) ==="
pip3 install --quiet --no-input 'jax[cuda12]==0.4.35' 2>&1 | tail -5
rc=${PIPESTATUS[0]}
if [[ $rc -ne 0 ]]; then
  echo "FATAL: jax did not install (rc=$rc). This probe says NOTHING about sm_70."
  exit 91
fi

# MATCH THE CELL'S ENVIRONMENT OR THE PROBE TESTS SOMETHING ELSE.
# battery-chain.sh:99 launches every cell with CUDA_ROOT=/usr/local/cuda. Without it, jax's
# _cuda_path() falls past the CUDA_ROOT branch into _try_cuda_nvcc_import(), where
# `cuda_nvcc.__file__` is None for the namespace package and the import dies with
# `TypeError: expected str, bytes or os.PathLike object, not NoneType`. That is a property of THIS
# PROBE's environment, not of ctrl on this card, and reporting it as the latter would be a lie.
export CUDA_ROOT=/usr/local/cuda
export CUDA_PATH=/usr/local/cuda
echo "CUDA_ROOT=$CUDA_ROOT exists=$([[ -d $CUDA_ROOT ]] && echo yes || echo NO)"

python3 - <<'PY'
import sys
import jax, jaxlib, numpy as np
print(f"jax={jax.__version__} jaxlib={jaxlib.__version__}")
try:
    devices = jax.devices()
except Exception as error:
    print(f"FATAL: jax.devices() raised {type(error).__name__}: {error}")
    sys.exit(92)
print("devices:", devices)
if not any(d.platform == "gpu" for d in devices):
    print("FATAL: no GPU device visible -- probe says NOTHING about sm_70")
    sys.exit(93)
for d in devices:
    print(f"  device: {d.device_kind} compute_capability={getattr(d, 'compute_capability', '?')}")

ok_matmul = False
try:                                    # 1. does the card compute at all
    x = jax.numpy.ones((512, 512), dtype=jax.numpy.float32)
    r = float((x @ x).sum())
    print(f"MATMUL OK  sum={r:.0f}")
    ok_matmul = True
except Exception as error:
    print(f"MATMUL FAILED  {type(error).__name__}: {str(error)[:600]}")

ok_conv = False
try:                                    # 2. the operation ctrl actually died on
    img = jax.numpy.ones((1, 3, 64, 64), dtype=jax.numpy.float32)
    kern = jax.numpy.ones((32, 3, 3, 3), dtype=jax.numpy.float32)
    out = jax.lax.conv_general_dilated(img, kern, (1, 1), "SAME",
                                       dimension_numbers=("NCHW", "OIHW", "NCHW"))
    out.block_until_ready()
    print(f"CONV OK    shape={out.shape} sum={float(out.sum()):.0f}")
    ok_conv = True
except Exception as error:
    print(f"CONV FAILED  {type(error).__name__}: {str(error)[:1200]}")

print()
if ok_matmul and ok_conv:
    print("VERDICT: this jax build runs convolutions on this card. The sm_70 lead is REFUTED;")
    print("         ctrl's failure must be explained by something else.")
    sys.exit(0)
if ok_matmul and not ok_conv:
    print("VERDICT: the card computes but CONVOLUTION fails. The sm_70 lead is CONFIRMED for this")
    print("         build: ctrl cannot run here without a jax/cuDNN build that covers sm_70.")
    sys.exit(10)
print("VERDICT: even matmul failed. The cause is broader than cuDNN; the sm_70 lead is NOT the")
print("         explanation and must not be recorded as one.")
sys.exit(11)
PY
status=$?
echo "=== probe python exit=$status ==="
exit $status
