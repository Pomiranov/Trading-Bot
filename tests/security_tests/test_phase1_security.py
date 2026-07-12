"""Phase 1 security tests — secrets, encryption, logging, audit."""
from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bot"))

from config import AppConfig, SecretsConfig, TelegramConfig
from security.config_validation import validate_config
from security.credential_vault import CredentialVault
from security.encryption import SecretBox
from security.redaction import redact_text
from security.secrets import ChainedSecretProvider, DockerSecretProvider, EnvSecretProvider


class EncryptionTests(unittest.TestCase):
    def test_roundtrip(self):
        key_hex = "a" * 64
        box = SecretBox(key_hex)
        original = "t.super_secret_broker_token_value"
        token = box.encrypt(original)
        self.assertNotIn(original, token)
        self.assertEqual(box.decrypt(token), original)


class RedactionTests(unittest.TestCase):
    def test_redacts_tinkoff_token(self):
        msg = "Failed with t.abc123XYZ_secret_token_value_here"
        redacted = redact_text(msg)
        self.assertNotIn("abc123XYZ", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_redacts_bearer(self):
        msg = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"
        redacted = redact_text(msg)
        self.assertIn("[REDACTED]", redacted)


class SecretProviderTests(unittest.TestCase):
    def test_env_provider(self):
        with patch.dict("os.environ", {"TEST_SECRET": " hello "}):
            self.assertEqual(EnvSecretProvider().get("TEST_SECRET"), "hello")

    def test_docker_provider_reads_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            secret_file = Path(tmp) / "db_password"
            secret_file.write_text("from-docker\n")
            provider = DockerSecretProvider(base_dir=Path(tmp))
            self.assertEqual(provider.get("DB_PASSWORD"), "from-docker")

    def test_chained_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "key").write_text("docker-val")
            providers = [
                DockerSecretProvider(base_dir=Path(tmp)),
                EnvSecretProvider(),
            ]
            with patch.dict("os.environ", {"KEY": "env-val"}):
                self.assertEqual(ChainedSecretProvider(providers).get("KEY"), "docker-val")


class CredentialVaultTests(unittest.TestCase):
    def test_vault_encrypts_on_disk(self):
        key_hex = "b" * 64
        box = SecretBox(key_hex)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "vault.json"
            vault = CredentialVault(path=path, box=box)
            vault.put("TINKOFF_TOKEN", "t.secret_value")
            raw = path.read_text()
            self.assertNotIn("t.secret_value", raw)
            self.assertEqual(vault.get("TINKOFF_TOKEN"), "t.secret_value")


class ConfigValidationTests(unittest.TestCase):
    def test_telegram_requires_whitelist(self):
        cfg = AppConfig(
            telegram=TelegramConfig(token="tok", chat_id="", allowed_chat_ids=[]),
        )
        issues = validate_config(cfg)
        codes = [i.code for i in issues]
        self.assertIn("TELEGRAM_AUTH_UNCONFIGURED", codes)

    def test_exposed_dashboard_requires_api_key(self):
        from config import DashboardConfig
        cfg = AppConfig(dashboard=DashboardConfig(host="0.0.0.0", api_key=""))
        issues = validate_config(cfg)
        self.assertTrue(any(i.code == "DASHBOARD_EXPOSED_NO_API_KEY" for i in issues))


class LoggingConfigTests(unittest.TestCase):
    def test_redacting_filter_on_log_record(self):
        from security.redaction import RedactingFilter

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="token=t.leaked_secret_value_abcdefghijklmnop",
            args=(),
            exc_info=None,
        )
        RedactingFilter().filter(record)
        self.assertNotIn("leaked_secret_value", record.msg)
        self.assertIn("[REDACTED]", record.msg)


if __name__ == "__main__":
    unittest.main()