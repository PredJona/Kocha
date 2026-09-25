import pytest

from backend.agent.config import AgentSettings


def test_settings_use_development_defaults(monkeypatch):
    for name in ("OLLAMA_HOST", "OLLAMA_MODEL", "OLLAMA_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)

    settings = AgentSettings.from_env()

    assert settings.host == "http://127.0.0.1:11434"
    assert settings.model == "qwen2.5:3b"
    assert settings.timeout == 120.0


def test_settings_allow_model_and_connection_overrides(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "https://models.example.test:8443///")
    monkeypatch.setenv("OLLAMA_MODEL", "my-custom-model:latest")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "2.5")

    settings = AgentSettings.from_env()

    assert settings.host == "https://models.example.test:8443"
    assert settings.model == "my-custom-model:latest"
    assert settings.timeout == 2.5


@pytest.mark.parametrize("value", ["", "  ", "ftp://localhost", "http://", "localhost:11434", "https://x.test/path", "https://x.test?key=secret", "https://user:pass@x.test"])
def test_settings_reject_invalid_host(monkeypatch, value):
    monkeypatch.setenv("OLLAMA_HOST", value)

    with pytest.raises(ValueError, match="OLLAMA_HOST"):
        AgentSettings.from_env()


@pytest.mark.parametrize("value", ["", "  \t "])
def test_settings_reject_blank_model(monkeypatch, value):
    monkeypatch.setenv("OLLAMA_MODEL", value)

    with pytest.raises(ValueError, match="OLLAMA_MODEL"):
        AgentSettings.from_env()


@pytest.mark.parametrize("value", ["", "abc", "0", "-1", "nan", "inf", "-inf"])
def test_settings_reject_invalid_timeout(monkeypatch, value):
    monkeypatch.setenv("OLLAMA_TIMEOUT", value)

    with pytest.raises(ValueError, match="OLLAMA_TIMEOUT"):
        AgentSettings.from_env()
