import json
from pathlib import Path

import pytest

from devforge_ai_cli.commands.init import SUBDIRS, run_init


def test_init_creates_devforge_dir(tmp_path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    assert (tmp_path / ".devforge").is_dir()


def test_init_creates_all_subdirs(tmp_path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    for subdir in SUBDIRS:
        assert (tmp_path / ".devforge" / subdir).is_dir()


def test_init_creates_config_yml(tmp_path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    config = tmp_path / ".devforge" / "config.yml"
    assert config.exists()
    assert config.stat().st_size > 0


def test_init_creates_audit_ndjson(tmp_path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    audit = tmp_path / ".devforge" / "audit" / "audit.ndjson"
    assert audit.exists()
    event = json.loads(audit.read_text().splitlines()[0])
    assert event["event"] == "init"
    assert "timestamp" in event


def test_init_idempotent(tmp_path):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    run_init(plain=True, output_json=False, cwd=tmp_path)
    assert (tmp_path / ".devforge").is_dir()


def test_init_json_output(tmp_path, capsys):
    run_init(plain=False, output_json=True, cwd=tmp_path)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert "project" in data
    assert "devforge_dir" in data


def test_init_plain_output(tmp_path, capsys):
    run_init(plain=True, output_json=False, cwd=tmp_path)
    captured = capsys.readouterr()
    assert "Setup concluído" in captured.out


def test_init_config_content(tmp_path):
    import yaml
    run_init(plain=True, output_json=False, cwd=tmp_path)
    config_data = yaml.safe_load((tmp_path / ".devforge" / "config.yml").read_text())
    assert config_data["edition"] == "community"
    assert config_data["cloud_login"] is False
    assert config_data["audit_enabled"] is True
