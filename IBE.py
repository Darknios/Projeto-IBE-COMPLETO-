"""Acesso seguro às contagens do IBE no Supabase."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date

import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError
from streamlit.errors import StreamlitSecretNotFoundError
from supabase import create_client


DISPLAY_COLUMNS = {
    "data": "Data",
    "grupo_recepcao": "Grupo da recepção",
    "horario_culto": "Horário do culto",
    "quantidade_pulpito": "Quantidade Púlpito",
    "quantidade_cadeiras_a": "Quantidade Cadeiras A",
    "quantidade_cadeiras_b": "Quantidade Cadeiras B",
    "quantidade_cadeiras_c": "Quantidade Cadeiras C",
    "quantidade_cadeiras_d": "Quantidade Cadeiras D",
    "quantidade_galeria": "Quantidade Galeria",
    "quantidade_salas": "Quantidade Salas",
    "quantidade_externo": "Quantidade Externo",
    "quantidade_online": "Quantidade On-line",
    "total_presencial": "Total",
}
VISITOR_COLUMN = "Quantidade Visitantes"
VISITOR_COLUMN_CANDIDATES = (
    "quantidade_visitantes",
    "quantidadeVisitantes",
    "quantidade_visitas",
    "quantidade_visitante",
)
NUMERIC_COLUMNS = tuple(
    column for column in DISPLAY_COLUMNS if column.startswith("quantidade_") or column == "total_presencial"
)
PAGE_SIZE = 1_000
PUBLIC_DASHBOARD_URL = "https://fyyvubvceijyeuhvncri.supabase.co"
PUBLIC_DASHBOARD_KEY = "sb_publishable_AvqTQvdX630cTqbJ0kIlHQ_Ky-BaS8i"


class SupabaseConfigurationError(RuntimeError):
    """A configuração local ou de produção está incompleta."""


class SupabaseDataError(RuntimeError):
    """Os dados retornados não atendem ao formato esperado."""


def _get_optional_secret(secrets: Mapping[str, str], key: str) -> object | None:
    """Read a Secret without blocking the dashboard when no file exists."""
    try:
        return secrets.get(key)
    except StreamlitSecretNotFoundError:
        return None


def _get_table(secrets: Mapping[str, str]) -> str:
    table = str(_get_optional_secret(secrets, "SUPABASE_TABLE") or "ibe_contagens")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        raise SupabaseConfigurationError("O nome configurado para SUPABASE_TABLE é inválido.")
    return table


def _get_read_configuration(secrets: Mapping[str, str]) -> tuple[str, str, str]:
    url = _get_optional_secret(secrets, "SUPABASE_URL") or PUBLIC_DASHBOARD_URL
    key = (
        _get_optional_secret(secrets, "SUPABASE_ANON_KEY")
        or _get_optional_secret(secrets, "SUPABASE_KEY")
        or PUBLIC_DASHBOARD_KEY
    )
    if not url or not key:
        raise SupabaseConfigurationError(
            "Configure SUPABASE_URL e SUPABASE_ANON_KEY nos Secrets do Streamlit."
        )
    return str(url), str(key), _get_table(secrets)


def _get_write_configuration(secrets: Mapping[str, str]) -> tuple[str, str, str]:
    url = _get_optional_secret(secrets, "SUPABASE_URL") or PUBLIC_DASHBOARD_URL
    key = _get_optional_secret(secrets, "SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SupabaseConfigurationError(
            "Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY nos Secrets para salvar contagens."
        )
    return str(url), str(key), _get_table(secrets)


def write_configuration_is_available(secrets: Mapping[str, str]) -> bool:
    """Indica se o Streamlit já possui a configuração necessária para gravar."""
    return bool(_get_optional_secret(secrets, "SUPABASE_SERVICE_ROLE_KEY"))


def _normalize_dashboard_data(rows: list[dict]) -> pd.DataFrame:
    dataframe = pd.DataFrame(rows)
    if dataframe.empty:
        return pd.DataFrame(columns=DISPLAY_COLUMNS.values())

    missing_columns = [column for column in DISPLAY_COLUMNS if column not in dataframe.columns]
    if missing_columns:
        raise SupabaseDataError("A tabela de contagens não possui as colunas esperadas.")

    dataframe = dataframe.rename(columns=DISPLAY_COLUMNS)
    dataframe["Data"] = pd.to_datetime(dataframe["Data"], errors="coerce")
    if dataframe["Data"].isna().any():
        raise SupabaseDataError("A coluna Data contém valores inválidos.")

    for column in [DISPLAY_COLUMNS[name] for name in NUMERIC_COLUMNS]:
        dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce").fillna(0).astype(int)

    visitor_column = next(
        (
            column
            for column in dataframe.columns
            if str(column).strip().lower() in {candidate.lower() for candidate in VISITOR_COLUMN_CANDIDATES}
        ),
        None,
    )
    if visitor_column is not None:
        dataframe[VISITOR_COLUMN] = pd.to_numeric(dataframe[visitor_column], errors="coerce").fillna(0).astype(int)
    else:
        dataframe[VISITOR_COLUMN] = 0
    return dataframe


def _fetch_rows(query: object) -> list[dict]:
    """Fetch all rows from a paginated Supabase query."""
    rows: list[dict] = []
    start = 0
    while True:
        response = query.range(start, start + PAGE_SIZE - 1).execute()
        page = response.data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


def _load_legacy_dashboard_data(client: object) -> pd.DataFrame:
    """Read the existing Contagens/Cultos structure used by this project."""
    rows = _fetch_rows(
        client.table("Contagens").select("*,Cultos!inner(Data,GrupoRecepcao,Horario)")
    )
    normalized_rows: list[dict] = []
    for row in rows:
        culto = row.get("Cultos") or {}
        if isinstance(culto, list):
            culto = culto[0] if culto else {}
        normalized_rows.append(
            {
                "data": culto.get("Data"),
                "grupo_recepcao": culto.get("GrupoRecepcao"),
                "horario_culto": culto.get("Horario"),
                "quantidade_pulpito": row.get("QuantidadePulpito", 0),
                "quantidade_cadeiras_a": row.get("QuantidadeCadeirasA", 0),
                "quantidade_cadeiras_b": row.get("QuantidadeCadeirasB", 0),
                "quantidade_cadeiras_c": row.get("QuantidadeCadeirasC", 0),
                "quantidade_cadeiras_d": row.get("QuantidadeCadeirasD", 0),
                "quantidade_galeria": row.get("QuantidadeGaleria", 0),
                "quantidade_salas": row.get("QuantidadeSalas", 0),
                "quantidade_externo": row.get("QuantidadeExterno", 0),
                "quantidade_online": row.get("QuantidadeOnline", 0),
                "total_presencial": row.get("Total", 0),
            }
        )
    return _normalize_dashboard_data(normalized_rows)


@st.cache_data(ttl=300, show_spinner="Atualizando dados do Supabase...")
def load_dashboard_data(url: str, key: str, table: str) -> pd.DataFrame:
    """Busca todos os registros públicos em páginas para evitar truncamento."""
    client = create_client(url, key)
    if table == "Contagens":
        return _load_legacy_dashboard_data(client)

    try:
        return _normalize_dashboard_data(_fetch_rows(client.table(table).select("*")))
    except APIError as error:
        if table != "ibe_contagens" or getattr(error, "code", None) != "PGRST205":
            raise
        return _load_legacy_dashboard_data(client)


def get_dashboard_data(secrets: Mapping[str, str]) -> pd.DataFrame:
    """Lê as contagens usando a chave pública, adequada ao dashboard aberto."""
    return load_dashboard_data(*_get_read_configuration(secrets))


def get_existing_count(
    secrets: Mapping[str, str], count_date: date, group: str, service_time: str
) -> dict | None:
    """Retorna a contagem existente para a combinação escolhida, se houver."""
    url, key, table = _get_write_configuration(secrets)
    response = (
        create_client(url, key)
        .table(table)
        .select("*")
        .eq("data", count_date.isoformat())
        .eq("grupo_recepcao", group)
        .eq("horario_culto", service_time)
        .maybe_single()
        .execute()
    )
    return response.data


def save_count(secrets: Mapping[str, str], payload: Mapping[str, object]) -> None:
    """Cria ou atualiza uma contagem com a chave de servidor, fora do navegador."""
    url, key, table = _get_write_configuration(secrets)
    create_client(url, key).table(table).upsert(
        dict(payload), on_conflict="data,grupo_recepcao,horario_culto"
    ).execute()
    load_dashboard_data.clear()
