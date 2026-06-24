import os

import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from dash import dash_table, dcc, html
from dash.dependencies import Input, Output

app = dash.Dash(__name__)
server = app.server

PREDICTIONS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "predictions.csv",
)

_DARK = "#0f172a"
_CARD = "#1e293b"
_TEAL = "#14b8a6"
_BORDER = "#334155"
_TEAL_BRIGHT = "#2dd4bf"


def fetch_data() -> pd.DataFrame:
    try:
        response = requests.get("http://twin-api:5000/data", timeout=2)
        return pd.DataFrame(response.json()) if response.status_code == 200 else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def read_predictions() -> pd.DataFrame:
    try:
        df = pd.read_csv(PREDICTIONS_PATH)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception:
        return pd.DataFrame()


def detect_anomalies(df: pd.DataFrame) -> list:
    if df.empty:
        return []
    latest = df.iloc[0]
    anomalies = []
    if latest["temperature"] > 87:
        anomalies.append(f"⚠️ High temperature: {latest['temperature']:.1f}°C")
    if latest["vibration"] > 4.1:
        anomalies.append(f"⚠️ High vibration: {latest['vibration']:.2f} g")
    if latest["pressure"] > 91:
        anomalies.append(f"⚠️ High pressure: {latest['pressure']:.1f} bar")
    return anomalies if anomalies else ["✅ All systems normal"]


def _card(children, extra_style=None):
    style = {
        "background": f"linear-gradient(135deg, {_DARK} 0%, {_CARD} 100%)",
        "padding": "25px",
        "borderRadius": "16px",
        "border": f"1px solid {_BORDER}",
        "marginTop": "25px",
    }
    if extra_style:
        style.update(extra_style)
    return html.Div(children, style=style)


app.layout = html.Div([
    html.Div([
        html.H1("🏭 Digital Twin — Industrial Monitoring System",
                style={"textAlign": "center", "marginBottom": "10px",
                       "color": _TEAL, "fontSize": "2.5rem", "fontWeight": "700"}),
        html.P("Real-time sensor data · anomaly detection · failure predictions",
               style={"textAlign": "center", "color": "#64748b",
                      "marginBottom": "30px", "fontSize": "1.1rem"}),
    ]),

    # ── KPI cards ─────────────────────────────────────────────────────────────
    html.Div([
        html.Div([
            html.Div("🌡️", style={"fontSize": "2rem"}),
            html.Div("Temperature", style={"fontSize": "0.9rem", "color": "#94a3b8", "marginTop": "5px"}),
            html.Div(id="temp-value", children="--°C",
                     style={"fontSize": "1.8rem", "fontWeight": "700", "color": _TEAL, "marginTop": "8px"}),
        ], style={"background": f"linear-gradient(135deg, {_DARK} 0%, {_CARD} 100%)",
                  "padding": "25px", "borderRadius": "16px", "textAlign": "center",
                  "border": f"1px solid {_TEAL_BRIGHT}"}),

        html.Div([
            html.Div("📊", style={"fontSize": "2rem"}),
            html.Div("Vibration", style={"fontSize": "0.9rem", "color": "#94a3b8", "marginTop": "5px"}),
            html.Div(id="vib-value", children="-- g",
                     style={"fontSize": "1.8rem", "fontWeight": "700", "color": _TEAL, "marginTop": "8px"}),
        ], style={"background": f"linear-gradient(135deg, {_DARK} 0%, {_CARD} 100%)",
                  "padding": "25px", "borderRadius": "16px", "textAlign": "center",
                  "border": f"1px solid {_TEAL_BRIGHT}"}),

        html.Div([
            html.Div("⚡", style={"fontSize": "2rem"}),
            html.Div("Pressure", style={"fontSize": "0.9rem", "color": "#94a3b8", "marginTop": "5px"}),
            html.Div(id="press-value", children="-- bar",
                     style={"fontSize": "1.8rem", "fontWeight": "700", "color": _TEAL, "marginTop": "8px"}),
        ], style={"background": f"linear-gradient(135deg, {_DARK} 0%, {_CARD} 100%)",
                  "padding": "25px", "borderRadius": "16px", "textAlign": "center",
                  "border": f"1px solid {_TEAL_BRIGHT}"}),

        html.Div([
            html.Div("🔔", style={"fontSize": "2rem"}),
            html.Div("System Status", style={"fontSize": "0.9rem", "color": "#94a3b8", "marginTop": "5px"}),
            html.Div(id="status-value", children="Monitoring…",
                     style={"fontSize": "1.1rem", "fontWeight": "600", "color": _TEAL, "marginTop": "8px"}),
        ], style={"background": f"linear-gradient(135deg, {_DARK} 0%, {_CARD} 100%)",
                  "padding": "25px", "borderRadius": "16px", "textAlign": "center",
                  "border": f"1px solid {_TEAL_BRIGHT}"}),
    ], style={"display": "grid", "gridTemplateColumns": "repeat(4, 1fr)",
              "gap": "20px", "marginBottom": "25px"}),

    # ── Sensor trend chart ────────────────────────────────────────────────────
    _card([
        html.H3("📈 Sensor Trends Over Time",
                style={"color": _TEAL, "marginBottom": "20px", "fontSize": "1.4rem"}),
        dcc.Graph(id="sensor-graph", style={"height": "400px"}),
    ], {"marginTop": "0"}),

    # ── Anomaly alerts ────────────────────────────────────────────────────────
    _card([
        html.H3("🚨 Sensor-Health Anomalies",
                style={"color": _TEAL, "marginBottom": "15px", "fontSize": "1.2rem"}),
        html.Div(id="anomaly-alerts", children=["Initializing…"],
                 style={"fontSize": "0.95rem", "lineHeight": "1.8"}),
    ]),

    # ── Failure predictions panel ─────────────────────────────────────────────
    _card([
        html.H3("🤖 Failure Predictions (pipeline)",
                style={"color": _TEAL, "marginBottom": "20px", "fontSize": "1.4rem"}),
        html.Div(id="predictions-status",
                 style={"color": "#64748b", "fontSize": "0.9rem", "marginBottom": "10px"}),
        dcc.Graph(id="predictions-graph", style={"height": "300px"}),
    ]),

    # ── Recent readings table ─────────────────────────────────────────────────
    _card([
        html.H3("📋 Recent Sensor Readings",
                style={"color": _TEAL, "marginBottom": "20px", "fontSize": "1.4rem"}),
        dash_table.DataTable(
            id="sensor-table",
            columns=[{"name": c, "id": c}
                     for c in ["timestamp", "temperature", "vibration", "pressure"]],
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "center", "padding": "14px",
                        "backgroundColor": _CARD, "color": "#e2e8f0",
                        "border": f"1px solid {_BORDER}", "fontSize": "13px"},
            style_header={"backgroundColor": _DARK, "fontWeight": "700",
                          "color": _TEAL, "fontSize": "14px",
                          "border": f"1px solid {_TEAL_BRIGHT}"},
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": _DARK}
            ],
            page_size=5,
        ),
    ]),

    dcc.Interval(id="interval-component", interval=2000, n_intervals=0),
], style={"padding": "40px 60px", "backgroundColor": "#020617",
          "minHeight": "100vh", "maxWidth": "100%", "overflow": "hidden"})


@app.callback(
    [
        Output("sensor-table", "data"),
        Output("sensor-graph", "figure"),
        Output("temp-value", "children"),
        Output("vib-value", "children"),
        Output("press-value", "children"),
        Output("status-value", "children"),
        Output("anomaly-alerts", "children"),
        Output("predictions-graph", "figure"),
        Output("predictions-status", "children"),
    ],
    [Input("interval-component", "n_intervals")],
)
def update_dashboard(n):
    _layout = dict(
        plot_bgcolor=_DARK, paper_bgcolor=_DARK,
        font={"color": "#e2e8f0"},
        xaxis={"gridcolor": _BORDER, "title": ""},
        yaxis={"gridcolor": _BORDER},
        margin={"l": 50, "r": 20, "t": 20, "b": 50},
    )

    # ── Sensor panel ──────────────────────────────────────────────────────────
    df = fetch_data()
    if df.empty:
        empty_fig = go.Figure(layout=_layout)
        return [], empty_fig, "--°C", "-- g", "-- bar", "No Data", \
               ["Waiting for data…"], empty_fig, "No predictions yet."

    latest = df.iloc[0]
    temp_val  = f"{latest['temperature']:.1f}°C"
    vib_val   = f"{latest['vibration']:.2f} g"
    press_val = f"{latest['pressure']:.1f} bar"

    anomalies = detect_anomalies(df)
    status = "⚠️ ALERT" if any("⚠️" in a for a in anomalies) else "✅ Normal"

    sensor_fig = px.line(df, x="timestamp", y=["temperature", "vibration", "pressure"],
                         markers=True)
    sensor_fig.update_layout(**_layout,
                             legend={"bgcolor": _CARD, "bordercolor": _BORDER, "borderwidth": 1})
    sensor_fig.update_traces(line={"width": 3})

    alert_divs = [
        html.Div(a, style={"marginBottom": "8px",
                           "color": "#ef4444" if "⚠️" in a else "#22c55e"})
        for a in anomalies
    ]

    # ── Predictions panel ─────────────────────────────────────────────────────
    pred_df = read_predictions()
    if pred_df.empty or "confidence" not in pred_df.columns:
        pred_fig = go.Figure(layout=_layout)
        pred_fig.add_annotation(text="No predictions yet — pipeline not running",
                                xref="paper", yref="paper", x=0.5, y=0.5,
                                showarrow=False, font={"color": "#64748b", "size": 14})
        pred_status = "Waiting for pipeline/api to write predictions.csv…"
    else:
        x_col = "timestamp" if "timestamp" in pred_df.columns else pred_df.index
        pred_fig = go.Figure(layout=_layout)
        pred_fig.add_trace(go.Scatter(
            x=pred_df[x_col] if "timestamp" in pred_df.columns else list(range(len(pred_df))),
            y=pred_df["confidence"],
            mode="lines+markers",
            line={"color": _TEAL, "width": 2},
            name="confidence",
        ))
        if "anomaly" in pred_df.columns:
            flagged = pred_df[pred_df["anomaly"] == True]
            pred_fig.add_trace(go.Scatter(
                x=flagged[x_col] if "timestamp" in pred_df.columns else flagged.index,
                y=flagged["confidence"],
                mode="markers",
                marker={"color": "#ef4444", "size": 10, "symbol": "x"},
                name="anomaly flagged",
            ))
        pred_fig.update_layout(yaxis_title="Failure confidence",
                               legend={"bgcolor": _CARD, "bordercolor": _BORDER, "borderwidth": 1})
        n_flagged = int(pred_df["anomaly"].sum()) if "anomaly" in pred_df.columns else 0
        pred_status = f"{len(pred_df)} predictions loaded · {n_flagged} anomalies flagged"

    return (df.to_dict("records"), sensor_fig, temp_val, vib_val, press_val,
            status, alert_divs, pred_fig, pred_status)


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=8050)
