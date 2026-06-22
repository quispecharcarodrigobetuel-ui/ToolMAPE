from datetime import datetime, timezone

from src.news.gpt.classifier import OllamaClassifier, classification_input_hash, create_classifier
from src.news.models import NewsItem


VALID_CLASSIFICATION = {
    "tipo_activo": "oro",
    "subtipo_evento": "política monetaria",
    "pais_region": ["Estados Unidos"],
    "sentido_oro": "alcista",
    "sentido_dolar": "bajista",
    "sentido_usd_pen": "incierto",
    "sentido_precio_oro_soles": "alcista",
    "impacto_esperado": "medio",
    "horizonte_probable": "3d",
    "confianza_gpt": 0.7,
    "resumen_estandarizado": "La Fed evalúa recortar tasas.",
    "escenario_base": "Menores tasas favorecen al oro.",
    "escenario_diferente": "La inflación evita el recorte.",
    "condicion_de_cambio": "Datos de inflación superiores a lo esperado.",
    "variables_afectadas": ["oro", "dólar", "tasas"],
    "actores_clave": ["Fed"],
    "razonamiento_resumido": "Menores tasas reducen el costo de oportunidad del oro.",
}


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        import json

        return {"message": {"content": json.dumps(VALID_CLASSIFICATION)}}


class FakeSession:
    def __init__(self):
        self.payload = None

    def post(self, url, json, timeout):
        self.payload = json
        return FakeResponse()


def config():
    return {
        "pipeline": {
            "llm_provider": "ollama",
            "ollama_model": "llama3:latest",
            "ollama_base_url": "http://localhost:11434",
            "llm_max_retries": 1,
            "llm_timeout_seconds": 30,
        }
    }


def item():
    return NewsItem(
        news_id="id",
        source_id="test",
        source_name="Test",
        source_url="https://example.com",
        url="https://example.com/a",
        title="La Fed evalúa recortar tasas",
        scraped_at=datetime.now(timezone.utc),
        language="es",
        content_hash="hash",
    )


def test_ollama_uses_json_schema_and_validates_response():
    session = FakeSession()
    classifier = OllamaClassifier(config(), session=session)
    result = classifier.classify(item())
    assert result.enrichment_status == "completed"
    assert result.provider == "ollama"
    assert result.classification.sentido_oro == "alcista"
    assert result.input_hash == classification_input_hash(item())
    assert session.payload["format"]["additionalProperties"] is False
    assert session.payload["stream"] is False


def test_factory_defaults_to_ollama():
    assert isinstance(create_classifier(config()), OllamaClassifier)
