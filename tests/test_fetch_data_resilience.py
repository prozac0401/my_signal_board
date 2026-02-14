import ast
import io
import re
import html as html_lib
import types
from pathlib import Path

import pandas as pd


def load_fetch_data_functions():
    src = Path("fetch_data.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mod = types.ModuleType("fetch_data_partial")
    mod.pd = pd
    mod.io = io
    mod.re = re
    mod.html_lib = html_lib
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in {
            "empty_series",
            "to_datetime_index",
            "safe_resample",
            "fetch_buy_index",
            "_extract_table_rows",
        }:
            code = ast.Module([node], [])
            exec(compile(code, filename="fetch_data.py", mode="exec"), mod.__dict__)
    return mod


def test_safe_resample_handles_empty_rangeindex():
    mod = load_fetch_data_functions()
    s = pd.Series(dtype=float, name="M2")
    out = mod.safe_resample(s, "D", "linear", name="M2_D")
    assert out.empty
    assert isinstance(out.index, pd.DatetimeIndex)
    assert out.name == "M2_D"


def test_fetch_buy_index_falls_back_without_lxml(monkeypatch):
    mod = load_fetch_data_functions()

    class DummyResponse:
        text = """
        <table>
            <tr><th>날짜</th><th>지수</th></tr>
            <tr><td>2024-01-01</td><td>100.1</td></tr>
            <tr><td>2024-01-08</td><td>101.2</td></tr>
        </table>
        """

    class DummyRequests:
        @staticmethod
        def get(url, timeout=30):
            return DummyResponse()

    def fake_read_html(*args, **kwargs):
        raise ImportError("Missing optional dependency 'lxml'.")

    mod.requests = DummyRequests()
    monkeypatch.setattr(pd, "read_html", fake_read_html)

    out = mod.fetch_buy_index()
    assert list(out.index) == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-08")]
    assert out.name == "BuyIndex"
    assert out.iloc[-1] == 101.2
