from __future__ import annotations

import pandas as pd


SECTOR_COLUMNS = {
    "Púlpito": "Quantidade Púlpito",
    "Cadeiras A": "Quantidade Cadeiras A",
    "Cadeiras B": "Quantidade Cadeiras B",
    "Cadeiras C": "Quantidade Cadeiras C",
    "Cadeiras D": "Quantidade Cadeiras D",
    "Galeria": "Quantidade Galeria",
    "Salas": "Quantidade Salas",
    "Externo": "Quantidade Externo",
    "On-line": "Quantidade On-line",
    "Visitantes": "Quantidade Visitantes",
}

SERVICE_LABELS = {
    "1": "Manhã",
    "manhã": "Manhã",
    "manha": "Manhã",
    "2": "Noite",
    "noite": "Noite",
}


def total_by_event_name(events: list[dict], registrations: list[dict]) -> pd.DataFrame:
    """Soma Registro.Total somente quando NomeEvento corresponde a Eventos.Nome."""
    event_names: dict[str, str] = {}
    for event in events:
        name = event.get("Nome")
        if name is None:
            continue
        display_name = " ".join(str(name).split())
        if display_name:
            event_names.setdefault(display_name.casefold(), display_name)

    totals: dict[str, float] = {}
    for registration in registrations:
        event_key = " ".join(str(registration.get("NomeEvento") or "").split()).casefold()
        if event_key not in event_names:
            continue
        total = pd.to_numeric(registration.get("Total"), errors="coerce")
        if pd.isna(total):
            total = 0
        totals[event_key] = totals.get(event_key, 0) + float(total)

    return pd.DataFrame(
        [
            {"Evento": event_names[event_key], "Total": total}
            for event_key, total in totals.items()
        ],
        columns=["Evento", "Total"],
    )


def sector_average_by_service(dataframe: pd.DataFrame, sector: str = "Todos") -> pd.DataFrame:
    """Calcula a média por período do culto obedecendo ao setor selecionado.

    Quando o filtro é "Todos", usa o total do culto. Caso seja um setor específico,
    soma a quantidade do setor em cada linha antes de agrupar por manhã/noite.
    """
    if dataframe.empty:
        return pd.DataFrame(columns=["Período do culto", "Valor"])

    data = dataframe.copy()
    data["Período do culto"] = data["Horário do culto"].map(
        lambda value: SERVICE_LABELS.get(str(value).strip().lower(), str(value))
    )
    data = data[data["Período do culto"] != "Missa"]

    if sector == "Todos":
        data["Valor"] = pd.to_numeric(data["Total"], errors="coerce").fillna(0)
    else:
        metric = SECTOR_COLUMNS.get(sector)
        if metric is None:
            data["Valor"] = pd.to_numeric(data["Total"], errors="coerce").fillna(0)
        else:
            data["Valor"] = pd.to_numeric(data.get(metric, 0), errors="coerce").fillna(0)

    result = (
        data.groupby("Período do culto", as_index=False)["Valor"]
        .mean()
        .sort_values("Período do culto")
    )
    return result.reset_index(drop=True)
