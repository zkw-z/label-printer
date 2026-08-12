"""最近文件管理 单元测试"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from models.recent_files import add_recent_file, load_recent_files


def test_empty_recent(tmp_path: Path, monkeypatch):
    """测试空列表"""
    _patch_recent_file(tmp_path, monkeypatch)
    files = load_recent_files()
    assert files == []


def test_add_and_load(tmp_path: Path, monkeypatch):
    """测试添加和加载"""
    _patch_recent_file(tmp_path, monkeypatch)
    test_file = tmp_path / "test.xlsx"
    test_file.touch()

    add_recent_file(str(test_file))
    files = load_recent_files()
    assert len(files) == 1
    assert Path(files[0]).name == "test.xlsx"


def test_dedup(tmp_path: Path, monkeypatch):
    """测试去重：重复添加同一文件只保留一次"""
    _patch_recent_file(tmp_path, monkeypatch)
    test_file = tmp_path / "test.xlsx"
    test_file.touch()

    add_recent_file(str(test_file))
    add_recent_file(str(test_file))
    files = load_recent_files()
    assert len(files) == 1


def test_order(tmp_path: Path, monkeypatch):
    """测试排序：最新添加的在前"""
    _patch_recent_file(tmp_path, monkeypatch)
    file_a = tmp_path / "a.xlsx"
    file_b = tmp_path / "b.xlsx"
    file_a.touch()
    file_b.touch()

    add_recent_file(str(file_a))
    add_recent_file(str(file_b))
    files = load_recent_files()
    assert Path(files[0]).name == "b.xlsx"


def _patch_recent_file(tmp_path: Path, monkeypatch):
    """将 recent_files 模块的 _RECENT_FILE 指向临时路径"""
    import models.recent_files as rf
    monkeypatch.setattr(rf, "_RECENT_FILE", tmp_path / "recent_files.json")
