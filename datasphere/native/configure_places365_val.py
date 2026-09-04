"""Configure the pinned RL-ViGen Places loader for the validation split only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# [Claude 2026-09-02 04:05 MSK: two source families load the overlay dataset, not one. RL-ViGen's
# utils.py and dmcontrol-generalization-benchmark's src/augmentations.py hold the same loader with
# different worker counts and different config files -- RL-ViGen copied it. soda calls
# augmentations.random_overlay exactly as svea/sgqn call utils.random_overlay, so if only one of
# them is pinned to `val` the two are overlaying from DIFFERENT image distributions and their
# numbers are not comparable. That, not convenience, is why this is generalised.]
FLAVORS = {
    "rlvigen": {
        "loader": "utils.py",
        "config": "cfgs/aug_config.cfg",
        "workers": 8,
        "witness": "cfgs/aug_config.cfg",
    },
    "dmc_gb": {
        "loader": "src/augmentations.py",
        "config": "setup/config.cfg",
        "workers": 16,
        "witness": "src/algorithms/soda.py",
    },
}


def signatures(workers: int) -> tuple[str, str]:
    unpatched = f"def _load_places(batch_size=256, image_size=84, num_workers={workers}, use_val=False):"
    return unpatched, unpatched.replace("use_val=False", "use_val=True")


UNPATCHED_FALLBACK = """\t\t\tif not os.path.exists(fp):
\t\t\t\tprint(f'Warning: path {fp} does not exist, falling back to {data_dir}')
\t\t\t\tfp = data_dir"""
PATCHED_FALLBACK = """\t\t\tif not os.path.isdir(fp):
\t\t\t\traise FileNotFoundError(
\t\t\t\t\tf'required Places365 {partition} split is absent at {fp}; fallback disabled'
\t\t\t\t)"""


def fail(message: str) -> None:
    raise ValueError(message)


def configure(repo: Path, dataset_root: Path, check_only: bool, flavor: str = "rlvigen") -> None:
    if flavor not in FLAVORS:
        fail(f"unknown Places365 loader flavor: {flavor}")
    entry = FLAVORS[flavor]

    expected_images = dataset_root / "places365_standard" / "val" / "images"
    if not expected_images.is_dir():
        fail(f"Places365 validation images are absent: {expected_images}")

    loader_path = repo / entry["loader"]
    config_path = repo / entry["config"]
    if not loader_path.is_file() or not (repo / entry["witness"]).exists():
        fail(f"not a {flavor} checkout: {repo}")

    unpatched_signature, patched_signature = signatures(entry["workers"])
    source = loader_path.read_text()
    changed = False
    if unpatched_signature in source:
        source = source.replace(unpatched_signature, patched_signature, 1)
        changed = True
    elif patched_signature not in source:
        fail("unexpected Places365 loader signature")
    if UNPATCHED_FALLBACK in source:
        source = source.replace(UNPATCHED_FALLBACK, PATCHED_FALLBACK, 1)
        changed = True
    elif PATCHED_FALLBACK not in source:
        fail("unexpected Places365 loader fallback")

    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as error:
        fail(f"invalid {flavor} augmentation config: {error}")
    expected_datasets = [str(dataset_root.resolve())]
    config_is_correct = config.get("datasets") == expected_datasets

    if check_only:
        if changed or not config_is_correct:
            fail("Places365 validation loader is not configured")
        return

    if changed:
        loader_path.write_text(source)
    if not config_is_correct:
        config["datasets"] = expected_datasets
        config_path.write_text(json.dumps(config, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--flavor", default="rlvigen", choices=sorted(FLAVORS))
    args = parser.parse_args(argv)
    try:
        configure(args.repo.resolve(), args.dataset_root.resolve(), args.check, args.flavor)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
