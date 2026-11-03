import pytest

import config


def test_remote_database_uses_verified_aiven_tls(monkeypatch):
    monkeypatch.setenv("MYSQL_HOST", "mysql.example.aivencloud.com")
    options = config._database_engine_options()

    assert options["connect_args"] == {
        "ssl_ca": str(config.AIVEN_CA_CERT_PATH),
        "ssl_verify_cert": True,
        "ssl_verify_identity": True,
    }


def test_production_fails_clearly_when_aiven_ca_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("MYSQL_HOST", "mysql.example.aivencloud.com")
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setattr(config, "AIVEN_CA_CERT_PATH", tmp_path / "missing-ca.pem")

    with pytest.raises(RuntimeError, match="Aiven CA certificate"):
        config._database_engine_options()


def test_local_development_does_not_require_aiven_ca(monkeypatch, tmp_path):
    monkeypatch.setenv("MYSQL_HOST", "localhost")
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setattr(config, "AIVEN_CA_CERT_PATH", tmp_path / "missing-ca.pem")

    assert config._database_engine_options() == {}
