from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, RootModel, field_validator, model_validator

from backend.schemas import Factura


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


def validate_raw_quantities(value: Any) -> Any:
    if isinstance(value, dict):
        items = value.get("items")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and "cantidad" in item:
                    quantity = item["cantidad"]
                    if type(quantity) is not int or quantity <= 0:
                        raise ValueError("item quantity must be a positive integer")
    return value


def validate_invoice(invoice: Factura) -> Factura:
    if any(not getattr(invoice, field).strip() for field in ("numero", "siniestro_id", "taller")):
        raise ValueError("invoice fields must not be blank")
    if not invoice.items:
        raise ValueError("invoice must contain at least one item")
    for item in invoice.items:
        if any(not getattr(item, field).strip() for field in ("codigo", "descripcion")):
            raise ValueError("item fields must not be blank")
        if type(item.cantidad) is not int or item.cantidad <= 0:
            raise ValueError("item quantity must be a positive integer")
        if not item.precio_unitario.is_finite() or item.precio_unitario <= 0:
            raise ValueError("item price must be finite and positive")
    return invoice


AgentInvoice = Annotated[Factura, BeforeValidator(validate_raw_quantities), AfterValidator(validate_invoice)]


class AgentRequest(StrictContract):
    invoice: AgentInvoice
    prompt: str

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must not be blank")
        return value


class ChatMessage(StrictContract):
    role: Literal["system", "user", "assistant"]
    content: str


class ToolCall(StrictContract):
    call_id: str
    name: str
    arguments: dict[str, Any]


class ToolDecision(StrictContract):
    type: Literal["tool_call"]
    name: str
    arguments: dict[str, Any]


class FinalDecision(StrictContract):
    type: Literal["final_answer"]
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("final message must not be blank")
        return value


class AgentDecision(RootModel[Annotated[ToolDecision | FinalDecision, Field(discriminator="type")]]):
    pass


class AgentError(StrictContract):
    code: str
    message: str


class AgentStep(StrictContract):
    type: Literal["pdf_text_extracted", "invoice_extracted", "invoice_validated", "model_call", "tool_call", "response_generated", "error"]
    tool: str | None = None
    status: Literal["running", "completed", "failed"]
    message: str


class ToolResult(StrictContract):
    call_id: str
    tool: str
    status: Literal["success", "error"]
    output: dict[str, Any] | None = None
    error: AgentError | None = None
    duration_ms: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_status(self) -> "ToolResult":
        if self.status == "error" and self.error is None:
            raise ValueError("failed tool result requires an error")
        if self.status == "success" and self.error is not None:
            raise ValueError("successful tool result cannot contain an error")
        return self


class AgentResponse(StrictContract):
    status: Literal["completed", "failed"]
    message: str
    steps: list[AgentStep] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    invoice: Factura | None = None
    claim: dict[str, Any] | None = None
    audit: dict[str, Any] | None = None
    error: AgentError | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "AgentResponse":
        if self.status == "failed" and self.error is None:
            raise ValueError("failed agent response requires an error")
        if self.status == "completed" and self.error is not None:
            raise ValueError("completed agent response cannot contain an error")
        return self
