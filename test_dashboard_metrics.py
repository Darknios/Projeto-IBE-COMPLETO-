import pandas as pd

from dashboard_metrics import sector_average_by_service
from IBE import sidebar_filter_group


def test_sidebar_filter_group_can_hide_sector_filter():
    data = pd.DataFrame(
        {
            "Data": ["2024-01-21", "2024-01-28"],
            "Grupo da recepção": ["Renove", "Renove"],
            "Horário do culto": ["Manhã", "Noite"],
        }
    )

    result = sidebar_filter_group(
        data,
        title="Filtro Culto Renove:",
        key_prefix="renove",
        date_label="Data",
        filter_renove=True,
        show_service_filter=False,
        show_sector_filter=False,
        render_in_tab=True,
    )

    assert result["sector"] == ["Todos"]


def test_sector_average_by_service_filters_selected_sector():
    data = pd.DataFrame(
        {
            "Horário do culto": ["Manhã", "Noite", "Manhã", "Noite"],
            "Total": [100, 200, 300, 400],
            "Quantidade Púlpito": [10, 20, 30, 40],
            "Quantidade Cadeiras A": [5, 15, 25, 35],
            "Quantidade On-line": [7, 9, 11, 13],
            "Quantidade Visitantes": [2, 4, 6, 8],
        }
    )

    result = sector_average_by_service(data, sector="Púlpito")

    assert list(result["Período do culto"]) == ["Manhã", "Noite"]
    assert list(result["Valor"]) == [20.0, 30.0]


def test_sector_average_by_service_all_sectors_uses_total():
    data = pd.DataFrame(
        {
            "Horário do culto": ["Manhã", "Noite"],
            "Total": [100, 200],
        }
    )

    result = sector_average_by_service(data, sector="Todos")

    assert list(result["Período do culto"]) == ["Manhã", "Noite"]
    assert list(result["Valor"]) == [100.0, 200.0]
