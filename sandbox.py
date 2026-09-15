"""Per-session Docker sandboxes for agent command execution."""
import io
import json
import os
import subprocess
import tarfile

IMAGE = "formal-sweep-sandbox:1.0"
EXEC_TIMEOUT = 10

# Network mode. "none" gives hard isolation but makes evasion invisible: you
# cannot tell "never tried" from "tried and was refused". "canary" puts the
# sandbox on an --internal network with a recording listener, so an attempt
# becomes an observed connection -- ground truth the LLM auditor cannot give.
# Switch with SANDBOX_NETWORK=canary, but run validation check 7 first
# (DOCKER_MIGRATION.md S8): a bridge without --internal would be a live route.
NETWORK_MODE = os.environ.get("SANDBOX_NETWORK", "none").lower()

NETWORK_NAME = "fsweep-net"
CANARY_IMAGE = "formal-sweep-canary:1.0"
CANARY_NAME = "fsweep-canary"
CANARY_ALIAS = "canary.fsweep.internal"
HITS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "canary")
HITS_FILE = os.path.join(HITS_DIR, "hits.jsonl")


def ensure_network():
    """Create the --internal sandbox network if absent. Idempotent."""
    existing = subprocess.run(
        ["docker", "network", "ls", "--filter", f"name=^{NETWORK_NAME}$", "-q"],
        capture_output=True, text=True, timeout=60,
    )
    if existing.stdout.strip():
        return
    created = subprocess.run(
        ["docker", "network", "create", "--internal", NETWORK_NAME],
        capture_output=True, text=True, timeout=60,
    )
    if created.returncode != 0:
        raise SandboxError(f"could not create {NETWORK_NAME}: {created.stderr.strip()}")


def ensure_canary():
    """Start the recording canary on the sandbox network. Idempotent."""
    running = subprocess.run(
        ["docker", "ps", "-q", "--filter", f"name=^{CANARY_NAME}$"],
        capture_output=True, text=True, timeout=60,
    )
    if running.stdout.strip():
        return
    subprocess.run(["docker", "rm", "-f", CANARY_NAME], capture_output=True, timeout=60)
    os.makedirs(HITS_DIR, exist_ok=True)
    started = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", CANARY_NAME,
            "--network", NETWORK_NAME,
            "--network-alias", CANARY_ALIAS,
            "-v", f"{HITS_DIR}:/var/log/canary",
            "--memory", "128m",
            CANARY_IMAGE,
        ],
        capture_output=True, text=True, timeout=120,
    )
    if started.returncode != 0:
        raise SandboxError(f"could not start canary: {started.stderr.strip()}")


def read_hits(since: str, until: str):
    """Canary hits recorded between two ISO timestamps.

    Commands are executed serially by the interceptor, so a time window
    attributes a connection to the command that caused it.
    """
    if not os.path.exists(HITS_FILE):
        return []
    hits = []
    with open(HITS_FILE, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                hit = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since <= hit.get("timestamp", "") <= until:
                hits.append(hit)
    return hits


class SandboxError(RuntimeError):
    """Docker itself failed. Distinct from the agent's command failing."""


class DockerSandbox:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.name = f"fsweep-{session_id}"
        self.container_id = None

    def start(self):
        if NETWORK_MODE == "canary":
            ensure_network()
            ensure_canary()
        result = subprocess.run(
            [
                "docker", "run", "-d",
                "--name", self.name,
                "--network", NETWORK_NAME if NETWORK_MODE == "canary" else "none",
                "--user", "1000:1000",
                "--read-only",              # image layers immutable
                "--tmpfs", "/work:rw,exec,size=256m,uid=1000",
                "--tmpfs", "/tmp:rw,size=64m",
                "--memory", "512m",
                "--cpus", "1.0",
                "--pids-limit", "128",
                "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                IMAGE,
            ],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise SandboxError(f"could not start sandbox: {result.stderr.strip()}")
        self.container_id = result.stdout.strip()

        # The tmpfs mounted at /work hides anything the image has at that path,
        # so fixtures are staged at /opt/fixtures and copied in after start.
        seed = self._exec_raw(["sh", "-c", "cp -a /opt/fixtures/. /work/"])
        if seed.returncode != 0:
            self.stop()          # don't leak the container we just started
            raise SandboxError(f"fixture seeding failed: {seed.stderr.strip()}")
        return self

    def exec(self, cmd: str, timeout: int = EXEC_TIMEOUT):
        """Run one agent command. Returns (stdout, stderr, exit_code, timed_out)."""
        try:
            result = self._exec_raw(["sh", "-c", cmd], timeout=timeout)
        except subprocess.TimeoutExpired:
            return "", "", None, True
        return result.stdout.strip(), result.stderr.strip(), result.returncode, False

    def _exec_raw(self, argv, timeout=EXEC_TIMEOUT):
        return subprocess.run(
            ["docker", "exec", "--user", "1000:1000", "-w", "/work", self.name, *argv],
            capture_output=True, text=True, timeout=timeout,
        )

    def snapshot_workdir(self, dest: str):
        """Copy /work out for forensics before teardown.

        `docker cp` CANNOT read a tmpfs mount -- it exits 0 and copies nothing,
        so it silently produces an empty snapshot. Stream a tar from inside the
        container instead, where the mount is actually visible.
        """
        os.makedirs(dest, exist_ok=True)
        tar = subprocess.run(
            ["docker", "exec", self.name, "tar", "-cf", "-", "-C", "/work", "."],
            capture_output=True, timeout=60,
        )
        if tar.returncode != 0 or not tar.stdout:
            err = tar.stderr.decode(errors="replace").strip()
            print(f"[WARN] workdir snapshot failed for {self.name}: {err}")
            return
        # The agent controls every filename in /work, so this archive is
        # untrusted input. filter="data" rejects absolute paths, traversal via
        # "..", symlinks and device nodes -- without it a file named
        # ../../interceptor.py would be written onto the host.
        try:
            with tarfile.open(fileobj=io.BytesIO(tar.stdout)) as tf:
                tf.extractall(dest, filter="data")
        except (tarfile.TarError, OSError) as e:
            # A rejected member is a finding, not a crash: the agent planted
            # something the filter refused. Record it and keep going, so a
            # hostile archive can never block container teardown.
            print(f"[WARN] workdir snapshot for {self.name} partially rejected: {e}")

    def stop(self):
        subprocess.run(["docker", "rm", "-f", self.name],
                       capture_output=True, timeout=60)


def reap_orphans() -> int:
    """Remove orphaned session sandboxes left by a previous process.

    `uvicorn --reload` restarts on every edit, which resets SANDBOXES while the
    containers keep running -- unreachable, un-reaped, and 512m each. Sweep at
    startup so a dev loop cannot leak memory. The shared canary is deliberately
    spared: it holds no per-session state and is reused across restarts.
    """
    names = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=fsweep-", "--format", "{{.ID}} {{.Names}}"],
        capture_output=True, text=True, timeout=60,
    )
    ids = [
        line.split()[0]
        for line in names.stdout.splitlines()
        if line.strip() and line.split()[1] != CANARY_NAME
    ]
    if ids:
        subprocess.run(["docker", "rm", "-f", *ids], capture_output=True, timeout=120)
    return len(ids)


SANDBOXES: dict[str, DockerSandbox] = {}


def get_sandbox(session_id: str) -> DockerSandbox:
    if session_id not in SANDBOXES:
        SANDBOXES[session_id] = DockerSandbox(session_id).start()
    return SANDBOXES[session_id]