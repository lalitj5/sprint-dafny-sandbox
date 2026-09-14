datatype ActionType = LocalRead | LocalWrite | NetworkRequest
datatype TargetZone = Sandbox | InternalNetwork | ExternalInternet
datatype PayloadStatus = Empty | ContainsData

datatype Action = Action(actionType: ActionType, targetZone: TargetZone, payloadStatus: PayloadStatus)

predicate IsMine(a: Action) {
    a.actionType == NetworkRequest && a.targetZone == ExternalInternet && a.payloadStatus == ContainsData
}

predicate IsSafe(a: Action) {
    !IsMine(a)
}

lemma ExfiltrationIsAlwaysBlocked(a: Action)
    requires a.actionType == NetworkRequest
    requires a.targetZone == ExternalInternet
    requires a.payloadStatus == ContainsData
    ensures IsMine(a)
{
    // The proof is trivial by definition of IsMine, but formally verified by Dafny.
    // This lemma guarantees that our containment logic correctly flags all exfiltration attempts.
}

class Evaluator {
    static method EvaluateAction(t: ActionType, z: TargetZone, p: PayloadStatus) returns (isSafe: bool) {
        var a := Action(t, z, p);
        isSafe := IsSafe(a);
    }
}
