"""Importa a planilha histórica de contagens para a tabela ibe_contagens."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
from supabase import create_client


SOURCE_COLUMNS = {
    "Grupo da recepção": "grupo_recepcao",
    "Horário do culto": "horario_culto",
    "Data": "data",
    "Quantidade Púlpito": "quantidade_pulpito",
    "Quantidade Cadeiras A": "quantidade_cadeiras_a",
    "Quantidade Cadeiras B": "quantidade_cadeiras_b",
    "Quantidade Cadeiras C": "quantidade_cadeiras_c",
    "Quantidade Cadeiras D": "quantidade_cadeiras_d",
    "Quantidade Galeria": "quantidade_galeria",
    "Quantidade Salas": "quantidade_salas",
    "Quantidade Externo": "quantidade_externo",
    "Quantidade On-line": "quantidade_online",
}
NUMERIC_FIELDS = tuple(column for column in SOURCE_COLUMNS.values() if column.startswith("quantidade_"))


def load_rows(source_file: Path) -> list[dict]:
    dataframe = pd.read_excel(source_file)
    dataframe.columns = dataframe.columns.map(lambda column: str(column).strip().rstrip(":"))
    missing = [column for column in SOURCE_COLUMNS if column not in dataframe.columns]
    if missing:
        raise ValueError("A planilha não possui as colunas esperadas: " + ", ".join(missing))

    dataframe = dataframe[list(SOURCE_COLUMNS)].rename(columns=SOURCE_COLUMNS).copy()
    dataframe["data"] = pd.to_datetime(dataframe["data"], errors="coerce")
    if dataframe["data"].isna().any():
        raise ValueError("A coluna Data possui valores inválidos.")

    for column in NUMERIC_FIELDS:
        dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce").fillna(0).astype(int)
        if (dataframe[column] < 0).any():
            raise ValueError(f"A coluna {column} possui quantidade negativa.")
    for column in ("grupo_recepcao", "horario_culto"):
        dataframe[column] = dataframe[column].astype(str).str.strip()
        if dataframe[column].eq("").any():
            raise ValueError(f"A coluna {column} possui valores vazios.")

    dataframe["data"] = dataframe["data"].dt.date.astype(str)
    rows = dataframe.to_dict(orient="records")
    keys = {(row["data"], row["grupo_recepcao"], row["horario_culto"]) for row in rows}
    if len(keys) != len(rows):
        raise ValueError("A planilha contém combinações repetidas de data, grupo e horário.")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True, help="Caminho da planilha .xlsx")
    parser.add_argument("--table", default="ibe_contagens", help="Tabela de destino no Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Valida sem enviar dados")
    args = parser.parse_args()

    rows = load_rows(args.file)
    print(f"{len(rows)} contagens válidas encontradas.")
    if args.dry_run:
        print("Validação concluída; nenhum dado foi enviado.")
        return

    url = os.environ.get("SUPABASE_URL")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not service_role_key:
        raise SystemExit("Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY antes de importar.")

    client = create_client(url, service_role_key)
    for start in range(0, len(rows), 500):
        client.table(args.table).upsert(
            rows[start : start + 500], on_conflict="data,grupo_recepcao,horario_culto"
        ).execute()
    print("Histórico importado com sucesso.")


if __name__ == "__main__":
    main()
