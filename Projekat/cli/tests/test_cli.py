"""
tests/test_cli.py
──────────────────
Testovi za CDK CLI komande.

Pokretanje:
  pip install pytest pytest-mock
  pytest tests/ -v
"""

import json
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli import cli


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture
def runner():
    return CliRunner()


# ── Benign testovi: Deploy ─────────────────────────────────────────────────────

class TestDeploy:

    def test_deploy_valid_py_file(self, runner, tmp_path):
        """Uspešan deploy .py fajla – server vraća 201."""
        script = tmp_path / "handler.py"
        script.write_text("print('hello world')")

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "urlHash": "a" * 64,
            "invokeUrl": "/api/functions/" + "a" * 64 + "/invoke",
        }

        with patch("oblak.auth.client.post", return_value=mock_resp), \
             patch("oblak.auth.token_store.load_token", return_value="fake.jwt.token"):
            result = runner.invoke(cli, ["deploy", str(script)])

        assert result.exit_code == 0, result.output
        assert "Deploy uspešan" in result.output

    def test_deploy_with_requirements(self, runner, tmp_path):
        """Deploy sa requirements.txt fajlom."""
        script = tmp_path / "handler.py"
        script.write_text("import requests\nprint('ok')")
        req = tmp_path / "requirements.txt"
        req.write_text("requests==2.31.0\n")

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "urlHash": "b" * 64,
            "invokeUrl": "/api/functions/" + "b" * 64 + "/invoke",
        }

        with patch("oblak.auth.client.post", return_value=mock_resp), \
             patch("oblak.auth.token_store.load_token", return_value="fake.jwt.token"):
            result = runner.invoke(
                cli, ["deploy", str(script), "--requirements", str(req)]
            )

        assert result.exit_code == 0, result.output

    def test_deploy_auto_detects_requirements(self, runner, tmp_path):
        """Auto-detekcija requirements.txt u istom folderu."""
        script = tmp_path / "handler.py"
        script.write_text("print('test')")
        req = tmp_path / "requirements.txt"
        req.write_text("flask==3.0.0\n")

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"urlHash": "c" * 64, "invokeUrl": "/x"}

        with patch("oblak.auth.client.post", return_value=mock_resp) as mock_post, \
             patch("oblak.auth.token_store.load_token", return_value="fake.jwt.token"):
            result = runner.invoke(cli, ["deploy", str(script)])

        assert result.exit_code == 0
        call_kwargs = mock_post.call_args[1]
        assert "requirements" in call_kwargs.get("files", {})

    def test_deploy_rejects_non_py_file(self, runner, tmp_path):
        """CLI odbija non-.py fajlove pre slanja ka serveru."""
        txt_file = tmp_path / "script.txt"
        txt_file.write_text("print('hello')")

        result = runner.invoke(cli, ["deploy", str(txt_file)])

        assert result.exit_code != 0
        assert ".py" in result.output

    def test_deploy_rejects_empty_file(self, runner, tmp_path):
        """CLI odbija prazan .py fajl."""
        empty = tmp_path / "empty.py"
        empty.write_text("")

        result = runner.invoke(cli, ["deploy", str(empty)])

        assert result.exit_code != 0
        assert "prazan" in result.output.lower()

    def test_deploy_handles_verification_failure(self, runner, tmp_path):
        """CLI prikazuje grešku kad server odbije kod zbog verifikacije (422)."""
        script = tmp_path / "malicious.py"
        script.write_text("import os; os.system('rm -rf /')")

        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 422
        mock_resp.json.return_value = {
            "error": "Static analysis found security issues."
        }

        with patch("oblak.auth.client.post", return_value=mock_resp), \
             patch("oblak.auth.token_store.load_token", return_value="fake.jwt.token"):
            result = runner.invoke(cli, ["deploy", str(script)])

        assert result.exit_code != 0
        assert "verifikaci" in result.output.lower()

    def test_deploy_rejects_oversized_file(self, runner, tmp_path):
        """CLI odbija fajlove veće od 1 MB bez slanja ka serveru."""
        big = tmp_path / "big.py"
        big.write_bytes(b"x" * (1024 * 1024 + 1))

        result = runner.invoke(cli, ["deploy", str(big)])

        assert result.exit_code != 0
        assert "prevelik" in result.output.lower()


# ── Benign testovi: Login / Logout ─────────────────────────────────────────────

class TestLogin:

    def test_login_success(self, runner):
        """Uspešan login čuva token."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "token": "header.payload.signature",
            "refreshToken": "refresh_abc",
        }

        with patch("requests.post", return_value=mock_resp), \
             patch("oblak.auth.token_store.save_tokens") as mock_save:
            result = runner.invoke(
                cli,
                ["login", "--username", "testuser", "--password", "testpass"],
            )

        assert result.exit_code == 0, result.output
        assert "testuser" in result.output
        mock_save.assert_called_once_with("header.payload.signature", "refresh_abc")

    def test_login_wrong_credentials(self, runner):
        """Login sa pogrešnom lozinkom prikazuje grešku."""
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 401

        with patch("requests.post", return_value=mock_resp):
            result = runner.invoke(
                cli,
                ["login", "--username", "user", "--password", "wrong"],
            )

        assert result.exit_code != 0

    def test_logout_clears_token(self, runner):
        """Logout briše token."""
        with patch("oblak.auth.token_store.is_logged_in", return_value=True), \
             patch("oblak.auth.token_store.clear_tokens") as mock_clear:
            result = runner.invoke(cli, ["logout"])

        assert result.exit_code == 0
        mock_clear.assert_called_once()

    def test_logout_when_not_logged_in(self, runner):
        """Logout kad nisi ulogovan prikazuje info poruku."""
        with patch("oblak.auth.token_store.is_logged_in", return_value=False):
            result = runner.invoke(cli, ["logout"])

        assert result.exit_code == 0
        assert "odjavljen" in result.output.lower()


# ── Benign testovi: Invoke ─────────────────────────────────────────────────────

class TestInvoke:

    def test_invoke_valid_hash(self, runner):
        """Uspešno pozivanje funkcije po validnom hashu."""
        valid_hash = "a" * 64

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 202
        mock_resp.json.return_value = {
            "status": "ACCEPTED",
            "message": "Execution request received.",
        }

        with patch("oblak.auth.client.post", return_value=mock_resp), \
             patch("oblak.auth.token_store.load_token", return_value="fake.jwt.token"):
            result = runner.invoke(cli, ["invoke", valid_hash])

        assert result.exit_code == 0
        assert "ACCEPTED" in result.output

    def test_invoke_invalid_hash_format(self, runner):
        """CLI odbija hash u pogrešnom formatu."""
        result = runner.invoke(cli, ["invoke", "not-a-valid-hash"])

        assert result.exit_code != 0
        assert "hash" in result.output.lower()

    def test_invoke_function_not_found(self, runner):
        """CLI prikazuje grešku kad funkcija ne postoji (404)."""
        valid_hash = "b" * 64

        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 404

        with patch("oblak.auth.client.post", return_value=mock_resp), \
             patch("oblak.auth.token_store.load_token", return_value="fake.jwt.token"):
            result = runner.invoke(cli, ["invoke", valid_hash])

        assert result.exit_code != 0
        assert "ne postoji" in result.output.lower()


# ── Maliciozni testovi: Security ──────────────────────────────────────────────

class TestSecurityMalicious:

    def test_path_traversal_in_script_arg(self, runner, tmp_path):
        """Maliciozan korisnik pokušava path traversal kao argument."""
        result = runner.invoke(cli, ["deploy", "../../etc/passwd"])
        assert result.exit_code != 0

    def test_deploy_unauthenticated(self, runner, tmp_path):
        """Deploy bez tokena treba da vrati grešku."""
        script = tmp_path / "handler.py"
        script.write_text("print('test')")

        with patch("oblak.auth.token_store.load_token",
                   side_effect=RuntimeError("Nisi ulogovan. Pokreni: oblak login")):
            result = runner.invoke(cli, ["deploy", str(script)])

        assert result.exit_code != 0
        assert "login" in result.output.lower()

    def test_credentials_file_permissions(self, tmp_path):
        """Credentials fajl mora imati chmod 600."""
        import oblak.auth.token_store as ts

        fake_dir = tmp_path / ".oblak"
        fake_creds = fake_dir / "credentials"

        with patch.object(ts, "_OBLAK_DIR", fake_dir), \
             patch.object(ts, "_CREDS_FILE", fake_creds), \
             patch("keyring.set_password", side_effect=Exception("no keyring")):
            ts.save_tokens("test.token.value", None)

        assert fake_creds.exists(), "Credentials fajl nije kreiran"
        file_mode = fake_creds.stat().st_mode
        assert not (file_mode & stat.S_IRGRP), "Group ne sme čitati credentials"
        assert not (file_mode & stat.S_IROTH), "Others ne sme čitati credentials"

    def test_audit_log_created_on_deploy_attempt(self, runner, tmp_path):
        """Audit log se kreira pri svakom deploy pokušaju."""
        import oblak.audit as audit_module

        fake_dir = tmp_path / ".oblak"
        fake_log = fake_dir / "audit.log"

        script = tmp_path / "handler.py"
        script.write_text("print('hello')")

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"urlHash": "d" * 64, "invokeUrl": "/x"}

        with patch("oblak.auth.client.post", return_value=mock_resp), \
             patch("oblak.auth.token_store.load_token", return_value="fake.jwt.token"), \
             patch.object(audit_module, "_OBLAK_DIR", fake_dir), \
             patch.object(audit_module, "_AUDIT_FILE", fake_log):
            runner.invoke(cli, ["deploy", str(script)])

        assert fake_log.exists(), "Audit log nije kreiran"
        entries = [json.loads(line) for line in fake_log.read_text().splitlines()]
        actions = [e["action"] for e in entries]
        assert "DEPLOY_START" in actions

    def test_invoke_hash_injection_attempt(self, runner):
        """Maliciozni hash pokušaji se odbijaju regex validacijom."""
        malicious_hashes = [
            "' OR '1'='1",
            "../../../etc/passwd",
            "abc; rm -rf /",
            "a" * 63,
            "a" * 65,
            "G" * 64,
        ]

        for bad_hash in malicious_hashes:
            result = runner.invoke(cli, ["invoke", bad_hash])
            assert result.exit_code != 0, f"Trebalo je odbiti: {bad_hash!r}"