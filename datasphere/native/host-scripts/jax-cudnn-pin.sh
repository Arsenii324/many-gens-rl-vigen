#!/usr/bin/env bash
# Is ctrl's conv failure the CARD (sm_70) or the DEPENDENCY RESOLUTION DATE?
#
# ctrl pins jax and jaxlib and leaves every nvidia-* transitive unpinned, so they resolve to
# whatever is newest ON THE DAY THE CELL RUNS. Today that is cuDNN 9.26.0.51 / CUDA 12.9 against
# jaxlib 0.4.34, built ~Oct 2024. Every engine returns `<unknown cudnn status: 5003>` -- XLA
# printing UNKNOWN means the loaded cuDNN returned a code its build does not know, which is the
# signature of a version skew rather than of an unsupported architecture.
#
# ctrl attested on an L4 at an EARLIER DATE, when pip would have resolved an older cuDNN. So the
# L4/V100 split may be a date split wearing a hardware label. This decides it: same card, same
# jax, older cuDNN.
#   conv works  -> drift. ctrl runs here once the stack is pinned. sm_70 was never the cause.
#   conv fails with a RECOGNISED arch error -> genuinely the card.
#   conv fails with 5003 again -> neither pin is old enough; report that rather than concluding.
set -uo pipefail
if ! python3 -VV 2>/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq python3 python3-pip >/dev/null 2>&1
  python3 -VV || { echo "FATAL: no interpreter -- measured NOTHING"; exit 90; }
fi
export CUDA_ROOT=/usr/local/cuda CUDA_PATH=/usr/local/cuda
pip3 install --quiet --no-input 'jax[cuda12]==0.4.35' 2>&1 | tail -2
[[ ${PIPESTATUS[0]} -eq 0 ]] || { echo "FATAL: base install failed"; exit 91; }

run_conv () {
  python3 - "$1" <<'PY'
import sys
label = sys.argv[1]
import jax
try:
    img = jax.numpy.ones((1, 3, 64, 64), dtype=jax.numpy.float32)
    kern = jax.numpy.ones((32, 3, 3, 3), dtype=jax.numpy.float32)
    out = jax.lax.conv_general_dilated(img, kern, (1, 1), "SAME",
                                       dimension_numbers=("NCHW", "OIHW", "NCHW"))
    out.block_until_ready()
    print(f"RESULT {label}: CONV OK sum={float(out.sum()):.0f}")
except Exception as error:
    first = str(error).replace("\n", " ")[:300]
    print(f"RESULT {label}: CONV FAILED {first}")
PY
}

for ver in 9.5.1.17 9.1.0.70; do
  echo
  echo "=== pinning nvidia-cudnn-cu12==$ver ==="
  if pip3 install --quiet --no-input "nvidia-cudnn-cu12==$ver" 2>&1 | tail -2; then
    installed="$(pip3 list 2>/dev/null | awk '/nvidia-cudnn-cu12/{print $2}')"
    echo "installed cudnn: $installed"
    run_conv "cudnn=$installed"
  else
    echo "RESULT cudnn=$ver: INSTALL FAILED -- says nothing about the card"
  fi
done
echo "=== PIN DIAG DONE ==="
