"""配置 Schema 单元测试"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from config_schema import AppConfig


class TestAppConfig:
    """AppConfig 加载/保存/校验"""

    def test_default_values(self):
        """测试默认值"""
        cfg = AppConfig()
        assert cfg.fba_printer == ""
        assert cfg.fba_orientation == "portrait"
        assert cfg.fba_scale == 0.98
        assert cfg.fba_width == 100
        assert cfg.fba_height == 100
        assert cfg.sku_orientation == "portrait"

    def test_orientation_validation(self):
        """测试 orientation 字段合法性校验"""
        AppConfig(fba_orientation="portrait")
        AppConfig(fba_orientation="landscape")
        with pytest.raises(Exception):
            AppConfig(fba_orientation="invalid")

    def test_scale_range(self):
        """测试 scale 范围校验"""
        AppConfig(fba_scale=0.5)
        AppConfig(fba_scale=1.0)
        with pytest.raises(Exception):
            AppConfig(fba_scale=0.4)
        with pytest.raises(Exception):
            AppConfig(fba_scale=1.1)

    def test_width_height_range(self):
        """测试 fba_width/height 范围校验"""
        AppConfig(fba_width=10, fba_height=10)
        AppConfig(fba_width=500, fba_height=500)
        with pytest.raises(Exception):
            AppConfig(fba_width=9)
        with pytest.raises(Exception):
            AppConfig(fba_height=501)

    def test_load_save_roundtrip(self, tmp_path: Path):
        """测试加载和保存往返一致性"""
        config_file = tmp_path / "test_config.json"
        original = AppConfig(
            fba_printer="Test Printer",
            fba_width=120,
            fba_height=80,
            fba_scale=0.85,
        )
        original.save(config_file)
        assert config_file.exists()

        loaded = AppConfig.load(config_file)
        assert loaded.fba_printer == "Test Printer"
        assert loaded.fba_width == 120
        assert loaded.fba_height == 80
        assert loaded.fba_scale == 0.85

    def test_load_missing_file(self, tmp_path: Path):
        """测试加载不存在的文件返回默认值"""
        cfg = AppConfig.load(tmp_path / "nonexistent.json")
        assert isinstance(cfg, AppConfig)
        assert cfg.fba_printer == ""

    def test_load_corrupted_file(self, tmp_path: Path):
        """测试加载损坏的 JSON 返回默认值"""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json}", encoding="utf-8")
        cfg = AppConfig.load(bad_file)
        assert isinstance(cfg, AppConfig)

    def test_load_unknown_fields_filtered(self, tmp_path: Path):
        """测试加载时自动过滤未知字段"""
        config_file = tmp_path / "test_config.json"
        data = {
            "fba_printer": "My Printer",
            "unknown_field": "should be ignored",
        }
        config_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        cfg = AppConfig.load(config_file)
        assert cfg.fba_printer == "My Printer"
        assert not hasattr(cfg, "unknown_field")

    def test_save_only_known_fields(self, tmp_path: Path):
        """测试保存时只保留已知字段"""
        config_file = tmp_path / "test_config.json"
        cfg = AppConfig(fba_printer="Test")
        cfg.save(config_file)
        data = json.loads(config_file.read_text(encoding="utf-8"))
        assert "fba_printer" in data
        assert "unknown_field" not in data

    def test_to_dict(self):
        """测试 to_dict 返回正确字段"""
        cfg = AppConfig(fba_printer="P1", fba_width=200)
        d = cfg.to_dict()
        assert d["fba_printer"] == "P1"
        assert d["fba_width"] == 200
        assert "fba_orientation" in d
