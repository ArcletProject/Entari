def nest_dict_update(old: dict, new: dict) -> dict:
    """递归更新字典"""
    for k, v in new.items():
        if k not in old:
            old[k] = v
        elif isinstance(v, dict):
            old[k] = nest_dict_update(old[k], v)
        elif isinstance(v, list):
            old[k] = nest_list_update(old[k], v)
        else:
            old[k] = v
    return old


def nest_list_update(old: list, new: list) -> list:
    """递归更新列表"""
    for i, v in enumerate(new):
        if i >= len(old):
            old.append(v)
        elif isinstance(v, dict):
            old[i] = nest_dict_update(old[i], v)
        elif isinstance(v, list):
            old[i] = nest_list_update(old[i], v)
        else:
            old[i] = v
    return old


def nest_obj_update(old, new, attrs: list[str]):
    """递归更新对象"""
    for attr in attrs:
        new_attr = getattr(new, attr)
        if not hasattr(old, attr):
            setattr(old, attr, new_attr)
            continue
        old_attr = getattr(old, attr)
        if not isinstance(new_attr, old_attr.__class__):
            setattr(old, attr, new_attr)
            continue
        if isinstance(new_attr, dict):
            nest_dict_update(old_attr, new_attr)
        elif isinstance(new_attr, list):
            nest_list_update(old_attr, new_attr)
        else:
            setattr(old, attr, new_attr)
    return old
