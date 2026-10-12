"""patch 引擎：编辑走 patch，不走全量（源文档 1.5 第四层）。

架构性消灭失败模式 6（全量重写覆盖人工修改）：
  - 模型只允许产 RFC 6902 风格 patch（op: add/remove/replace/move）；
  - 影响范围断言：path 必须落在白名单前缀内；对根 "/" 的 replace 被直接禁止；
  - 人工改过的节点打 manual_locked 锁：patch 触碰（自身/祖先/后代/移动源）即拒绝；
  - 原子性：任一 op 被拒 → 整个 patch 不应用；
  - 应用后仍需通过结构校验，否则回滚（PATCH_BREAKS_STRUCTURE）。
"""
import copy

from .schema import validate_structure
from .violations import PatchRejection


class PatchResult:
    def __init__(self, ok: bool, config: dict, applied: list, rejections: list):
        self.ok = ok
        self.config = config
        self.applied = applied
        self.rejections = rejections  # list[PatchRejection]

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "applied": self.applied,
            "rejections": [r.__dict__ for r in self.rejections],
        }


_VALID_OPS = {"add", "remove", "replace", "move"}


def _segments(path: str) -> list:
    return [s for s in path.split("/") if s != ""]


def _under(prefix_segs: list, segs: list) -> bool:
    """segs 位于 prefix_segs 之下（含相等），按段边界比较。"""
    return len(segs) >= len(prefix_segs) and segs[:len(prefix_segs)] == prefix_segs


def _touches(path_segs: list, locked_segs: list) -> bool:
    """path 与锁节点有任何包含关系（自身/祖先/后代）都算触碰。"""
    return _under(locked_segs, path_segs) or _under(path_segs, locked_segs)


def apply_patch(config: dict, patch: list, manual_locked=(), allowed_prefixes=("/pages",)) -> PatchResult:
    """应用受约束的 patch；任何违规拒绝并保持 config 原样（原子性）。"""
    rejections = []
    work = copy.deepcopy(config)

    for idx, op in enumerate(patch):
        if not isinstance(op, dict) or op.get("op") not in _VALID_OPS:
            rejections.append(PatchRejection(idx, "INVALID_OP", str(op.get("path", "/")),
                                             f"非法操作 {op.get('op')!r}，可选 {sorted(_VALID_OPS)}"))
            continue
        path = op.get("path", "")
        segs = _segments(path)

        # —— 全量重写防护：对根的替换/删除 = 重写整棵树，架构上禁止 ——
        if path == "/" and op["op"] in ("replace", "remove", "add"):
            rejections.append(PatchRejection(idx, "ROOT_REPLACE_FORBIDDEN", path,
                                             "禁止对根节点操作——编辑必须走增量 patch，不允许全量重写"))
            continue

        # —— 路径白名单（影响范围断言）——
        if not any(_under(_segments(p), segs) for p in allowed_prefixes):
            rejections.append(PatchRejection(idx, "PATH_NOT_WHITELISTED", path,
                                             f"路径 {path} 不在允许前缀 {list(allowed_prefixes)} 内"))
            continue

        # —— manual_locked 锁：触碰（含祖先/后代/move 源）即拒绝 ——
        touched_locked = [l for l in manual_locked if _touches(segs, _segments(l))]
        if op["op"] == "move" and "from" in op:
            from_segs = _segments(op["from"])
            touched_locked += [l for l in manual_locked if _touches(from_segs, _segments(l))]
        if touched_locked:
            rejections.append(PatchRejection(idx, "LOCKED_NODE_TOUCHED", path,
                                             f"路径 {path} 触碰人工锁定节点 {sorted(set(touched_locked))}"))
            continue

        # —— 执行 ——
        err = _apply_op(work, op, segs, idx, rejections)
        if err:
            continue

    # —— 应用后结构必须仍然合法 ——
    if not rejections and validate_structure(work):
        codes = [v.code for v in validate_structure(work)]
        rejections.append(PatchRejection(len(patch), "PATCH_BREAKS_STRUCTURE", "/",
                                         f"patch 破坏配置结构：{codes}"))
        work = copy.deepcopy(config)

    ok = not rejections
    return PatchResult(ok, work if ok else copy.deepcopy(config),
                       [op.get("path") for op in patch] if ok else [], rejections)


def _apply_op(root: dict, op: dict, segs: list, idx: int, rejections: list):
    """在 root 上执行单个 op；违规时追加 rejection 并返回标记。"""
    try:
        if op["op"] == "move":
            from_segs = _segments(op["from"])
            value = _pop(root, from_segs)
            _set(root, segs, value, insert=True)
            return None
        if op["op"] == "remove":
            _pop(root, segs)
            return None
        if op["op"] == "replace":
            _set(root, segs, op["value"])
            return None
        if op["op"] == "add":
            _set(root, segs, op["value"], insert=True)
            return None
    except (PatchPathError, IndexError, ValueError, TypeError, KeyError) as e:
        # R1-1（评审修复）：非数字下标/越界/类型不匹配统一转为结构化拒绝，
        # patch 来自模型输出——防线自身不能先崩。
        rejections.append(PatchRejection(idx, "PATH_UNRESOLVABLE", op.get("path", "/"),
                                         f"路径无法解析：{type(e).__name__}: {e}"))
        return e
    return None


class PatchPathError(Exception):
    pass


def _navigate(root: dict, segs: list):
    """按段导航到父容器，返回 (parent, last_key)。"""
    node = root
    for s in segs[:-1]:
        if isinstance(node, list):
            node = node[int(s)]
        elif isinstance(node, dict):
            node = node[s]
        else:
            raise PatchPathError(f"路径段 {s!r} 不可导航")
    last = segs[-1] if segs else None
    return node, last


def _pop(root: dict, segs: list):
    if not segs:
        raise PatchPathError("不能对根 pop")
    parent, last = _navigate(root, segs)
    if isinstance(parent, list):
        i = int(last)
        if i >= len(parent):
            raise PatchPathError(f"数组下标越界 {i}")
        return parent.pop(i)
    if isinstance(parent, dict):
        if last not in parent:
            raise PatchPathError(f"字段 {last!r} 不存在")
        return parent.pop(last)
    raise PatchPathError("父容器既非数组也非对象")


def _set(root: dict, segs: list, value, insert: bool = False):
    if not segs:
        raise PatchPathError("不能对根 set")
    parent, last = _navigate(root, segs)
    if isinstance(parent, list):
        i = int(last)
        if i > len(parent):
            raise PatchPathError(f"数组下标越界 {i}")
        if insert and i == len(parent):
            parent.append(value)
        else:
            parent[i] = value
    elif isinstance(parent, dict):
        parent[last] = value
    else:
        raise PatchPathError("父容器既非数组也非对象")
