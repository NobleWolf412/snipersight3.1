from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "static"


def text(name):
    return (STATIC / name).read_text(encoding="utf-8")


def test_signal_map_never_totals_alignment_or_calls_it_confidence():
    source = text("signal-map.js").lower()
    assert "confidence" not in source
    assert ".reduce(" not in source
    assert "research observation — did not affect this setup" in source
    for state in ("aligned", "opposed", "neutral", "missing", "stale",
                  "not_applicable"):
        assert state in source


def test_results_uses_signals_label_and_locked_research_heading():
    shell = text("shell.html")
    cards = text("factor-evidence.js")
    assert 'data-view="factors" aria-pressed="false">Signals</button>' in shell
    assert "Signal research — which readings have earned trust?" in cards
    assert "Used in trading: No" in cards
    assert "Other patterns observed" in cards
    assert "promotion" not in cards.lower()


def test_research_preset_is_separate_and_clean_trade_do_not_enable_it():
    source = text("chart.js")
    assert "research:   ['zones', 'orderblocks', 'sequences', 'divergence'" in source
    assert "clean:      []" in source
    assert "trade:      ['zones']" in source
    assert "stochrsi: false, openinterest: false" in source


def test_signal_map_and_pane_resize_are_keyboard_accessible():
    signal_map = text("signal-map.js")
    shell = text("shell.html")
    chart = text("research-chart.js")
    assert 'role="tab"' in signal_map and "ArrowRight" in signal_map
    assert 'role="separator" tabindex="0"' in shell
    assert "ArrowUp" in chart and "ArrowDown" in chart
    assert "signal-row-toggle" in signal_map
    assert "showNotice:false" in signal_map
    assert 'aria-valuenow="126"' in shell


def test_primary_cockpit_reuses_signal_research_contracts():
    html = text("cockpit.html")
    app = text("cockpit/app.js")
    assert '/static/signal-map.js' in html
    assert "signalMap.disclosure" in app
    assert "signalMap.trade" in app
    assert "Signal research — which readings have earned trust?" in app
    assert "Used in trading: No" in app
    assert "Open-interest feed" in app
    assert "Collecting only — unused by trading." in app


def test_primary_chart_research_preset_is_opt_in_and_resizable():
    app = text("cockpit/app.js")
    assert 'data-chart-preset="clean"' in app
    assert 'data-chart-preset="trade"' in app
    assert 'data-chart-preset="research"' in app
    assert "const isResearch=preset==='research'" in app
    assert "enabled=new Set(isResearch?researchKeys:[])" in app
    assert "ArrowUp" in app and "ArrowDown" in app
    assert "onpointerdown" in app
    assert "research-ob" in app and "svgNode('rect'" in app
    assert "research-sequence" in app and "svgNode('polyline'" in app
    assert "data-sequence-state" in app and "summary.dataset.sequenceMarkers" in app
    assert "chart!==chartRequest" in app
    assert "Value ${last.value}" in app
    assert "regular divergence lines (solid teal)" in app
    assert "aria-valuemin" in app and "aria-valuetext" in app


def test_sparse_research_panes_follow_the_price_window_without_driving_it():
    cockpit = text("cockpit/app.js")
    classic = text("research-chart.js")
    assert "The price chart is the sole time-window controller" in cockpit
    assert "mainChart.timeScale().subscribeVisibleTimeRangeChange(rangeListener)" in cockpit
    assert "handleScroll:false,handleScale:false" in cockpit
    assert "research-ob-label" in cockpit and "OB ${bull?'↑':'↓'}" in cockpit
    assert "B→OB · partial" in cockpit and "partial means no sweep recorded" in cockpit
    assert "if(main) main.timeScale().subscribeVisibleTimeRangeChange" in classic
    assert "handleScale:false, handleScroll:false" in classic
    assert "research-ob-label" in classic and "OB ${bull?'↑':'↓'}" in classic
    assert "B→OB · partial" in classic and "sweep unavailable" in classic
