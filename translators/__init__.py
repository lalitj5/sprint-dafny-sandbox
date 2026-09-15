import os

from .regex_translator import RegexTranslator
from .llm_translator import LLMTranslator
from .ast_translator import ASTTranslator
from .sysaudit_translator import SysAuditTranslator

# ── Translator Selection ─────────────────────────────────
# Set the TRANSLATOR env var to switch between versions:
#   V1 = regex   (fast, brittle baseline)
#   V2 = llm     (semantic, accurate, slow + costly)
#   V3 = ast     (static analysis, zero-cost, evadable by eval/exec)
#   V4 = sysaudit (runtime hooks, robust, Python-only)
#
# Default: V1 (regex)

_TRANSLATORS = {
    "V1": RegexTranslator,
    "V2": LLMTranslator,
    "V3": ASTTranslator,
    "V4": SysAuditTranslator,
}

_selected = os.environ.get("TRANSLATOR", "V1").upper()
ACTIVE_TRANSLATOR = _TRANSLATORS.get(_selected, RegexTranslator)()

print(f"[Formal-Sweep] Active Translator: {_selected} ({type(ACTIVE_TRANSLATOR).__name__})")
