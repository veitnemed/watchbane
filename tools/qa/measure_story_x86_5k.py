"""Opt-in Linux x86 5K synthetic FP32 loopback lab; not a service or cgroup gate."""
import argparse
from contextlib import contextmanager
import json
from math import isfinite
import os
from pathlib import Path
import re
import platform
import signal
import subprocess
import sys
import tempfile
from threading import Event, Thread

from tools.qa import measure_story_arm_capacity as capacity

_BUDGET = {"cold": (335, 370), "restart": (30, 65)}
_RSS_KIB = 2 * 1024**2
_ROWS = 5000
_REPO = Path(__file__).resolve().parents[2]
_SHA = re.compile(r"[0-9a-f]{64}")
_IDENTITY_FIELDS = ("catalog_sha256", "passage_snapshot_id", "passage_snapshot_sha256")
_TIME_FIELDS = ("process_ready_seconds", "first_http_ms", "warm_p50_ms", "warm_p95_ms")
_PUBLIC_PHASE_FIELDS = (
    "cache_phase", "proof_of_cache_hit", "child_peak_rss_kib", "warm_samples",
    *_IDENTITY_FIELDS, *_TIME_FIELDS,
)
_OFFLINE_GUARD = """
import ipaddress
import sys

def guard(event, args):
    if event == 'socket.getaddrinfo':
        host = args[0]
    elif event in ('socket.gethostbyname', 'socket.gethostbyaddr', 'socket.getnameinfo'):
        host = args[0][0] if isinstance(args[0], tuple) else args[0]
    elif event in ('socket.connect', 'socket.bind', 'socket.sendto'):
        if args[0].family not in (2, 10):
            return
        host = args[1][0]
    else:
        return
    if host is None or host == 'localhost':
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise OSError('QA guard: non-loopback socket operation refused')
sys.addaudithook(guard)
"""


def child_rss_kib(pid):
    for row in Path(f"/proc/{pid}/status").read_text().splitlines():
        if row.startswith("VmRSS:"):
            return int(row.split()[1])
    raise ValueError("child RSS unavailable")


@contextmanager
def watched_launch(*args, **kwargs):
    with capacity.launch(*args, **kwargs) as server:
        child = server[1]
        done = Event()
        failures = []

        def monitor():
            while not done.wait(.1):
                if child.poll() is not None:
                    return
                try:
                    too_large = child_rss_kib(child.pid) > _RSS_KIB
                except (OSError, ValueError):
                    if child.poll() is not None:
                        return
                    failures.append("child RSS could not be sampled")
                else:
                    if not too_large:
                        continue
                    failures.append("sampled 2 GiB child RSS limit exceeded")
                child.terminate()
                return

        watcher = Thread(target=monitor, daemon=True)
        watcher.start()
        try:
            yield server
        finally:
            done.set()
            watcher.join()
            if failures:
                raise RuntimeError(failures[0])


def _deadline(*_):
    raise TimeoutError("x86 5K phase exceeded wall deadline")


def phase(phase_name, model, cache):
    from resource import RUSAGE_CHILDREN, getrusage

    ready_seconds, wall_seconds = _BUDGET[phase_name]
    signal.signal(signal.SIGALRM, _deadline)
    signal.alarm(wall_seconds)
    try:
        result = capacity.measure(model, _ROWS, "low", "prepared",
                                  readiness_timeout=ready_seconds, cache_dir=cache,
                                  cache_phase=phase_name, launcher=watched_launch, x86_5k_lab=True)
        peak = getrusage(RUSAGE_CHILDREN).ru_maxrss
        if not 0 < peak <= _RSS_KIB:
            raise RuntimeError("reaped child peak RSS unavailable or exceeded 2 GiB")
        return dict(result, child_peak_rss_kib=peak)
    finally:
        signal.alarm(0)


def _run_phase(name, model, cache, env):
    cmd = [sys.executable, "-m", "tools.qa.measure_story_x86_5k", str(model), "--_phase", name, str(cache)]
    child = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             start_new_session=True, text=True, cwd=_REPO)
    try:
        output, _ = child.communicate(timeout=_BUDGET[name][1] + 15)
        if child.returncode:
            raise RuntimeError(f"{name} phase failed with status {child.returncode}")
        return json.loads(output)
    finally:
        if child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait(timeout=5)


def verified_pair(cold, restart):
    for sample, name, proof in ((cold, "cold", False), (restart, "restart", True)):
        if ((sample.get("rows"), sample.get("fixture"), sample.get("density"), sample.get("mode"),
             sample.get("cache_phase"), sample.get("proof_of_cache_hit"))
                != (_ROWS, "synthetic_qa_only", "low", "prepared", name, proof)
                or not capacity.valid_results(sample.get("ordered_typed_results"), _ROWS)
                or type(sample.get("rows")) is not int
                or sample.get("proof_of_cache_hit") is not proof
                or type(sample.get("warm_samples")) is not int or sample["warm_samples"] != 21
                or any(type(sample.get(key)) not in (int, float) or not isfinite(sample[key])
                       or sample[key] < 0 for key in _TIME_FIELDS)
                or sample["warm_p95_ms"] < sample["warm_p50_ms"]
                or any(type(sample.get(key)) is not str or not _SHA.fullmatch(sample[key])
                       for key in _IDENTITY_FIELDS)
                or type(sample.get("child_peak_rss_kib")) is not int
                or not 0 < sample["child_peak_rss_kib"] <= _RSS_KIB):
            raise RuntimeError("invalid x86 5K phase evidence")
    checks = ("ordered_typed_results", *_IDENTITY_FIELDS)
    if any(cold[k] != restart[k] for k in checks):
        raise RuntimeError("x86 5K cached replay changed identity or ordered typed search results")
    # Report hashes and timings, not individual fixture IDs or search text.
    return {
        "lab": "Linux x86_64 (not ARM or production), 5000 one-sentence low-density synthetic rows",
        "limits": "two logical CPUs; 100ms server RSS watchdog + reaped server peak (not cgroup)",
        "ordered_typed_top5_probes": len(cold["ordered_typed_results"]),
        **{item["cache_phase"]: {key: item[key] for key in _PUBLIC_PHASE_FIELDS}
           for item in (cold, restart)},
    }


def run(model):
    cpus = sorted(os.sched_getaffinity(0)) if sys.platform == "linux" else []
    if platform.machine() != "x86_64" or len(cpus) < 2:
        raise RuntimeError("expected Linux x86_64 with at least two available logical CPUs")
    with tempfile.TemporaryDirectory(prefix="watchbane-x86-5k-") as work:
        owner_dir = Path(work)
        cache, home = owner_dir / "cache", owner_dir / "home"
        cache.mkdir(mode=0o700)
        home.mkdir(mode=0o700)
        (owner_dir / "sitecustomize.py").write_text(_OFFLINE_GUARD, encoding="utf-8")
        env = {
            "HOME": str(home), "TMPDIR": work, "PATH": os.environ.get("PATH", os.defpath),
            "PYTHONPATH": os.pathsep.join(filter(None, (work, str(_REPO), os.environ.get("PYTHONPATH")))),
            "PYTHONDONTWRITEBYTECODE": "1", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
            "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        }
        original = set(cpus)
        os.sched_setaffinity(0, set(cpus[:2]))
        try:
            cold = _run_phase("cold", model, cache, env)
            restart = _run_phase("restart", model, cache, env)
        finally:
            os.sched_setaffinity(0, original)
    return dict(verified_pair(cold, restart), logical_cpu_ids=cpus[:2])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_dir", type=Path, help="existing verified local multilingual E5 small FP32 files")
    parser.add_argument("--_phase", nargs=2, metavar=("PHASE", "CACHE"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args._phase:
            name, cache = args._phase
            owner = Path(os.environ["TMPDIR"])
            active_guard = getattr(sys.modules.get("sitecustomize"), "__file__", None)
            if (name not in _BUDGET or Path(cache) != owner / "cache"
                    or not owner.name.startswith("watchbane-x86-5k-")
                    or Path(cache).is_symlink()
                    or active_guard != str(owner / "sitecustomize.py")):
                raise RuntimeError("unexpected private phase configuration")
            result = phase(name, args.model_dir, Path(cache))
        else:
            result = run(args.model_dir.resolve())
    except Exception as exc:
        print(f"x86 5K lab failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
