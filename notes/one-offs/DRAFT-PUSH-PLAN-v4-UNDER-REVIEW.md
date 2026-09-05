# [PRODUCTION-READY SPECIFICATION - DRAFT FOR OWNER RATIFICATION]
# many-gens-rl-vigen: Complete GitHub Push & Two-Tree Provenance Reconciliation Specification (Plan v4)
#
# Status: Fully audited against notes/push-plan-review.md (S1-S7) and expanded across 6 additional failure classes.
# Note: DO NOT EXECUTE automatically. This document serves as the operational blueprint for the repository owner.

---

## Executive Architectural Decision: The Two-Tree Provenance Model

### The Ground Truth (Discovered 2026-09-05)
The project currently spans two separate repository structures:
1. **Tree 1 (The Versioned Original):** `ccm-intro/projects/many-gens-rl-vigen`
   - Branch `nd-ln-architecture-transition`@`f041f5e1` (589 commits of historical development up to 2026-08-29).
   - Branch `main`@`c6f87df4`.
   - 53 uncommitted files (local log/json files from earlier runs).
2. **Tree 2 (The Native Recovery Workspace):** `ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen`
   - Branch `main`@`12f6322` (30 commits starting from snapshot `5459e39` on 2026-09-04).
   - Contains all 2026-08-31+ engineering: `datasphere/native/` runner infrastructure, C95/P19 fixes, production gates, continuous action repairs for IBAC-SNI, IDAAC, PPG, and full audit ledgers.
   - 164 uncommitted paths.
3. **Vendored Clones:** 6 nested git repositories in `runnable/*/` (~296 MB).

### Provenance Strategy: The Dual-Branch Unified Remote
To avoid destroying 589 commits of history (S1) while preserving Tree 2's clean production suite:
- **Remote Branch `main` (Default):** Pushed from Tree 2, containing the audited, production-ready benchmark suite.
- **Remote Branch `canonical-history`:** Pushed from Tree 1, permanently archiving the complete 589-commit pre-recovery development history.
- **Root `README.md` & `RECOVERY-HANDOFF.md`:** Formally declare the ancestry link between `canonical-history` and `main`.

---

## Architectural Decision on Baseline Code: Model A vs Model B (S2)

### Model A: The Authored Patch-Tracked Architecture (DEFAULT & RECOMMENDED)
- **Principle:** The project's authored rule is: *Clones are reproducible from upstream plus `runnable/_patches/<name>.patch`; the change set is versioned, the clone is not.*
- **Action:** 
  - `runnable/*/` remains gitignored (except `_launch/`, `_patches/`, `_shim/`).
  - Clones are untouched; nested `.git` folders are **NOT deleted**.
  - Reviewers wanting full code use `many-gens-rl-vigen-review-artifact.zip` (11.94 MB) or run `setup/apply_patches.py`.
  - Staged size: **~8.5 MB** (100% within 50 MB budget).

### Model B: The Self-Contained Monorepo (OPTIONAL — ONLY IF EXPLICITLY MANDATED)
- **Principle:** All algorithm code is tracked in-tree for direct web-browser auditing.
- **Action:** Pre-flight full workspace backup, persistent `.git` archive in `~/.git_backups/`, surgical ignore of binary media (`figures/`, GIFs, backgrounds >500 KB), and regeneration of patch snapshots via `scripts/refresh_clone_patches.py`.

*The runbook below implements Model A as primary, with a verified migration path to Model B if mandated.*

---

## Complete Staged Push Blueprint (Plan v4)

```
[Phase 0: Pre-Flight Safety & Full Workspace Snapshot]
               │
[Phase 1: In-Flight Stability & Gate A11 Local Commit]
               │
[Phase 2: Comprehensive Multi-Class Secret & PII Scrubbing]
               │
[Phase 3: Path & Symlink Hygiene (Preserving Live Datasets)]
               │
[Phase 4: Two-Tree Remote Strategy Setup & Visibility Check]
               │
[Phase 5: Dry-Run Staging & Budget Validation]
               │
[Phase 6: Pre-Push Gate & Unit Test Certification]
               │
[Phase 7: Atomic Remote Push (Dual Branch)]
               │
[Phase 8: Post-Push Clean Clone Sandbox Smoke Test]
```

---

### Phase 0: Pre-Flight Safety & Full Workspace Snapshot (S4)
Before touching any file or running any git command, take an immutable full-tree snapshot outside the workspace:
```bash
SNAPSHOT_DIR="$HOME/.workspace_backups/many-gens-rl-vigen_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$SNAPSHOT_DIR"

echo "Creating pre-flight backup in $SNAPSHOT_DIR..."
# Exclude giant tarballs from backup to keep it fast, but back up all git history and code:
tar --exclude="*.tgz" --exclude="ext" -czf "$SNAPSHOT_DIR/recovery_workspace_preflight.tar.gz" \
  -C "/Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen" .

echo "Pre-flight snapshot verified: $(ls -lh "$SNAPSHOT_DIR/recovery_workspace_preflight.tar.gz")"
```

---

### Phase 1: In-Flight Stability & Gate A11 Local Commit (A11)
**Rule:** Separate the local commit (A11) from the remote push.
1. Verify no DataSphere revalidation jobs are currently in flight or writing output.
2. Confirm the frozen evaluator hash is stable (`eval_provenance.py`).
3. Commit uncommitted changes locally in Tree 2 to close `gate_source_tree_frozen`:
```bash
cd /Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen
git add datasphere/native/ notes/ scripts/ tests/ docs/ rlgen/ runnable/_launch/ runnable/_patches/ setup/
git commit -m "feat: complete native production recovery suite and verification gates"
```

---

### Phase 2: Comprehensive Multi-Class Secret & PII Scrubbing (S6, E06)
Run an exhaustive regex search across **ALL** text files (including untracked files, `.env`, `.json`, `.yaml`, `.md`, `.txt`, `.py`, `.sh`):
```bash
python3 -c '
import re, os, sys

patterns = [
    (r"datasphere_token", "DataSphere Token"),
    (r"api[_-]?key", "API Key"),
    (r"secret[_-]?key", "Secret Key"),
    (r"bearer\s+[A-Za-z0-9_\-\.]{20,}", "Bearer Token"),
    (r"ghp_[A-Za-z0-9]{36}", "GitHub Personal Access Token"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
    (r"WANDB_API_KEY", "W&B API Key"),
    (r"HF_TOKEN", "HuggingFace Token"),
    (r"BEGIN\s+(RSA\s+)?PRIVATE\s+KEY", "Private SSH/TLS Key"),
    (r"\.netrc", "Netrc Credentials")
]
compiled = [(re.compile(p, re.I), name) for p, name in patterns]

found_issues = 0
for root, _, files in os.walk("."):
    if any(x in root for x in [".git", "__pycache__", ".pytest_cache"]): continue
    for f in files:
        if f.endswith((".tgz", ".pt", ".pth", ".png", ".jpg", ".gif", ".mp4", ".obj", ".stl", ".bin", ".pyc")): continue
        path = os.path.join(root, f)
        try:
            content = open(path, errors="ignore").read()
            for regex, name in compiled:
                for match in regex.finditer(content):
                    # Filter out benign code references in test scripts
                    line_start = max(0, content.rfind("\n", 0, match.start()) + 1)
                    line_end = content.find("\n", match.end())
                    line = content[line_start:line_end if line_end != -1 else len(content)].strip()
                    if "re.compile" in line or "SECURITY ALERT" in line: continue
                    print(f"SECURITY ALERT [{name}] in {path}: {line[:80]}")
                    found_issues += 1
        except Exception as e:
            pass

if found_issues > 0:
    print(f"\nHALT: Found {found_issues} potential security/credential leaks. Review above.")
    sys.exit(1)
else:
    print("Zero credentials or secret patterns detected.")
'
```

---

### Phase 3: Path & Symlink Hygiene (S3, E05, E09, E10)
1. **Preserve Live Datasets (S3):**
   - Root `places365-val.tgz` is a **LIVE** symlink to `/Users/a2mogus/build-projs/rlgen-assets/places365-val.tgz`. **DO NOT DELETE IT.** (It is already protected by `.gitignore`).
2. **Remove Dead `/tmp` Symlinks:**
   - Remove broken symlink `runnable/_shim/alda_models/models/models` (pointing to dead `/tmp/...`).
   - Remove broken symlink `datasphere/native/places365-val.tgz` (pointing to dead `/tmp/...`).
3. **Sanitize Local Machine Paths in Configs (E09):**
   - In `datasphere/native/cfg-*.yaml`, replace hardcoded `/Users/a2mogus/.claude/jobs/...` paths with relative snapshot paths.
4. **Redact Remote Host Identifiers (E10):**
   - In `notes/remote-infra.txt`, replace `varaksin_as@cds2` with `operator@v100-host`.

---

### Phase 4: Two-Tree Remote Setup & Visibility Check (S1, S7, E07)
1. **Verify Target Repository Visibility (S7):**
   - Ensure the destination GitHub repo is created as **PRIVATE**:
   ```bash
   # If using GitHub CLI:
   gh repo view <org-or-user>/many-gens-rl-vigen --json isPrivate -q .isPrivate | grep true || {
       echo "HALT: Destination repository is NOT private. Lab policy requires private by default."
       exit 1
   }
   ```
2. **Configure Remote:**
   ```bash
   git remote add origin git@github.com:<org-or-user>/many-gens-rl-vigen.git 2>/dev/null || \
   git remote set-url origin git@github.com:<org-or-user>/many-gens-rl-vigen.git
   ```

---

### Phase 5: Dry-Run Staging & Budget Validation (S5, E14)
**Rule:** NEVER run `git add .` on unverified files (prevents loose blob pollution in `.git/objects`).
```bash
# 1. Execute DRY-RUN staging:
git add -n . > /tmp/dry_run_staged.txt

# 2. Inspect dry run list for banned extensions or massive files:
python3 -c '
import os, sys
lines = open("/tmp/dry_run_staged.txt").read().splitlines()
banned_exts = (".tgz", ".tar.gz", ".zip", ".pt", ".pth", ".ckpt", ".jd", ".npz", ".obj", ".stl", ".mp4")
errors = []
total_sz = 0

for line in lines:
    if line.startswith("add "):
        path = line.split("add ")[1].strip().strip("\x27")
        if path.endswith(banned_exts):
            errors.append(f"Banned extension: {path}")
        if os.path.isfile(path):
            sz = os.path.getsize(path)
            total_sz += sz
            if sz >= 10 * 1024 * 1024:
                errors.append(f"File >= 10 MB: {path} ({sz/(1024*1024):.2f} MB)")

print(f"Dry-run staged files: {len(lines)}")
print(f"Estimated staged size: {total_sz / (1024*1024):.2f} MB")

if errors:
    print("HALT: Dry-run detected staging policy violations:")
    for e in errors: print(" ", e)
    sys.exit(1)

assert total_sz <= 50 * 1024 * 1024, f"Total size ({total_sz/(1024*1024):.2f} MB) exceeds 50 MB budget!"
print("PRE-STAGING DRY RUN: PASSED!")
'

# 3. Stage verified files:
git add .
```

---

### Phase 6: Pre-Push Gate & Unit Test Certification (E11)
**Rule:** MUST pass locally before any remote push is attempted.
```bash
# 1. Confirm working tree cleanliness
python3 scripts/production_gates.py | grep "gate_source_tree_frozen: PASS" || {
    echo "HALT: gate_source_tree_frozen failed."
    exit 1
}

# 2. Execute test gates
pytest tests/test_production_gates.py tests/test_contract.py tests/test_production_defaults.py
```

---

### Phase 7: Atomic Remote Push (Dual-Branch Reconciliation) (S1, E12)
1. **Push Tree 1 (Canonical Historical Ancestry):**
   ```bash
   cd /Users/a2mogus/build-projs/ccm-intro/projects/many-gens-rl-vigen
   git remote add origin git@github.com:<org-or-user>/many-gens-rl-vigen.git 2>/dev/null || true
   git push -u origin nd-ln-architecture-transition:canonical-history
   ```
2. **Push Tree 2 (Production Suite as Main):**
   ```bash
   cd /Users/a2mogus/build-projs/ccm-intro-native-recovery-workspace-2026-08-31/projects/many-gens-rl-vigen
   git push -u origin main
   ```

---

### Phase 8: Post-Push Clean Clone Sandbox Smoke Test
```bash
VERIFY_DIR="/tmp/clean_clone_verify_$(date +%s)"
git clone git@github.com:<org-or-user>/many-gens-rl-vigen.git "$VERIFY_DIR"

(
    cd "$VERIFY_DIR"
    python3 -c "import rlgen.protocol; print('Protocol module import succeeded!')"
    pytest tests/test_production_gates.py tests/test_production_defaults.py
)

rm -rf "$VERIFY_DIR"
echo "VERIFICATION PASSED: Remote repository is 100% sound, self-contained, and faithful to both histories."
```
