from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class NewsItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    news_id: str
    source_id: str
    source_name: str
    source_url: str
    url: str
    title: str
    summary: str | None = None
    published_at: datetime | None = None
    category: str | None = None
    scraped_at: datetime
    language: str
    content_hash: str
    reliability_weight: float = 1.0
    collector_method: str = "requests"


Direction = Literal["alcista", "bajista", "neutral", "mixto", "incierto"]
Impact = Literal["nulo", "bajo", "medio", "alto", "muy_alto"]


class GPTClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo_activo: str
    subtipo_evento: str
    pais_region: list[str]
    sentido_oro: Direction
    sentido_dolar: Direction
    sentido_usd_pen: Direction
    sentido_precio_oro_soles: Direction
    impacto_esperado: Impact
    horizonte_probable: Literal["inmediato", "1d", "3d", "semanas", "largo_plazo", "incierto"]
    confianza_gpt: float = Field(ge=0, le=1)
    resumen_estandarizado: str
    escenario_base: str
    escenario_diferente: str
    condicion_de_cambio: str
    variables_afectadas: list[str]
    actores_clave: list[str]
    razonamiento_resumido: str


class EnrichedNews(BaseModel):
    news_id: str
    enriched_at: datetime
    provider: Literal["ollama", "openai"]
    model: str
    input_hash: str | None = None
    enrichment_status: Literal["completed", "pending", "error"]
    error: str | None = None
    classification: GPTClassification | None = None


class MarketLabel(BaseModel):
    news_id: str
    reference_date: str
    reference_price: float
    price_1d: float | None = None
    return_1d: float | None = None
    direction_1d: str | None = None
    impact_class_1d: str | None = None
    price_3d: float | None = None
    return_3d: float | None = None
    direction_3d: str | None = None
    impact_class_3d: str | None = None
    labeled_at: datetime


class PipelineRun(BaseModel):
    run_id: str
    timestamp: datetime
    stage: str
    source: str | None = None
    news_found: int = 0
    news_new: int = 0
    news_duplicates: int = 0
    news_enriched: int = 0
    errors: list[dict[str, Any]] = Field(default_factory=list)
    duration_seconds: float = 0
    mode: str = "local"
