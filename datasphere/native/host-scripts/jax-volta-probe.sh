set -uo pipefail
echo "=== JAX/XLA on this card: does ANY convolution run? ==="
pip3 install -q "jax[cuda12]==0.4.35" 2>&1 | tail -2
python3 - <<'PY'
import sys
try:
    import jax, jax.numpy as jnp
    from jax import lax
except Exception as e:
    print(f"  IMPORT FAILED: {type(e).__name__}: {e}"); sys.exit(2)
print(f"  jax {jax.__version__}  jaxlib {getattr(jax,'lib',None) and jax.lib.__version__}")
for d in jax.devices():
    print(f"  device: {d.device_kind}  platform={d.platform}")
# 1. trivial elementwise -- proves the device works at all
try:
    x = jnp.ones((256, 256)); print("  matmul ok:", float((x @ x)[0, 0]))
except Exception as e:
    print(f"  MATMUL FAILED: {type(e).__name__}: {str(e)[:200]}"); sys.exit(3)
# 2. a tiny conv -- the operation ctrl dies on
try:
    img = jnp.ones((1, 3, 8, 8)); k = jnp.ones((4, 3, 3, 3))
    out = lax.conv_general_dilated(img, k, (1, 1), "SAME",
                                   dimension_numbers=("NCHW", "OIHW", "NCHW"))
    print("  TINY CONV OK:", out.shape)
except Exception as e:
    print(f"  TINY CONV FAILED: {type(e).__name__}: {str(e)[:300]}")
# 3. ctrl's exact failing shape
try:
    img = jnp.ones((10, 9, 64, 64)); k = jnp.ones((16, 9, 3, 3))
    out = lax.conv_general_dilated(img, k, (1, 1), "SAME",
                                   dimension_numbers=("NCHW", "OIHW", "NCHW"))
    print("  CTRL-SHAPE CONV OK:", out.shape)
except Exception as e:
    print(f"  CTRL-SHAPE CONV FAILED: {type(e).__name__}: {str(e)[:300]}")
PY
echo "=== DONE ==="
