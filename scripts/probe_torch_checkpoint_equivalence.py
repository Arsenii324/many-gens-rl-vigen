#!/usr/bin/env python3
"""Do two `torch.save` files hold the same tensors in the same structure, whatever their bytes?

    python scripts/probe_torch_checkpoint_equivalence.py A.pt B.pt

Two checkpoint files can differ byte-for-byte and still hold identical weights. For example, ppg's
intermediate `model012.jd` and its terminal `model_terminal.jd` were written by different calls
with different pickle protocols. This probe answers the question without importing the pickled
classes. Loading a whole pickled `nn.Module` needs the training package and its mpi4py/gym3
imports.

1. **Storages.** Every tensor storage in the zip (`archive/data/<key>`) is compared byte-for-byte,
   by key.
2. **Structure.** `data.pkl` is unpickled with stubs. Classes become inert records of their name,
   constructor arguments and state. Each tensor becomes (storage key, dtype, offset, shape,
   stride, requires_grad). The resulting object graph is serialised canonically and compared.
   Pickle protocol, memo layout and framing do not survive this, so they cannot cause a
   difference.

Equal storages plus an equal graph means the two files hold the same model, down to parameter
names and tensor views. The probe prints each file's SHA-256 so the output can be tied to a hash
taken elsewhere.
"""
from __future__ import annotations

import collections
import hashlib
import io
import json
import pickle
import sys
import zipfile


class _Stub:
    qualname = "?"

    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)
        obj.args, obj.state = args, None
        return obj

    def __init__(self, *args, **kwargs):
        self.args = args

    def __setstate__(self, state):
        self.state = state


def _tensor(storage, offset, size, stride, requires_grad, *_rest):
    return {"tensor": storage, "offset": offset, "size": list(size), "stride": list(stride),
            "requires_grad": requires_grad}


def _parameter(data, requires_grad, *_rest):
    return {"parameter": data, "requires_grad": requires_grad}


class _Unpickler(pickle.Unpickler):
    _classes: dict[str, type] = {}
    SPECIAL = {
        ("torch._utils", "_rebuild_tensor_v2"): _tensor,
        ("torch._utils", "_rebuild_parameter"): _parameter,
        ("collections", "OrderedDict"): collections.OrderedDict,
        # protocol 2 spells builtins the Python 2 way and rebuilds a set by REDUCE
        ("__builtin__", "set"): set, ("builtins", "set"): set,
        ("__builtin__", "frozenset"): frozenset, ("builtins", "frozenset"): frozenset,
    }

    def find_class(self, module, name):
        if (module, name) in self.SPECIAL:
            return self.SPECIAL[(module, name)]
        if module == "torch" and name.endswith("Storage"):
            return f"{module}.{name}"
        key = f"{module}.{name}"
        if key not in self._classes:
            self._classes[key] = type(name, (_Stub,), {"qualname": key})
        return self._classes[key]

    def persistent_load(self, pid):
        kind, storage_type, key, location, numel = pid
        return {"storage": key, "type": str(storage_type), "location": location, "numel": numel}


def _canon(obj):
    if isinstance(obj, _Stub):
        return {"class": obj.qualname, "args": _canon(obj.args), "state": _canon(obj.state)}
    if isinstance(obj, dict):
        return [["dict"]] + [[_canon(k), _canon(v)] for k, v in obj.items()]
    if isinstance(obj, (list, tuple)):
        return [_canon(x) for x in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(json.dumps(_canon(x), sort_keys=True) for x in obj)
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, type):
        return f"type:{getattr(obj, 'qualname', obj.__name__)}"
    return f"{type(obj).__name__}:{obj!r}"


def _load(path):
    z = zipfile.ZipFile(path)
    items = {i.filename.split("/", 1)[1]: z.read(i) for i in z.infolist()}
    graph = _canon(_Unpickler(io.BytesIO(items["data.pkl"])).load())
    return items, graph, hashlib.sha256(open(path, "rb").read()).hexdigest()


def main(a: str, b: str) -> int:
    ma, ga, sha_a = _load(a)
    mb, gb, sha_b = _load(b)
    print(f"A sha256 {sha_a}  members {len(ma)}")
    print(f"B sha256 {sha_b}  members {len(mb)}")
    sa = {k: v for k, v in ma.items() if k.startswith("data/")}
    sb = {k: v for k, v in mb.items() if k.startswith("data/")}
    same = sum(sa[k] == sb.get(k) for k in sa)
    print(f"storages A {len(sa)} B {len(sb)}  same keys {set(sa) == set(sb)}  byte-identical {same}")
    ja, jb = json.dumps(ga, sort_keys=True), json.dumps(gb, sort_keys=True)
    ha, hb = hashlib.sha256(ja.encode()).hexdigest(), hashlib.sha256(jb.encode()).hexdigest()
    print(f"data.pkl bytes A {len(ma['data.pkl'])} B {len(mb['data.pkl'])}")
    print(f"object graph sha256 A {ha[:16]} B {hb[:16]}  tensors A {ja.count(chr(34) + 'tensor' + chr(34))} "
          f"B {jb.count(chr(34) + 'tensor' + chr(34))}")
    if ja != jb:
        i = next(i for i, (x, y) in enumerate(zip(ja, jb)) if x != y)
        print(f"  first difference at char {i}:\n  A: ...{ja[max(0, i - 80):i + 80]}\n  B: ...{jb[max(0, i - 80):i + 80]}")
    equal = set(sa) == set(sb) and same == len(sa) and ja == jb
    print("VERDICT", "same tensors, same structure" if equal else "DIFFERENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:3]))
