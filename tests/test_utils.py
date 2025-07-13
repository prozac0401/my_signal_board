import ast
import types
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


def load_functions():
    """Load scaler and add_monthly_guides from app.py without running the app."""
    src = Path("app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    module = types.ModuleType("app_partial")
    # provide pandas and plotly modules expected by the functions
    module.pd = pd
    module.go = go
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in {"scaler", "add_monthly_guides"}:
            code = ast.Module([node], [])
            exec(compile(code, filename="app.py", mode="exec"), module.__dict__)
    return module


def test_scaler_constant_returns_zeros():
    mod = load_functions()
    mod.scale_mode = "표준화"
    s = pd.Series([1, 1, 1])
    result = mod.scaler(s)
    assert isinstance(result, pd.Series)
    assert (result == 0).all()


def test_add_monthly_guides_shape_count():
    mod = load_functions()
    fig = go.Figure()
    start = pd.Timestamp("2021-01-01")
    end = pd.Timestamp("2021-04-30")
    mod.add_monthly_guides(fig, start, end)
    assert len(fig.layout.shapes) == 4

