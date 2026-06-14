from typing import Dict, Any, Optional
import json
import os
import time

def merge_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    c = a.copy()
    c.update(b)
    return c

_IDMAP_PATH = os.path.join(os.path.dirname(__file__), '../id_map.json')

def _load_idmap() -> Dict[str, Dict[str, str]]:
    if os.path.exists(_IDMAP_PATH):
        with open(_IDMAP_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"group_to_chat": {}, "chat_to_group": {}}

def _save_idmap(data: Dict[str, Dict[str, str]]):
    with open(_IDMAP_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def link_group_and_chat(group_id: str, chat_id: str):
    data = _load_idmap()
    data["group_to_chat"][group_id] = chat_id
    data["chat_to_group"][chat_id] = group_id
    _save_idmap(data)

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