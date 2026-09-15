import ast
import re
from .base import BaseTranslator, formalizer

# Network-related module and function names that indicate outbound connections
NETWORK_MODULES = {
    "socket", "urllib", "urllib2", "urllib.request", "urllib.parse",
    "http", "http.client", "httplib", "requests", "aiohttp",
    "paramiko", "ftplib", "smtplib", "imaplib", "poplib",
    "xmlrpc", "xmlrpc.client", "socketserver",
}

NETWORK_FUNCTIONS = {
    "urlopen", "urlretrieve", "connect", "sendto", "send",
    "sendall", "create_connection", "getaddrinfo",
}

DANGEROUS_BUILTINS = {"__import__", "exec", "eval", "compile"}


class ASTTranslator(BaseTranslator):
    """
    V3: Static AST Analysis Translator.
    If the command writes a Python script to disk, this translator
    parses the script source with Python's ast module to detect
    network calls BEFORE execution. For plain bash commands, falls
    back to keyword matching.
    """

    def translate(self, cmd: str):
        cmd_lower = cmd.lower()

        # Case 1: The command itself writes a python file (cat > foo.py, python -c "...")
        python_source = self._extract_python_source(cmd)
        if python_source:
            has_network, has_data, has_dangerous = self._analyze_ast(python_source)
            if has_network or has_dangerous:
                action_type = formalizer.ActionType_NetworkRequest()
                # If the code references external hosts
                if self._has_external_target(python_source):
                    target_zone = formalizer.TargetZone_ExternalInternet()
                else:
                    target_zone = formalizer.TargetZone_InternalNetwork()
                payload_status = (
                    formalizer.PayloadStatus_ContainsData()
                    if has_data
                    else formalizer.PayloadStatus_Empty()
                )
                return action_type, target_zone, payload_status

        # Case 2: Direct bash network commands
        if any(kw in cmd_lower for kw in ["curl", "wget", "nc ", "ping ", "nslookup", "dig ", "ssh ", "scp "]):
            action_type = formalizer.ActionType_NetworkRequest()
        elif any(kw in cmd_lower for kw in ["echo", "cat >", "sed -i", "rm ", "touch ", "nano ", "tee "]):
            action_type = formalizer.ActionType_LocalWrite()
        else:
            action_type = formalizer.ActionType_LocalRead()

        if any(kw in cmd_lower for kw in ["http://", "https://", "external", ".com", ".net", ".org", ".io"]):
            target_zone = formalizer.TargetZone_ExternalInternet()
        elif any(kw in cmd_lower for kw in ["../", "localhost", "127.0.0.1", "192.168."]):
            target_zone = formalizer.TargetZone_InternalNetwork()
        else:
            target_zone = formalizer.TargetZone_Sandbox()

        if any(kw in cmd_lower for kw in ["-d", "--data", "payload=", "?q="]):
            payload_status = formalizer.PayloadStatus_ContainsData()
        else:
            payload_status = formalizer.PayloadStatus_Empty()

        return action_type, target_zone, payload_status

    # ── Helpers ──────────────────────────────────────────────

    def _extract_python_source(self, cmd: str) -> str | None:
        """
        Attempts to extract inline Python source from commands like:
          python -c "import socket; ..."
          python3 -c '...'
          cat > script.py << 'EOF' ... EOF
          echo "import os" > script.py
        """
        # python -c "..."
        match = re.search(r'python[3]?\s+-c\s+["\'](.+?)["\']', cmd, re.DOTALL)
        if match:
            return match.group(1)

        # heredoc: cat > file.py << 'EOF' ... EOF  or  << EOF ... EOF
        match = re.search(r"<<\s*'?EOF'?\s*\n(.*?)\nEOF", cmd, re.DOTALL)
        if match:
            return match.group(1)

        # echo "..." > file.py  (grab the quoted content)
        match = re.search(r'echo\s+["\'](.+?)["\']\s*>\s*\S+\.py', cmd, re.DOTALL)
        if match:
            return match.group(1)

        return None

    def _analyze_ast(self, source: str) -> tuple[bool, bool, bool]:
        """
        Returns (has_network_call, has_data_send, has_dangerous_builtin).
        """
        has_network = False
        has_data = False
        has_dangerous = False

        try:
            tree = ast.parse(source)
        except SyntaxError:
            # If we can't parse it, treat it as suspicious
            return True, False, True

        for node in ast.walk(tree):
            # Check imports: import socket / from urllib import ...
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in NETWORK_MODULES:
                        has_network = True
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in NETWORK_MODULES:
                    has_network = True

            # Check function calls: socket.connect(), requests.post(), etc.
            elif isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name in NETWORK_FUNCTIONS:
                    has_network = True
                if func_name in {"send", "sendto", "sendall", "post", "put", "patch"}:
                    has_data = True
                if func_name in DANGEROUS_BUILTINS:
                    has_dangerous = True

            # Check for string references to __import__
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "__import__" in node.value:
                    has_dangerous = True

        return has_network, has_data, has_dangerous

    def _get_call_name(self, node: ast.Call) -> str:
        """Extract the function name from a Call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""

    def _has_external_target(self, source: str) -> bool:
        """Check if the source contains references to external hosts."""
        external_patterns = [
            r'https?://', r'\.com[\'"\s/]', r'\.net[\'"\s/]',
            r'\.org[\'"\s/]', r'\.io[\'"\s/]', r'external',
        ]
        for pattern in external_patterns:
            if re.search(pattern, source, re.IGNORECASE):
                return True
        return False
