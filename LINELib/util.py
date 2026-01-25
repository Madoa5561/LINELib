from typing import Dict, Any

def merge_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    c = a.copy()
    c.update(b)
    return c
