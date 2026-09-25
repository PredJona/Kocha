"""Public-safe agent execution errors."""

MODEL_TIMEOUT = "MODEL_TIMEOUT"
MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
MODEL_HTTP_ERROR = "MODEL_HTTP_ERROR"
MODEL_INVALID_RESPONSE = "MODEL_INVALID_RESPONSE"


class AgentExecutionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
