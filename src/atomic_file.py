"""
woldvein Trainer v0.4.6 - 原子文件操作工具

防止写入中断（断电、崩溃、进程被杀）导致文件损坏。

核心原则：
    - 写入目标文件时，先写临时文件，确认完整后再原子替换（os.replace）
    - 备份目录时，先复制到 .tmp 目录，成功后再重命名
    - 任何步骤失败都不影响原始文件

使用方式：
    from .atomic_file import atomic_write_text, atomic_write_json, atomic_backup_dir
    atomic_write_json(config_path, config_dict)
    atomic_backup_dir(source_dir, backup_dir, "save_backup")
"""
import os
import json
import shutil
import tempfile


def atomic_write_text(filepath, content, encoding="utf-8"):
    """原子写入文本文件。

    流程：写 .tmp → fsync → os.replace 原子替换。
    任何步骤失败都不会破坏原文件。
    """
    filepath = os.path.abspath(filepath)
    parent = os.path.dirname(filepath)
    if parent:
        os.makedirs(parent, exist_ok=True)

    # 临时文件放在同目录（保证 os.replace 是同卷原子操作）
    tmp_path = filepath + ".tmp"
    try:
        with open(tmp_path, "w", encoding=encoding, newline="") as f:
            f.write(content)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass  # 某些文件系统不支持 fsync，忽略
        # 原子替换（Windows 上 os.replace 也是原子的）
        os.replace(tmp_path, filepath)
        return True
    except Exception:
        # 失败时清理临时文件
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_json(filepath, data, encoding="utf-8", indent=2):
    """原子写入 JSON 文件。"""
    content = json.dumps(data, ensure_ascii=False, indent=indent)
    return atomic_write_text(filepath, content, encoding)


def atomic_backup_dir(source_dir, dest_dir, name_prefix="backup"):
    """原子备份目录。

    流程：
        1. 创建 name_prefix_YYYYMMDD_HHMMSS.tmp 临时目录
        2. copytree 源目录到临时目录
        3. 成功后重命名为最终名称（去掉 .tmp）
        4. 失败则删除临时目录

    返回：
        (success, final_path, error_msg)
    """
    import datetime
    if not os.path.exists(source_dir):
        return False, None, f"源目录不存在: {source_dir}"

    os.makedirs(dest_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    final_name = f"{name_prefix}_{timestamp}"
    final_path = os.path.join(dest_dir, final_name)
    tmp_path = final_path + ".tmp"

    # 如果临时目录已存在（上次中断残留），先删除
    if os.path.exists(tmp_path):
        try:
            shutil.rmtree(tmp_path)
        except OSError:
            pass

    try:
        shutil.copytree(source_dir, tmp_path)
        # 复制成功，原子重命名（同目录下 rename 是原子的）
        os.rename(tmp_path, final_path)
        return True, final_path, None
    except Exception as e:
        # 失败则清理临时目录
        try:
            if os.path.exists(tmp_path):
                shutil.rmtree(tmp_path)
        except OSError:
            pass
        return False, None, str(e)


def atomic_backup_file(source_file, dest_dir, name_prefix=None):
    """原子备份单个文件。

    流程：复制到 .tmp → 重命名为最终名称。
    """
    import datetime
    if not os.path.exists(source_file):
        return False, None, f"源文件不存在: {source_file}"

    os.makedirs(dest_dir, exist_ok=True)
    basename = os.path.basename(source_file)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = name_prefix if name_prefix else basename
    final_name = f"{prefix}_{timestamp}"
    final_path = os.path.join(dest_dir, final_name)
    tmp_path = final_path + ".tmp"

    try:
        shutil.copy2(source_file, tmp_path)
        os.rename(tmp_path, final_path)
        return True, final_path, None
    except Exception as e:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        return False, None, str(e)


def safe_restore_backup(backup_path, target_path):
    """安全恢复备份：先备份目标，再用备份替换。

    流程：
        1. 将当前目标重命名为 .old（保留兜底）
        2. 将备份复制/移动到目标位置
        3. 成功后删除 .old
        4. 失败则从 .old 恢复

    返回：
        (success, error_msg)
    """
    if not os.path.exists(backup_path):
        return False, f"备份不存在: {backup_path}"

    old_path = target_path + ".old"
    # 清理旧的 .old
    if os.path.exists(old_path):
        try:
            if os.path.isdir(old_path):
                shutil.rmtree(old_path)
            else:
                os.remove(old_path)
        except OSError:
            pass

    try:
        # 1. 先把当前目标改名为 .old
        if os.path.exists(target_path):
            os.rename(target_path, old_path)

        # 2. 复制备份到目标
        if os.path.isdir(backup_path):
            shutil.copytree(backup_path, target_path)
        else:
            shutil.copy2(backup_path, target_path)

        # 3. 成功，删除 .old
        if os.path.exists(old_path):
            if os.path.isdir(old_path):
                shutil.rmtree(old_path)
            else:
                os.remove(old_path)

        return True, None
    except Exception as e:
        # 4. 失败，从 .old 恢复
        try:
            if os.path.exists(old_path):
                if os.path.exists(target_path):
                    if os.path.isdir(target_path):
                        shutil.rmtree(target_path)
                    else:
                        os.remove(target_path)
                os.rename(old_path, target_path)
        except OSError:
            pass
        return False, str(e)
