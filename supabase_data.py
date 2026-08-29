"""Leitura das contagens do IBE no Supabase.

O banco que originou este dashboard já teve mais de uma estrutura ao longo do
projeto. Este módulo suporta tanto a estrutura antiga (Contagens com colunas de
setores) quanto a estrutura relacional atual (Contagens/Cultos/Registros/Setores).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
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
PAGE_SIZE = 1_000
SUPABASE_PROJECT_REF = "fyyvubvceijyeuhvncri"
PUBLIC_DASHBOARD_URL = f"https://{SUPABASE_PROJECT_REF}.supabase.co"
PUBLIC_DASHBOARD_KEY = "sb_publishable_AvqTQvdX630cTqbJ0kIlHQ_Ky-BaS8i"
LEGACY_PUBLIC_DASHBOARD_KEY = "sb_publishable__R5PSqn3VUYXJdcy-RsXOQ_69pJelxj"
KNOWN_TABLES = ("Contagens", "Cultos", "Registros", "Setores", "Igrejas")


class SupabaseConfigurationError(RuntimeError):
    pass


class SupabaseDataError(RuntimeError):
    pass


def _empty_dashboard() -> pd.DataFrame:
    columns = list(DISPLAY_COLUMNS.values()) + [VISITOR_COLUMN]
    return pd.DataFrame(columns=columns)


def _get_optional_secret(secrets: Mapping[str, str], key: str) -> object | None:
    try:
        return secrets.get(key)
    except StreamlitSecretNotFoundError:
        return None


def _unique_strings(values) -> list[str]:
    result: list[str] = []
    for value in values:
        if not value:
            continue
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _get_read_configuration(secrets: Mapping[str, str]) -> tuple[str, list[str]]:
    url = str(_get_optional_secret(secrets, "SUPABASE_URL") or PUBLIC_DASHBOARD_URL).strip()
    keys = _unique_strings(
        [
            # A chave de servidor fica apenas no backend Streamlit e evita bloqueios de RLS.
            _get_optional_secret(secrets, "SUPABASE_SERVICE_ROLE_KEY"),
            _get_optional_secret(secrets, "SUPABASE_ANON_KEY"),
            _get_optional_secret(secrets, "SUPABASE_KEY"),
            PUBLIC_DASHBOARD_KEY,
            LEGACY_PUBLIC_DASHBOARD_KEY,
        ]
    )
    if not url or not keys:
        raise SupabaseConfigurationError("Configuração do Supabase incompleta.")
    return url, keys


def _get_write_configuration(secrets: Mapping[str, str]) -> tuple[str, str, str]:
    url = str(_get_optional_secret(secrets, "SUPABASE_URL") or PUBLIC_DASHBOARD_URL).strip()
    key = _get_optional_secret(secrets, "SUPABASE_SERVICE_ROLE_KEY")
    table = str(_get_optional_secret(secrets, "SUPABASE_WRITE_TABLE") or "ibe_contagens").strip()
    if not url or not key:
        raise SupabaseConfigurationError(
            "Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY nos Secrets para salvar contagens."
        )
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        raise SupabaseConfigurationError("O nome da tabela de gravação é inválido.")
    return url, str(key), table


def write_configuration_is_available(secrets: Mapping[str, str]) -> bool:
    # A tela principal atual é somente relatório. Mantemos compatibilidade com o
    # formulário antigo, sem fingir que a tabela relacional aceita o payload antigo.
    return bool(
        _get_optional_secret(secrets, "SUPABASE_SERVICE_ROLE_KEY")
        and _get_optional_secret(secrets, "SUPABASE_WRITE_TABLE")
    )


def _canonical(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _lookup(mapping: Mapping[str, object], *names: str) -> object | None:
    """Busca uma coluna ignorando caixa, acentos, espaços e underscore."""
    if not mapping:
        return None
    normalized = {_canonical(key): value for key, value in mapping.items()}
    for name in names:
        key = _canonical(name)
        if key in normalized and normalized[key] not in (None, ""):
            return normalized[key]
    return None


def _row_id(row: Mapping[str, object]) -> object | None:
    return _lookup(row, "Id", "ID", "id", "Uuid", "uuid")


def _foreign_id(row: Mapping[str, object], entity: str) -> object | None:
    return _lookup(
        row,
        f"{entity}Id",
        f"{entity}_id",
        f"Id{entity}",
        f"id_{entity}",
        entity,
    )


def _number(value: object) -> int:
    if value in (None, ""):
        return 0
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return 0
    return int(number)


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text.lower() not in {"none", "nan", "null"} else None


def _fetch_rows(query: object) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        response = query.range(start, start + PAGE_SIZE - 1).execute()
        page = response.data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


def _fetch_table(client: object, table: str) -> list[dict]:
    try:
        return _fetch_rows(client.table(table).select("*"))
    except Exception:
        return []


def _index_by_id(rows: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for row in rows:
        value = _row_id(row)
        if value is not None:
            index[str(value)] = row
    return index


SECTOR_TARGETS = {
    "pulpito": "quantidade_pulpito",
    "palco": "quantidade_pulpito",
    "cadeiraa": "quantidade_cadeiras_a",
    "cadeirasa": "quantidade_cadeiras_a",
    "setora": "quantidade_cadeiras_a",
    "cadeirab": "quantidade_cadeiras_b",
    "cadeirasb": "quantidade_cadeiras_b",
    "setorb": "quantidade_cadeiras_b",
    "cadeirac": "quantidade_cadeiras_c",
    "cadeirasc": "quantidade_cadeiras_c",
    "setorc": "quantidade_cadeiras_c",
    "cadeirad": "quantidade_cadeiras_d",
    "cadeirasd": "quantidade_cadeiras_d",
    "setord": "quantidade_cadeiras_d",
    "galeria": "quantidade_galeria",
    "salas": "quantidade_salas",
    "sala": "quantidade_salas",
    "externo": "quantidade_externo",
    "areaexterna": "quantidade_externo",
    "online": "quantidade_online",
    "onlineculto": "quantidade_online",
}
VISITOR_NAMES = {"visitante", "visitantes", "quantidadevisitantes"}


def _sector_target(name: object) -> str | None:
    key = _canonical(name)
    if key in VISITOR_NAMES or "visitant" in key:
        return "quantidade_visitantes"
    if key in SECTOR_TARGETS:
        return SECTOR_TARGETS[key]
    for token, target in SECTOR_TARGETS.items():
        if token and token in key:
            return target
    return None


def _base_normalized_row() -> dict[str, object]:
    return {
        "data": None,
        "grupo_recepcao": None,
        "horario_culto": None,
        "quantidade_pulpito": 0,
        "quantidade_cadeiras_a": 0,
        "quantidade_cadeiras_b": 0,
        "quantidade_cadeiras_c": 0,
        "quantidade_cadeiras_d": 0,
        "quantidade_galeria": 0,
        "quantidade_salas": 0,
        "quantidade_externo": 0,
        "quantidade_online": 0,
        "quantidade_visitantes": 0,
        "total_presencial": 0,
    }


def _fill_direct_counts(target: dict[str, object], row: Mapping[str, object]) -> None:
    direct = {
        "quantidade_pulpito": ("QuantidadePulpito", "Quantidade Púlpito", "Pulpito"),
        "quantidade_cadeiras_a": ("QuantidadeCadeirasA", "Quantidade Cadeiras A", "CadeirasA"),
        "quantidade_cadeiras_b": ("QuantidadeCadeirasB", "Quantidade Cadeiras B", "CadeirasB"),
        "quantidade_cadeiras_c": ("QuantidadeCadeirasC", "Quantidade Cadeiras C", "CadeirasC"),
        "quantidade_cadeiras_d": ("QuantidadeCadeirasD", "Quantidade Cadeiras D", "CadeirasD"),
        "quantidade_galeria": ("QuantidadeGaleria", "Quantidade Galeria", "Galeria"),
        "quantidade_salas": ("QuantidadeSalas", "Quantidade Salas", "Salas"),
        "quantidade_externo": ("QuantidadeExterno", "Quantidade Externo", "Externo"),
        "quantidade_online": ("QuantidadeOnline", "Quantidade On-line", "Online"),
        "quantidade_visitantes": ("QuantidadeVisitantes", "Visitantes", "QtdVisitantes"),
    }
    for field, candidates in direct.items():
        value = _lookup(row, *candidates)
        if value not in (None, ""):
            target[field] = _number(value)


def _extract_quantity(row: Mapping[str, object]) -> int:
    return _number(
        _lookup(
            row,
            "Quantidade",
            "Qtd",
            "Qnt",
            "Valor",
            "NumeroPessoas",
            "QuantidadePessoas",
            "QtdPessoas",
            "Numero",
            "Total",
        )
    )


def _extract_date(row: Mapping[str, object]) -> object | None:
    return _lookup(
        row,
        "Data",
        "DataCulto",
        "DataDaContagem",
        "DataContagem",
        "DataHora",
        "DataRegistro",
        "DataEvento",
        "Date",
        "CreatedAt",
        "created_at",
    )


def _extract_group(*rows: Mapping[str, object]) -> str | None:
    for row in rows:
        value = _lookup(
            row,
            "GrupoRecepcao",
            "Grupo da recepção",
            "Grupo",
            "EquipeRecepcao",
            "Equipe",
            "Recepcao",
        )
        text = _clean_text(value)
        if text:
            return text
    return None


def _extract_service(*rows: Mapping[str, object]) -> str | None:
    # Primeiro tenta campos de horário; depois o nome do culto.
    for row in rows:
        value = _lookup(row, "Horario", "Hora", "HorarioCulto", "Turno", "Periodo")
        text = _clean_text(value)
        if text:
            return text
    for row in rows:
        value = _lookup(row, "NomeCulto", "CultoNome", "Nome", "Titulo", "TipoCulto", "Descricao")
        text = _clean_text(value)
        if text:
            return text
    return None


def _related_rows(rows: list[dict], entity: str, parent_id: object) -> list[dict]:
    if parent_id is None:
        return []
    wanted = str(parent_id)
    result = []
    for row in rows:
        value = _foreign_id(row, entity)
        if value is not None and str(value) == wanted:
            result.append(row)
    return result


def _apply_registros(
    target: dict[str, object],
    registros: list[dict],
    setores_by_id: dict[str, dict],
) -> None:
    for registro in registros:
        setor = {}
        setor_id = _foreign_id(registro, "Setor")
        if setor_id is not None:
            setor = setores_by_id.get(str(setor_id), {})

        setor_name = (
            _lookup(registro, "NomeSetor", "SetorNome", "Setor", "Nome")
            or _lookup(setor, "Nome", "NomeSetor", "Setor", "Descricao", "Titulo")
        )
        quantity = _extract_quantity(registro)
        if not quantity and setor:
            quantity = _extract_quantity(setor)
        field = _sector_target(setor_name)
        if field:
            # Caso existam várias linhas para o mesmo setor, soma em vez de sobrescrever.
            target[field] = _number(target.get(field)) + quantity


def _finalize_row(row: dict[str, object]) -> dict[str, object] | None:
    if row.get("data") in (None, ""):
        return None

    parsed_date = pd.to_datetime(row.get("data"), errors="coerce")
    if pd.isna(parsed_date):
        return None

    group = _clean_text(row.get("grupo_recepcao"))
    service = _clean_text(row.get("horario_culto"))

    # Quando o banco não grava explicitamente o grupo de recepção, ele pode ser
    # reconstruído pela própria data do culto. Isso também resolve a diferença
    # histórica entre “1ª Domingo” e “1º Domingo”.
    service_key = _canonical(service)
    if not group:
        if "renove" in service_key:
            group = "Renove"
        elif "cafofo" in service_key:
            group = "Cafofo"
        elif parsed_date.weekday() == 6:
            ordinal = ((parsed_date.day - 1) // 7) + 1
            group = f"{ordinal}ª Domingo"
        elif parsed_date.weekday() == 2:
            group = "Quarta-feira"
        else:
            group = "Não informado"

    # Uniformiza os horários mais comuns sem depender do tipo usado no banco.
    if service:
        key = _canonical(service)
        if key in {"1", "manha", "matutino", "matutina"} or "manha" in key:
            service = "Manhã"
        elif key in {"2", "noite", "noturno", "noturna"} or "noite" in key:
            service = "Noite"
        else:
            time_match = re.search(r"(?:^|\D)([01]?\d|2[0-3]):[0-5]\d", service)
            if time_match:
                hour = int(time_match.group(1))
                service = "Manhã" if hour < 15 else "Noite"

    row["data"] = parsed_date
    row["grupo_recepcao"] = group
    row["horario_culto"] = service or "Não informado"

    physical_fields = [
        "quantidade_pulpito",
        "quantidade_cadeiras_a",
        "quantidade_cadeiras_b",
        "quantidade_cadeiras_c",
        "quantidade_cadeiras_d",
        "quantidade_galeria",
        "quantidade_salas",
        "quantidade_externo",
    ]
    direct_total = _number(row.get("total_presencial"))
    calculated_total = sum(_number(row.get(field)) for field in physical_fields)
    row["total_presencial"] = direct_total or calculated_total
    return row


def _normalize_rows(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return _empty_dashboard()
    dataframe = pd.DataFrame(rows)
    for column in DISPLAY_COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = 0 if column.startswith("quantidade_") or column == "total_presencial" else None
    if "quantidade_visitantes" not in dataframe.columns:
        dataframe["quantidade_visitantes"] = 0

    dataframe = dataframe.rename(columns={**DISPLAY_COLUMNS, "quantidade_visitantes": VISITOR_COLUMN})
    dataframe["Data"] = pd.to_datetime(dataframe["Data"], errors="coerce")
    dataframe = dataframe[dataframe["Data"].notna()].copy()
    if dataframe.empty:
        return _empty_dashboard()

    numeric = [
        "Quantidade Púlpito",
        "Quantidade Cadeiras A",
        "Quantidade Cadeiras B",
        "Quantidade Cadeiras C",
        "Quantidade Cadeiras D",
        "Quantidade Galeria",
        "Quantidade Salas",
        "Quantidade Externo",
        "Quantidade On-line",
        "Total",
        "Quantidade Visitantes",
    ]
    for column in numeric:
        dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce").fillna(0).astype(int)

    dataframe["Grupo da recepção"] = dataframe["Grupo da recepção"].fillna("Não informado").astype(str)
    dataframe["Horário do culto"] = dataframe["Horário do culto"].fillna("Não informado").astype(str)
    dataframe = dataframe.sort_values("Data").reset_index(drop=True)
    return dataframe


def _load_relational_dashboard_data(client: object) -> pd.DataFrame:
    """Lê as tabelas reais do banco e monta a visão larga usada pelo dashboard."""
    tables = {name: _fetch_table(client, name) for name in KNOWN_TABLES}
    contagens = tables["Contagens"]
    cultos = tables["Cultos"]
    registros = tables["Registros"]
    setores = tables["Setores"]

    cultos_by_id = _index_by_id(cultos)
    setores_by_id = _index_by_id(setores)

    normalized: list[dict] = []

    # Estrutura mais comum do projeto atual:
    # Contagens (cabeçalho/data/culto) -> Registros (quantidade) -> Setores (nome).
    for contagem in contagens:
        contagem_id = _row_id(contagem)
        culto_id = _foreign_id(contagem, "Culto")
        culto = cultos_by_id.get(str(culto_id), {}) if culto_id is not None else {}

        row = _base_normalized_row()
        row["data"] = _extract_date(contagem) or _extract_date(culto)
        row["grupo_recepcao"] = _extract_group(contagem, culto)
        row["horario_culto"] = _extract_service(contagem, culto)
        _fill_direct_counts(row, contagem)
        _fill_direct_counts(row, culto)

        direct_total = _lookup(contagem, "Total", "TotalPresencial", "QuantidadeTotal", "TotalPessoas")
        if direct_total not in (None, ""):
            row["total_presencial"] = _number(direct_total)

        linked = _related_rows(registros, "Contagem", contagem_id)
        # Alguns modelos chamaram a FK de RegistroId dentro de Setores, então também
        # lidamos com o arranjo inverso mais abaixo.
        _apply_registros(row, linked, setores_by_id)

        final = _finalize_row(row)
        if final:
            normalized.append(final)

    if normalized:
        return _normalize_rows(normalized)

    # Compatibilidade com uma versão em que Registros eram o cabeçalho e Setores
    # continham as quantidades por registro.
    registros_by_id = _index_by_id(registros)
    for registro in registros:
        registro_id = _row_id(registro)
        culto_id = _foreign_id(registro, "Culto")
        culto = cultos_by_id.get(str(culto_id), {}) if culto_id is not None else {}

        row = _base_normalized_row()
        row["data"] = _extract_date(registro) or _extract_date(culto)
        row["grupo_recepcao"] = _extract_group(registro, culto)
        row["horario_culto"] = _extract_service(registro, culto)
        _fill_direct_counts(row, registro)
        direct_total = _lookup(registro, "Total", "TotalPresencial", "QuantidadeTotal", "TotalPessoas")
        if direct_total not in (None, ""):
            row["total_presencial"] = _number(direct_total)

        linked_setores = _related_rows(setores, "Registro", registro_id)
        for setor_row in linked_setores:
            name = _lookup(setor_row, "Nome", "NomeSetor", "Setor", "Descricao", "Titulo")
            field = _sector_target(name)
            if field:
                row[field] = _number(row.get(field)) + _extract_quantity(setor_row)

        final = _finalize_row(row)
        if final:
            normalized.append(final)

    if normalized:
        return _normalize_rows(normalized)

    return _empty_dashboard()


def _load_local_history() -> pd.DataFrame:
    """Último recurso: mantém o histórico visível se a API estiver indisponível."""
    candidates = sorted(Path(__file__).resolve().parent.glob("*.xlsx"))
    for path in candidates:
        try:
            df = pd.read_excel(path)
        except Exception:
            continue
        if df.empty:
            continue

        normalized_columns = {_canonical(column): column for column in df.columns}

        def col(*names: str):
            for name in names:
                key = _canonical(name)
                if key in normalized_columns:
                    return normalized_columns[key]
            return None

        date_col = col("Data", "Data:")
        group_col = col("Grupo da recepção", "Grupo da recepção:")
        service_col = col("Horário do culto", "Horário do culto:")
        if not date_col or not group_col or not service_col:
            continue

        rows = []
        for _, item in df.iterrows():
            row = _base_normalized_row()
            row["data"] = item.get(date_col)
            row["grupo_recepcao"] = item.get(group_col)
            row["horario_culto"] = item.get(service_col)

            mapping = {
                "quantidade_pulpito": col("Quantidade Púlpito", "Quantidade Púlpito:"),
                "quantidade_cadeiras_a": col("Quantidade Cadeiras A", "Quantidade Cadeiras A:"),
                "quantidade_cadeiras_b": col("Quantidade Cadeiras B", "Quantidade Cadeiras B:"),
                "quantidade_cadeiras_c": col("Quantidade Cadeiras C", "Quantidade Cadeiras C:"),
                "quantidade_cadeiras_d": col("Quantidade Cadeiras D", "Quantidade Cadeiras D:"),
                "quantidade_galeria": col("Quantidade Galeria", "Quantidade Galeria:"),
                "quantidade_salas": col("Quantidade Salas", "Quantidade Salas:"),
                "quantidade_externo": col("Quantidade Externo", "Quantidade Externo:"),
                "quantidade_online": col("Quantidade On-line", "Quantidade On-line:"),
                "total_presencial": col("Total", "Total:"),
            }
            for field, source in mapping.items():
                if source:
                    row[field] = _number(item.get(source))
            final = _finalize_row(row)
            if final:
                rows.append(final)
        if rows:
            result = _normalize_rows(rows)
            result.attrs["source"] = "historico_local"
            return result
    return _empty_dashboard()


@st.cache_data(ttl=90, show_spinner="Atualizando dados...")
def load_dashboard_data(url: str, key: str) -> pd.DataFrame:
    client = create_client(url, key)
    dataframe = _load_relational_dashboard_data(client)
    if not dataframe.empty:
        dataframe.attrs["source"] = "supabase"
    return dataframe


def get_dashboard_data(secrets: Mapping[str, str]) -> pd.DataFrame:
    """Tenta as credenciais disponíveis e nunca trata uma tabela vazia como sucesso."""
    url, keys = _get_read_configuration(secrets)
    last_error: Exception | None = None

    for key in keys:
        try:
            dataframe = load_dashboard_data(url, key)
        except Exception as error:
            last_error = error
            continue
        if not dataframe.empty:
            return dataframe

    local = _load_local_history()
    if not local.empty:
        return local

    if last_error:
        raise SupabaseDataError("Não foi possível carregar as contagens do Supabase.") from last_error
    raise SupabaseDataError("As tabelas foram encontradas, mas não há dados compatíveis para exibir.")


@st.cache_data(ttl=90, show_spinner=False)
def load_sector_distribution(url: str, key: str) -> pd.DataFrame:
    """Une Registros e Contagens para montar a distribuição por setor."""
    client = create_client(url, key)
    registros = pd.DataFrame(
        _fetch_rows(client.table("Registros").select("Id"))
    )
    contagens = pd.DataFrame(
        _fetch_rows(
            client.table("Contagens").select("RegistroId,NomeSetor,Quantidade")
        )
    )
    if registros.empty or contagens.empty:
        return pd.DataFrame(columns=["Setor", "Quantidade"])

    joined = pd.merge(
        registros,
        contagens,
        how="inner",
        left_on="Id",
        right_on="RegistroId",
    )
    if joined.empty:
        return pd.DataFrame(columns=["Setor", "Quantidade"])

    names = joined.get("NomeSetor", pd.Series(index=joined.index, dtype="object"))
    quantities = joined.get("Quantidade", pd.Series(index=joined.index, dtype="object"))
    distribution = pd.DataFrame(
        {
            "Setor": names.fillna("Não informado").astype(str).str.strip().replace("", "Não informado"),
            "Quantidade": pd.to_numeric(quantities, errors="coerce").fillna(0),
        }
    )
    return (
        distribution.groupby("Setor", as_index=False)["Quantidade"]
        .sum()
        .sort_values("Setor")
        .reset_index(drop=True)
    )


def get_sector_distribution(secrets: Mapping[str, str]) -> pd.DataFrame:
    """Obtém a distribuição diretamente de Contagens.NomeSetor e Quantidade."""
    url, keys = _get_read_configuration(secrets)
    last_error: Exception | None = None
    for key in keys:
        try:
            distribution = load_sector_distribution(url, key)
        except Exception as error:
            last_error = error
            continue
        if not distribution.empty:
            return distribution

    empty_distribution = pd.DataFrame(columns=["Setor", "Quantidade"])
    if last_error:
        empty_distribution.attrs["load_error"] = True
    return empty_distribution


@st.cache_data(ttl=90, show_spinner=False)
def load_online_by_reception(url: str, key: str) -> pd.DataFrame:
    """Carrega a agregação SQL das pessoas on-line por grupo de recepção."""
    rows = _fetch_rows(
        create_client(url, key)
        .table("vw_online_por_grupo_recepcao")
        .select("grupo_recepcao,quantidade_online")
    )
    dataframe = pd.DataFrame(rows)
    if dataframe.empty:
        return pd.DataFrame(columns=["Grupo da recepção", "Quantidade On-line"])

    dataframe = dataframe.rename(
        columns={
            "grupo_recepcao": "Grupo da recepção",
            "quantidade_online": "Quantidade On-line",
        }
    )
    dataframe["Quantidade On-line"] = pd.to_numeric(
        dataframe["Quantidade On-line"], errors="coerce"
    ).fillna(0)
    return dataframe.sort_values("Grupo da recepção").reset_index(drop=True)


def get_online_by_reception(secrets: Mapping[str, str]) -> pd.DataFrame:
    """Obtém a soma on-line por grupo de recepção da view SQL."""
    url, keys = _get_read_configuration(secrets)
    last_error: Exception | None = None
    for key in keys:
        try:
            dataframe = load_online_by_reception(url, key)
        except Exception as error:
            last_error = error
            continue
        if not dataframe.empty:
            return dataframe

    empty_dataframe = pd.DataFrame(columns=["Grupo da recepção", "Quantidade On-line"])
    if last_error:
        empty_dataframe.attrs["load_error"] = True
    return empty_dataframe


def get_existing_count(
    secrets: Mapping[str, str], count_date: date, group: str, service_time: str
) -> dict | None:
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
    url, key, table = _get_write_configuration(secrets)
    create_client(url, key).table(table).upsert(
        dict(payload), on_conflict="data,grupo_recepcao,horario_culto"
    ).execute()
    load_dashboard_data.clear()
    load_sector_distribution.clear()
    load_online_by_reception.clear()
