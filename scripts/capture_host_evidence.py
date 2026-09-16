#!/usr/bin/env python3
"""Capture a verbatim excerpt as evidence, with enough provenance to re-derive it.

    # a slice of a host file, by pattern
    python scripts/capture_host_evidence.py ppg-nminibatch-clamp train-warnings \\
        --host-path ~/rlvigen-runs/card0-20260909-115331/native-out/cells/ppg-s1/training.log \\
        --grep 'nminibatch > ntrain' --max 5 \\
        --fact warning_count=293 --anchor 'header:# matched-lines: 293 '

    # a member of a result archive on the host
    ... --host-path ~/rlvigen-runs/reeval-v214/ppg-smoke-run1.tgz --tar-member ./offline_eval_cuda.jsonl

    # a local command (git history, a repo script's output)
    ... --command 'git show 237f876:datasphere/native/families.json' --grep '"nminibatch"'

Writes `results/evidence/<slug>/raw/<name>.txt` and records it in
`results/evidence/<slug>/manifest.json`.

## Why this exists

Findings in this project have repeatedly rested on artifacts that live only on the production host
-- training logs, sentinel files, result archives, `docker ps` snapshots -- and the run directories
holding them are finished scratch that will be reclaimed. A claim whose evidence has been deleted
can only be repeated, never checked, and this project has already had to retract claims that were
repeated rather than checked. So the excerpt comes into the repository, and with it everything
needed to tell whether it is still what it says it is:

* **where it came from** -- host, absolute path, byte size, mtime and SHA-256 of the SOURCE, taken
  at capture time. If the source still exists, it can be compared; if it changed, that is visible.
* **exactly how it was cut** -- the command, verbatim, and how many lines matched in total. An
  excerpt capped at `--max` lines says so, so a truncated excerpt cannot pass for a complete one.
* **its own hash** -- recorded in the manifest, so an excerpt edited after capture fails
  `tests/test_evidence_bundles_hold.py` instead of silently changing what the evidence says.
* **the facts it supports** -- `--fact key=value --anchor TEXT` binds a structured value to a
  substring that must appear in this excerpt. A fact with no anchor in its evidence is an
  assertion, and the test refuses it.

## Host rule

The production host allows docker operations and trivial shell only. Everything run there is
`stat`, `sha256sum`, `find`, `wc`, `grep`, `sed`, `head` or `tar`. No python, no writes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import shlex
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "results" / "evidence"
HOST = "varaksin_as@100.98.2.11"
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=25", HOST]


def _ssh(command: str) -> str:
    proc = subprocess.run(SSH + [command], capture_output=True, text=True, timeout=600)
    # ssh prints a post-quantum warning on stderr; only a non-zero status is an error
    if proc.returncode != 0:
        raise SystemExit(f"host command failed ({proc.returncode}): {command}\n{proc.stderr.strip()[-400:]}")
    return proc.stdout


def _local(command: str) -> str:
    proc = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=ROOT, timeout=600)
    if proc.returncode != 0:
        raise SystemExit(f"local command failed ({proc.returncode}): {command}\n{proc.stderr.strip()[-400:]}")
    return proc.stdout


def _host_path(raw: str) -> str:
    """Expand a leading ~ on the host side, never locally."""
    return raw if not raw.startswith("~/") else "$HOME/" + raw[2:]


def _q(path: str) -> str:
    # $HOME must stay expandable on the host; everything after it is quoted
    if path.startswith("$HOME/"):
        return '"$HOME"/' + shlex.quote(path[len("$HOME/"):])
    return shlex.quote(path)


def _hashes_command(args) -> str:
    d = _q(_host_path(args.host_hashes))
    glob = shlex.quote(args.name_glob)
    # sizes and hashes of every matching regular file, in name order; nothing is written
    return (f"cd {d} && find . -maxdepth 1 -type f -name {glob} | LC_ALL=C sort | "
            f"while read -r f; do printf '%s %s ' \"$(stat -c %s \"$f\")\" \"$(stat -c %Y \"$f\")\"; "
            f"sha256sum \"$f\"; done")


def _source_meta(args) -> dict:
    if args.host_hashes:
        d = _q(_host_path(args.host_hashes))
        out = _ssh(f"test -d {d} && echo DIR || echo MISSING")
        if out.strip() != "DIR":
            raise SystemExit(f"directory does not exist on the host: {args.host_hashes}")
        return {"kind": "host-dir-hashes", "host": HOST, "path": args.host_hashes, "glob": args.name_glob}
    if args.host_path:
        p = _q(_host_path(args.host_path))
        out = _ssh(f"test -e {p} || {{ echo MISSING; exit 0; }}; test -r {p} || {{ echo UNREADABLE; exit 0; }}; "
                   f"stat -c '%s %Y' {p}; sha256sum {p} | cut -d' ' -f1")
        if out.strip() == "MISSING":
            raise SystemExit(f"source does not exist on the host: {args.host_path}. "
                             "Evidence cannot be captured from a file that is gone -- say so in CLAIM.md instead.")
        if out.strip() == "UNREADABLE":
            raise SystemExit(f"source exists but is not readable by this user: {args.host_path} "
                             "(files written by root inside containers can be mode 600). Take it from "
                             "a readable copy, e.g. the cell's result archive, and say which in the note.")
        size_mtime, sha = out.strip().splitlines()
        size, mtime = size_mtime.split()
        return {"kind": "host-file", "host": HOST, "path": args.host_path,
                "bytes": int(size), "sha256": sha,
                "mtime": dt.datetime.fromtimestamp(int(mtime), dt.timezone.utc).isoformat()}
    if args.local_path:
        p = (ROOT / args.local_path)
        data = p.read_bytes()
        return {"kind": "repo-file", "path": args.local_path, "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest()}
    head = _local("git rev-parse HEAD").strip()
    return {"kind": "local-command", "command": args.command, "repo_head": head,
            "inputs": command_inputs(args.command)}


def command_inputs(command: str) -> dict[str, str]:
    """SHA-256 of every repo file a local command names.

    HEAD alone does not pin a command's input: the file may be uncommitted or edited since. So
    each token that resolves to a file under the project root is hashed at capture time.
    """
    inputs = {}
    for token in re.split(r"[\s'\"<>()|;]+", command):
        token = token.strip()
        if not token or token.startswith("-"):
            continue
        path = ROOT / token
        if path.is_file() and ROOT in path.resolve().parents:
            inputs[token] = hashlib.sha256(path.read_bytes()).hexdigest()
    return inputs


def _extract(args) -> tuple[str, str, int]:
    """Return (excerpt text, the exact extraction command, total matching lines)."""
    cap = f" | head -n {args.max}" if args.max else ""
    if args.host_hashes:
        command = _hashes_command(args)
        text = _ssh(command)
        return text, command, text.count("\n")
    # -o prints each match on its own line, so a 27 KB JSON row can be cut to the fields that matter
    gflags = "-n -o -E" if args.only_matching else "-n -E"
    cflags = "-o -E" if args.only_matching else "-c -E"
    ccount = " | wc -l" if args.only_matching else " || true"
    if args.host_path:
        p = _q(_host_path(args.host_path))
        if args.tar_member:
            # a missing member must fail here, not read as "0 matching lines" below
            _ssh(f"tar -tzf {p} {shlex.quote(args.tar_member)} > /dev/null")
            src = f"tar -xzOf {p} {shlex.quote(args.tar_member)}"
        else:
            src = f"cat {p}"
        if args.grep:
            pat = shlex.quote(args.grep)
            body = f"{src} | grep {gflags} {pat}"
            count_cmd = f"{src} | grep {cflags} {pat}{ccount}"
        elif args.lines:
            a, b = args.lines.split(":")
            body = f"{src} | grep -n '' | sed -n '{int(a)},{int(b)}p'"
            count_cmd = f"{body} | wc -l"
        else:
            body = src
            # grep -c '' also counts a final line with no newline; wc -l does not
            count_cmd = f"{src} | grep -c '' || true"
        text = _ssh(body + cap + " || true")
        total = int((_ssh(count_cmd).strip() or "0").splitlines()[-1])
        return text, body + cap, total

    if args.local_path:
        base = f"cat {shlex.quote(args.local_path)}"
    else:
        # a subshell, so `a; b | grep` is filtered and counted as a whole rather than `b` alone
        base = f"( {args.command} )"
        # the pipeline below exits with grep's or head's status, so a failing command would read
        # as an empty excerpt; run it alone first so a failure is a failure
        _local(base + " > /dev/null")
    if args.grep:
        body = f"{base} | grep {gflags} {shlex.quote(args.grep)}"
        count_cmd = f"{base} | grep {cflags} {shlex.quote(args.grep)}{ccount}"
    elif args.lines:
        a, b = args.lines.split(":")
        body = f"{base} | grep -n '' | sed -n '{int(a)},{int(b)}p'"
        count_cmd = f"{body} | wc -l"
    else:
        body = base
        count_cmd = f"{base} | grep -c '' || true"
    text = _local(body + cap + " || true")
    total = int((_local(count_cmd).strip() or "0").splitlines()[-1])
    return text, body + cap, total


SEPARATOR = "#" + "-" * 99


HEADER_ANCHOR = "header:"


def anchor_holds(anchor: str, header_text: str, excerpt_text: str) -> bool:
    """An anchor is looked up in the excerpt body; one prefixed `header:` in the header instead.

    The header quotes the extraction command, and a command such as `grep 'nminibatch > ntrain'`
    contains its own pattern. Searching the whole file would let an anchor be "found" in the
    command that looked for it, so a fact would pass even when nothing matched. The prefix is
    explicit because excerpt lines can themselves start with '#'.
    """
    if anchor.startswith(HEADER_ANCHOR):
        return anchor[len(HEADER_ANCHOR):] in header_text
    return anchor in excerpt_text


def split_excerpt(content: str) -> tuple[str, str]:
    """(header, body) of a captured excerpt file, split at the separator line."""
    head, sep, rest = content.partition(SEPARATOR + "\n")
    if not sep:
        raise ValueError("no separator line; not a captured excerpt")
    return head, rest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("slug", help="bundle directory under results/evidence/")
    ap.add_argument("name", help="excerpt name; written to raw/<name>.txt")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--host-path")
    src.add_argument("--host-hashes", help="a host DIRECTORY: size, mtime and sha256 of each file "
                                           "matching --name-glob (default '*')")
    src.add_argument("--local-path", help="path relative to the project root")
    src.add_argument("--command", help="local shell command run at the project root")
    ap.add_argument("--name-glob", default="*", help="with --host-hashes")
    ap.add_argument("--tar-member", help="with --host-path: read this member of a .tgz")
    how = ap.add_mutually_exclusive_group()
    how.add_argument("--grep", help="extended regex; matching lines, with line numbers")
    ap.add_argument("--only-matching", action="store_true",
                    help="with --grep: keep only the matched text (grep -o), one match per line")
    how.add_argument("--lines", help="A:B inclusive line range, numbered like --grep output")
    ap.add_argument("--max", type=int, default=200, help="cap on excerpt lines (0 = no cap)")
    ap.add_argument("--allow-empty", action="store_true",
                    help="record an excerpt with no lines -- evidence of ABSENCE; anchor it on "
                         "'header:# matched-lines: 0 '")
    ap.add_argument("--note", default="", help="one line saying what this excerpt shows")
    ap.add_argument("--fact", action="append", default=[], help="key=value supported by this excerpt")
    ap.add_argument("--anchor", action="append", default=[],
                    help="substring that must appear in the excerpt body, or with a 'header:' prefix in "
                         "the header (e.g. 'header:# matched-lines: 0 '); one per --fact, in order")
    args = ap.parse_args()

    if len(args.fact) != len(args.anchor):
        raise SystemExit("every --fact needs exactly one --anchor: a fact not tied to text in its "
                         "evidence is an assertion, not evidence")

    meta = _source_meta(args)
    text, command, total = _extract(args)
    if meta["kind"] == "host-dir-hashes":
        # the listing IS the source; its hash is what a later recheck recomputes
        meta["listing_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    # count newline-terminated lines the way grep and wc do; str.splitlines also splits on form
    # feeds, which pdftotext emits at page breaks
    shown = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    if shown == 0 and not args.allow_empty:
        raise SystemExit("the excerpt is empty. If absence is the evidence, pass --allow-empty and "
                         "anchor the fact on 'header:# matched-lines: 0 '; otherwise the extraction is wrong.")
    captured = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    header = [
        f"# evidence-slug: {args.slug}",
        f"# excerpt: {args.name}",
        f"# note: {args.note}" if args.note else None,
        f"# source-kind: {meta['kind']}",
        (f"# source: {meta.get('host', '')}{':' if meta.get('host') else ''}"
         f"{meta.get('path', meta.get('command', ''))}").replace("\n", "\n#   "),
        (f"# source-bytes: {meta['bytes']}  source-sha256: {meta['sha256']}  source-mtime: {meta.get('mtime', '')}"
         if "sha256" in meta else
         f"# name-glob: {meta['glob']}  listing-sha256: {meta['listing_sha256']}"
         if meta["kind"] == "host-dir-hashes" else f"# repo-head: {meta['repo_head']}"),
        ("# inputs: " + "  ".join(f"{k}={v[:16]}" for k, v in meta["inputs"].items()))
        if meta.get("inputs") else None,
        f"# tar-member: {args.tar_member}" if args.tar_member else None,
        "# extraction: " + command.replace("\n", "\n#   "),
        f"# matched-lines: {total}  shown-lines: {shown}"
        + ("  (TRUNCATED -- the excerpt is capped; matched-lines is the full count)" if shown < total else ""),
        f"# captured-at: {captured}",
        SEPARATOR,
    ]
    header_text = "\n".join(h for h in header if h is not None) + "\n"
    body = header_text + text
    for anchor in args.anchor:
        if not anchor_holds(anchor, header_text, text):
            raise SystemExit(f"anchor not found in the captured excerpt: {anchor!r}. "
                             "Refusing to record a fact its own evidence does not show.")

    bundle = EVIDENCE / args.slug
    (bundle / "raw").mkdir(parents=True, exist_ok=True)
    out = bundle / "raw" / f"{args.name}.txt"
    out.write_text(body)

    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {
        "slug": args.slug, "excerpts": {}, "facts": []}
    manifest["excerpts"][args.name] = {
        "file": f"raw/{args.name}.txt",
        "sha256": hashlib.sha256(body.encode()).hexdigest(),
        "source": meta, "extraction": command, "tar_member": args.tar_member,
        "matched_lines": total, "shown_lines": shown, "captured_at": captured, "note": args.note,
    }
    manifest["facts"] = [f for f in manifest["facts"] if f.get("excerpt") != args.name]
    for fact, anchor in zip(args.fact, args.anchor):
        key, _, value = fact.partition("=")
        manifest["facts"].append({"key": key, "value": value, "excerpt": args.name, "anchor": anchor})
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    print(f"wrote {out.relative_to(ROOT)}  ({shown}/{total} lines, source {(meta.get('sha256') or meta.get('listing_sha256') or meta.get('repo_head'))[:12]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
