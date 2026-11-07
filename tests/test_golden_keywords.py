"""Tests de Keywords de Oro importando directamente de src.collection.collector."""
import pytest
from src.collection.collector import _check_keywords_de_oro, _normalize_text

POSITIVE_CASES = [
    "Feminicidio de Cindy en Cuautitlan dejo a dos menores en orfandad",
    "Doble feminicidio en Cuautitlan: matan a mujer y su hija; nina de 3 anos fue robada",
    "Asesinan a una mujer frente a sus hijos en Ecatepec",
    "Erika Camila esta bajo resguardo del DIF tras el feminicidio de su madre",
    "Quedan huerfanos tres ninos tras feminicidio de su madre",
    "La madre fue asesinada y dejaron a dos menores desamparados",
    "Los hijos de la victima presenciaron el crimen",
    "Mujer baleada frente a sus hijos",
    "Dejó a dos menores en orfandad por feminicidio",
    "Orfandad por feminicidio: 3 ninos quedaron solos",
    "Huerfanos de madre tras feminicidio en Edomex",
]

NEGATIVE_CASES = [
    "Menor de edad asesina a su madre en Guadalajara",
    "Detienen a adolescente por feminicidio en Jalisco",
    "Cifras de feminicidio en Mexico 2025",
    "Marcha contra la violencia de genero en CDMX",
    "Ley contra la violencia vicaria aprobada en el Senado",
]


@pytest.mark.parametrize("text", POSITIVE_CASES)
def test_positive_gold_keywords(text: str):
    assert _check_keywords_de_oro(_normalize_text(text)) is True


@pytest.mark.parametrize("text", NEGATIVE_CASES)
def test_negative_gold_keywords(text: str):
    assert _check_keywords_de_oro(_normalize_text(text)) is False
