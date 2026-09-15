import sys
import subprocess
import json
import re
import tempfile
import os
from .base import BaseTranslator, formalizer

# The audit hook script that gets injected into the agent's Python process.
# It intercepts real interpreter-level events and writes them to a temp file.
AUDIT_HOOK_SCRIPT = '''
import sys
import json
import os

_audit_log_path = os.environ.get("AUDIT_LOG_PATH", "")
_audit_events = []

def _audit_hook(event, args):
    """
    Python sys.audit hook. Fires on real interpreter events,
    regardless of how the code was obfuscated.
    
    Key events:
      - "socket.connect"    -> agent is opening a network connection
      - "socket.getaddrinfo" -> agent is resolving a hostname
      - "open"              -> agent is opening a file
      - "subprocess.Popen"  -> agent is spawning a child process
      - "exec"              -> agent is calling exec/eval
      - "import"            -> agent is importing a module
    """
    record = {"event": event, "args": str(args)}
    _audit_events.append(record)

sys.addaudithook(_audit_hook)

import atexit
@atexit.register
def _flush_audit():
    if _audit_log_path:
        with open(_audit_log_path, "w") as f:
            json.dump(_audit_events, f)
'''

# Events that indicate network activity
NETWORK_EVENTS = {
    "socket.connect", "socket.getaddrinfo", "socket.bind",
    "socket.sendto", "socket.sendmsg",
}

# Events that indicate file writes
WRITE_EVENTS = {"open"}

# Events that indicate dangerous dynamic execution
DANGEROUS_EVENTS = {"exec", "compile", "cpython.run_command"}


class SysAuditTranslator(BaseTranslator):
    """
    V4: OS-Level Runtime Hooks via sys.audit.
    
    Instead of parsing code statically, this translator actually RUNS
    the agent's Python code in a subprocess with sys.audit hooks injected.
    The hooks intercept real interpreter-level events (socket.connect, open, etc.)
    and we map THOSE to Dafny enums.
    
    This is the Python-level equivalent of eBPF/strace syscall interception.
    No matter how the agent obfuscates its code (base64, eval, __import__),
    the moment the interpreter actually tries to open a socket, we catch it.
    
    For non-Python commands (plain bash), falls back to keyword matching.
    """

    def translate(self, cmd: str):
        cmd_lower = cmd.lower()

        # Check if this is a Python execution command
        python_source = self._extract_python_for_audit(cmd)
        if python_source:
            audit_events = self._run_with_audit(python_source)
            return self._classify_events(audit_events)

        # Fallback for plain bash commands
        if any(kw in cmd_lower for kw in ["curl", "wget", "nc ", "ping ", "nslookup", "ssh "]):
            action_type = formalizer.ActionType_NetworkRequest()
        elif any(kw in cmd_lower for kw in ["echo", "cat >", "sed -i", "rm ", "touch ", "tee "]):
            action_type = formalizer.ActionType_LocalWrite()
        else:
            action_type = formalizer.ActionType_LocalRead()

        if any(kw in cmd_lower for kw in ["http://", "https://", "external", ".com", ".net", ".org"]):
            target_zone = formalizer.TargetZone_ExternalInternet()
        elif any(kw in cmd_lower for kw in ["../", "localhost", "127.0.0.1", "192.168."]):
            target_zone = formalizer.TargetZone_InternalNetwork()
        else:
            target_zone = formalizer.TargetZone_Sandbox()

        if any(kw in cmd_lower for kw in ["-d", "--data", "payload="]):
            payload_status = formalizer.PayloadStatus_ContainsData()
        else:
            payload_status = formalizer.PayloadStatus_Empty()

        return action_type, target_zone, payload_status

    # ── Core Audit Logic ─────────────────────────────────────

    def _run_with_audit(self, python_source: str) -> list[dict]:
        """
        Runs the given Python source in a subprocess with
        sys.audit hooks injected. Returns the list of audit events.
        """
        audit_log = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir="."
        )
        audit_log.close()

        # Prepend the audit hook to the agent's code
        full_script = AUDIT_HOOK_SCRIPT + "\n" + python_source

        script_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir="."
        )
        script_file.write(full_script)
        script_file.close()

        try:
            env = os.environ.copy()
            env["AUDIT_LOG_PATH"] = audit_log.name

            subprocess.run(
                [sys.executable, script_file.name],
                capture_output=True, text=True, timeout=10, env=env
            )

            # Read the audit events
            if os.path.exists(audit_log.name):
                with open(audit_log.name, "r") as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            print(f"SysAudit execution error: {e}")
        finally:
            # Cleanup temp files
            for path in [audit_log.name, script_file.name]:
                try:
                    os.unlink(path)
                except OSError:
                    pass

        return []

    def _classify_events(self, events: list[dict]) -> tuple:
        """
        Maps the raw audit events to Dafny enums.
        This is where syscalls become formal states.
        """
        has_network = False
        has_write = False
        has_data_send = False
        has_external = False

        for event in events:
            event_name = event.get("event", "")
            event_args = event.get("args", "")

            if event_name in NETWORK_EVENTS:
                has_network = True
                # Check if the connection target is external
                if not any(local in event_args for local in ["127.0.0.1", "localhost", "192.168."]):
                    has_external = True
                # sendto/sendmsg imply data is being sent
                if "send" in event_name:
                    has_data_send = True

            elif event_name in WRITE_EVENTS:
                # Check if the file is being opened for writing
                if any(mode in event_args for mode in ["'w'", "'a'", "'wb'", "'ab'"]):
                    has_write = True

            elif event_name in DANGEROUS_EVENTS:
                # Dynamic exec/eval is treated as potentially network-capable
                has_network = True

        # Map to Dafny enums
        if has_network:
            action_type = formalizer.ActionType_NetworkRequest()
        elif has_write:
            action_type = formalizer.ActionType_LocalWrite()
        else:
            action_type = formalizer.ActionType_LocalRead()

        if has_external:
            target_zone = formalizer.TargetZone_ExternalInternet()
        elif has_network:
            target_zone = formalizer.TargetZone_InternalNetwork()
        else:
            target_zone = formalizer.TargetZone_Sandbox()

        if has_data_send:
            payload_status = formalizer.PayloadStatus_ContainsData()
        else:
            payload_status = formalizer.PayloadStatus_Empty()

        return action_type, target_zone, payload_status

    # ── Helpers ──────────────────────────────────────────────

    def _extract_python_for_audit(self, cmd: str) -> str | None:
        """Extract Python source that we can run with audit hooks."""
        # python -c "..."
        match = re.search(r'python[3]?\s+-c\s+["\'](.+?)["\']', cmd, re.DOTALL)
        if match:
            return match.group(1)

        # python3 script.py (check if the file exists)
        match = re.search(r'python[3]?\s+(\S+\.py)', cmd)
        if match:
            script_path = match.group(1)
            if os.path.exists(script_path):
                with open(script_path, "r") as f:
                    return f.read()

        # heredoc
        match = re.search(r"<<\s*'?EOF'?\s*\n(.*?)\nEOF", cmd, re.DOTALL)
        if match:
            return match.group(1)

        return None
