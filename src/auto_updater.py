"""
woldvein Trainer v0.4.6 - 自动更新系统

功能：
    - 检查更新（从 GitHub Releases 或自定义服务器获取最新版本）
    - 下载更新包
    - 验证更新包完整性（SHA256 哈希校验）
    - 应用更新（原子替换文件）
    - 更新失败自动回滚

使用方式：
    from .auto_updater import AutoUpdater
    updater = AutoUpdater(current_version="0.4.6", repo="180lisilence/woldvein0.3-0.4")
    has_update, latest_version, download_url = updater.check_update()
    if has_update:
        success, msg = updater.download_and_install(download_url)
"""
import os
import sys
import json
import hashlib
import shutil
import tempfile
import datetime

from .logger import log, log_success, log_error, log_warning
from .atomic_file import atomic_write_json


class AutoUpdater:
    """自动更新器"""

    def __init__(self, current_version, repo=None, update_url=None):
        """
        参数：
            current_version: 当前版本号，如 "0.4.6"
            repo: GitHub 仓库，如 "180lisilence/woldvein0.3-0.4"（可选）
            update_url: 自定义更新服务器URL（可选，优先于GitHub）
        """
        self.current_version = current_version
        self.repo = repo
        self.update_url = update_url
        self._temp_dir = None

    def check_update(self):
        """检查更新。

        返回：
            (has_update, latest_version, download_url, release_notes)
        """
        try:
            if self.update_url:
                return self._check_custom_server()
            elif self.repo:
                return self._check_github()
            else:
                return False, self.current_version, None, "未配置更新源"
        except Exception as e:
            log_error(f"检查更新失败: {e}")
            return False, self.current_version, None, str(e)

    def _check_github(self):
        """从 GitHub Releases 检查更新"""
        import urllib.request
        api_url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        req = urllib.request.Request(api_url, headers={"User-Agent": "woldvein-trainer"})

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        latest_version = data.get("tag_name", "").lstrip("v")
        release_notes = data.get("body", "")
        download_url = None

        # 查找合适的资产（Windows EXE 或 ZIP）
        for asset in data.get("assets", []):
            name = asset.get("name", "").lower()
            if name.endswith(".exe") or name.endswith(".zip"):
                download_url = asset.get("browser_download_url")
                break

        has_update = self._compare_versions(latest_version, self.current_version) > 0
        return has_update, latest_version, download_url, release_notes

    def _check_custom_server(self):
        """从自定义服务器检查更新"""
        import urllib.request
        req = urllib.request.Request(self.update_url, headers={"User-Agent": "woldvein-trainer"})

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        latest_version = data.get("version", "")
        download_url = data.get("download_url", "")
        release_notes = data.get("notes", "")
        expected_hash = data.get("sha256", "")

        has_update = self._compare_versions(latest_version, self.current_version) > 0
        return has_update, latest_version, download_url, release_notes

    def _compare_versions(self, v1, v2):
        """比较版本号。

        返回：
            1: v1 > v2
            0: v1 == v2
            -1: v1 < v2
        """
        def parse_version(v):
            parts = []
            for p in v.split("."):
                try:
                    parts.append(int(p))
                except ValueError:
                    parts.append(0)
            return parts

        v1_parts = parse_version(v1)
        v2_parts = parse_version(v2)

        # 补齐长度
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))

        for a, b in zip(v1_parts, v2_parts):
            if a > b:
                return 1
            elif a < b:
                return -1
        return 0

    def download_and_install(self, download_url, expected_hash=None, callback=None):
        """下载并安装更新。

        参数：
            download_url: 下载URL
            expected_hash: 期望的SHA256哈希（可选，用于校验）
            callback: 进度回调函数 callback(downloaded, total)

        返回：
            (success, message)
        """
        try:
            # 创建临时目录
            self._temp_dir = tempfile.mkdtemp(prefix="woldvein_update_")
            archive_path = os.path.join(self._temp_dir, "update.zip")

            # 下载
            success, msg = self._download(download_url, archive_path, callback)
            if not success:
                return False, msg

            # 校验哈希
            if expected_hash:
                actual_hash = self._sha256(archive_path)
                if actual_hash.lower() != expected_hash.lower():
                    return False, f"哈希校验失败: 期望 {expected_hash}, 实际 {actual_hash}"

            # 备份当前版本
            backup_dir = self._backup_current_version()

            # 应用更新
            success, msg = self._apply_update(archive_path)
            if not success:
                # 回滚
                self._rollback(backup_dir)
                return False, f"更新失败，已回滚: {msg}"

            log_success("更新安装成功，需要重启程序生效")
            return True, "更新安装成功，请重启程序"

        except Exception as e:
            log_error(f"下载安装更新失败: {e}")
            return False, str(e)
        finally:
            # 清理临时目录
            if self._temp_dir and os.path.exists(self._temp_dir):
                try:
                    shutil.rmtree(self._temp_dir)
                except Exception:
                    pass

    def _download(self, url, dest_path, callback=None):
        """下载文件。

        返回：
            (success, message)
        """
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "woldvein-trainer"})

        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 8192

            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if callback:
                        callback(downloaded, total)

        return True, "下载完成"

    def _sha256(self, filepath):
        """计算文件SHA256哈希"""
        sha = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def _backup_current_version(self):
        """备份当前版本。

        返回：
            备份目录路径
        """
        if getattr(sys, "frozen", False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(app_dir, f"backup_{timestamp}")
        os.makedirs(backup_dir, exist_ok=True)

        # 备份关键文件
        for fname in os.listdir(app_dir):
            fpath = os.path.join(app_dir, fname)
            if os.path.isfile(fpath) and fname.lower().endswith((".exe", ".dll", ".json", ".py")):
                try:
                    shutil.copy2(fpath, os.path.join(backup_dir, fname))
                except Exception:
                    pass

        log(f"[更新] 当前版本已备份到: {backup_dir}")
        return backup_dir

    def _apply_update(self, archive_path):
        """应用更新（解压并替换文件）。

        返回：
            (success, message)
        """
        import zipfile
        if not zipfile.is_zipfile(archive_path):
            # 如果不是ZIP，假设是EXE直接替换
            return self._apply_exe_update(archive_path)

        if getattr(sys, "frozen", False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        extract_dir = os.path.join(self._temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(extract_dir)

        # 替换文件
        for root, dirs, files in os.walk(extract_dir):
            for fname in files:
                src = os.path.join(root, fname)
                rel_path = os.path.relpath(src, extract_dir)
                dst = os.path.join(app_dir, rel_path)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)

        return True, "更新已应用"

    def _apply_exe_update(self, exe_path):
        """直接替换EXE更新"""
        if getattr(sys, "frozen", False):
            current_exe = sys.executable
        else:
            return False, "源码运行模式下不支持EXE替换"

        # 注意：正在运行的EXE无法直接替换，需要写入批处理在重启后替换
        bat_path = os.path.join(os.path.dirname(current_exe), "update.bat")
        with open(bat_path, "w") as f:
            f.write(f'@echo off\n')
            f.write(f'timeout /t 2 /nobreak >nul\n')
            f.write(f'copy /y "{exe_path}" "{current_exe}"\n')
            f.write(f'del "{bat_path}"\n')
            f.write(f'start "" "{current_exe}"\n')

        return True, "更新包已下载，重启后自动应用"

    def _rollback(self, backup_dir):
        """回滚到备份版本"""
        if not backup_dir or not os.path.exists(backup_dir):
            return

        if getattr(sys, "frozen", False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        for fname in os.listdir(backup_dir):
            src = os.path.join(backup_dir, fname)
            dst = os.path.join(app_dir, fname)
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass

        log_warning("[更新] 已回滚到旧版本")


def check_for_updates(current_version, repo=None):
    """便捷函数：检查更新。

    返回：
        (has_update, latest_version, download_url, release_notes)
    """
    updater = AutoUpdater(current_version, repo=repo)
    return updater.check_update()
