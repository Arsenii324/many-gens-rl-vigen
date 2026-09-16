#!/usr/bin/env python3
"""Fetch ibac_sni s101's terminal snapshot and its 600,064-frame intermediate, and compare WEIGHTS.

The two files are not byte-identical, so `audit_record_frame_provenance.py`, which indexes
checkpoints by the sha256 of the file, cannot tie them together. This asks the narrower question the
file hash cannot: are the parameters the same?

Re-derivable: it pulls both files from the production host by exact path. It needs the host to still
hold that run directory, and it needs torch plus ibac's own ACModel class importable, which is why
it lives here rather than inside the auditor.

    python results/evidence/ibac-endpoint-weights-equal-frame-600064/compare_weights.py
"""
import pathlib, subprocess, sys, tempfile

HOST = "varaksin_as@100.98.2.11"
RUN = "~/rlvigen-runs/card1-20260916-203537/native-out/cells/ibac_sni-s101"
ROOT = pathlib.Path(__file__).resolve().parents[3]

def main() -> int:
    sys.path.insert(0, str(ROOT / "runnable" / "ibac_sni" / "torch_rl"))
    import torch
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        for remote, local in ((f"{RUN}/snapshot.pt", "snapshot.pt"),
                              (f"{RUN}/checkpoints/model_600064.pt", "model_600064.pt")):
            rc = subprocess.run(["scp", "-q", "-o", "BatchMode=yes", f"{HOST}:{remote}",
                                 str(tmp / local)]).returncode
            if rc != 0:
                print(f"FETCH FAILED: {remote}")
                return 2
        a = torch.load(tmp / "snapshot.pt", weights_only=False, map_location="cpu")
        b = torch.load(tmp / "model_600064.pt", weights_only=False, map_location="cpu")
        sa, sb = a.state_dict(), b.state_dict()
        print(f"snapshot.pt      {(tmp/'snapshot.pt').stat().st_size} bytes, {len(sa)} tensors")
        print(f"model_600064.pt  {(tmp/'model_600064.pt').stat().st_size} bytes, {len(sb)} tensors")
        if set(sa) != set(sb):
            print("KEY MISMATCH:", sorted(set(sa) ^ set(sb)))
            return 1
        worst = 0.0
        for k in sa:
            x, y = sa[k].float(), sb[k].float()
            if x.shape != y.shape:
                print(f"SHAPE MISMATCH {k}: {x.shape} vs {y.shape}")
                return 1
            worst = max(worst, (x - y).abs().max().item())
        print(f"tensors compared: {len(sa)}")
        print(f"max |snapshot - model_600064| over every parameter: {worst}")
        print("EQUAL" if worst == 0.0 else "NOT EQUAL")
        return 0 if worst == 0.0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
