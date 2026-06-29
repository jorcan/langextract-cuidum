"""
Pydantic schemas v2 — Schema reducido para uso real.
Pipeline A (Triage): 9 entidades para alertas en tiempo real.
Pipeline B (Perfil): 16 entidades para perfil semanal de partner.

Uso de Literal types para forzar consistencia de valores.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class TriageExtraction(BaseModel):
    """
    Pipeline A — Triage en tiempo real.
    9 entidades clave para detectar señales de retención, venta y urgencia.
    Coste estimado: ~$0.001/llamada.
    """
    urgencia: Literal["rutinario", "urgente"] = Field(
        description="Nivel de urgencia de la llamada"
    )
    menciona_baja: bool = Field(
        description="True si el interlocutor menciona EXPLÍCITAMENTE querer darse de baja o cancelar"
    )
    menciona_queja: bool = Field(
        description="True si expresa queja explícita sobre el servicio, cuidadora, facturación o cualquier aspecto"
    )
    menciona_competidores: bool = Field(
        description="True si menciona otras empresas del sector (Cuideo, Atenzia, Sanyres, etc.)"
    )
    upsell_opportunity: bool = Field(
        description="True si hay oportunidad de vender más horas, servicios extra o producto"
    )
    intencion_futura: Literal["renovar", "cancelar", "esperar", "evaluando", "no_mencionada"] = Field(
        description="Intención explícita o inferida del cliente respecto al servicio"
    )
    sentimiento_general: Literal["positivo", "neutral", "negativo", "preocupado", "agradecido"] = Field(
        description="Sentimiento general del interlocutor durante la llamada"
    )
    necesidad_especifica: Optional[str] = Field(
        None,
        description="Necesidad concreta expresada. Texto libre. Ej: 'Necesito alguien que hable inglés', 'Solo por las mañanas'"
    )
    churn_risk_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Riesgo de baja inferido de 0.0 (ninguno) a 1.0 (seguro). Basado en tono, menciones de baja, competidores y frustración"
    )


class PartnerProfileExtraction(BaseModel):
    """
    Pipeline B — Perfil semanal de partner.
    16 entidades. Añade contexto demográfico y relacional al triage.
    Coste estimado: ~$0.003/llamada.
    """
    # Del triage
    urgencia: Literal["rutinario", "urgente"]
    menciona_baja: bool
    menciona_queja: bool
    menciona_competidores: bool
    upsell_opportunity: bool
    intencion_futura: Literal["renovar", "cancelar", "esperar", "evaluando", "no_mencionada"]
    sentimiento_general: Literal["positivo", "neutral", "negativo", "preocupado", "agradecido"]
    necesidad_especifica: Optional[str] = None
    churn_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Contexto demographic
    quien_llama: Literal["familiar", "paciente", "cuidadora", "gestor", "otro"] = Field(
        description="Persona que realiza la llamada"
    )
    relacion_llamante_paciente: Optional[str] = Field(
        None,
        description="Relación del llamante con el paciente. Ej: 'hijo', 'hija', 'esposo', 'esposa', 'ella_misma'"
    )
    patologia_principal: Optional[str] = Field(
        None,
        description="Patología principal mencionada. Ej: 'Alzheimer', 'Parkinson', 'ictus', 'vejez' o null si no se menciona"
    )
    fase_ciclo_cliente: Literal["prospeccion", "captacion", "onboarding", "estable", "riesgo", "fuga", "no_aplica"] = Field(
        description="Fase del ciclo de vida del cliente inferida de la conversación"
    )
    intencion_permanencia: Literal["seguro", "evaluando", "temporal", "no_mencionada"] = Field(
        description="Intención del cliente de permanecer en el servicio a medio plazo"
    )
    ampliacion_horas_interes: bool = Field(
        description="True si el cliente muestra interés en ampliar horas/servicios"
    )
    agradecimiento_cliente: bool = Field(
        description="True si el cliente expresa agradecimiento explícito"
    )


class ExtractionMetadata(BaseModel):
    """Metadata de la llamada."""
    call_id: int
    partner_id: Optional[int] = None
    call_date: Optional[str] = None


class TriageResult(BaseModel):
    """Resultado completo del triage."""
    call: ExtractionMetadata
    entities: TriageExtraction
    confidence: float = 1.0
    schema_version: str = "3.0.0"


class ProfileResult(BaseModel):
    """Resultado completo del perfil."""
    call: ExtractionMetadata
    entities: PartnerProfileExtraction
    confidence: float = 1.0
    schema_version: str = "3.0.0"
