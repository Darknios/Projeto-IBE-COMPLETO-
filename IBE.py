from __future__ import annotations

from datetime import date, datetime
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

from supabase_data import (
    SupabaseConfigurationError,
    SupabaseDataError,
    get_dashboard_data,
    get_existing_count,
    save_count,
    write_configuration_is_available,
)


COUNT_FIELDS = (
    ("quantidade_pulpito", "Púlpito"),
    ("quantidade_cadeiras_a", "Cadeiras A"),
    ("quantidade_cadeiras_b", "Cadeiras B"),
    ("quantidade_cadeiras_c", "Cadeiras C"),
    ("quantidade_cadeiras_d", "Cadeiras D"),
    ("quantidade_galeria", "Galeria"),
    ("quantidade_salas", "Salas"),
    ("quantidade_externo", "Externo"),
)
ONLINE_FIELD = "quantidade_online"
VISITORS_COLUMN = "Quantidade Visitantes"
DEFAULT_GROUPS = ["1º Domingo", "2º Domingo", "3º Domingo", "4º Domingo", "5º Domingo"]
DEFAULT_SERVICE_TIMES = ["Manhã", "Noite"]


def _matches_group_names(value: object, allowed_groups: list[str]) -> bool:
    text = str(value).strip().lower()
    return any(candidate.lower() in text for candidate in allowed_groups)


def format_service_time(value: object) -> str:
    """Keep legacy values in the data while showing clear labels in the UI."""
    labels = {"1": "Manhã", "2": "Noite"}
    return labels.get(str(value).strip(), str(value))


def dataframe_to_excel(dataframe: pd.DataFrame) -> bytes:
    """Create an XLSX file in memory from the rows currently shown in the dashboard."""
    output = BytesIO()
    sheet_name = "Quantidades por setor"
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name=sheet_name)
        worksheet = writer.sheets[sheet_name]
        for column_index, column_name in enumerate(dataframe.columns, start=1):
            longest_value = max(len(str(column_name)), *(len(str(value)) for value in dataframe[column_name]))
            worksheet.column_dimensions[worksheet.cell(1, column_index).column_letter].width = min(longest_value + 2, 32)
    return output.getvalue()


st.set_page_config(page_title="Frequência IBE", page_icon="logo_transparent.png", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
    <style>
    .block-container { max-width: 1144px; padding-top: 3rem; padding-bottom: 3rem; }
    .ibe-hero { background: #4b5563; border-radius: 10px; color: white; padding: 1.35rem 1.25rem; margin-bottom: 0; }
    .ibe-hero h1 { margin: 0; font-size: clamp(1.6rem, 3vw, 2rem); line-height: 1.1; }
    .ibe-hero p { margin: .35rem 0 0; opacity: .88; font-size: 1rem; }
    .dashboard-title { margin: 2rem 0 2rem; font-size: clamp(1.4rem, 2.2vw, 1.7rem); font-weight: 700; color: #f0f0f0; text-align: center; }
    .st-key-ibe_header div[data-testid="stImage"] { margin-top: .45rem; }
    .metric-card { background: #27364b; border-radius: 14px; color: white; padding: 1.1rem; text-align: center; }
    .metric-card strong { display: block; font-size: 2rem; margin-top: .25rem; }
    .entry-total { background: #e8f3eb; border: 1px solid #9bbfa3; border-radius: 12px; padding: 1rem; font-size: 1.05rem; }
    @media (max-width: 768px) {
        .block-container { padding: 1rem .85rem 2rem; }
        .st-key-ibe_header div[data-testid="stHorizontalBlock"] { gap: .75rem; flex-wrap: nowrap; }
        .st-key-ibe_header div[data-testid="stColumn"]:first-child { flex: 0 0 130px; min-width: 130px; }
        .st-key-ibe_header div[data-testid="stColumn"]:last-child { flex: 1 1 auto; min-width: 0; }
        .st-key-ibe_header div[data-testid="stImage"] img { width: 128px !important; max-width: 128px; height: auto; }
        .st-key-ibe_header div[data-testid="stImage"] { margin-top: .25rem; }
        .st-key-ibe_header .ibe-hero { padding: .65rem .75rem; }
        .stButton > button { min-height: 3.1rem; font-size: 1.05rem; font-weight: 650; }
        div[data-baseweb="input"] input { font-size: 16px; }
    }

    /* Larger screens: improve spacing and readability on notebooks */
    @media (min-width: 1024px) {
        .block-container { max-width: 1144px; padding-top: 3rem; padding-bottom: 3.5rem; }
        .ibe-hero h1 { font-size: 2rem; }
        .dashboard-title { font-size: 1.7rem; }
    }
    /* Summary cards */
    .summary-cards { display:flex; gap:5.6rem; justify-content:center; flex-wrap:wrap; margin:0 0 1.1rem; }
    .summary-card { background: #6b7280; color: #ffffff; border-radius: 14px; padding: 1rem 1.25rem; min-width: 180px; display:flex; flex-direction:column; align-items:center; box-shadow: none; }
    .summary-card .label { font-size: 0.95rem; opacity: 0.95; margin-bottom: 0.25rem; }
    .summary-card .value { font-size: 2.2rem; font-weight: 700; line-height: 1; }
    @media (max-width: 768px) {
        .summary-cards { gap: 0.75rem; }
        .summary-card { min-width: 140px; padding: 0.75rem 1rem; }
        .summary-card .value { font-size: 1.6rem; }
    }
    /* Sidebar logo styling: remove any background and round corners */
    .stSidebar img, .sidebar .stImage img, div[data-testid="stImage"] img { background: transparent !important; border-radius: 8px !important; }
    .stSidebar .stImage, .sidebar .stImage { background: transparent !important; }
    /* Dashboard filter sidebar */
    [data-testid="stSidebar"] { min-width: 280px !important; max-width: 280px !important; background: #282932; border-right: 1px solid #30323b; }
    [data-testid="stSidebar"] > div:first-child { background: #282932; }
    [data-testid="stSidebarContent"] { padding: 1.45rem 1.2rem; overflow-y: auto; max-height: calc(100vh - 4rem); }
    [data-testid="stSidebar"] .filters-title { color: #f5f5f7; font-size: 1.28rem; font-weight: 700; line-height: 1; margin: .1rem 0 1rem; }
    [data-testid="stSidebar"] .filter-section { color: #f5f5f7; font-size: .9rem; font-weight: 700; margin: 0 0 1rem; }
    [data-testid="stSidebar"] label { color: #f2f2f4 !important; font-size: .78rem !important; margin-bottom: -.1rem; }
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
        min-height: 2.28rem; background: #0d1016; border: 1px solid #0d1016; border-radius: 7px;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] * { color: #f2f2f4; }
    [data-testid="stSidebar"] [data-baseweb="select"] svg { fill: #f2f2f4; }
    [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.filter-section) { margin-top: .95rem; }
    /* footer logo removed */
    @media (max-width: 768px) {
        [data-testid="stSidebar"] { min-width: min(230px, 82vw) !important; max-width: min(230px, 82vw) !important; }
        .st-key-sidebar_footer_logo { left: 55px; bottom: 0.8rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def initialize_entry_state() -> None:
    for field, _ in COUNT_FIELDS:
        st.session_state.setdefault(field, 0)
    st.session_state.setdefault(ONLINE_FIELD, 0)
    st.session_state.setdefault("entry_authenticated", False)
    st.session_state.setdefault("loaded_entry_identity", None)


def _show_header_current() -> None:
    with st.container(key="ibe_header"):
        left, right = st.columns([1, 5], vertical_alignment="center")
        with left:
            st.image("logo.png", width=110)
        with right:
            st.markdown(
                "<div class='ibe-hero'><h1>Frequência IBE</h1><p>Contagens dos cultos de domingo.</p></div>",
                unsafe_allow_html=True,
            )


def show_header() -> None:
    with st.container(key="ibe_header"):
        left, right = st.columns([2, 6], vertical_alignment="center")
        with left:
            st.image("logo.png", width=190)
        with right:
            st.markdown(
                "<div class='ibe-hero'><h1>Relatório de Frequência Cultos IBE</h1></div>",
                unsafe_allow_html=True,
            )


def sidebar_filter_group(
    dataframe: pd.DataFrame,
    title: str,
    key_prefix: str,
    date_label: str = "Domingo/data",
    filter_renove: bool = False,
    show_service_filter: bool = True,
    weekday_filter: int | None = None,
    exclude_service_values: list[str] | None = None,
    group_contains: str | None = None,
) -> dict[str, list]:
    df = dataframe.copy()
    df["Mês"] = df["Data"].dt.month
    df["Ano"] = df["Data"].dt.year
    if filter_renove:
        df = df[df["Grupo da recepção"].astype(str).str.contains("Renove", case=False, na=False)]
    else:
        df = df[~df["Grupo da recepção"].astype(str).str.contains("Renove", case=False, na=False)]
    if group_contains:
        df = df[df["Grupo da recepção"].astype(str).str.contains(group_contains, case=False, na=False)]
    if weekday_filter is not None:
        df = df[df["Data"].dt.weekday == weekday_filter]

    available_dates = sorted(df["Data"].dt.date.unique().tolist())

    st.sidebar.markdown(f"<div class='filters-title'>{title}</div>", unsafe_allow_html=True)
    selected_month = st.sidebar.multiselect(
        "Mês",
        ["Todos"] + sorted(df["Mês"].unique().tolist()),
        default=["Todos"],
        key=f"{key_prefix}_month",
    )
    selected_year = st.sidebar.multiselect(
        "Ano",
        ["Todos"] + sorted(df["Ano"].unique().tolist()),
        default=["Todos"],
        key=f"{key_prefix}_year",
    )
    selected_date = st.sidebar.multiselect(
        date_label,
        ["Todos"] + available_dates,
        default=["Todos"],
        format_func=lambda value: value.strftime("%d/%m/%Y") if value != "Todos" else value,
        key=f"{key_prefix}_date",
    )
    selected_service = ["Todos"]
    if show_service_filter:
        available_services = sorted(df["Horário do culto"].dropna().unique().tolist())
        if exclude_service_values:
            exclude_lower = [value.lower() for value in exclude_service_values]
            available_services = [
                value
                for value in available_services
                if str(value).lower() not in exclude_lower
            ]
        selected_service = st.sidebar.multiselect(
            "Horário do culto",
            ["Todos"] + available_services,
            default=["Todos"],
            format_func=lambda value: value if value == "Todos" else format_service_time(value),
            key=f"{key_prefix}_service",
        )
    return {
        "month": selected_month,
        "year": selected_year,
        "date": selected_date,
        "service": selected_service,
    }


def _show_dashboard_compact(dataframe: pd.DataFrame) -> None:
    st.markdown("<h2 class='dashboard-title'>Dashboard</h2>", unsafe_allow_html=True)
    if dataframe.empty:
        st.info("Ainda não há contagens. Use a área “Lançar contagem” para registrar a primeira.")
        return

    dataframe = dataframe.copy()
    dataframe["Mês"] = dataframe["Data"].dt.month
    dataframe["Ano"] = dataframe["Data"].dt.year
    # Sidebar logo + filters for compact view (keeps mobile friendly behaviour)
    # removed inline logo per request
    st.sidebar.markdown("**Filtros**")
    selected_year = st.sidebar.multiselect(
        "Ano",
        ["Todos"] + sorted(dataframe["Ano"].unique().tolist()),
        default=["Todos"],
        key="compact_year",
    )
    selected_service = st.sidebar.multiselect(
        "Horário do culto",
        ["Todos"] + sorted(dataframe["Horário do culto"].dropna().unique().tolist()),
        default=["Todos"],
        format_func=lambda value: value if value == "Todos" else format_service_time(value),
        key="compact_service",
    )

    filtered = dataframe.copy()
    # apply compact filters (support multiple selections)
    if not (not selected_year or "Todos" in selected_year):
        filtered = filtered[filtered["Ano"].isin(selected_year)]
    if not (not selected_service or "Todos" in selected_service):
        filtered = filtered[filtered["Horário do culto"].isin(selected_service)]

    total_present = int(filtered["Total"].sum())
    total_online = int(filtered["Quantidade On-line"].sum())
    total_visitors = int(filtered[VISITORS_COLUMN].sum()) if VISITORS_COLUMN in filtered.columns else 0
    number_services = len(filtered)
    latest_date = filtered["Data"].max().strftime("%d/%m/%Y")
    # Render summary cards (gray background, white text)
    st.markdown(
        f"""
        <div class="summary-cards">
          <div class="summary-card"><div class="label">Total presencial</div><div class="value">{total_present}</div></div>
          <div class="summary-card"><div class="label">Total on-line</div><div class="value">{total_online}</div></div>
          <div class="summary-card"><div class="label">Total visitantes</div><div class="value">{total_visitors}</div></div>
          <div class="summary-card"><div class="label">Última contagem</div><div class="value">{latest_date}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if filtered.empty:
        st.info("Nenhum lançamento encontrado para os filtros escolhidos.")
        return

    by_date = filtered.groupby("Data", as_index=False)["Total"].sum().sort_values("Data")
    chart = px.line(by_date, x="Data", y="Total", markers=True, title="Presença por data")
    chart.update_layout(margin=dict(l=0, r=0, t=80, b=0), yaxis_title="Pessoas", xaxis_title="")
    st.plotly_chart(chart, use_container_width=True, config={"displayModeBar": True, "responsive": True})

    with st.expander("Ver lançamentos", expanded=False):
        display = filtered.sort_values("Data", ascending=False).copy()
        display["Data"] = display["Data"].dt.strftime("%d/%m/%Y")
        st.dataframe(display, use_container_width=True, hide_index=True)


def show_dashboard(
    dataframe: pd.DataFrame,
    key_prefix: str = "dashboard",
    filter_group_contains: str | None = None,
    exclude_group_contains: str | None = None,
    weekday: int | None = None,
    exclude_weekday_from_charts: int | None = None,
    sidebar_filters: dict[str, list] | None = None,
    allowed_groups: list[str] | None = None,
    visitors_chart_mode: str = "data",
) -> None:
    """Restaura a análise completa do dashboard original usando dados do Supabase."""
    st.markdown("<h2 class='dashboard-title'>Dashboard de frequência</h2>", unsafe_allow_html=True)
    if dataframe.empty:
        st.info("Ainda não há contagens disponíveis.")
        return

    dataframe = dataframe.copy()
    dataframe["Mês"] = dataframe["Data"].dt.month
    dataframe["Ano"] = dataframe["Data"].dt.year
    if filter_group_contains:
        dataframe = dataframe[dataframe["Grupo da recepção"].astype(str).str.contains(filter_group_contains, case=False, na=False)]
    if weekday is not None:
        dataframe = dataframe[dataframe["Data"].dt.weekday == weekday]
    if allowed_groups:
        dataframe = dataframe[dataframe["Grupo da recepção"].apply(lambda value: _matches_group_names(value, allowed_groups))]

    if sidebar_filters is None:
        selected_month = ["Todos"]
        selected_year = ["Todos"]
        selected_date = ["Todos"]
        selected_service = ["Todos"]
    else:
        selected_month = sidebar_filters["month"]
        selected_year = sidebar_filters["year"]
        selected_date = sidebar_filters["date"]
        selected_service = sidebar_filters["service"]

    # footer logo removed
    filtered = dataframe.copy()
    if exclude_group_contains:
        filtered = filtered[
            ~filtered["Grupo da recepção"].astype(str).str.contains(exclude_group_contains, case=False, na=False)
        ]
    # apply dashboard filters (support multiple selections)
    if not (not selected_month or "Todos" in selected_month):
        filtered = filtered[filtered["Mês"].isin(selected_month)]
    if not (not selected_year or "Todos" in selected_year):
        filtered = filtered[filtered["Ano"].isin(selected_year)]
    if not (not selected_date or "Todos" in selected_date):
        filtered = filtered[filtered["Data"].dt.date.isin(selected_date)]
    if not (not selected_service or "Todos" in selected_service):
        filtered = filtered[filtered["Horário do culto"].isin(selected_service)]
    if filtered.empty:
        st.info("Nenhum lançamento encontrado para os filtros escolhidos.")
        return

    export_data = filtered.copy()
    chart_data = filtered.copy()
    if exclude_weekday_from_charts is not None:
        chart_data = chart_data[chart_data["Data"].dt.weekday != exclude_weekday_from_charts]

    total_present = int(chart_data["Total"].sum()) if not chart_data.empty else 0
    total_online = int(chart_data["Quantidade On-line"].sum()) if not chart_data.empty else 0
    total_visitors = int(chart_data[VISITORS_COLUMN].sum()) if not chart_data.empty and VISITORS_COLUMN in chart_data.columns else 0
    latest_date = chart_data["Data"].max().strftime("%d/%m/%Y") if not chart_data.empty else "-"
    # Render summary cards (gray background, white text)
    st.markdown(
        f"""
        <div class="summary-cards">
          <div class="summary-card"><div class="label">Total presencial</div><div class="value">{total_present}</div></div>
          <div class="summary-card"><div class="label">Total on-line</div><div class="value">{total_online}</div></div>
          <div class="summary-card"><div class="label">Total visitantes</div><div class="value">{total_visitors}</div></div>
          <div class="summary-card"><div class="label">Última contagem</div><div class="value">{latest_date}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if filter_group_contains or weekday is not None:
        by_date = filtered.groupby("Data", as_index=False)["Total"].sum().sort_values("Data")
        by_date["DataLabel"] = by_date["Data"].dt.strftime("%d/%m")
        title_suffix = filter_group_contains if filter_group_contains else "Quarta-feira"
        chart = px.line(
            by_date,
            x="DataLabel",
            y="Total",
            markers=True,
            title=f"Total de pessoas por data ({title_suffix})",
        )
        chart.update_layout(margin=dict(l=0, r=0, t=80, b=0), yaxis_title="Total de pessoas", xaxis_title="Data")
        st.plotly_chart(chart, use_container_width=True, config={"displayModeBar": True, "responsive": True})

        if VISITORS_COLUMN in chart_data.columns:
            visitors_by_date = (
                chart_data.groupby("Data", as_index=False)[VISITORS_COLUMN].sum().sort_values("Data")
            )
            visitors_by_date["DataLabel"] = visitors_by_date["Data"].dt.strftime("%d/%m")
            if not visitors_by_date.empty:
                visitors_chart = px.line(
                    visitors_by_date,
                    x="DataLabel",
                    y=VISITORS_COLUMN,
                    markers=True,
                    text=VISITORS_COLUMN,
                    title="Evolução de visitantes por data",
                )
                visitors_chart.update_traces(textposition="top center", cliponaxis=False)
                visitors_chart.update_layout(margin=dict(l=0, r=0, t=80, b=0), yaxis_title="Quantidade de visitantes", xaxis_title="Data")
                st.plotly_chart(visitors_chart, use_container_width=True, config={"displayModeBar": True, "responsive": True})

        st.subheader("Métricas")
        average_metric, highest_metric, lowest_metric, count_metric, visitors_metric = st.columns(5)
        average_metric.metric("Média por culto", f"{filtered['Total'].mean():.0f}")
        highest_metric.metric("Maior quantidade", int(filtered["Total"].max()))
        lowest_metric.metric("Menor quantidade", int(filtered["Total"].min()))
        count_metric.metric("Número de cultos", len(filtered))
        visitors_metric.metric(
            "Total de visitantes",
            int(filtered[VISITORS_COLUMN].sum()) if VISITORS_COLUMN in filtered.columns else 0,
        )
        return

    by_group = (
        chart_data.groupby("Grupo da recepção", as_index=False)["Total"].sum().sort_values("Grupo da recepção")
    )
    group_chart = px.line(
        by_group,
        x="Grupo da recepção",
        y="Total",
        markers=True,
        text="Total",
        title="Evolução do Total de Pessoas por Domingo",
    )
    group_chart.update_traces(textposition="top center", cliponaxis=False)
    group_chart.update_layout(margin=dict(l=0, r=0, t=80, b=0), yaxis_title="Total de pessoas")
    st.plotly_chart(group_chart, use_container_width=True, config={"displayModeBar": True, "responsive": True})

    online_by_group = (
        chart_data.groupby("Grupo da recepção", as_index=False)["Quantidade On-line"]
        .sum()
        .sort_values("Grupo da recepção")
    )
    online_chart = px.bar(
        online_by_group,
        x="Grupo da recepção",
        y="Quantidade On-line",
        text="Quantidade On-line",
        title="Pessoas on-line por domingo",
    )
    online_chart.update_traces(textposition="outside", cliponaxis=False)
    online_chart.update_layout(margin=dict(l=0, r=0, t=80, b=0), yaxis_title="Pessoas")
    st.plotly_chart(online_chart, use_container_width=True, config={"displayModeBar": True, "responsive": True})

    sector_labels = {
        "Quantidade Púlpito": "Púlpito",
        "Quantidade Cadeiras A": "Cadeiras A",
        "Quantidade Cadeiras B": "Cadeiras B",
        "Quantidade Cadeiras C": "Cadeiras C",
        "Quantidade Cadeiras D": "Cadeiras D",
        "Quantidade Galeria": "Galeria",
        "Quantidade Salas": "Salas",
        "Quantidade Externo": "Externo",
        "Quantidade On-line": "On-line",
    }
    sector_data = pd.DataFrame(
        {
            "Setor": list(sector_labels.values()),
            "Total": [int(filtered[column].sum()) for column in sector_labels],
        }
    )
    sector_chart = px.bar(
        sector_data,
        x="Setor",
        y="Total",
        text="Total",
        color="Setor",
        title="Distribuição de pessoas por setor",
    )
    sector_chart.update_traces(textposition="outside", cliponaxis=False)
    sector_chart.update_layout(showlegend=False, margin=dict(l=0, r=0, t=80, b=0), yaxis_title="Pessoas")
    st.plotly_chart(sector_chart, use_container_width=True, config={"displayModeBar": True, "responsive": True})

    by_service = chart_data.groupby("Horário do culto", as_index=False)["Total"].sum()
    service_labels = {
        "1": "Manhã",
        "manhã": "Manhã",
        "manha": "Manhã",
        "2": "Noite",
        "noite": "Noite",
    }
    by_service["Período do culto"] = by_service["Horário do culto"].map(
        lambda value: service_labels.get(str(value).strip().lower(), str(value))
    )
    service_chart = px.pie(
        by_service,
        names="Período do culto",
        values="Total",
        title="Total de pessoas por horário de culto (Manhã e Noite)",
        color="Período do culto",
        color_discrete_map={"Manhã": "#93c5fd", "Noite": "#1e3a8a"},
    )
    service_chart.update_layout(margin=dict(l=0, r=0, t=80, b=0))
    st.plotly_chart(service_chart, use_container_width=True, config={"displayModeBar": True, "responsive": True})

    st.subheader("Evolução por período")
    period_start_column, period_end_column = st.columns(2)
    with period_start_column:
        start_date = st.date_input(
            "Data inicial", value=filtered["Data"].min().date(), format="DD/MM/YYYY"
        )
    with period_end_column:
        end_date = st.date_input(
            "Data final", value=filtered["Data"].max().date(), format="DD/MM/YYYY"
        )
    period_filtered = filtered[
        (filtered["Data"].dt.date >= start_date) & (filtered["Data"].dt.date <= end_date)
    ]
    if period_filtered.empty:
        st.info("Nenhum lançamento encontrado no período selecionado.")
        return

    export_data = period_filtered.copy()
    by_date = chart_data[
        (chart_data["Data"].dt.date >= start_date) & (chart_data["Data"].dt.date <= end_date)
    ].groupby("Data", as_index=False)["Total"].sum().sort_values("Data")
    date_chart = px.line(
        by_date,
        x="Data",
        y="Total",
        markers=True,
        text="Total",
        title="Evolução do total de pessoas por data",
    )
    date_chart.update_traces(textposition="top center", cliponaxis=False)
    date_chart.update_layout(margin=dict(l=0, r=0, t=80, b=0), yaxis_title="Total de pessoas")
    st.plotly_chart(date_chart, use_container_width=True, config={"displayModeBar": True, "responsive": True})

    if VISITORS_COLUMN in chart_data.columns:
        if visitors_chart_mode == "group":
            visitors_by_group = (
                chart_data.groupby("Grupo da recepção", as_index=False)[VISITORS_COLUMN].sum().sort_values("Grupo da recepção")
            )
            if not visitors_by_group.empty:
                visitors_chart = px.line(
                    visitors_by_group,
                    x="Grupo da recepção",
                    y=VISITORS_COLUMN,
                    markers=True,
                    text=VISITORS_COLUMN,
                    title="Evolução de visitantes por grupo de recepção",
                )
                visitors_chart.update_traces(textposition="top center", cliponaxis=False)
                visitors_chart.update_layout(margin=dict(l=0, r=0, t=80, b=0), yaxis_title="Quantidade de visitantes", xaxis_title="Grupo de recepção")
                st.plotly_chart(visitors_chart, use_container_width=True, config={"displayModeBar": True, "responsive": True})
        else:
            visitors_by_date = (
                chart_data.groupby("Data", as_index=False)[VISITORS_COLUMN].sum().sort_values("Data")
            )
            visitors_by_date["DataLabel"] = visitors_by_date["Data"].dt.strftime("%d/%m")
            if not visitors_by_date.empty:
                visitors_chart = px.line(
                    visitors_by_date,
                    x="DataLabel",
                    y=VISITORS_COLUMN,
                    markers=True,
                    text=VISITORS_COLUMN,
                    title="Evolução de visitantes por data",
                )
                visitors_chart.update_traces(textposition="top center", cliponaxis=False)
                visitors_chart.update_layout(margin=dict(l=0, r=0, t=80, b=0), yaxis_title="Quantidade de visitantes", xaxis_title="Data")
                st.plotly_chart(visitors_chart, use_container_width=True, config={"displayModeBar": True, "responsive": True})

    st.subheader("Quantidades de pessoas por setor")
    display = period_filtered.sort_values("Data", ascending=False).copy()
    display["Data"] = display["Data"].dt.strftime("%d/%m/%Y")
    display_columns = [column for column in display.columns if column != VISITORS_COLUMN]
    if "Total" in display_columns:
        total_index = display_columns.index("Total")
        display_columns = display_columns[:total_index] + [VISITORS_COLUMN] + display_columns[total_index:]
    display = display[display_columns]
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.download_button(
        "Exportar para Excel",
        data=dataframe_to_excel(display),
        file_name="quantidades_por_setor.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.subheader("Métricas")
    average_metric, highest_metric, lowest_metric, count_metric, visitors_metric = st.columns(5)
    average_metric.metric("Média por culto", f"{period_filtered['Total'].mean():.0f}")
    highest_metric.metric("Maior quantidade", int(period_filtered["Total"].max()))
    lowest_metric.metric("Menor quantidade", int(period_filtered["Total"].min()))
    count_metric.metric("Número de cultos", len(period_filtered))
    visitors_metric.metric(
        "Total de visitantes",
        int(period_filtered[VISITORS_COLUMN].sum()) if VISITORS_COLUMN in period_filtered.columns else 0,
    )


def _entry_credentials_are_valid() -> bool:
    username = st.secrets.get("ENTRY_USERNAME")
    password = st.secrets.get("ENTRY_PASSWORD")
    if not username or not password:
        raise SupabaseConfigurationError(
            "Configure ENTRY_USERNAME e ENTRY_PASSWORD nos Secrets para liberar lançamentos."
        )
    return True


def _load_entry_if_needed(identity: tuple[str, str, str]) -> None:
    if st.session_state.loaded_entry_identity == identity:
        return
    entry = get_existing_count(st.secrets, date.fromisoformat(identity[0]), identity[1], identity[2])
    for field, _ in COUNT_FIELDS:
        st.session_state[field] = int((entry or {}).get(field, 0))
    st.session_state[ONLINE_FIELD] = int((entry or {}).get(ONLINE_FIELD, 0))
    st.session_state.loaded_entry_identity = identity


def show_entry_form(dataframe: pd.DataFrame) -> None:
    st.subheader("Lançar contagem")
    if not write_configuration_is_available(st.secrets):
        st.info(
            "Lançamento temporariamente indisponível. "
            "A configuração para salvar novas contagens será concluída em breve."
        )
        return

    try:
        _entry_credentials_are_valid()
    except SupabaseConfigurationError as error:
        st.error(str(error))
        return

    if not st.session_state.entry_authenticated:
        st.caption("Acesso restrito à equipe de recepção.")
        with st.form("entry_login"):
            username = st.text_input("Login", autocomplete="username")
            password = st.text_input("Senha", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Entrar", use_container_width=True)
        if submitted:
            if username == st.secrets["ENTRY_USERNAME"] and password == st.secrets["ENTRY_PASSWORD"]:
                st.session_state.entry_authenticated = True
                st.rerun()
            st.error("Login ou senha incorretos.")
        return

    top_left, top_right = st.columns([4, 1], vertical_alignment="bottom")
    with top_left:
        st.caption("Preencha e confira o total antes de salvar.")
    with top_right:
        if st.button("Sair", use_container_width=True):
            st.session_state.entry_authenticated = False
            st.rerun()

    known_groups = sorted(set(dataframe.get("Grupo da recepção", pd.Series(dtype=str)).dropna()) | set(DEFAULT_GROUPS))
    known_times = sorted(set(dataframe.get("Horário do culto", pd.Series(dtype=str)).dropna()) | set(DEFAULT_SERVICE_TIMES))
    count_date = st.date_input("Data do culto", value=date.today(), format="DD/MM/YYYY")
    group = st.selectbox("Grupo da recepção", known_groups)
    service_time = st.selectbox("Horário do culto", known_times)
    identity = (count_date.isoformat(), group, service_time)

    try:
        _load_entry_if_needed(identity)
    except Exception:
        st.error("Não foi possível carregar esta contagem. Verifique a conexão e tente novamente.")
        return

    st.divider()
    st.caption("Contagem presencial")
    for field, label in COUNT_FIELDS:
        st.number_input(label, min_value=0, step=1, key=field)
    st.number_input("On-line", min_value=0, step=1, key=ONLINE_FIELD)

    total_present = sum(int(st.session_state[field]) for field, _ in COUNT_FIELDS)
    st.markdown(f"<div class='entry-total'><strong>Total presencial: {total_present}</strong><br>Calculado automaticamente pela soma dos setores.</div>", unsafe_allow_html=True)

    if st.button("Salvar contagem", type="primary", use_container_width=True):
        payload = {
            "data": count_date.isoformat(),
            "grupo_recepcao": group,
            "horario_culto": service_time,
            **{field: int(st.session_state[field]) for field, _ in COUNT_FIELDS},
            ONLINE_FIELD: int(st.session_state[ONLINE_FIELD]),
        }
        try:
            save_count(st.secrets, payload)
            st.success(f"Contagem de {group} — {service_time} salva com sucesso. Total presencial: {total_present}.")
        except SupabaseConfigurationError as error:
            st.error(str(error))
        except Exception:
            st.error("Não foi possível salvar agora. Confira a conexão e tente novamente.")


initialize_entry_state()
show_header()

try:
    data = get_dashboard_data(st.secrets)
except SupabaseConfigurationError as error:
    st.error(str(error))
    st.info("Use .streamlit/secrets.toml.example como modelo para a configuração local.")
    st.stop()
except (SupabaseDataError, Exception):
    st.error("Não foi possível consultar as contagens. Verifique a configuração e as permissões do Supabase.")
    st.stop()

domingo_filters = sidebar_filter_group(
    data,
    title="Filtro Culto Domingos:",
    key_prefix="domingo",
    date_label="Domingo/data",
    filter_renove=False,
    exclude_service_values=["Oração", "Cafofo"],
)
renove_filters = sidebar_filter_group(
    data,
    title="Filtro Culto Renove:",
    key_prefix="renove",
    date_label="Data",
    filter_renove=True,
    show_service_filter=False,
)
quarta_filters = sidebar_filter_group(
    data,
    title="Filtro Culto de Quarta-feira:",
    key_prefix="quarta",
    date_label="Data",
    filter_renove=False,
    show_service_filter=False,
    weekday_filter=2,
)
cafofo_filters = sidebar_filter_group(
    data,
    title="Filtro Culto Cafofo:",
    key_prefix="cafofo",
    date_label="Data",
    filter_renove=False,
    show_service_filter=False,
    group_contains="Cafofo",
)

default_filters = {
    "month": ["Todos"],
    "year": ["Todos"],
    "date": ["Todos"],
    "service": ["Todos"],
}

tabs = st.tabs(["Cultos de Domingo", "Cultos Renove", "Cultos de Quarta-feira", "Cultos do Cafofo"])

with tabs[0]:
    show_dashboard(
        data,
        key_prefix="domingo",
        exclude_group_contains="Renove|Cafofo",
        exclude_weekday_from_charts=2,
        sidebar_filters=domingo_filters,
        allowed_groups=DEFAULT_GROUPS,
        visitors_chart_mode="group",
    )

with tabs[1]:
    show_dashboard(
        data,
        key_prefix="renove",
        filter_group_contains="Renove",
        sidebar_filters=renove_filters,
        visitors_chart_mode="data",
    )

with tabs[2]:
    show_dashboard(
        data,
        key_prefix="quarta",
        weekday=2,
        sidebar_filters=quarta_filters,
        visitors_chart_mode="data",
    )

with tabs[3]:
    show_dashboard(
        data,
        key_prefix="cafofo",
        filter_group_contains="Cafofo",
        sidebar_filters=cafofo_filters,
        visitors_chart_mode="data",
    )
    
