"""Tests for core.config — configuration loading and precedence."""

import os
from pathlib import Path
from unittest.mock import patch

from core.config import (
    Config,
    GmailConfig,
    IMAPConfig,
    MailAppConfig,
    OutlookConfig,
    ProviderConfig,
    load_config,
    load_yaml_config,
    find_config_file,
    create_sample_config,
    _apply_yaml_config,
    _apply_env_config,
    apply_vip_senders_from_config,
)
from core.rules import VIP_SENDERS


class TestConfigDefaults:
    def test_default_config(self):
        config = Config()
        assert config.default_provider == "gmail"
        assert config.log_level == "INFO"
        assert config.dry_run is False
        assert config.batch_size == 100
        assert config.throttle_seconds == 1.0

    def test_default_gmail(self):
        config = Config()
        assert config.gmail.name == "gmail"
        assert config.gmail.default_query == "has:nouserlabels"
        assert config.gmail.state_file == "gmail_state.json"
        assert config.gmail.enabled is True

    def test_default_imap(self):
        config = Config()
        assert config.imap.host == "imap.gmail.com"
        assert config.imap.port == 993
        assert config.imap.use_gmail_extensions is False

    def test_default_outlook(self):
        config = Config()
        assert config.outlook.client_id is None
        assert config.outlook.token_cache_path is None

    def test_default_mailapp(self):
        config = Config()
        assert config.mailapp.account is None
        assert config.mailapp.default_mailbox == "INBOX"


class TestProviderConfig:
    def test_base_provider(self):
        pc = ProviderConfig(name="test")
        assert pc.enabled is True
        assert pc.default_query == ""
        assert pc.state_file is None
        assert pc.extra == {}


class TestLoadYamlConfig:
    def test_loads_valid_yaml(self, tmp_yaml_config):
        data = load_yaml_config(tmp_yaml_config)
        assert data["default_provider"] == "outlook"
        assert data["log_level"] == "DEBUG"
        assert data["batch_size"] == 50

    def test_nonexistent_file_returns_empty(self, tmp_path):
        data = load_yaml_config(tmp_path / "nope.yaml")
        assert data == {}

    def test_invalid_yaml_returns_empty(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(": : : invalid yaml {{{\n")
        data = load_yaml_config(bad)
        assert data == {}


class TestApplyYamlConfig:
    def test_applies_general_settings(self):
        config = Config()
        data = {
            "default_provider": "imap",
            "log_level": "WARNING",
            "batch_size": 200,
            "dry_run": True,
            "throttle_seconds": 2.5,
        }
        _apply_yaml_config(config, data)
        assert config.default_provider == "imap"
        assert config.log_level == "WARNING"
        assert config.batch_size == 200
        assert config.dry_run is True
        assert config.throttle_seconds == 2.5

    def test_applies_gmail_config(self):
        config = Config()
        data = {
            "gmail": {
                "default_query": "label:Test",
                "state_file": "custom.json",
            }
        }
        _apply_yaml_config(config, data)
        assert config.gmail.default_query == "label:Test"
        assert config.gmail.state_file == "custom.json"

    def test_applies_imap_config(self):
        config = Config()
        data = {
            "imap": {
                "host": "mail.example.com",
                "port": 143,
                "use_gmail_extensions": True,
            }
        }
        _apply_yaml_config(config, data)
        assert config.imap.host == "mail.example.com"
        assert config.imap.port == 143
        assert config.imap.use_gmail_extensions is True

    def test_applies_outlook_config(self):
        config = Config()
        data = {"outlook": {"client_id": "abc-123"}}
        _apply_yaml_config(config, data)
        assert config.outlook.client_id == "abc-123"

    def test_applies_vip_senders(self):
        config = Config()
        data = {
            "vip_senders": {
                "boss@co.com": {"pattern": "boss@co\\.com", "tier": 1, "star": True}
            }
        }
        _apply_yaml_config(config, data)
        assert "boss@co.com" in config.vip_senders

    def test_empty_data_no_change(self):
        config = Config()
        _apply_yaml_config(config, {})
        assert config.default_provider == "gmail"

    def test_none_data_no_change(self):
        config = Config()
        _apply_yaml_config(config, None)
        assert config.default_provider == "gmail"


class TestApplyEnvConfig:
    def test_env_overrides_provider(self):
        config = Config()
        with patch.dict(os.environ, {"MAIL_AUTO_DEFAULT_PROVIDER": "outlook"}):
            _apply_env_config(config, "MAIL_AUTO_")
        assert config.default_provider == "outlook"

    def test_env_overrides_dry_run(self):
        config = Config()
        with patch.dict(os.environ, {"MAIL_AUTO_DRY_RUN": "true"}):
            _apply_env_config(config, "MAIL_AUTO_")
        assert config.dry_run is True

    def test_env_overrides_batch_size(self):
        config = Config()
        with patch.dict(os.environ, {"MAIL_AUTO_BATCH_SIZE": "500"}):
            _apply_env_config(config, "MAIL_AUTO_")
        assert config.batch_size == 500

    def test_env_overrides_imap_host(self):
        config = Config()
        with patch.dict(os.environ, {"IMAP_HOST": "custom.imap.com"}):
            _apply_env_config(config, "MAIL_AUTO_")
        assert config.imap.host == "custom.imap.com"

    def test_env_overrides_outlook(self):
        config = Config()
        with patch.dict(os.environ, {"OUTLOOK_CLIENT_ID": "env-client-id"}):
            _apply_env_config(config, "MAIL_AUTO_")
        assert config.outlook.client_id == "env-client-id"


class TestLoadConfig:
    def test_loads_from_yaml(self, tmp_yaml_config):
        config = load_config(config_path=tmp_yaml_config)
        assert config.default_provider == "outlook"
        assert config.log_level == "DEBUG"
        assert config.batch_size == 50

    def test_defaults_without_file(self, tmp_path):
        config = load_config(config_path=tmp_path / "nonexistent.yaml")
        assert config.default_provider == "gmail"

    def test_env_overrides_yaml(self, tmp_yaml_config):
        with patch.dict(os.environ, {"MAIL_AUTO_DEFAULT_PROVIDER": "imap"}):
            config = load_config(config_path=tmp_yaml_config)
        assert config.default_provider == "imap"


class TestFindConfigFile:
    def test_env_variable_path(self, tmp_path):
        config_file = tmp_path / "env_config.yaml"
        config_file.write_text("default_provider: test\n")
        with patch.dict(os.environ, {"MAIL_AUTOMATION_CONFIG": str(config_file)}):
            found = find_config_file()
        assert found == config_file

    def test_returns_none_when_nothing_found(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("core.config.DEFAULT_CONFIG_PATHS", [Path("/nonexistent/path.yaml")]):
                found = find_config_file()
        assert found is None


class TestApplyVipSendersFromConfig:
    def test_adds_vip_senders(self):
        config = Config()
        config.vip_senders = {
            "ceo": {"pattern": r"ceo@corp\.com", "tier": 1, "star": True, "note": "CEO"},
        }
        count = apply_vip_senders_from_config(config)
        assert count == 1
        assert "ceo" in VIP_SENDERS

    def test_skips_invalid_entries(self):
        config = Config()
        config.vip_senders = {
            "bad": {"tier": 1},  # Missing 'pattern'
        }
        count = apply_vip_senders_from_config(config)
        assert count == 0


class TestCreateSampleConfig:
    def test_returns_yaml_string(self):
        sample = create_sample_config()
        assert "default_provider:" in sample
        assert "gmail:" in sample
        assert "vip_senders:" in sample

    def test_writes_to_file(self, tmp_path):
        path = tmp_path / "sample" / "config.yaml"
        create_sample_config(path=path)
        assert path.exists()
        content = path.read_text()
        assert "default_provider:" in content
