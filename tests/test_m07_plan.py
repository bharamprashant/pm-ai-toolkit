import csv
import importlib.util
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "modules" / "m07_agentic_pmo" / "jira"
spec = importlib.util.spec_from_file_location("make_import", P / "make_import.py")
mi = importlib.util.module_from_spec(spec); spec.loader.exec_module(mi)


def test_plan_is_valid():
    assert mi.validate() == []


def test_cycle_is_detected():
    original = list(mi.S)
    try:
        # make 101 depend on 102 (102 already depends on 101) -> cycle
        mi.S[0] = mi.S[0][:9] + ([102],) + mi.S[0][10:]
        assert any("cycle" in e for e in mi.validate())
    finally:
        mi.S[:] = original


def test_csv_is_rectangular_and_links_point_to_real_ids():
    rows = mi.build_rows()
    assert len({len(r) for r in rows}) == 1
    ids = {str(r[0]) for r in rows[1:]}
    for r in rows[1:]:
        for cell in r[12:]:
            assert cell == "" or str(cell) in ids
