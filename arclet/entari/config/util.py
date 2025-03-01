def nest_dict_update(old: dict, new: dict) -> dict:
    """递归更新字典"""
    for k, v in new.items():
        if k not in old:
            old[k] = v
        elif isinstance(v, dict):
            old[k] = nest_dict_update(old[k], v)
        else:
            old[k] = v
    return old
