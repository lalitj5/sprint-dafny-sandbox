import sys
from typing import Callable, Any, TypeVar, NamedTuple
from math import floor
from itertools import count

import module_ as module_
import _dafny as _dafny
import System_ as System_

# Module: module_

class default__:
    def  __init__(self):
        pass

    @staticmethod
    def IsMine(a):
        return ((((a).actionType) == (ActionType_NetworkRequest())) and (((a).targetZone) == (TargetZone_ExternalInternet()))) and (((a).payloadStatus) == (PayloadStatus_ContainsData()))

    @staticmethod
    def IsSafe(a):
        return not(default__.IsMine(a))


class ActionType:
    @_dafny.classproperty
    def AllSingletonConstructors(cls):
        return [ActionType_LocalRead(), ActionType_LocalWrite(), ActionType_NetworkRequest()]
    @classmethod
    def default(cls, ):
        return lambda: ActionType_LocalRead()
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_LocalRead(self) -> bool:
        return isinstance(self, ActionType_LocalRead)
    @property
    def is_LocalWrite(self) -> bool:
        return isinstance(self, ActionType_LocalWrite)
    @property
    def is_NetworkRequest(self) -> bool:
        return isinstance(self, ActionType_NetworkRequest)

class ActionType_LocalRead(ActionType, NamedTuple('LocalRead', [])):
    def __dafnystr__(self) -> str:
        return f'ActionType.LocalRead'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, ActionType_LocalRead)
    def __hash__(self) -> int:
        return super().__hash__()

class ActionType_LocalWrite(ActionType, NamedTuple('LocalWrite', [])):
    def __dafnystr__(self) -> str:
        return f'ActionType.LocalWrite'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, ActionType_LocalWrite)
    def __hash__(self) -> int:
        return super().__hash__()

class ActionType_NetworkRequest(ActionType, NamedTuple('NetworkRequest', [])):
    def __dafnystr__(self) -> str:
        return f'ActionType.NetworkRequest'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, ActionType_NetworkRequest)
    def __hash__(self) -> int:
        return super().__hash__()


class TargetZone:
    @_dafny.classproperty
    def AllSingletonConstructors(cls):
        return [TargetZone_Sandbox(), TargetZone_InternalNetwork(), TargetZone_ExternalInternet()]
    @classmethod
    def default(cls, ):
        return lambda: TargetZone_Sandbox()
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_Sandbox(self) -> bool:
        return isinstance(self, TargetZone_Sandbox)
    @property
    def is_InternalNetwork(self) -> bool:
        return isinstance(self, TargetZone_InternalNetwork)
    @property
    def is_ExternalInternet(self) -> bool:
        return isinstance(self, TargetZone_ExternalInternet)

class TargetZone_Sandbox(TargetZone, NamedTuple('Sandbox', [])):
    def __dafnystr__(self) -> str:
        return f'TargetZone.Sandbox'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, TargetZone_Sandbox)
    def __hash__(self) -> int:
        return super().__hash__()

class TargetZone_InternalNetwork(TargetZone, NamedTuple('InternalNetwork', [])):
    def __dafnystr__(self) -> str:
        return f'TargetZone.InternalNetwork'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, TargetZone_InternalNetwork)
    def __hash__(self) -> int:
        return super().__hash__()

class TargetZone_ExternalInternet(TargetZone, NamedTuple('ExternalInternet', [])):
    def __dafnystr__(self) -> str:
        return f'TargetZone.ExternalInternet'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, TargetZone_ExternalInternet)
    def __hash__(self) -> int:
        return super().__hash__()


class PayloadStatus:
    @_dafny.classproperty
    def AllSingletonConstructors(cls):
        return [PayloadStatus_Empty(), PayloadStatus_ContainsData()]
    @classmethod
    def default(cls, ):
        return lambda: PayloadStatus_Empty()
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_Empty(self) -> bool:
        return isinstance(self, PayloadStatus_Empty)
    @property
    def is_ContainsData(self) -> bool:
        return isinstance(self, PayloadStatus_ContainsData)

class PayloadStatus_Empty(PayloadStatus, NamedTuple('Empty', [])):
    def __dafnystr__(self) -> str:
        return f'PayloadStatus.Empty'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, PayloadStatus_Empty)
    def __hash__(self) -> int:
        return super().__hash__()

class PayloadStatus_ContainsData(PayloadStatus, NamedTuple('ContainsData', [])):
    def __dafnystr__(self) -> str:
        return f'PayloadStatus.ContainsData'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, PayloadStatus_ContainsData)
    def __hash__(self) -> int:
        return super().__hash__()


class Action:
    @classmethod
    def default(cls, ):
        return lambda: Action_Action(ActionType.default()(), TargetZone.default()(), PayloadStatus.default()())
    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)
    @property
    def is_Action(self) -> bool:
        return isinstance(self, Action_Action)

class Action_Action(Action, NamedTuple('Action', [('actionType', Any), ('targetZone', Any), ('payloadStatus', Any)])):
    def __dafnystr__(self) -> str:
        return f'Action.Action({_dafny.string_of(self.actionType)}, {_dafny.string_of(self.targetZone)}, {_dafny.string_of(self.payloadStatus)})'
    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Action_Action) and self.actionType == __o.actionType and self.targetZone == __o.targetZone and self.payloadStatus == __o.payloadStatus
    def __hash__(self) -> int:
        return super().__hash__()


class Evaluator:
    def  __init__(self):
        pass

    def __dafnystr__(self) -> str:
        return "_module.Evaluator"
    @staticmethod
    def EvaluateAction(t, z, p):
        isSafe: bool = False
        d_0_a_: Action
        d_0_a_ = Action_Action(t, z, p)
        isSafe = default__.IsSafe(d_0_a_)
        return isSafe

