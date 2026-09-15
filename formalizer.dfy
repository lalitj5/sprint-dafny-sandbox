datatype ActionType = LocalRead | LocalWrite | NetworkRequest
datatype TargetZone = Sandbox | InternalNetwork | ExternalInternet
datatype PayloadStatus = Empty | ContainsData

datatype Action = Action(actionType: ActionType, targetZone: TargetZone, payloadStatus: PayloadStatus)
datatype SystemState = SystemState(isTainted: bool)

predicate IsMine(s: SystemState, a: Action) {
    // It is a mine if the agent makes an external network request while carrying a tainted payload OR explicitly sending data
    a.actionType == NetworkRequest && a.targetZone == ExternalInternet && 
    (a.payloadStatus == ContainsData || s.isTainted)
}

predicate IsSafe(s: SystemState, a: Action) {
    !IsMine(s, a)
}

function Transition(s: SystemState, a: Action): SystemState {
    // Reading local files taints the state (assume all local files could be secrets for this strict sandbox)
    if a.actionType == LocalRead then
        SystemState(true)
    else
        s
}

// Formal mathematical proof that our state machine blocks tainted exfiltration
lemma TaintBlocksNetwork(s: SystemState, a: Action)
    requires s.isTainted
    requires a.actionType == NetworkRequest
    requires a.targetZone == ExternalInternet
    ensures !IsSafe(s, a)
{
    // Dafny verifies this lemma automatically.
}

class Evaluator {
    // This is the bridge function called from Python
    static method EvaluateStep(currentState: SystemState, t: ActionType, z: TargetZone, p: PayloadStatus) returns (isSafe: bool, nextState: SystemState) {
        var a := Action(t, z, p);
        isSafe := IsSafe(currentState, a);
        nextState := Transition(currentState, a);
    }
}
