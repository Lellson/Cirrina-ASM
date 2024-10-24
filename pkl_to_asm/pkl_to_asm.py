import argparse
from enum import Enum

import pkl
from expression_parser import parse

TIMEOUT_MULTIPLIER = 0.01

class ActionType(Enum):
    acInvoke = "invoke"
    acRaise = "raise"
    acCreate = "create"
    acAssign = "assign"
    acDelete = "delete"
    acTimeout = "timeout"
    acReset = "timeoutReset"
    acMatch = "match"

class EventChannel(Enum):
    internal = "internal"
    _global = "global"

def asm_repr(obj, t=0):
    if obj == None:
        return "undef"
    if isinstance(obj, dict):
        indentation = ""
        if t <= 3:
            indentation = "\n" + ("  " * t)
        if len(obj) == 0:
            return indentation + "{->}"
        return indentation + "{" + ", ".join(f"{asm_repr(key)}->{value.replace("'", "\"")}" for key, value in obj.items()) + "}"
    elif isinstance(obj, list):
        indentation = ""
        inside = ""
        if t <= 3:
            indentation = "\n" + ("  " * t)
            inside = indentation + "  "
        return f"{indentation}[{inside}" + ", ".join(asm_repr(item, t+1) for item in obj) + f"{indentation}]"
    elif isinstance(obj, bool):
        return "true" if obj else "false"
    elif isinstance(obj, ActionType):
        return obj.name
    elif isinstance(obj, EventChannel):
        return obj.name.replace("_", "")
    elif isinstance(obj, str):
        return f'"{obj}"'
    else:
        return repr(obj).replace("'", "\"")

def state_machine_asm(stateMachine):
    return [
        stateMachine.name,
        [state_asm(state) for state in stateMachine.states],
        [state_machine_asm(nStateMachine) for nStateMachine in stateMachine.stateMachines],
        context_asm(stateMachine.localContext)
    ]

def state_asm(state):
    return [
        state.name,
        state.initial,
        state.terminal,
        [transition_asm(transition) for transition in state.on],
        [transition_asm(transition) for transition in state.always],
        [action_asm(action) for action in state.entry],
        [action_asm(action) for action in state.exit],
        [action_asm(action) for action in state._while],
        [action_asm(action) for action in state.after],
        context_asm(state.localContext),
        context_asm(state.staticContext)
    ]

def context_asm(context):
    if context == None:
        return dict()
    return dict([[var.name, var.value] for var in context.variables])

def transition_asm(transition):
    return [
        [expression_asm(guard.expression) for guard in transition.guards],
        transition.target,
        [action_asm(action) for action in transition.actions],
        transition.event if hasattr(transition, "event") else None,
        transition._else
    ]

def expression_asm(expression):
    return parse(expression)

def action_asm(action):
    type = ActionType(action.type)
    params = []

    if type == ActionType.acInvoke:
        params = [
            action.serviceType, 
            action.isLocal,
            [variable_asm(var) for var in action.input],
            [event_asm(event) for event in action.done],
            [var.reference for var in action.output]
        ]
    if type == ActionType.acRaise:
        params = event_asm(action.event)
    if type == ActionType.acCreate:
        params = variable_asm(action.variable)
        params.append(action.isPersistent)
    if type == ActionType.acAssign:
        params = variable_asm(action.variable)
    if type == ActionType.acDelete:
        params = [action.name]
    if type == ActionType.acTimeout:
        params = [
            action.name,
            max(1, int(float(action.delay) * TIMEOUT_MULTIPLIER)),
            action_asm(action.action)
        ]
    if type == ActionType.acReset:
        params = [action.action]
    if type == ActionType.acMatch:
        params = [
            expression_asm(action.value),
            [[expression_asm(case.case), action_asm(case.action)] for case in action.cases]
        ]
        
    return [type, params]

def variable_asm(var):
    return [var.name, expression_asm(var.value)]

def event_asm(event):
    return [
        event.name, 
        EventChannel("internal" if event.channel == "internal" else "global"),
        [variable_asm(var) for var in event.data]
    ]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pkl_uri", type=str, help="File path or URL to a .pkl file")

    args = parser.parse_args()

    csm = pkl.load(args.pkl_uri)
    asm = asm_repr(
        [state_machine_asm(stateMachine) for stateMachine in csm.stateMachines]
    )
    
    print(asm) 