"""Validated configuration for the local Ollama connection."""

import math
import os
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class AgentSettings:
    host: str = "http://127.0.0.1:11434"
    model: str = "qwen3:4b-instruct"
    timeout: float = 120.0

    def __post_init__(self) -> None:
        raw_host = self.host.strip()
        try:
            parsed = urlsplit(raw_host)
            valid_port = parsed.port is None or parsed.port > 0
        except ValueError as exc:
            raise ValueError("OLLAMA_HOST must be an HTTP or HTTPS host URL") from exc

        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or not valid_port
            or parsed.username is not None
            or parsed.password is not None
            or any(char.isspace() for char in parsed.netloc)
            or (parsed.path and set(parsed.path) != {"/"})
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("OLLAMA_HOST must be an HTTP or HTTPS host URL")

        object.__setattr__(self, "host", f"{parsed.scheme}://{parsed.netloc}")

        if not self.model.strip():
            raise ValueError("OLLAMA_MODEL must not be blank")
        object.__setattr__(self, "model", self.model.strip())

        try:
            timeout = float(self.timeout)
        except (TypeError, ValueError) as exc:
            raise ValueError("OLLAMA_TIMEOUT must be a finite positive number") from exc
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("OLLAMA_TIMEOUT must be a finite positive number")
        object.__setattr__(self, "timeout", timeout)

    @classmethod
    def from_env(cls) -> "AgentSettings":
        return cls(
            host=os.environ.get("OLLAMA_HOST", cls.host),
            model=os.environ.get("OLLAMA_MODEL", cls.model),
            timeout=os.environ.get("OLLAMA_TIMEOUT", cls.timeout),
        )
