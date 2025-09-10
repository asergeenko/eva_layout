import pytest

from excel_loader import load_excel_file, parse_orders_from_excel


def test_empty_excel_file():
    with pytest.raises(ValueError):
        df = load_excel_file(open("tests/empty_excel_file.xlsx","rb").read())
        orders = parse_orders_from_excel(df)