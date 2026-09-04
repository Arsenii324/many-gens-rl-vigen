#!/usr/bin/env bash
# Job 1 of the DataSphere bring-up: prove the RETURN PATH, and nothing else.
#
# Discovering that outputs do not come back at the END of a long training job is the expensive
# failure. So the first job on a new project produces artifacts and exits, on the cheapest CPU
# tier. No GPU, no rendering, no training, no payload.
#
# WHY THIS FILE HAS SO MANY ASSERTIONS. Its first version reported SUCCESS while returning
# nothing: `dd bs=1m` is a BSD spelling that GNU coreutils rejects, so `big.bin` was never
# created -- and the pack guard checked only that `tar` exited 0, which it happily did over the
# three small files that did exist. Manifest fields came back empty, the job was green, and the
# CLI said "job completed successfully". The guard was testing the wrong proposition: not "did I
# return what I promised" but "did the packing command run". Every check below exists because the
# job must fail LOUDLY at the first missing byte rather than hand back a plausible tarball.
#
# It writes three things, because they fail differently:
#   result.tgz    a real tarball          -- the normal deliverable
#   manifest.txt  a small plain file      -- proves multi-output configs work, not just one file
#   big.bin       ~40 MB of random bytes  -- proves size is carried, and gives the local side a
#                                            checksum to compare instead of "the file exists"
set -uo pipefail
RESULT=${1:?result tarball}
MANIFEST=${2:?manifest file}
t0=$(date +%s)

# `stat` differs between GNU (-c %s) and BSD (-f %z); neither is present everywhere. wc -c is
# POSIX and always right. The first version used `stat` and printed an error into the manifest.
fsize() { wc -c < "$1" | tr -d ' '; }

echo "=== pull-back probe ==="
echo "host: $(uname -a)"
nproc 2>/dev/null || echo "nproc unavailable"
free -g 2>/dev/null | awk 'NR==2{print "RAM "$2"G total, "$7"G avail"}' || true

W=/tmp/payload
rm -rf "$W"; mkdir -p "$W"

# 40 MiB of incompressible data. Incompressible ON PURPOSE: random bytes cannot be squeezed by
# tar's gzip, so the tarball on the far end has a size that actually reflects the payload. A
# compressible filler would produce a tiny tarball and prove nothing about carrying bytes.
# bs=1048576 rather than 1m/1M -- a plain byte count is accepted by both GNU and BSD dd.
WANT=41943040
dd if=/dev/urandom of="$W/big.bin" bs=1048576 count=40 2>/dev/null
if [ ! -s "$W/big.bin" ]; then
  echo "!! dd produced no big.bin -- ABORTING before anything can report success"; exit 1
fi
GOT=$(fsize "$W/big.bin")
if [ "$GOT" != "$WANT" ]; then
  echo "!! big.bin is $GOT bytes, expected $WANT -- ABORTING"; exit 1
fi
echo "wrote big.bin: $GOT bytes"

# A few small files too -- a tar of one file is a weak test of extraction.
for i in 1 2 3; do
  echo "small file $i, generated $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$W/small_$i.txt"
done

SUM=$( { sha256sum "$W/big.bin" 2>/dev/null || shasum -a 256 "$W/big.bin"; } | cut -d' ' -f1 )
if [ -z "$SUM" ]; then
  echo "!! no checksum tool on this image -- the local side could not verify integrity"; exit 1
fi
echo "big.bin sha256: $SUM"

{
  echo "generated_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "big_bin_sha256=$SUM"
  echo "big_bin_bytes=$GOT"
  echo "files=$(ls "$W" | wc -l | tr -d ' ')"
} > "$MANIFEST"
cat "$MANIFEST"

if ! tar czf "$RESULT" -C "$W" .; then
  echo "!! PACKING FAILED -- the job would otherwise report SUCCESS with no artifacts"; exit 1
fi

# THE CHECK THAT WAS MISSING. `tar` exiting 0 says the command ran, not that the archive holds
# what was promised. Read the archive back and confirm big.bin is in it at full size.
PACKED=$(tar tzvf "$RESULT" 2>/dev/null | awk '$NF ~ /big\.bin$/ {print $3}')
if [ "$PACKED" != "$WANT" ]; then
  echo "!! archive contains big.bin at '${PACKED:-<absent>}' bytes, expected $WANT -- ABORTING"
  tar tzvf "$RESULT"; exit 1
fi
echo "packed: $(fsize "$RESULT") bytes, archive verified to contain big.bin at $PACKED bytes"
echo "=== seconds: $(( $(date +%s) - t0 )) ==="
