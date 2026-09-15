from .base import BaseTranslator, formalizer

class RegexTranslator(BaseTranslator):
    def translate(self, cmd: str):
        """
        Translates raw bash commands into abstract Dafny semantic states (enums).
        Uses simple regex and keyword matching (V1 Baseline).
        """
        cmd_lower = cmd.lower()
        
        # 1. ActionType Resolution
        if any(kw in cmd_lower for kw in ["curl", "wget", "requests.get", "nc ", "ping "]):
            action_type = formalizer.ActionType_NetworkRequest()
        elif any(kw in cmd_lower for kw in ["echo", "cat >", "sed -i", "rm ", "touch ", "nano "]):
            action_type = formalizer.ActionType_LocalWrite()
        else:
            action_type = formalizer.ActionType_LocalRead()
            
        # 2. TargetZone Resolution
        if any(kw in cmd_lower for kw in ["http://", "https://", "external", ".com"]):
            target_zone = formalizer.TargetZone_ExternalInternet()
        elif any(kw in cmd_lower for kw in ["../", "internal", "localhost", "127.0.0.1", "192.168."]):
            target_zone = formalizer.TargetZone_InternalNetwork()
        else:
            target_zone = formalizer.TargetZone_Sandbox()
            
        # 3. PayloadStatus Resolution
        if any(kw in cmd_lower for kw in ["-d", "--data", "payload=", "?q="]):
            payload_status = formalizer.PayloadStatus_ContainsData()
        else:
            payload_status = formalizer.PayloadStatus_Empty()
            
        return action_type, target_zone, payload_status
