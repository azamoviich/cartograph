"""HTML report rendering had no test coverage before milestone 6's viewer
refactor split it into two modes sharing one template — lock both.
"""

from __future__ import annotations

from cartograph.report.html import build_html_report, build_static_viewer

_FAKE_REPORT = {
    "summary": {"file_count": 2, "internal_edge_count": 1, "unresolved_ratio": 0.0, "cluster_count": 1},
    "nodes": [
        {"module": "pkg.a", "path": "pkg/a.py", "loc": 10, "symbols": ["Foo"], "external_deps": [], "unresolved": [], "cluster": "a"},
        {"module": "pkg.b", "path": "pkg/b.py", "loc": 5, "symbols": ["Bar"], "external_deps": [], "unresolved": [], "cluster": "a"},
    ],
    "edges": [{"src": "pkg.a", "dst": "pkg.b"}],
    "risk": {
        "god_files": [], "cycles": {"scc_count": 0, "scc_sizes": [], "cycles": [], "truncated_sccs": 0},
        "ownership_concentration": [], "untested_hot_paths": [], "sdp_violations": [], "churn_hotspots": [],
    },
}


def test_embedded_report_contains_inline_json_and_no_fetch():
    html = build_html_report(_FAKE_REPORT, title="demo/repo")
    assert 'id="report-data"' in html
    assert '"pkg.a"' in html
    assert "demo/repo" in html
    assert "fetch(reportUrl)" not in html


def test_static_viewer_has_no_embedded_data_and_fetches_by_query_param():
    html = build_static_viewer()
    assert 'id="report-data"' not in html
    assert '"pkg.a"' not in html
    assert "fetch(reportUrl)" in html
    assert "params.get('report')" in html


def test_html_escapes_script_close_tag_in_data():
    report = dict(_FAKE_REPORT)
    report["nodes"] = [dict(_FAKE_REPORT["nodes"][0], path="pkg/</script><script>alert(1)</script>.py")]
    html = build_html_report(report)
    assert "<script>alert(1)</script>" not in html
