"""Shared strict operation-journal mechanics; each scientific family owns its laws."""
import copy
import hashlib
import json


from core.mathematics.errors import MathematicsError as JournalError


def keys(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise JournalError("Unknown or missing journal fields.")


def read_operations(value, format_name, validate_changes):
    keys(value, ["format", "version", "volumes"])
    if value["format"] != format_name or type(value["version"]) is not int or value["version"] != 1:
        raise JournalError("Unsupported derivation format/version.")
    if not isinstance(value["volumes"], dict) or len(value["volumes"]) > 160:
        raise JournalError("Expected at most 160 volume journals.")
    for owner, entry in value["volumes"].items():
        if not isinstance(owner, str) or not owner.strip():
            raise JournalError("A volume ID is required.")
        keys(entry, ["origin", "operations"],['cursor'])
        if entry["origin"] not in ("recorded", "reviewed_rebuild"):
            raise JournalError("Unknown journal origin.")
        if not isinstance(entry["operations"], list) or len(entry["operations"]) > 400:
            raise JournalError("Expected at most 400 operations per volume.")
        if 'cursor' in entry and (type(entry['cursor']) is not int or not 0<=entry['cursor']<=len(entry['operations'])):raise JournalError('Invalid physical assumption cursor.')
        seen = set()
        for operation in entry["operations"]:
            keys(operation, ["id", "title", "changes"])
            if any(not isinstance(operation[key], str) or not operation[key].strip() for key in ("id", "title")):
                raise JournalError("Nonempty operation IDs and titles are required.")
            if operation["id"] in seen:
                raise JournalError("Repeated operation ID.")
            seen.add(operation["id"])
            validate_changes(operation["changes"])
    return value


def replay(entry, fundamental, normalize):
    state = normalize(fundamental())
    states = [copy.deepcopy(state)]
    for operation in entry["operations"][:entry.get('cursor',len(entry['operations']))]:
        state = normalize({**state, **copy.deepcopy(operation["changes"])})
        states.append(copy.deepcopy(state))
    return states


def evidence(owner, entry, relation_ids):
    return {"volumeId": owner, "origin": entry["origin"], "operationIds": [step["id"] for step in entry["operations"][:entry.get('cursor',len(entry['operations']))]],
            "signature": hashlib.sha256(json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            "relationIds": relation_ids}


def edit(value, owner, action, format_name, validate_changes, normalize, fundamental, choices):
    read_operations(value, format_name, validate_changes)
    keys(action, ["kind"])
    if not isinstance(owner, str) or not owner.strip() or not isinstance(action["kind"], str):
        raise JournalError("A volume ID and operation kind are required.")
    result = copy.deepcopy(value)
    kind = action["kind"]
    if kind == "start":
        if owner in result["volumes"]:
            raise JournalError("This volume already has a journal. Undo operations to return to its fundamental law.")
        result["volumes"][owner] = {"origin": "reviewed_rebuild", "operations": []}
    else:
        if owner not in result["volumes"]:
            raise JournalError("Start from the fundamental law before applying an operation.")
        entry = result["volumes"][owner]
        if kind == "undo":
            if 'cursor' in entry:entry['cursor']=max(0,entry['cursor']-1)
            elif entry["operations"]:
                entry["operations"].pop()
        else:
            if kind not in choices:
                raise JournalError("Unknown deduction operation.")
            title, changes = choices[kind]
            state = replay(entry, fundamental, normalize)[-1]
            if normalize({**state, **changes}) == state:
                raise JournalError("This operation is already effective.")
            if 'cursor' in entry:entry['operations']=entry['operations'][:entry['cursor']]
            entry["operations"].append({"id": f"step-{len(entry['operations']) + 1}", "title": title, "changes": changes})
            if 'cursor' in entry:entry['cursor']=len(entry['operations'])
    read_operations(result, format_name, validate_changes)
    # Replay also checks prerequisites such as pressure separation before enthalpy.
    replay(result["volumes"][owner], fundamental, normalize)
    return result
