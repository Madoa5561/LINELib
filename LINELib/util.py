from typing import Dict, Any, Optional
import os
import time

from .storage import read_json, update_json, write_json

def merge_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    c = a.copy()
    c.update(b)
    return c

_IDMAP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../id_map.json"))


def _empty_idmap() -> Dict[str, Dict[str, str]]:
    return {"group_to_chat": {}, "chat_to_group": {}}


def _validate_idmap(data: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    group_to_chat = data.get("group_to_chat")
    chat_to_group = data.get("chat_to_group")
    if not isinstance(group_to_chat, dict) or not isinstance(chat_to_group, dict):
        raise ValueError("ID map must contain group_to_chat and chat_to_group objects")
    return data

def _load_idmap() -> Dict[str, Dict[str, str]]:
    return _validate_idmap(read_json(_IDMAP_PATH, missing=_empty_idmap()))

def _save_idmap(data: Dict[str, Dict[str, str]]):
    write_json(_IDMAP_PATH, _validate_idmap(data))

def link_group_and_chat(group_id: str, chat_id: str):
    def update_idmap(data: Dict[str, Any]) -> None:
        group_to_chat = data.setdefault("group_to_chat", {})
        chat_to_group = data.setdefault("chat_to_group", {})
        if not isinstance(group_to_chat, dict) or not isinstance(chat_to_group, dict):
            raise ValueError("ID map must contain group_to_chat and chat_to_group objects")

        previous_chat_id = group_to_chat.get(group_id)
        if (
            previous_chat_id != chat_id
            and chat_to_group.get(previous_chat_id) == group_id
        ):
            del chat_to_group[previous_chat_id]

        previous_group_id = chat_to_group.get(chat_id)
        if (
            previous_group_id != group_id
            and group_to_chat.get(previous_group_id) == chat_id
        ):
            del group_to_chat[previous_group_id]

        group_to_chat[group_id] = chat_id
        chat_to_group[chat_id] = group_id

    update_json(_IDMAP_PATH, update_idmap, missing=_empty_idmap())

def get_chatid_from_groupid(group_id: str) -> Optional[str]:
    data = _load_idmap()
    return data["group_to_chat"].get(group_id)

def get_groupid_from_chatid(chat_id: str) -> Optional[str]:
    data = _load_idmap()
    return data["chat_to_group"].get(chat_id)

def ratelimiter(timestamps: list, limit: int = 18, window: float = 60) -> bool:
    """
    timestamps: list of UNIX timestamps (seconds).
    Return True if `limit` or more messages were sent within the last `window` seconds.
    """
    now = time.time()
    recent = [t for t in timestamps if now - t < window]
    return len(recent) >= limit


def ratelimit_after(timestamps: list, limit: int = 18, window: float = 60) -> float:
    """
    Return the UNIX timestamp (seconds) when the ratelimit will be lifted.
    If fewer than `limit` timestamps, return 0.
    """
    if len(timestamps) < limit:
        return 0
    oldest = sorted(timestamps)[-limit]
    return oldest + window

Ratelimiter = ratelimiter
