# Refuse to run outside a container. Source this at the top of any script whose body installs
# system packages, so that being on a host is a REFUSAL rather than a mutation.
#
#     . "$(dirname "${BASH_SOURCE[0]}")/require_container.sh"
#
# WHY A GUARD AND NOT A COMMENT
#
# The job bodies in this repository apt-get and pip install unguarded, which is correct: they run
# in a fresh container whose filesystem is discarded. A banner at the top saying so protects a
# person who READS it. It protects nobody against the actual failure mode -- a script that looks
# container-side being run on a host, by someone in a hurry or by an agent that concluded "this is
# fine, it is containerised" without checking WHERE it was about to execute.
#
# On the production host that is not a hypothetical class of mistake: it is the one the whole
# `notes/production-host/` directory exists to prevent, and the difference between a throwaway
# layer and somebody else's Python.
#
# DETECTION, and why several signals rather than one
#
# No single check is reliable across runtimes. `/.dockerenv` is Docker-specific and absent under
# podman; `/proc/1/cgroup` shows the container path under cgroup v1 but often a bare `/` under
# cgroup v2; `$container` is set by podman and systemd-nspawn and not by Docker. An overlay root
# filesystem catches most of what the others miss. Any ONE positive is enough -- the guard exists
# to catch a host, and a host produces none of them.
#
# It fails CLOSED: no evidence of a container means refuse. NATIVE_ALLOW_UNCONTAINED=1 is the
# deliberate escape, and it exists so that the refusal is never worked around by editing this file.
_in_container() {
  [[ -e /.dockerenv ]] && return 0
  [[ -n "${container:-}" ]] && return 0
  grep -qaE '(docker|containerd|lxc|kubepods|podman)' /proc/1/cgroup 2>/dev/null && return 0
  grep -qaE ' / / overlay| /docker/| /containers/' /proc/self/mountinfo 2>/dev/null && return 0
  return 1
}

if ! _in_container; then
  if [[ "${NATIVE_ALLOW_UNCONTAINED:-0}" == "1" ]]; then
    echo "=== NATIVE_UNCONTAINED_ACCEPTED this job body is running OUTSIDE a container, explicitly ===" >&2
  else
    echo "REFUSING: this is a CONTAINER JOB BODY and no container was detected." >&2
    echo "  It installs system packages. On a host that means apt-get and pip into the HOST's" >&2
    echo "  python -- on a shared machine, into everyone's." >&2
    echo "  Checked: /.dockerenv, \$container, /proc/1/cgroup, /proc/self/mountinfo (overlay root)." >&2
    echo "  Run it the intended way:" >&2
    echo "    host   -> bash datasphere/native/run_on_production_host.sh PAYLOAD RESULT ..." >&2
    echo "    remote -> bash datasphere/native/job.sh submit <config>.yaml" >&2
    echo "    ad hoc -> bash datasphere/native/host-run.sh <script>" >&2
    echo "  If you genuinely mean to run it uncontained, set NATIVE_ALLOW_UNCONTAINED=1." >&2
    exit 3
  fi
fi
