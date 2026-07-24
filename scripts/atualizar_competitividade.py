#!/usr/bin/env python3
"""Atualiza preços médios e tarifas efetivas de molduras de pinus nos EUA.

Fonte: U.S. Census Bureau, Monthly U.S. Imports by Harmonized System.
A API exige a variável de ambiente CENSUS_API_KEY.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "competitividade.json"
API_URL = "https://api.census.gov/data/timeseries/intltrade/imports/hsimport"
HTS_CODES = ("4409104010", "4409104090")
SAO_PAULO = timezone(timedelta(hours=-3))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("competitividade-molduras")


def load_data() -> dict[str, Any]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def save_data(payload: dict[str, Any]) -> None:
    DATA_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": "RadarTarifacoMadeira/2.0"})
    return session


def candidate_periods(months_back: int = 8) -> list[str]:
    today = datetime.now(tz=SAO_PAULO)
    year, month = today.year, today.month - 1
    if month == 0:
        year -= 1
        month = 12

    periods: list[str] = []
    for _ in range(months_back):
        periods.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year -= 1
            month = 12
    return periods


def as_number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def fetch_country_commodity(
    session: requests.Session,
    api_key: str,
    period: str,
    country_code: str,
    commodity: str,
) -> dict[str, Any] | None:
    params = {
        "get": (
            "CTY_CODE,CTY_NAME,I_COMMODITY,I_COMMODITY_LDESC,"
            "CON_VAL_MO,CON_QY1_MO,CAL_DUT_MO,UNIT_QY1,LAST_UPDATE"
        ),
        "for": f"usitc standard countries and areas:{country_code}",
        "time": period,
        "I_COMMODITY": commodity,
        "key": api_key,
    }
    response = session.get(API_URL, params=params, timeout=45)
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list) or len(rows) < 2:
        return None

    headers = rows[0]
    values = rows[1]
    return dict(zip(headers, values))


def fetch_country(
    session: requests.Session,
    api_key: str,
    period: str,
    country: dict[str, Any],
) -> dict[str, Any]:
    total_value = 0.0
    total_quantity = 0.0
    total_duty = 0.0
    last_update = None
    units: set[str] = set()
    returned_codes: list[str] = []

    for commodity in HTS_CODES:
        row = fetch_country_commodity(
            session=session,
            api_key=api_key,
            period=period,
            country_code=str(country["codigo_census"]),
            commodity=commodity,
        )
        if not row:
            continue
        total_value += as_number(row.get("CON_VAL_MO"))
        total_quantity += as_number(row.get("CON_QY1_MO"))
        total_duty += as_number(row.get("CAL_DUT_MO"))
        last_update = row.get("LAST_UPDATE") or last_update
        if row.get("UNIT_QY1"):
            units.add(str(row["UNIT_QY1"]))
        returned_codes.append(commodity)

    price_linear = total_value / total_quantity if total_quantity > 0 else None
    effective_tariff = total_duty / total_value * 100 if total_value > 0 else None

    updated = dict(country)
    updated.update(
        {
            "preco_usd_m_linear": round(price_linear, 6) if price_linear is not None else None,
            "quantidade_m_linear": round(total_quantity, 3) if total_quantity else None,
            "valor_importado_usd": round(total_value, 2) if total_value else None,
            "direito_calculado_usd": round(total_duty, 2) if total_duty else 0,
            "tarifa_efetiva_pct": round(effective_tariff, 4) if effective_tariff is not None else None,
            "unidades_census": sorted(units),
            "hts_com_movimento": returned_codes,
            "ultima_atualizacao_census": last_update,
        }
    )
    return updated


def has_trade(rows: list[dict[str, Any]]) -> bool:
    return any(as_number(row.get("valor_importado_usd")) > 0 for row in rows)


def main() -> int:
    payload = load_data()
    api_key = os.getenv("CENSUS_API_KEY", "").strip()
    metadata = payload.setdefault("metadata", {})
    metadata["atualizado_em"] = datetime.now(tz=SAO_PAULO).isoformat(timespec="seconds")

    if not api_key:
        metadata["status"] = "aguardando_chave"
        metadata["mensagem"] = (
            "A tabela está pronta, mas a API do U.S. Census exige uma chave gratuita. "
            "Cadastre CENSUS_API_KEY nos Secrets do GitHub e execute novamente o workflow."
        )
        save_data(payload)
        logger.warning("CENSUS_API_KEY não configurada; estrutura preservada.")
        return 0

    session = build_session()
    original_countries = payload.get("paises", [])
    errors: list[str] = []
    selected_rows: list[dict[str, Any]] | None = None
    selected_period: str | None = None

    for period in candidate_periods():
        logger.info("Consultando período %s", period)
        rows: list[dict[str, Any]] = []
        errors_for_period: list[str] = []
        for country in original_countries:
            try:
                rows.append(fetch_country(session, api_key, period, country))
            except requests.RequestException as exc:
                logger.warning("Falha em %s (%s): %s", country.get("pais"), period, exc)
                errors_for_period.append(f"{country.get('pais')}: {exc}")
                rows.append(dict(country))
            except (ValueError, KeyError, TypeError) as exc:
                logger.warning("Resposta inválida em %s (%s): %s", country.get("pais"), period, exc)
                errors_for_period.append(f"{country.get('pais')}: resposta inválida")
                rows.append(dict(country))

        if has_trade(rows):
            selected_rows = rows
            selected_period = period
            errors = errors_for_period
            break

    if selected_rows is None:
        metadata["status"] = "erro"
        metadata["mensagem"] = (
            "A API respondeu, mas não foi encontrado movimento para os códigos HTS monitorados "
            "nos últimos meses. Os dados anteriores foram preservados."
        )
        save_data(payload)
        logger.error("Nenhum período com movimento encontrado.")
        return 0

    payload["paises"] = selected_rows
    metadata.update(
        {
            "status": "ok" if not errors else "parcial",
            "periodo_referencia": selected_period,
            "mensagem": (
                "Preços médios calculados por valor aduaneiro de importação dividido por metros lineares. "
                "A tarifa efetiva é o direito calculado dividido pelo valor de importação."
            ),
            "falhas": errors,
            "hts": list(HTS_CODES),
            "fonte_precos": "U.S. Census Bureau - Monthly U.S. Imports by Harmonized System",
            "fonte_tarifas_efetivas": "CAL_DUT_MO / CON_VAL_MO",
        }
    )
    save_data(payload)
    logger.info("Arquivo atualizado: %s (%s)", DATA_PATH, selected_period)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
