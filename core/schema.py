"""Dynamic extraction schema: FieldSpec + runtime-built Pydantic model.

Domain-agnostic. FieldSpec declares a single extractable field; the caller
passes a list of them and build_dynamic_model() produces a Pydantic model
where every field is Optional (absent data = None).
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, create_model, model_validator

FieldType = Literal["string", "bool", "int", "float", "literal", "list"]

_FIELD_NAME_RE = r"^[a-z_][a-z0-9_]*$"


class FieldSpec(BaseModel):
    """Declaración de un campo a extraer.

    - name: snake_case, `^[a-z_][a-z0-9_]*$`
    - type: tipo de dato del valor extraído
    - allowed: obligatorio si type == "literal" (vocabulario cerrado)
    - validator: nombre de un validador determinista del registry (Task 6)
    - description: instrucción para el LLM sobre qué buscar
    """

    name: str = Field(..., pattern=_FIELD_NAME_RE, description="snake_case, minúsculas")
    type: FieldType
    description: str = ""
    allowed: Optional[list[str]] = Field(
        None, description="Valores permitidos — OBLIGATORIO si type == 'literal'"
    )
    validator: Optional[str] = Field(
        None, description="Nombre del validador determinista (dni, nie, phone_es, email, date)"
    )
    validator_config: Optional[dict[str, Any]] = None  # p.ej. {"fmt": "%d/%m/%Y"}
    external_field: Optional[str] = Field(
        None, description="Columna del sistema externo (CRM/ERP) a la que mapea el campo. "
        "Si esa columna declara vocabulario cerrado (selection), los valores reales "
        "restringen 'allowed'."
    )

    @property
    def is_literal(self) -> bool:
        return self.type == "literal"

    @model_validator(mode="after")
    def _literal_requires_allowed(self):
        if self.type == "literal" and not self.allowed:
            raise ValueError(
                f"Campo literal '{self.name}' requiere 'allowed' con el vocabulario cerrado"
            )
        return self


def _py_type(spec: FieldSpec) -> Any:
    """Map a FieldSpec type to a Python/Pydantic type annotation."""
    base: Any
    if spec.type == "string":
        base = str
    elif spec.type == "bool":
        base = bool
    elif spec.type == "int":
        base = int
    elif spec.type == "float":
        base = float
    elif spec.type == "list":
        base = list[str]  # listas de strings (no anidar más en el MVP)
    elif spec.type == "literal":
        if not spec.allowed:
            raise ValueError(
                f"Campo literal '{spec.name}' requiere 'allowed' con el vocabulario cerrado"
            )
        base = Literal[tuple(spec.allowed)]
    else:  # pragma: no cover — FieldType ya valida
        raise ValueError(f"Tipo desconocido: {spec.type}")

    return Optional[base]


def build_dynamic_model(fields: list[FieldSpec], model_name: str = "DynamicEntities") -> type[BaseModel]:
    """Construye un modelo Pydantic con todos los campos OBLIGATORIAMENTE opcionales."""
    annotations = {}
    for spec in fields:
        annotations[spec.name] = (_py_type(spec), Field(None, description=spec.description))
    return create_model(model_name, **annotations)