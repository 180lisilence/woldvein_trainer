"""
woldvein Trainer v0.4.6 - 输入数值范围校验

通用数值校验工具，防止用户输入非法数值导致游戏崩溃或存档损坏。

校验原则：
    - 非数字输入：拒绝执行，给出提示
    - 负数：资源类拒绝（资源不能为负），等级类钳制到下限
    - 超大数：钳制到 int32 上限（2,147,483,647），避免Lua/游戏溢出
    - 零值：根据场景判断（资源增加不能为0，等级设置可以为0）

使用方式：
    from .input_validator import validate_int, validate_resource_amount, validate_boom_level
    amount, ok, msg = validate_resource_amount(entry.get())
    if not ok:
        messagebox.showwarning("输入无效", msg)
        return
"""

# int32 上限（Lua 数字和游戏内部通常用 32 位 int）
INT32_MAX = 2147483647
INT32_MIN = -2147483648

# 各场景的合理范围
RESOURCE_AMOUNT_MIN = 1
RESOURCE_AMOUNT_MAX = INT32_MAX  # 资源增加量上限
FAME_AMOUNT_MIN = 1
FAME_AMOUNT_MAX = 1000000  # 知名度单次增加上限
HAPPINESS_MIN = 0
HAPPINESS_MAX = 999  # 游戏内幸福度上限
BOOM_LEVEL_MIN = 1
BOOM_LEVEL_MAX = 14  # 鸿业满级（constants.BOOM_MAX_LEVEL）
SKIP_DAYS_MIN = 1
SKIP_DAYS_MAX = 3600  # 10年（constants.MAX_SKIP_DAYS）
TIME_SPEED_MIN = 0.05
TIME_SPEED_MAX = 60.0


def validate_int(value, min_val=None, max_val=None, field_name="数值"):
    """通用整数校验。

    参数：
        value: 输入值（字符串或数字）
        min_val: 最小值（None表示不限制）
        max_val: 最大值（None表示不限制）
        field_name: 字段名，用于错误提示

    返回：
        (parsed_value, is_valid, message)
        - parsed_value: 解析后的整数（无效时为None）
        - is_valid: 是否通过校验
        - message: 无效时的提示信息
    """
    if value is None:
        return None, False, f"{field_name}不能为空"

    # 字符串处理：去空白
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None, False, f"{field_name}不能为空"

    # 尝试解析为整数
    try:
        num = int(value)
    except (ValueError, TypeError):
        # 尝试先转float再int（如 "100.0"）
        try:
            num = int(float(value))
        except (ValueError, TypeError):
            return None, False, f"{field_name}必须是整数（当前: {value}）"

    # 范围校验
    if min_val is not None and num < min_val:
        return None, False, f"{field_name}不能小于 {min_val}（当前: {num}）"
    if max_val is not None and num > max_val:
        return None, False, f"{field_name}不能大于 {max_val}（当前: {num}）"

    return num, True, ""


def validate_resource_amount(value, field_name="资源数量"):
    """校验资源增加量（1 ~ INT32_MAX）。"""
    return validate_int(value, RESOURCE_AMOUNT_MIN, RESOURCE_AMOUNT_MAX, field_name)


def validate_fame_amount(value, field_name="知名度"):
    """校验知名度增加量（1 ~ 1,000,000）。"""
    return validate_int(value, FAME_AMOUNT_MIN, FAME_AMOUNT_MAX, field_name)


def validate_happiness(value, field_name="幸福度"):
    """校验幸福度（0 ~ 999）。"""
    return validate_int(value, HAPPINESS_MIN, HAPPINESS_MAX, field_name)


def validate_boom_level(value, field_name="鸿业等级"):
    """校验鸿业等级（1 ~ 14）。"""
    return validate_int(value, BOOM_LEVEL_MIN, BOOM_LEVEL_MAX, field_name)


def validate_skip_days(value, field_name="跳天天数"):
    """校验跳天天数（1 ~ 3600）。"""
    return validate_int(value, SKIP_DAYS_MIN, SKIP_DAYS_MAX, field_name)


def validate_float(value, min_val=None, max_val=None, field_name="数值"):
    """通用浮点数校验（用于时间流速等）。

    返回：
        (parsed_value, is_valid, message)
    """
    if value is None:
        return None, False, f"{field_name}不能为空"
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None, False, f"{field_name}不能为空"
    try:
        num = float(value)
    except (ValueError, TypeError):
        return None, False, f"{field_name}必须是数字（当前: {value}）"
    if min_val is not None and num < min_val:
        return None, False, f"{field_name}不能小于 {min_val}（当前: {num}）"
    if max_val is not None and num > max_val:
        return None, False, f"{field_name}不能大于 {max_val}（当前: {num}）"
    return num, True, ""


def validate_time_speed(value):
    """校验时间流速（0.05 ~ 60.0）。"""
    return validate_float(value, TIME_SPEED_MIN, TIME_SPEED_MAX, "时间流速")


def clamp_int(value, min_val, max_val):
    """将数值钳制到范围内（不报错，直接修正）。

    用于 Spinbox 等已有范围限制但需要兜底的场景。
    """
    try:
        num = int(value)
    except (ValueError, TypeError):
        return min_val
    return max(min_val, min(max_val, num))
