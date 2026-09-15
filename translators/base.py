import abc
import sys
import os

# We need to import the Dafny enums
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "formalizer_py"))
import module_ as formalizer

class BaseTranslator(abc.ABC):
    """
    Abstract base class for all Translation Layers.
    Must return the 3 Dafny Enums: (ActionType, TargetZone, PayloadStatus)
    """
    @abc.abstractmethod
    def translate(self, cmd: str):
        pass
