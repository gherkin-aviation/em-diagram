import dash
from dash import dcc, html, Input, Output, State, ctx
from dash.dependencies import ALL
import plotly.graph_objects as go
import numpy as np
import webbrowser
import threading
from edit_aircraft_page import edit_aircraft_layout
import copy 
from dash import ctx
from dash.exceptions import PreventUpdate
from core.calculations import (
    compute_dynamic_pressure,
    compute_cl,
    compute_cd,
    compute_drag,
    compute_thrust_available,
    compute_ps_knots_per_sec,
)
import time

# Toggle for console debug logging
DEBUG_LOG = False  # set to False before deploying to Render


def dprint(*args, **kwargs):
    """Debug print that can be globally toggled."""
    if DEBUG_LOG:
        print(*args, **kwargs)



# ✅ Load aircraft data FIRST
import sys
import os
import json
from itertools import zip_longest

def load_aircraft_data_from_folder():
    folder_path = os.path.join(os.path.dirname(__file__), "aircraft_data")
    aircraft_data = {}
    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            filepath = os.path.join(folder_path, filename)
            with open(filepath, "r") as f:
                try:
                    data = json.load(f)
                    name = os.path.splitext(filename)[0].replace("_", " ")
                    aircraft_data[name] = data
                except Exception as e:
                    dprint(f"[ERROR] Failed to load {filename}: {e}")
    return aircraft_data

class DynamicAircraftData:
    def __getitem__(self, key):
        return load_aircraft_data_from_folder()[key]

    def get(self, key, default=None):
        return load_aircraft_data_from_folder().get(key, default)

    def __contains__(self, key):
        return key in load_aircraft_data_from_folder()

aircraft_data = DynamicAircraftData()

def resource_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return filename

def extract_vmca_value(ac, preferred="clean_up"):
    vmca = ac.get("single_engine_limits", {}).get("Vmca", {})
    if isinstance(vmca, dict):
        return vmca.get(preferred) or next(iter(vmca.values()), None)
    return vmca if isinstance(vmca, (int, float)) else None

# ✅ Initialize Dash app
app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server




app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Energy Maneuverability Diagram Generator</title>
        <meta name="description" content="Interactive Energy Maneuverability Diagrams for general aviation, multi-engine, aerobatic, and military aircraft. Analyze Ps contours, Vmc dynamics, Vyse, G-limits, stall margins, and more.">
        <meta name="keywords" content="EM Diagram, Energy Maneuverability, Aircraft Performance, General Aviation, Vmc, Vyse, Vxse, Ps Contours, G-Limits, Stall Speed, Spin Awareness, Stall Awareness, Turn Rate, Flight Envelope, FAA Training, Multi-Engine Safety, Aerobatic Flight, FAA Flight Training, Maneuvering Performance, AOB, Angle of Bank, Aviation Education, Pilot Tools, Military Trainer Aircraft, FAA Checkride Prep, Performance Planning, General Aviation Safety">
        <meta name="robots" content="index, follow">
        <meta name="author" content="AEROEDGE">
        <meta name="google-site-verification" content="ukKfZyRJS6up-cpev6piffO5YyKPIhS-DdgnRgBUBig" />
        {%favicon%}
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""

app.layout = html.Div([
    dcc.Location(id="url"),
    dcc.Store(id="aircraft-data-store"),
    dcc.Store(id="last-saved-aircraft"),
    dcc.Store(id="stored-total-weight"),
    dcc.Store(id="screen-width"),
    html.Div(id="page-content"),
    dcc.Download(id="download-aircraft")
    
])

# Define clientside JS callback to detect screen width
app.clientside_callback(
    """
    function(_) {
        return window.innerWidth;
    }
    """,
    Output("screen-width", "data"),
    Input("url", "pathname")
)


import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, ctx, ALL

# === Redesigned Layout with Original IDs Preserved ===
def em_diagram_layout(is_mobile=False):
    if is_mobile:
        return mobile_layout()
    else:
        return desktop_layout()
def desktop_layout():
    return html.Div([
            # Header Row (centered banner logo inside a fixed-height header)
            html.Div([
                html.Div([
                    html.A(
                        html.Img(src="/assets/logo.png", className="banner-logo"),
                        href="https://www.flyaeroedge.com",  # or "/" if internal routing
                        style={"textDecoration": "none"}
                    )
                ], className="banner-inner")
            ], className="banner-header"),

            # Disclaimer Banner for EM Diagram Page
            html.Div(
                "⚠️ This tool visualizes performance data based on public or user-submitted values and is for educational use only. "
                "It is not FAA-approved and may not reflect actual aircraft capabilities. Always verify against the aircraft's POH/AFM. ⚠️",
                style={
                    "backgroundColor": "#fff3cd",
                    "border": "1px solid #ffeeba",
                    "padding": "10px 20px",
                    "fontSize": "13px",
                    "color": "#856404",
                    "marginBottom": "10px",
                    "textAlign": "center",
                    "fontWeight": "500"
                }
            ),

            # Legal Links Row
            html.Div([
                html.Div([
                    html.A("Full Legal Disclaimer", href="#", id="open-disclaimer", style={
                        "fontSize": "13px",
                        "textDecoration": "underline",
                        "color": "#007bff",
                        "cursor": "pointer"
                    }),
                    html.Span(" | ", style={"margin": "0 6px", "color": "#999"}),  # optional separator
                    html.A("Terms of Use & Privacy Policy", href="#", id="open-terms-policy", style={
                        "fontSize": "13px",
                        "textDecoration": "underline",
                        "color": "#007bff",
                        "cursor": "pointer"
                    }),
                ], style={
                    "display": "flex",
                    "justifyContent": "center",
                    "alignItems": "center",
                    "gap": "10px",
                    "margin": "4px 0 0 0",
                    "padding": "0",
                    "lineHeight": "1.2"
                }),

                # Disclaimer Modal
                dbc.Modal([
                    dbc.ModalHeader("AeroEdge Disclaimer", close_button=False),
                    dbc.ModalBody([
                        html.P("This tool supplements—not replaces—FAA-published documentation.", style={"marginBottom": "8px"}),
                        html.P("It is intended for educational and reference use only, and has not been approved or endorsed by the Federal Aviation Administration (FAA).", style={"marginBottom": "8px"}),
                        html.P("While AeroEdge is aligned with FAA safety principles, it is not an official source of operational data. Users must consult certified instructors and approved aircraft documentation when making flight decisions.", style={"marginBottom": "8px"}),
                        html.P("The data presented may be incomplete, inaccurate, outdated, or derived from public or user-submitted sources. No warranties, express or implied, are made regarding its accuracy, completeness, or fitness for purpose.", style={"marginBottom": "8px"}),
                        html.P("Instructors and users are encouraged to verify all EM diagram outputs against certified POH/AFM values. This tool is not a substitute for competent flight instruction, or for compliance with applicable regulations, including Airworthiness Directives (ADs), Federal Aviation Regulations (FARs), or Advisory Circulars (ACs).", style={"marginBottom": "8px"}),
                        html.P("If any information conflicts with the aircraft’s FAA-approved AFM or POH, the official documentation shall govern.", style={"marginBottom": "8px"}),
                        html.P("AeroEdge disclaims all liability for errors, omissions, injuries, or damages resulting from the use of this application or website. Use of this tool constitutes acceptance of these terms.", style={"marginBottom": "8px"})
                    ]),
                    dbc.ModalFooter(
                        dbc.Button("Close", id="close-disclaimer", className="ms-auto", color="secondary")
                    )
                ], id="disclaimer-modal", is_open=False),

                # Terms Modal
                dbc.Modal([
                    dbc.ModalHeader("Terms of Use & Privacy Policy", close_button=False),
                    dbc.ModalBody([
                        html.H6("Terms of Use", className="mb-2 mt-2"),
                        html.P("By accessing or using the AeroEdge application and its associated services, you agree to use this tool solely for educational and informational purposes. This tool is not FAA-certified and should not be relied upon for flight planning, aircraft operation, or regulatory compliance.", style={"marginBottom": "8px"}),
                        html.P("Users must verify all performance data with the aircraft's official Pilot's Operating Handbook (POH) or Aircraft Flight Manual (AFM). Use of AeroEdge is at your own risk. AeroEdge disclaims liability for any direct, indirect, incidental, or consequential damages arising from its use.", style={"marginBottom": "8px"}),

                        html.H6("Privacy Policy", className="mb-2 mt-4"),
                        html.P("AeroEdge does not collect, store, or share any personally identifiable information (PII). All use of the application is anonymous. Uploaded aircraft files remain local to your device and are not transmitted or stored on any external servers.", style={"marginBottom": "8px"}),
                        html.P("If you submit feedback through linked forms, that information is governed by the terms of Google Forms. AeroEdge does not sell or distribute any user-submitted information and uses it only to improve functionality and user experience.", style={"marginBottom": "8px"}),

                        html.P("By using this application, you acknowledge and accept these terms.")
                    ]),
                    dbc.ModalFooter(
                        dbc.Button("Close", id="close-terms-policy", className="ms-auto", color="secondary")
                    )
                ], id="terms-policy-modal", is_open=False),
            ]),

        # Two-Column Flex Layout: Sidebar + Graph
        html.Div([
            # Sidebar Left
            dbc.Col([
                html.Div(id="resize-handle", className="resize-handle"),
                html.Div("EM Diagram Generator", style={
                    "fontWeight": "600",
                    "fontSize": "20px",
                    "marginBottom": "10px",
                    "color": "#1b1e23"  # match your theme color
                }),
                dbc.Row([
                    dbc.Col(
                        dbc.Button(
                            "✏️ Edit / Create Aircraft",
                            id="edit-aircraft-button",
                            color="success",
                            className="mb-2",
                            style={"width": "200px", "fontWeight": "bold"}
                        ),
                        
                    ),
                    dbc.Col(
                        dcc.Upload(
                            id="upload-aircraft",
                            children=dbc.Button(
                                "📂 Load Aircraft File",
                                color="info",
                                style={"fontWeight": "bold"}
                            ),
                            multiple=False,
                            accept=".json"
                        ),
                        
                    )
                ], className="mb-2", style={"gap": "10px"}),

                # Aircraft Configuration Panel
                dbc.Card([
                    dbc.CardHeader("Aircraft Configuration"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Label("Aircraft", className="input-label"),
                                dcc.Dropdown(id="aircraft-select", options=[], placeholder="Select an Aircraft...", className="dropdown")
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Engine", className="input-label"),
                                dcc.Dropdown(id="engine-select", className="dropdown"),
                                
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Category", className="input-label"),
                                dcc.Dropdown(id="category-select", className="dropdown")
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Flap Configuration", className="input-label"),
                                dcc.Dropdown(id="config-select", className="dropdown")
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Landing Gear", className="input-label"),
                                dcc.Dropdown(id="gear-select", className="dropdown")
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Total Weight", className="input-label"),
                                html.Div(id="total-weight-display", className="weight-box")
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Occupants", className="input-label"),
                                dcc.Dropdown(id="occupants-select", className="dropdown-small")
                            ], width=6),
                            dbc.Col([
                                html.Label("Occupant Weight (lbs)", className="input-label"),
                                dcc.Input(id="passenger-weight-input", type="number", value=180, min=50, max=400, step=1, className="input-small")
                            ], width=6)
                        ], className="mb-3"),

                        
                        dbc.Row([
                            dbc.Col([
                                html.Label("Fuel (gal)", className="input-label"),
                                dcc.Slider(id="fuel-slider", min=0, max=50, step=1, value=20, marks={}, tooltip={"always_visible": True})
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Power Setting", className="input-label"),
                                dcc.Slider(
                                    id="power-setting",
                                    min=0.05,
                                    max=1.0,
                                    step=0.05,
                                    value=0.50,
                                    marks={0.05: "IDLE", 0.2: "20%", 0.4: "40%", 0.6: "60%", 0.8: "80%", 1: "100%"},
                                    tooltip={"always_visible": True}
                                )
                            ])
                        ], className="mb-3"),

                        html.Div([
                            dcc.Slider(id="cg-slider", min=0, max=1, value=0.5, step=0.01)
                        ], id="cg-slider-container"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Altitude (ft)", className="input-label"),
                                dcc.Slider(id="altitude-slider", min=0, max=35000, step=1000, value=0, marks={}, tooltip={"always_visible": True})
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Flight Path Angle (deg)", className="input-label"),
                                dcc.Slider(
                                    id="pitch-angle",
                                    min=-15,
                                    max=25,
                                    step=1,
                                    value=0,
                                    marks={-15: "-15°", -10: "-10°", -5: "-5°", 0: "0°", 5: "5°", 10: "10°", 15: "15°", 20: "20°", 25: "25°"},
                                    tooltip={"always_visible": True}
                                )
                            ])
                        ], className="mb-3")
                    ])
                ], className="mb-4"),

                # Overlay & Units
                dbc.Card([
                    dbc.CardHeader("Overlay Options"),
                    dbc.CardBody([

                        # Airspeed Units Toggle
                        html.Div([
                            html.Label("Airspeed Units", className="input-label", style={"marginBottom": "6px"}),
                            dbc.RadioItems(
                                id="unit-select",
                                options=[
                                    {"label": "KIAS", "value": "KIAS"},
                                    {"label": "MPH", "value": "MPH"}
                                ],
                                value="KIAS",
                                inline=True,
                                
                            )
                        ], className="radio-inline-group"),

                        # Overlay checklist (always visible)
                        dcc.Checklist(
                            id="overlay-toggle",
                            options=[
                                {"label": "Ps Contours", "value": "ps"},
                                {"label": "Intermediate G Lines", "value": "g"},
                                {"label": "Turn Radius Lines", "value": "radius"},
                                {"label": "Angle of Bank Shading", "value": "aob"},
                                {"label": "Negative G Envelope", "value": "negative_g"}
                            ],
                            value=["ps", "g", "radius", "aob"],
                            labelStyle={"display": "block"},
                            className="checklist mb-3"
                        ),
                        html.Div([
                            html.Label("Engine Failure Simulation", className="input-label"),
                            dcc.Checklist(
                                id="oei-toggle",
                                options=[{"label": "Simulate One Engine Inoperative", "value": "enabled"}],
                                value=[],
                                style={"margin-bottom": "5px"},
                            )
                        ], id="oei-container", className="mb-3"),
                        # OEI toggle (Simulate One Engine Inoperative)
                        html.Div(id="oei-container", className="mb-3"),

                        # Dynamic Vmc / Vyse Checklist (conditionally shown)
                        html.Div([
                            dcc.Checklist(
                                id="multi-engine-toggle-options",
                                options=[
                                    {"label": "Dynamic Vmc", "value": "vmca"},
                                    {"label": "Dynamic Vyse", "value": "dynamic_vyse"}
                                ],
                                value=[],
                                labelStyle={"display": "block"}
                            )
                        ], id="multi-engine-toggles", style={"display": "none"}, className="mb-3"),

                        
                        # === Prop Condition (only for Dynamic Vmc) ===
                        html.Div([
                            html.Label("Propeller Condition", className="input-label"),
                            dcc.RadioItems(
                                id="prop-condition",
                                options=[
                                    {"label": "Feathered", "value": "feathered"},
                                    {"label": "Stationary", "value": "stationary"},
                                    {"label": "Windmilling", "value": "windmilling"}                                    
                                ],
                                value="feathered",
                                labelStyle={"display": "inline-block", "margin-right": "10px"}
                            )
                        ], id="prop-condition-container", style={"display": "none"})
                    ])
                ], className="mb-4"),

                # Maneuver Builder
                dbc.Card([
                    dbc.CardHeader("Maneuver Overlays"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Label("Maneuver", className="input-label"),
                                dcc.Dropdown(
                                    id="maneuver-select", className="dropdown",
                                    options=[
                                        {"label": "Steep Turn", "value": "steep_turn"},
                                        {"label": "Chandelle", "value": "chandelle"}
                                    ],
                                    placeholder="Select a Maneuver",
                                    style={"width": "100%"}
                                )
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col(html.Div(id="maneuver-options-container"))
                        ])
                    ])
                ], className="mb-4"),

                # Export
                dbc.Card([
                    dbc.CardHeader("Export as PNG (use 📷 icon on graph)"),
                    dbc.CardBody([
                        html.Div([
                            dbc.Button("Export as PDF", id="pdf-button", color="primary", className="me-2"),
                        ], style={"display": "flex", "gap": "10px"}),
                        dcc.Download(id="pdf-download")
                    ])
                ]),
                # Error Reporting + Contact AeroEdge (Side-by-side)
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            dbc.Button(
                                "Report an Issue",
                                href="https://forms.gle/1xP29PwFze5MHCTZ7",
                                color="danger",
                                target="_blank",
                                className="me-2",
                                style={"fontWeight": "bold", "fontSize": "14px", "padding": "6px 12px"}
                            ),
                            dbc.Button(
                                "Contact AeroEdge",
                                href="https://forms.gle/AqS1uuTgcY6sRHob9",
                                color="secondary",
                                target="_blank",
                                style={"fontWeight": "bold", "fontSize": "14px", "padding": "6px 12px"}
                            )
                        ], style={
                            "display": "flex",
                            "alignItems": "center",
                            "gap": "10px",
                            "margin": "0",
                            "padding": "0"
                        })
                    ], style={"padding": "10px"})
                ], style={"marginTop": "5px", "marginBottom": "5px"}),
            ], xs=12, md=4, className="resizable-sidebar"),
            

            # Graph Column
            dbc.Col([
                html.Div([  # This div enforces the aspect ratio
                    dcc.Graph(
                        id="em-graph",
                        config={
                            "staticPlot": False,
                            "displaylogo": False,
                            "displayModeBar": True,
                            "modeBarButtonsToRemove": [
                                "zoom2d", "pan2d", "select2d", "lasso2d",
                                "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d",
                                "hoverCompareCartesian", "toggleSpikelines",
                                "drawline", "drawopenpath", "drawclosedpath", "drawcircle",
                                "drawrect", "eraseshape"
                            ]
                        },
                        className="dash-graph"
                    )
                ], className="graph-panel"),
                html.Div("© 2025 Nicholas Len, AEROEDGE. All rights reserved.",
                 className="footer")
            ], className="graph-column")
        ],className="main-row")
    ], className="full-height-container")

dcc.Checklist(id="oei-toggle", style={"display": "none"}, options=[], value=[])

def mobile_layout():
    return html.Div([
        # Header Row (logo banner)
        html.Div([
            html.Div([
                html.A(
                    html.Img(src="/assets/logo.png", className="banner-logo"),
                    href="https://flyaeroedge.com",
                    style={"textDecoration": "none"}
                )
            ], className="banner-inner")
        ], className="banner-header"),

        # Main App Layout
        html.Div([
            # Sidebar
            dbc.Col([
                html.Div(id="resize-handle", className="resize-handle"),
                html.Div("EM Diagram Generator", style={
                    "fontWeight": "600", "fontSize": "20px",
                    "marginBottom": "10px", "color": "#1b1e23"
                }),

                dbc.Button("Edit / Create Aircraft", id="edit-aircraft-button", color="success", className="mb-3", style={"width": "200px", "fontWeight": "bold"}),
                dbc.Col(dcc.Upload(id="upload-aircraft", children=dbc.Button("\ud83d\udcc2 Load Aircraft File", color="info", style={"fontWeight": "bold"}), multiple=False, accept=".json")),
                                                       

                # Aircraft Configuration Panel
                dbc.Card([
                    dbc.CardHeader("Aircraft Configuration"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Label("Aircraft", className="input-label"),
                                dcc.Dropdown(id="aircraft-select", options=[], placeholder="Select an Aircraft...", className="dropdown")
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Engine", className="input-label"),
                                dcc.Dropdown(id="engine-select", className="dropdown"),
                                
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Category", className="input-label"),
                                dcc.Dropdown(id="category-select", className="dropdown")
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Flap Configuration", className="input-label"),
                                dcc.Dropdown(id="config-select", className="dropdown")
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Landing Gear", className="input-label"),
                                dcc.Dropdown(id="gear-select", className="dropdown")
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Total Weight", className="input-label"),
                                html.Div(id="total-weight-display", className="weight-box")
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Occupants", className="input-label"),
                                dcc.Dropdown(id="occupants-select", className="dropdown-small")
                            ], width=6),
                            dbc.Col([
                                html.Label("Occupant Weight (lbs)", className="input-label"),
                                dcc.Input(id="passenger-weight-input", type="number", value=180, min=50, max=400, step=1, className="input-small")
                            ], width=6)
                        ], className="mb-3"),

                        
                        dbc.Row([
                            dbc.Col([
                                html.Label("Fuel (gal)", className="input-label"),
                                dcc.Slider(id="fuel-slider", min=0, max=50, step=1, value=20, marks={}, tooltip={"always_visible": True})
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Power Setting", className="input-label"),
                                dcc.Slider(
                                    id="power-setting",
                                    min=0.05,
                                    max=1.0,
                                    step=0.05,
                                    value=0.50,
                                    marks={0.05: "IDLE", 0.2: "20%", 0.4: "40%", 0.6: "60%", 0.8: "80%", 1: "100%"},
                                    tooltip={"always_visible": True}
                                )
                            ])
                        ], className="mb-3"),

                        html.Div([
                            dcc.Slider(id="cg-slider", min=0, max=1, value=0.5, step=0.01)
                        ], id="cg-slider-container"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Altitude (ft)", className="input-label"),
                                dcc.Slider(id="altitude-slider", min=0, max=35000, step=1000, value=0, marks={}, tooltip={"always_visible": True})
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                html.Label("Flight Path Angle (deg)", className="input-label"),
                                dcc.Slider(
                                    id="pitch-angle",
                                    min=-15,
                                    max=25,
                                    step=1,
                                    value=0,
                                    marks={-15: "-15°", -10: "-10°", -5: "-5°", 0: "0°", 5: "5°", 10: "10°", 15: "15°", 20: "20°", 25: "25°"},
                                    tooltip={"always_visible": True}
                                )
                            ])
                        ], className="mb-3")
                    ])
                ], className="mb-4"),

                # Overlay & Units
                dbc.Card([
                    dbc.CardHeader("Overlay Options"),
                    dbc.CardBody([

                        # Airspeed Units Toggle
                        html.Div([
                            html.Label("Airspeed Units", className="input-label", style={"marginBottom": "6px"}),
                            dbc.RadioItems(
                                id="unit-select",
                                options=[
                                    {"label": "KIAS", "value": "KIAS"},
                                    {"label": "MPH", "value": "MPH"}
                                ],
                                value="KIAS",
                                inline=True,
                                
                            )
                        ], className="radio-inline-group"),

                        # Overlay checklist (always visible)
                        dcc.Checklist(
                            id="overlay-toggle",
                            options=[
                                {"label": "Ps Contours", "value": "ps"},
                                {"label": "Intermediate G Lines", "value": "g"},
                                {"label": "Turn Radius Lines", "value": "radius"},
                                {"label": "Angle of Bank Shading", "value": "aob"},
                                {"label": "Negative G Envelope", "value": "negative_g"}
                            ],
                            value=["ps", "g", "radius", "aob"],
                            labelStyle={"display": "block"},
                            className="checklist mb-3"
                        ),
                        html.Div([
                            html.Label("Engine Failure Simulation", className="input-label"),
                            dcc.Checklist(
                                id="oei-toggle",
                                options=[{"label": "Simulate One Engine Inoperative", "value": "enabled"}],
                                value=[],
                                style={"margin-bottom": "5px"},
                            )
                        ], id="oei-container", className="mb-3"),
                        # OEI toggle (Simulate One Engine Inoperative)
                        html.Div(id="oei-container", className="mb-3"),

                        # Dynamic Vmc / Vyse Checklist (conditionally shown)
                        html.Div([
                            dcc.Checklist(
                                id="multi-engine-toggle-options",
                                options=[
                                    {"label": "Dynamic Vmc", "value": "vmca"},
                                    {"label": "Dynamic Vyse", "value": "dynamic_vyse"}
                                ],
                                value=[],
                                labelStyle={"display": "block"}
                            )
                        ], id="multi-engine-toggles", style={"display": "none"}, className="mb-3"),

                        
                        # === Prop Condition (only for Dynamic Vmc) ===
                        html.Div([
                            html.Label("Propeller Condition", className="input-label"),
                            dcc.RadioItems(
                                id="prop-condition",
                                options=[
                                    {"label": "Feathered", "value": "feathered"},
                                    {"label": "Stationary", "value": "stationary"},
                                    {"label": "Windmilling", "value": "windmilling"}                                    
                                ],
                                value="feathered",
                                labelStyle={"display": "inline-block", "margin-right": "10px"}
                            )
                        ], id="prop-condition-container", style={"display": "none"})
                    ])
                ], className="mb-4"),

                # Maneuver Builder
                dbc.Card([
                    dbc.CardHeader("Maneuver Overlays"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Label("Maneuver", className="input-label"),
                                dcc.Dropdown(
                                    id="maneuver-select", className="dropdown",
                                    options=[
                                        {"label": "Steep Turn", "value": "steep_turn"},
                                        {"label": "Chandelle", "value": "chandelle"}
                                    ],
                                    placeholder="Select a Maneuver",
                                    style={"width": "100%"}
                                )
                            ])
                        ], className="mb-3"),

                        dbc.Row([
                            dbc.Col(html.Div(id="maneuver-options-container"))
                        ])
                    ])
                ], className="mb-4"),

                # Export
                dbc.Card([
                    dbc.CardHeader("Export as PNG (use \ud83d\udcf7 icon on graph)"),
                    dbc.CardBody([
                        dbc.Button("Export as PDF", id="pdf-button", color="primary", className="me-2"),
                        dcc.Download(id="pdf-download")
                    ])
                ]),

                # Error Reporting and Contact
                dbc.Card([
                    dbc.CardBody([
                        dbc.Button("Report An Issue", href="https://forms.gle/1xP29PwFze5MHCTZ7", color="danger", target="_blank", className="me-2"),
                        dbc.Button("Contact AeroEdge", href="https://forms.gle/AqS1uuTgcY6sRHob9", color="secondary", target="_blank")
                    ], style={"display": "flex", "gap": "10px", "flexWrap": "wrap"})
                ], style={"marginTop": "5px", "marginBottom": "5px"}),
            ], xs=12, md=4, className="resizable-sidebar"),

            # Graph Column
            dbc.Col([
                html.Div([
                    dcc.Graph(
                        id="em-graph",
                        config={
                            "staticPlot": True,
                            "displaylogo": False,
                            "displayModeBar": True,
                            "modeBarButtonsToRemove": [
                                "zoom2d", "pan2d", "select2d", "lasso2d", "zoomIn2d", "zoomOut2d",
                                "autoScale2d", "resetScale2d", "hoverClosestCartesian", "hoverCompareCartesian",
                                "toggleSpikelines", "drawline", "drawopenpath", "drawclosedpath",
                                "drawcircle", "drawrect", "eraseshape"
                            ],
                            "modeBarButtonsToAdd": ["toImage"],
                            "modeBarMode": "always"
                        },
                        className="dash-graph"
                    )
                ], className="graph-panel"),
            ], className="graph-wrapper"),

            # Legal Section (bottom)
            html.Div([
                html.Div("\u00a9 2025 Nicholas Len, AEROEDGE. All rights reserved. For reference and educational purposes only.", className="footer"),

                # Legal Links Row
                html.Div([
                    html.A("Full Legal Disclaimer", href="#", id="open-disclaimer", style={"fontSize": "13px", "textDecoration": "underline", "color": "#007bff", "cursor": "pointer"}),
                    html.Span(" | ", style={"margin": "0 6px", "color": "#999"}),
                    html.A("Terms of Use & Privacy Policy", href="#", id="open-terms-policy", style={"fontSize": "13px", "textDecoration": "underline", "color": "#007bff", "cursor": "pointer"})
                ], style={"textAlign": "center", "marginTop": "8px", "marginBottom": "12px"}),

                # FAA Disclaimer Banner
                html.Div(
                    "\u26a0\ufe0f This tool visualizes performance data based on public or user-submitted values and is for educational use only. It is not FAA-approved and may not reflect actual aircraft capabilities. Always verify against the aircraft's POH/AFM. \u26a0\ufe0f",
                    style={
                        "backgroundColor": "#fff3cd", "border": "1px solid #ffeeba",
                        "padding": "8px 14px", "fontSize": "12px", "color": "#856404",
                        "textAlign": "center", "fontWeight": "500", "margin": "0 12px 10px 12px"
                    }
                ),
            ]),
        ], className="main-row"),

        # Modals (disclaimer + terms)
        dbc.Modal([
            dbc.ModalHeader("AeroEdge Disclaimer", close_button=False),
            dbc.ModalBody([
                html.P("This tool supplements\u2014not replaces\u2014FAA-published documentation.", style={"marginBottom": "8px"}),
                html.P("It is intended for educational and reference use only, and has not been approved or endorsed by the Federal Aviation Administration (FAA).", style={"marginBottom": "8px"}),
                html.P("While AeroEdge is aligned with FAA safety principles, it is not an official source of operational data. Users must consult certified instructors and approved aircraft documentation when making flight decisions.", style={"marginBottom": "8px"}),
                html.P("The data presented may be incomplete, inaccurate, outdated, or derived from public or user-submitted sources. No warranties, express or implied, are made regarding its accuracy, completeness, or fitness for purpose.", style={"marginBottom": "8px"}),
                html.P("Instructors and users are encouraged to verify all EM diagram outputs against certified POH/AFM values. This tool is not a substitute for competent flight instruction, or for compliance with applicable regulations, including Airworthiness Directives (ADs), Federal Aviation Regulations (FARs), or Advisory Circulars (ACs).", style={"marginBottom": "8px"}),
                html.P("If any information conflicts with the aircraft\u2019s FAA-approved AFM or POH, the official documentation shall govern.", style={"marginBottom": "8px"}),
                html.P("AeroEdge disclaims all liability for errors, omissions, injuries, or damages resulting from the use of this application or website. Use of this tool constitutes acceptance of these terms.", style={"marginBottom": "8px"})
            ]),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-disclaimer", className="ms-auto", color="secondary")
            )
        ], id="disclaimer-modal", is_open=False),

        dbc.Modal([
            dbc.ModalHeader("Terms of Use & Privacy Policy", close_button=False),
            dbc.ModalBody([
                html.H6("Terms of Use", className="mb-2 mt-2"),
                html.P("By accessing or using the AeroEdge application and its associated services, you agree to use this tool solely for educational and informational purposes. This tool is not FAA-certified and should not be relied upon for flight planning, aircraft operation, or regulatory compliance.", style={"marginBottom": "8px"}),
                html.P("Users must verify all performance data with the aircraft's official Pilot's Operating Handbook (POH) or Aircraft Flight Manual (AFM). Use of AeroEdge is at your own risk. AeroEdge disclaims liability for any direct, indirect, incidental, or consequential damages arising from its use.", style={"marginBottom": "8px"}),
                html.H6("Privacy Policy", className="mb-2 mt-4"),
                html.P("AeroEdge does not collect, store, or share any personally identifiable information (PII). All use of the application is anonymous. Uploaded aircraft files remain local to your device and are not transmitted or stored on any external servers.", style={"marginBottom": "8px"}),
                html.P("If you submit feedback through linked forms, that information is governed by the terms of Google Forms. AeroEdge does not sell or distribute any user-submitted information and uses it only to improve functionality and user experience.", style={"marginBottom": "8px"}),
                html.P("By using this application, you acknowledge and accept these terms.")
            ]),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-terms-policy", className="ms-auto", color="secondary")
            )
        ], id="terms-policy-modal", is_open=False),

        # Store fallback for checklist
        dcc.Checklist(id="oei-toggle", style={"display": "none"}, options=[], value=[])
    ], className="full-height-container")


# ✅ Automatically open the browser when the app starts
def open_browser():
    webbrowser.open("http://127.0.0.1:8050/")

@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
    Input("screen-width", "data")
)
def display_page(pathname, screen_width):
    # Gracefully handle undefined screen width
    if screen_width is None:
        screen_width = 1024  # assume desktop by default

    is_mobile = screen_width and screen_width < 768

    if pathname == "/" or pathname is None:
        return em_diagram_layout(is_mobile=is_mobile)
    elif pathname == "/edit-aircraft":
        return edit_aircraft_layout()
    else:
        return html.H1("404 - Page not found")


    

@app.callback(
    Output("aircraft-data-store", "data"),
    Input("url", "pathname"),
    prevent_initial_call=True
)
def reload_aircraft_on_return(pathname):
    if pathname == "/":
        dprint("[DEBUG] Reloading aircraft data from folder...")
        return load_aircraft_data_from_folder()
    raise PreventUpdate





@app.callback(
    Output("aircraft-select", "value", allow_duplicate=True),
    Input("aircraft-data-store", "data"),
    State("last-saved-aircraft", "data"),
    prevent_initial_call=True
)
def set_last_selected_aircraft_on_load(data, last_saved):
    if last_saved and last_saved in data:
        return last_saved
    raise PreventUpdate

@app.callback(
    Output("aircraft-select", "options"),
    Input("aircraft-data-store", "data")
)
def update_aircraft_options(data):
    return [{"label": name, "value": name} for name in sorted(data.keys())]

@app.callback(
    Output("category-select", "options"),
    Output("category-select", "value"),
    Input("aircraft-select", "value"),
)
def update_category_dropdown(ac_name):
    if not ac_name or ac_name not in aircraft_data:
        raise PreventUpdate

    ac = aircraft_data[ac_name]
    categories = list(ac.get("G_limits", {}).keys())
    options = [{"label": cat.capitalize(), "value": cat} for cat in categories]
    default = options[0]["value"] if options else None
    return options, default
from dash import html
from dash.exceptions import PreventUpdate
from dash.dependencies import Input, Output

@app.callback(
    Output("multi-engine-toggles", "style"),
    Output("prop-condition-container", "style"),
    Input("aircraft-select", "value"),
    Input("oei-toggle", "value"),
    Input("multi-engine-toggle-options", "value"),
    prevent_initial_call=True
)
def update_dynamic_vmca_visibility(ac_name, oei_toggle, multi_engine_opts):
    from dash.exceptions import PreventUpdate

    if not ac_name or ac_name not in aircraft_data:
        raise PreventUpdate

    ac = aircraft_data[ac_name]
    is_multi = ac.get("engine_count", 1) >= 2
    oei_enabled = oei_toggle and "enabled" in oei_toggle
    vmca_enabled = "vmca" in (multi_engine_opts or [])

    # Show dynamic overlays only when OEI is active
    show_vmca_block = {"display": "block"} if is_multi and oei_enabled else {"display": "none"}

    # Show prop condition only when Dynamic Vmc is toggled *and* OEI is active
    show_prop_condition = {"display": "block", "marginTop": "5px"} if is_multi and oei_enabled and vmca_enabled else {"display": "none"}

    return show_vmca_block, show_prop_condition

@app.callback(
    Output("engine-select", "options"),
    Output("engine-select", "value"),
    Output("occupants-select", "options"),
    Output("occupants-select", "value"),
    Output("fuel-slider", "max"),
    Output("fuel-slider", "marks"),
    Output("altitude-slider", "max"),
    Output("altitude-slider", "marks"),
    Input("aircraft-select", "value"),
    
)
def update_aircraft_dependent_inputs(ac_name):
    if not ac_name or ac_name not in aircraft_data:
        raise PreventUpdate

    ac = aircraft_data[ac_name]

    # Engine
    engines = ac["engine_options"]
    engine_opts = [{"label": name, "value": name} for name in engines.keys()]
    engine_val = engine_opts[0]["value"]

    # Occupants
    seat_count = ac["seats"]
    occ_opts = [{"label": str(i), "value": i} for i in range(seat_count + 1)]
    occ_val = min(2, seat_count)

    # Fuel
    fuel_max = ac["fuel_capacity_gal"]
    # Determine 8 evenly spaced marks between min and max
    tick_count = 10  # Total including min and max
    step = fuel_max / (tick_count - 1)

    fuel_marks = {
        int(round(i * step)): str(int(round(i * step)))
        for i in range(tick_count)
    }
    fuel_marks[0] = "0"
    fuel_marks[fuel_max] = f"{fuel_max}"

    # Altitude
    ceiling = ac.get("mx_altitude") or ac.get("max_altitude")
    if ceiling is None:
        ceiling = 15000
    alt_marks = {i: str(i) for i in range(0, ceiling + 1, 5000)}
    alt_marks[0] = "Sea Level"
    alt_marks[ceiling] = f"{ceiling} ft"

    return (
        engine_opts,
        engine_val,
        occ_opts,
        occ_val,
        fuel_max,
        fuel_marks,
        ceiling,
        alt_marks,
        
    )


@app.callback(
    Output("cg-slider-container", "children"),
    Input("aircraft-select", "value")
)
def render_cg_slider(ac_name):
    if not ac_name or ac_name not in aircraft_data:
        raise PreventUpdate

    ac = aircraft_data[ac_name]
    raw_min, raw_max = ac["cg_range"]
    cg_min = round(float(raw_min), 2)
    cg_max = round(float(raw_max), 2)
    cg_mid = round((cg_min + cg_max) / 2, 2)

    cg_marks = {
        str(cg_min): f"FWD ({cg_min:.1f}\")",
        str(cg_mid): f"MID ({cg_mid:.1f}\")",
        str(cg_max): f"AFT ({cg_max:.1f}\")"
    }

    dprint("CG DEBUG:", {
        "cg_min": cg_min,
        "cg_mid": cg_mid,
        "cg_max": cg_max,
        "marks": cg_marks
        })

    return html.Div([
        html.Label("Center of Gravity (inches)"),
        dcc.Slider(
            id="cg-slider",
            min=cg_min,
            max=cg_max,
            value=cg_mid,
            step=None,
            marks=cg_marks,
            tooltip={"always_visible": True}
        )
    ])

@app.callback(
    Output("config-select", "options"),
    Output("config-select", "value"),
    Input("aircraft-select", "value"),
)
def update_config_dropdown(ac_name):
    if not ac_name or ac_name not in aircraft_data:
        raise PreventUpdate

    flaps = aircraft_data[ac_name]["configuration_options"]["flaps"]
    options = [{"label": flap, "value": flap} for flap in flaps]
    default = options[0]["value"] if options else None
    return options, default

@app.callback(
    Output("gear-select", "options"),
    Output("gear-select", "value"),
    Input("aircraft-select", "value"),
)
def update_gear_dropdown(ac_name):
    if not ac_name or ac_name not in aircraft_data:
        raise PreventUpdate

    ac = aircraft_data[ac_name]
    if ac.get("gear_type") == "retractable":
        options = [{"label": "Up", "value": "up"}, {"label": "Down", "value": "down"}]
        return options, "up"
    else:
        return [], None

@app.callback(
    Output("gear-select", "style"),
    Input("aircraft-select", "value")
)
def toggle_gear_selector_visibility(ac_name):
    if not ac_name or ac_name not in aircraft_data:
        return {"display": "none"}

    gear_type = aircraft_data[ac_name].get("gear_type", "fixed")
    return {"display": "block"} if gear_type == "retractable" else {"display": "none"}

@app.callback(
    Output("total-weight-display", "children"),
    Output("total-weight-display", "style"),
    Output("stored-total-weight", "data"),
    Input("aircraft-select", "value"),
    Input("fuel-slider", "value"),
    Input("occupants-select", "value"),
    Input("passenger-weight-input", "value"),
)
def update_total_weight(ac_name, fuel, occupants, pax_weight):
    if not ac_name or ac_name not in aircraft_data:
        raise PreventUpdate

    ac = aircraft_data[ac_name]
    empty = ac["empty_weight"]
    fuel_weight = fuel * ac["fuel_weight_per_gal"]
    pax_weight = pax_weight or 180
    occupants = occupants or 0
    people_weight = occupants * pax_weight
    total = empty + fuel_weight + people_weight
    max_weight = ac["max_weight"]

    color = "darkgreen" if total <= max_weight else "red"

    return (
        f"{int(total)} lbs",
        {"color": color, "fontWeight": "bold", "fontSize": "16px"},
        total
    )

from dash.exceptions import PreventUpdate

def calculate_vmca(
    published_vmca,
    power_fraction,
    total_weight,
    reference_weight,
    cg,
    cg_range,
    prop_condition,
    unit="KIAS",
    bank_angles_deg=np.linspace(-5, 10, 50)
):
    """
    Returns Vmca values across a range of bank angles based on power, weight, CG, and prop condition.
    """

    # --- Extract usable numeric Vmca if a dict was passed ---
    if isinstance(published_vmca, dict):
        published_vmca = published_vmca.get("clean_up") or next(iter(published_vmca.values()), None)

    if not isinstance(published_vmca, (int, float)):
        return bank_angles_deg, np.full_like(bank_angles_deg, np.nan)

    # --- Base modifier (1.0 = no change from published) ---
    modifiers = np.ones_like(bank_angles_deg, dtype=float)

    # Power effect
    modifiers *= np.clip(0.7 + 0.3 * (power_fraction / 1.0), 0.7, 1.2)

    # Weight effect
    weight_factor = reference_weight / total_weight
    modifiers *= np.clip(weight_factor, 0.85, 1.15)

    # CG effect
    cg_span = cg_range[1] - cg_range[0]
    if cg_span > 0:
        cg_percent = (cg - cg_range[0]) / cg_span
        cg_penalty = 1.0 + (0.05 * cg_percent)
    else:
        cg_penalty = 1.0
    modifiers *= cg_penalty

    # Prop condition effect
    if prop_condition == "windmilling":
        modifiers *= 1.05
    elif prop_condition == "stationary":
        modifiers *= 1.02
    elif prop_condition == "feathered":
        modifiers *= 0.95

    # Bank angle effect
    bank_mod = np.ones_like(bank_angles_deg)
    for i, bank in enumerate(bank_angles_deg):
        if bank < 0:
            bank_mod[i] *= 1.10
        elif 0 <= bank <= 5:
            bank_mod[i] *= 1.0 - 0.04 * (bank / 5.0)
        elif bank > 5:
            bank_mod[i] *= 1.0 + 0.03 * ((bank - 5) / 5.0)
    modifiers *= bank_mod

    # Final Vmca array
    vmca_vals = published_vmca * modifiers

    # Convert to MPH if needed
    if unit == "MPH":
        vmca_vals = vmca_vals * 1.15078

    return bank_angles_deg, vmca_vals

def calculate_dynamic_vyse(
    published_vyse,
    total_weight,
    reference_weight,
    altitude_ft,
    gear_position,
    flap_config,
    prop_condition
):
    """
    Compute dynamic Vyse based on weight, altitude, gear, flaps, and prop condition.
    - published_vyse: baseline Vyse (KIAS)
    - total_weight: current aircraft weight
    - reference_weight: weight at which Vyse is published (typically max gross)
    - altitude_ft: current pressure altitude
    - gear_position: "up" or "down"
    - flap_config: e.g. "clean", "takeoff", "landing"
    - prop_condition: "feathered", "windmilling"
    """

    # --- Weight effect: Vyse increases as weight increases (less climb margin)
    weight_factor = min(max(total_weight / reference_weight, 0.9), 1.1)  # ±10% effect

    # --- Altitude effect: Vyse tends to increase with altitude (lower excess power)
    altitude_factor = 1.0 + (altitude_ft / 10000.0) * 0.02  # ~2% per 10,000 ft

    # --- Gear effect: gear down = more drag = higher Vyse
    gear_factor = 1.04 if gear_position == "down" else 1.0  # +4% if gear down

    # --- Flap effect: more flaps = higher Vyse (more drag)
    flap_penalty = {
        "clean": 1.00,
        "takeoff": 1.03,
        "landing": 1.06
    }
    config_factor = flap_penalty.get(flap_config, 1.00)

    if prop_condition == "windmilling":
        prop_factor = 1.05  # Highest drag penalty
    elif prop_condition == "feathered":
        prop_factor = 0.95  # Most efficient
    elif prop_condition == "stationary":
        prop_factor = 1.02  # Midpoint — more drag than feathered, less than windmilling

    # --- Final dynamic Vyse
    adjusted_vyse = (
        published_vyse
        * weight_factor
        * altitude_factor
        * gear_factor
        * config_factor
        * prop_factor
    )

    return adjusted_vyse

@app.callback(
    Output("em-graph", "figure"),
    Input("aircraft-select", "value"),
    Input("config-select", "value"),
    Input("engine-select", "value"),
    Input("occupants-select", "value"),
    Input("fuel-slider", "value"),
    Input("altitude-slider", "value"),
    Input("stored-total-weight", "data"),
    Input("power-setting", "value"),
    Input("overlay-toggle", "value"),
    Input("gear-select", "value"),
    Input("oei-toggle", "value"),
    Input("prop-condition", "value"),
    Input("cg-slider", "value"),
    Input("category-select", "value"),
    Input("unit-select", "value"),
    Input("multi-engine-toggle-options", "value"),
    Input("maneuver-select", "value"),
    Input({"type": "steepturn-aob", "index": ALL}, "value"),
    Input({"type": "steepturn-ias", "index": ALL}, "value"),
    Input({"type": "steepturn-ghost", "index": ALL}, "value"),
    Input({"type": "chandelle-ias", "index": ALL}, "value"),
    Input({"type": "chandelle-bank", "index": ALL}, "value"),
    Input({"type": "chandelle-ghost", "index": ALL}, "value"),
    Input("pitch-angle", "value"),
    Input("screen-width", "data"),
)

def update_graph(
    ac_name,
    config,
    engine_name,
    occupants,
    fuel,
    altitude_ft,
    total_weight,
    power_fraction,
    overlay_toggle,
    gear,
    oei_toggle,
    prop_condition,
    cg,
    selected_category,
    unit,
    multi_engine_toggle_options,
    maneuver,
    aob_values,             
    ias_values,
    ghost_mode_values,
    chandelle_ias_values,
    chandelle_bank_values,
    chandelle_ghost_values,
    pitch_angle,
    screen_width
    
):
    t_start = time.perf_counter()
    import plotly.graph_objects as go  # <== you must ensure this is imported here if not at top of file

    all_overlays = overlay_toggle + multi_engine_toggle_options

    if not ac_name or ac_name not in aircraft_data:
        return go.Figure()  # Return an empty graph if no aircraft is selected

    if engine_name is None or engine_name not in aircraft_data[ac_name]["engine_options"]:
        raise PreventUpdate

    KIAS_to_MPH = 1.15078
    def convert_display_airspeed(ias_vals, unit):
        return ias_vals * KIAS_to_MPH if unit == "MPH" else ias_vals
    def convert_input_airspeed(ias_vals, unit):
        return ias_vals / KIAS_to_MPH if unit == "MPH" else ias_vals
    
    if not ac_name or ac_name not in aircraft_data:
        raise PreventUpdate
    from dash import ctx
    if oei_toggle is None:
        oei_toggle = []
    if prop_condition is None:
        prop_condition = "feathered"

    oei_active = "enabled" in oei_toggle
    prop_mode = prop_condition if oei_active else None
 

    ac = aircraft_data[ac_name]
    engine_data = ac["engine_options"][engine_name]
    
    # --- Power Derating Based on Altitude ---
    power_curve = engine_data.get("power_curve", {})
    sea_level_max = power_curve.get("sea_level_max", engine_data["horsepower"])
    max_altitude = power_curve.get("max_altitude", 12000)
    derate_per_1000ft = power_curve.get("derate_per_1000ft", 0.03)

    alt_frac = min(altitude_ft / 1000.0, max_altitude / 1000.0)
    alt_derate = max(0.0, 1 - derate_per_1000ft * alt_frac)
    derated_hp = sea_level_max * alt_derate

    hp = derated_hp * power_fraction  # ✅ override earlier hp

    g_limit_block = ac.get("G_limits", {}).get(selected_category, {}).get(config, {})

    if isinstance(g_limit_block, dict):
        g_limit = g_limit_block.get("positive", 3.8)
        neg = g_limit_block.get("negative", -1.5)
        g_limit_neg = abs(neg) if isinstance(neg, (int, float)) else 1.5
    elif isinstance(g_limit_block, (int, float)):
        g_limit = g_limit_block
        g_limit_neg = 1.5
    else:
        g_limit = 3.8
        g_limit_neg = 1.5

        # --- Gear Drag & Lift Modifiers ---
    gear_drag_factor = 1.0
    gear_lift_factor = 1.0

    if gear == "down":
        gear_drag_factor = 1.15  # +15% drag when gear down
        gear_lift_factor = 0.98  # -2% CLmax when gear down

    # --- Determine Final Power Based on OEI Toggle ---
    oei_config_key = f"{config}_{gear or 'up'}"
    oei_data = (
        engine_data
        .get("oei_performance", {})
        .get(oei_config_key, {})
        .get(prop_mode, {})
    )
    # If OEI config lookup failed, try defaulting to "clean_up"
    if oei_active and not oei_data:
        oei_data = (
            engine_data.get("oei_performance", {})
            .get("clean_up", {})
            .get(prop_mode, {})
        )

    if oei_active and oei_data:
        hp = sea_level_max * oei_data.get("max_power_fraction", 1.0) * alt_derate
    else:
        hp = derated_hp * power_fraction
        

    # ✅ Debug log
    dprint("ENGINE DEBUG:", {
        "ac": ac_name,
        "engine": engine_name,
        "oei_active": oei_active,
        "prop_mode": prop_mode,
        "config_key": oei_config_key,
        "hp": hp,
    })
    
    import re
    import numpy as np
    from math import pi
    import plotly.graph_objects as go

  

    # ✅ Continue with existing logic...

    fig = go.Figure()
    weight = total_weight  # passed in directly from dcc.Store
    total_weight = weight  # ✅ ensures total_weight is defined

    fig.add_layout_image(
        dict(
            source="/assets/logo2.png",
            xref="paper", yref="paper",
            x=0, y=1,
            sizex=0.2, sizey=0.2,
            xanchor="left", yanchor="top",
            layer="above"
        )
    )

    fig.update_layout(
        paper_bgcolor="#f7f9fc",   # outside the plot
        plot_bgcolor="#f7f9fc",    # inside the plotting area
        font=dict(color="#1b1e23"),  # match your UI's text color
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis=dict(showgrid=True),
        yaxis=dict(showgrid=True),
        dragmode=False,             # ✅ disables box zoom drag
        hovermode="closest"         # ✅ enables hover tooltips
    )
    
    g = 32.174
    # --- CG Effects ---
    cl_base = ac["CL_max"][config]
    cg_min_val, cg_max_val = ac["cg_range"]
    cg_span = cg_max_val - cg_min_val
    cg_fraction = (cg - cg_min_val) / cg_span if cg_span else 0.5  # Avoid div by zero

    # Apply simple linear model: more forward = lower CL_max, more drag
    cl_max = cl_base * (1 - 0.05 * (1 - cg_fraction))  # up to 5% penalty at full forward CG
    cl_max *= gear_lift_factor
    cg_drag_factor = 1 + 0.04 * (0.5 - cg_fraction)     # up to 4% added drag for FWD CG

    dprint("CG INFLUENCE:", {
        "cg": cg,
        "cl_base": cl_base,
        "cl_max_adj": cl_max,
        "cg_fraction": cg_fraction,
        "cg_drag_factor": cg_drag_factor
    })

    
    wing_area = ac["wing_area"]
    lapse_rate = 0.0019812
    rho0 = 0.002377
    temp_K = 288.15 - lapse_rate * altitude_ft
    rho = rho0 * (temp_K / 288.15) ** 4.256

    stall_data = ac.get("stall_speeds", {}).get(config, {})
    vs_values = stall_data.get("speeds", [])
    vs_min = min(vs_values) if vs_values else 30
    ias_start = max(0, int(vs_min * 0.7))

    if config == "clean":
        max_speed = ac.get("Vne", 200)
        label = "Vne"
    else:
        max_speed = ac.get("Vfe", {}).get(config, 120)
        label = f"Vfe ({config})"

    max_speed_internal = max_speed  # always in KIAS for physics
    max_speed_display = convert_display_airspeed(max_speed, unit)

    vs_values = stall_data.get("speeds", [])
    vs_min = min(vs_values) if vs_values else 30
    ias_start = max(0, int(vs_min * 0.8))  # Add dynamic padding (20% below Vs)
    ias_vals = np.arange(ias_start, max_speed + 1, 1)
    ias_vals_display = convert_display_airspeed(ias_vals, unit)
    
    g_curve_x, g_curve_y = [], []
    for ias in ias_vals:
        v = ias * 1.68781
        omega = g * ((g_limit**2 - 1) ** 0.5) / v
        tr = omega * 180 / pi
        g_curve_x.append(ias)
        g_curve_y.append(tr)

    stall_x, stall_y = [], []
    for ias in ias_vals:
        v = ias * 1.68781
        n_stall = (0.5 * rho * v**2 * wing_area * cl_max) / weight
        if n_stall >= 1:
            omega = g * ((n_stall**2 - 1) ** 0.5) / v
            tr = omega * 180 / pi
            if not stall_x:
                stall_x.append(ias)
                stall_y.append(0)
            stall_x.append(ias)
            stall_y.append(tr)

    stall_x_display = convert_display_airspeed(np.array(stall_x), unit)
    g_curve_x_display = convert_display_airspeed(np.array(g_curve_x), unit)

    from numpy import interp
    corner_ias, corner_tr = None, None
    min_diff = float("inf")
    for ias in ias_vals:
        stall_tr = interp(ias, stall_x, stall_y)
        g_tr = interp(ias, g_curve_x, g_curve_y)
        diff = abs(stall_tr - g_tr)
        if diff < min_diff:
            min_diff = diff
            corner_ias = ias
            corner_tr = stall_tr
        if diff < 0.5:
            break

    if corner_ias is None:
        corner_ias = ias_vals[0]
        corner_tr = 0

    stall_clipped_x = [x for x in stall_x if x <= corner_ias]
    stall_clipped_y = stall_y[:len(stall_clipped_x)]
    g_clipped_x = [x for x in g_curve_x if x >= corner_ias]
    g_clipped_y = g_curve_y[-len(g_clipped_x):]

    oei_active = "enabled" in oei_toggle
    prop_mode = prop_condition if oei_active else None

    
    stall_clipped_x_display = convert_display_airspeed(np.array(stall_clipped_x), unit)
    g_clipped_x_display = convert_display_airspeed(np.array(g_clipped_x), unit)
    corner_ias_display = convert_display_airspeed(corner_ias, unit)

    if "negative_g" in overlay_toggle:
        # === Negative Lift Limit Curve ===
        neg_stall_x, neg_stall_y = [], []
        for ias in ias_vals:
            v = ias * 1.68781
            n_stall = (0.5 * rho * v**2 * wing_area * -cl_max) / weight
            if n_stall <= -1:
                # Compute turn rate, limit to G envelope
                try:
                    tr_limit_neg = g * np.sqrt(abs(g_limit_neg)**2 - 1) / v
                    omega = g * np.sqrt(n_stall**2 - 1) / v
                    tr = -min(omega * 180 / pi, tr_limit_neg * 180 / pi)
                except:
                    continue  # Skip invalid values (e.g. sqrt of negative)
                if not neg_stall_x:
                    neg_stall_x.append(ias)
                    neg_stall_y.append(0)
                neg_stall_x.append(ias)
                neg_stall_y.append(tr)

        neg_corner_idx = np.argmin(np.abs(np.array(neg_stall_y) - (-corner_tr)))
        neg_stall_x_clip = neg_stall_x[:neg_corner_idx + 1]
        neg_stall_y_clip = neg_stall_y[:neg_corner_idx + 1]
        neg_stall_x_display = convert_display_airspeed(np.array(neg_stall_x_clip), unit)

        # === Negative G-Limit Curve ===
        neg_g_x, neg_g_y = [], []
        for ias in ias_vals:
            v = ias * 1.68781
            try:
                omega = g * np.sqrt(g_limit_neg**2 - 1) / v
                tr = -omega * 180 / pi
                neg_g_x.append(ias)
                neg_g_y.append(tr)
            except:
                continue

        neg_g_x_clip = [x for x in neg_g_x if x >= neg_stall_x_clip[-1]]
        neg_g_y_clip = neg_g_y[-len(neg_g_x_clip):]
        neg_g_x_display = convert_display_airspeed(np.array(neg_g_x_clip), unit)

        # === Plot Negative G Envelope ===
        fig.add_trace(go.Scatter(
            x=neg_stall_x_display,
            y=neg_stall_y_clip,
            mode="lines",
            name="Neg Lift Limit",
            line=dict(color="red", width=3),
            hoverinfo="skip"
        ))

        fig.add_trace(go.Scatter(
            x=neg_g_x_display,
            y=neg_g_y_clip,
            mode="lines",
            name=f"Neg Load Limit ({g_limit_neg:.1f} G)",
            line=dict(color="black", width=3, dash="solid"),
            hoverinfo="skip"
        ))

        vne_y_top = None
        vne_y_bot = None

        # Adjust y_max/y_min to show full envelope
        y_span = max(
            abs(min(neg_g_y_clip)) if neg_g_y_clip else 0,
            max(g_clipped_y) if g_clipped_y else 0
        )
        y_max = y_span * 1.1
        y_min = -y_span * 1.1
    else:
        y_max = max(g_clipped_y) * 1.1 if g_clipped_y else 100
        y_min = 0

    fig.add_trace(go.Scatter(x=stall_clipped_x_display, y=stall_clipped_y,
        mode="lines", name="Lift Limit", line=dict(color="red", width=3), hoverinfo="skip")),
    fig.add_trace(go.Scatter(x=g_clipped_x_display, y=g_clipped_y,
        mode="lines", name=f"Load Limit ({g_limit:.1f} G)", line=dict(color="black", width=3, dash="solid"), hoverinfo="skip")),
    fig.add_trace(go.Scatter(x=[corner_ias_display], y=[corner_tr],
        mode="markers", name=f"Corner Speed ({corner_ias_display:.0f} {unit})", marker=dict(color="orange", size=9, symbol="x"), hoverinfo="skip")),

  # --- Interpolate Vne Y-positions (always present) ---
    vne_y_top = np.interp(max_speed, g_clipped_x, g_clipped_y) if g_clipped_x and g_clipped_y else 0
    vne_y_bot = 0  # Default if negative_g not shown

    # If negative G envelope is enabled and valid, interpolate bottom of Vne line
    if "negative_g" in overlay_toggle and 'neg_g_x_clip' in locals() and neg_g_x_clip and neg_g_y_clip:
        vne_y_bot = np.interp(max_speed, neg_g_x_clip, neg_g_y_clip)

    # Convert X for display units
    vne_x_display = convert_display_airspeed(max_speed, unit)

    # --- Plot Vne line
    fig.add_trace(go.Scatter(
        x=[vne_x_display, vne_x_display],
        y=[vne_y_bot, vne_y_top],
        mode="lines",
        name=label,
        line=dict(color="black", width=3, dash="dash"),
        hoverinfo="skip"
    ))  
    
    # Setup for overlays (continue with part 2)
    # --- INTERMEDIATE G CURVES (toggle controlled) ---
    if "g" in overlay_toggle:
        intermediate_gs = [round(g_val, 1) for g_val in np.arange(1.5, g_limit, 0.5)]
        for g_inter in intermediate_gs:
            gx, gy = [], []
            for ias in ias_vals:
                v = ias * 1.68781
                stall_v = np.sqrt((2 * weight * g_inter) / (rho * wing_area * cl_max))
                if v < stall_v:
                    continue
                omega = g * np.sqrt(g_inter**2 - 1) / v
                tr = omega * 180 / pi
                gx.append(ias)
                gy.append(tr)
                
            if len(gx) > 5:
                gx_display = convert_display_airspeed(np.array(gx), unit)
                fig.add_trace(go.Scatter(
                    x=gx_display, y=gy, mode="lines",
                    line=dict(color="yellow", width=1.2, dash="solid"),
                    showlegend=False, hoverinfo="skip"
                ))
                fig.add_annotation(
                    x=gx_display[-1] + 4, y=gy[-1], text=f"{g_inter:.1f}G",
                    showarrow=False, font=dict(color="black", size=10),
                    bgcolor="rgba(255,255,255,0.5)", borderpad=1
                )
# === Negative G Lines ===
        
        neg_intermediate_gs = [
            round(g_val, 1)
            for g_val in np.arange(-1.0, g_limit_neg, -0.5)
            if abs(g_val) >= 1.5 and abs(g_val - g_limit_neg) > 0.2
        ]
        for g_inter in neg_intermediate_gs:
            gx, gy = [], []
            for ias in ias_vals:
                v = ias * 1.68781
                stall_v = np.sqrt((2 * weight * abs(g_inter)) / (rho * wing_area * cl_max))
                if v < stall_v:
                    continue
                omega = g * np.sqrt(g_inter**2 - 1) / v
                tr = -omega * 180 / pi  # negative turn rate
                gx.append(ias)
                gy.append(tr)
            if len(gx) > 5:
                gx_display = convert_display_airspeed(np.array(gx), unit)
                fig.add_trace(go.Scatter(
                    x=gx_display, y=gy, mode="lines",
                    line=dict(color="yellow", width=1.2, dash="dot"),
                    showlegend=False, hoverinfo="skip"
                ))
                fig.add_annotation(
                    x=gx_display[-1] + 4, y=gy[-1], text=f"{g_inter:.1f}G",
                    showarrow=False, font=dict(color="black", size=10),
                    bgcolor="rgba(255,255,255,0.5)", borderpad=1
                )

# --- Ps GRID CALCULATION ---
    # --- Ps GRID CALCULATION ---
    ias_vals_ps_internal = np.arange(ias_start, max_speed_internal + 1, 1)
    ias_vals_ps_display = convert_display_airspeed(ias_vals_ps_internal, unit)
    CD0 = ac.get("CD0", 0.025)
    e = ac.get("e", 0.8)
    AR = ac.get("aspect_ratio", 7.5)

    # Detect steep turn override
    steep_turn_override = maneuver == "steep_turn" and ias_values and aob_values
    if steep_turn_override:
        aob_deg = aob_values[0]
        aob_rad = np.radians(aob_deg)
        V = ias_vals_ps_internal * 1.68781
        TR_fixed = np.degrees(g * np.tan(aob_rad) / V)  # TR as a function of IAS
        TR = np.tile(TR_fixed, (len(ias_vals_ps_internal), 1)).T  # 2D grid shape
        IAS = np.tile(ias_vals_ps_internal, (len(TR), 1))
        tr_vals_ps = TR[:, 0]  # save for mask below
    else:
        tr_vals_ps = np.arange(-100, 100, 1)
        IAS, TR = np.meshgrid(ias_vals_ps_internal, tr_vals_ps)

    V = IAS * 1.68781  # convert to ft/s
    omega_rad = TR * (np.pi / 180)
    n = np.sqrt(1 + (V * omega_rad / g) ** 2)

    q = 0.5 * rho * V**2
    CL = weight * n / (q * wing_area)
    CL_clipped = np.minimum(CL, cl_max)
    CD = (CD0 + (CL_clipped**2) / (np.pi * e * AR)) * cg_drag_factor * gear_drag_factor
    D = q * wing_area * CD

    # === Propeller Thrust Decay ===
    V_kts = IAS
    V_max_kts = ac.get("prop_thrust_decay", {}).get("V_max_kts", 160)
    T_static = ac.get("prop_thrust_decay", {}).get("T_static_factor", 2.6) * hp
    V_fraction = np.clip(V_kts / V_max_kts, 0, 1)
    T_available = T_static * (1 - V_fraction**2)
    T_available = np.maximum(T_available, 0)

    gamma_rad = np.radians(pitch_angle)
    Ps = ((T_available - D) * V / weight - g * np.sin(gamma_rad)) / 1.68781

    # Envelope mask
    mask = np.ones_like(Ps, dtype=bool)
    for i in range(Ps.shape[0]):
        for j in range(Ps.shape[1]):
            ias = IAS[i, j]
            tr = TR[i, j]
            v_fts = ias * 1.68781
            omega_rad = tr * (np.pi / 180)
            n_val = np.sqrt(1 + (v_fts * omega_rad / g) ** 2)
            stall_v_fts = np.sqrt((2 * weight * n_val) / (rho * wing_area * cl_max))
            stall_ias = stall_v_fts / 1.68781
            tr_limit_pos = g * np.sqrt(g_limit**2 - 1) / v_fts * 180 / np.pi
            tr_limit_neg = g * np.sqrt(g_limit_neg**2 - 1) / v_fts * 180 / np.pi

            if (
                ias >= stall_ias and
                (
                    (tr >= 0 and tr <= tr_limit_pos) or
                    (tr < 0 and abs(tr) <= tr_limit_neg)
                ) and
                ias <= max_speed
            ):
                mask[i, j] = False

    Ps_masked = np.where(mask, np.nan, Ps)

    dprint(f"[Ps DEBUG] ----")
    dprint(f"  Air Density: {rho:.5f} slugs/ft³")
    dprint(f"  CL avg: {np.nanmean(CL):.2f}, CD avg: {np.nanmean(CD):.3f}")
    dprint(f"  Thrust avg: {np.nanmean(T_available):.1f} lbs")
    dprint(f"  Drag avg: {np.nanmean(D):.1f} lbs")
    dprint(f"  Ps min: {np.nanmin(Ps):.2f}, Ps max: {np.nanmax(Ps):.2f} knots/sec")
    dprint(f"  Flight Path Angle (γ): {pitch_angle}°")
    dprint("[THRUST DECAY DEBUG]")
    dprint(f"  V_max_kts: {V_max_kts}")
    dprint(f"  T_static: {T_static:.1f} lbs")
    dprint(f"  T_available avg: {np.nanmean(T_available):.1f} lbs")
    dprint(f"  Drag avg: {np.nanmean(D):.1f} lbs")

   
# --- AOB HEATMAP: 10° to 90°, clipped to envelope ---

    if "aob" in overlay_toggle:
        # --- AOB HEATMAP (Valid Points Only) ---
        IAS_vals = np.arange(ias_start, max_speed + 1, 0.1)
        IAS_vals_display = convert_display_airspeed(IAS_vals, unit)
        ias_vals_display = convert_display_airspeed(ias_vals, unit)
        TR_vals = np.arange(1, 100, 0.1)
        IAS, TR = np.meshgrid(IAS_vals, TR_vals)
        V = IAS * 1.68781
        omega_rad = TR * (np.pi / 180)

        # Compute angle of bank at each point
        AOB_rad = np.arctan(omega_rad * V / g)
        AOB_deg = np.degrees(AOB_rad)

        # Mask: only show valid points (stall + G-limit + Vne)
        n = np.sqrt(1 + (V * omega_rad / g) ** 2)
        n = np.maximum(n, 1.001)  # Enforce minimum 1 G load factor

        stall_v = np.sqrt((2 * weight * n) / (rho * wing_area * cl_max))
        stall_IAS = stall_v / 1.68781
        tr_limit = g * np.sqrt(g_limit**2 - 1) / V * 180 / pi

        mask = (IAS >= stall_IAS) & (TR <= tr_limit) & (IAS <= max_speed)
        AOB_masked = np.where(mask, AOB_deg, np.nan)

        # Plot AOB heatmap
        fig.add_trace(go.Heatmap(
            x=IAS_vals_display,
            y=TR_vals,
            z=AOB_masked,
            colorscale="Turbo",
            zmin=0,
            zmax=90,
            opacity=0.5,
            zsmooth="fast",
            hoverinfo="skip",
            colorbar=dict(
                title="AOB (deg)",
                x=1.02,              # slightly beyond the plot area
                xanchor="left",
                y=0.25,
                len=0.6,            # scale down so it doesn’t dominate
                thickness=15,                
            )
            
        ))
        # --- AOB HEATMAP (Negative Turn Rates) ---
        if "aob" in overlay_toggle and "negative_g" in overlay_toggle:
            TR_vals_neg = np.arange(-100, -1, 0.1)
            IAS_vals_neg = np.arange(ias_start, max_speed + 1, 0.1)
            IAS_neg, TR_neg = np.meshgrid(IAS_vals_neg, TR_vals_neg)
            V_neg = IAS_neg * 1.68781
            omega_rad_neg = np.abs(TR_neg) * (np.pi / 180)  # use absolute to mirror

            AOB_rad_neg = np.arctan(omega_rad_neg * V_neg / g)
            AOB_deg_neg = np.degrees(AOB_rad_neg)  # keep positive AOB for mirror color scale

            n_neg = np.sqrt(1 + (V_neg * omega_rad_neg / g) ** 2)
            n_neg = np.maximum(n_neg, 1.001)
            stall_v_neg = np.sqrt((2 * weight * n_neg) / (rho * wing_area * cl_max))
            stall_IAS_neg = stall_v_neg / 1.68781
            tr_limit_neg = g * np.sqrt(g_limit_neg**2 - 1) / V_neg * 180 / pi

            mask_neg = (IAS_neg >= stall_IAS_neg) & (np.abs(TR_neg) <= tr_limit_neg) & (IAS_neg <= max_speed)
            AOB_masked_neg = np.where(mask_neg, AOB_deg_neg, np.nan)

            fig.add_trace(go.Heatmap(
                x=convert_display_airspeed(IAS_vals_neg, unit),
                y=TR_vals_neg,
                z=AOB_masked_neg,
                colorscale="Turbo",
                zmin=0,
                zmax=90,
                opacity=0.5,
                zsmooth="fast",
                hoverinfo="skip",
                showscale=False  # share scale with positive AOB
            ))
        

    if "radius" in overlay_toggle:
        ias_range = np.arange(ias_start, max_speed + 1, 1)
        min_radius = None
        max_radius = 0

        # --- Step 1a: Dynamically find smallest valid turn radius inside envelope
        min_radius = None
        for ias in np.arange(ias_start, max_speed + 1, 0.5):  # fine IAS sweep
            v_fts = ias * 1.68781
            for tr_candidate in np.arange(60, 1, -0.5):  # from tightest turns down
                omega_rad = tr_candidate * (np.pi / 180)
                r = v_fts / omega_rad

                n = np.sqrt(1 + (v_fts * omega_rad / g) ** 2)
                stall_v_fts = np.sqrt((2 * weight * n) / (rho * wing_area * cl_max))
                stall_ias = stall_v_fts / 1.68781
                tr_limit = g * np.sqrt(g_limit**2 - 1) / v_fts * 180 / np.pi

                if ias >= stall_ias and tr_candidate <= tr_limit and ias <= max_speed:
                    if min_radius is None or r < min_radius:
                        min_radius = r * 1.017
                    break  # first valid tightest radius is enough for this IAS

        # --- Step 1b: Compute max radius using 3 deg/sec
        max_radius = 0
        for ias in ias_range:
            v_fts = ias * 1.68781
            omega_3deg = 3 * (np.pi / 180)
            r = v_fts / omega_3deg

            n = np.sqrt(1 + (v_fts * omega_3deg / g) ** 2)
            stall_v_fts = np.sqrt((2 * weight * n) / (rho * wing_area * cl_max))
            stall_ias = stall_v_fts / 1.68781
            tr_limit = g * np.sqrt(g_limit ** 2 - 1) / v_fts * 180 / np.pi

            if ias >= stall_ias and 3 <= tr_limit and ias <= max_speed:
                max_radius = max(max_radius, r)

        span = max_radius - min_radius

        # Step 2: Visually spaced radius levels (5 total)
        mid1 = min_radius + 0.04 * span
        mid2 = min_radius + 0.12 * span
        mid3 = min_radius + 0.3 * span
        r1 = int(round(min_radius / 100.0)) * 100
        r2 = int(round(mid1 / 100.0)) * 100
        r3 = int(round(mid2 / 100.0)) * 100
        r4 = int(round(mid3 / 100.0)) * 100
        r5 = int(round(max_radius / 100.0)) * 100
        radius_levels = sorted(set([r1, r2, r3, r4, r5]))

        # Step 3: Plot radius lines
        for radius in radius_levels:
            valid_x = []
            valid_y = []

            for ias in ias_range:
                v_fts = ias * 1.68781
                omega_rad = v_fts / radius
                tr_deg = omega_rad * 180 / pi

                n = np.sqrt(1 + (v_fts * omega_rad / g) ** 2)
                stall_v_fts = np.sqrt((2 * weight * n) / (rho * wing_area * cl_max))
                stall_ias = stall_v_fts / 1.68781
                tr_limit = g * np.sqrt(g_limit**2 - 1) / v_fts * 180 / pi

                if ias >= stall_ias and tr_deg <= tr_limit and ias <= max_speed:
                    valid_x.append(convert_display_airspeed(ias, unit))
                    valid_y.append(tr_deg)

            if len(valid_x) > 5:
                fig.add_trace(go.Scatter(
                    x=valid_x,
                    y=valid_y,
                    mode="lines",
                    line=dict(color="blue", width=1, dash="dash"),
                    showlegend=False,
                    hoverinfo="skip",
                ))
                mid = len(valid_x) // 2
                fig.add_annotation(
                    x=valid_x[mid],
                    y=valid_y[mid],
                    text=f"{radius} ft",
                    showarrow=False,
                    font=dict(color="blue", size=10),
                    bgcolor="rgba(255,255,255,0.5)",
                    borderpad=1,
                )
        vs_min = min(vs_values) if vs_values else 30
        x_min = ias_start
        x_max = max_speed * 1.1
        y_max = (
            max(stall_clipped_y + g_clipped_y) * 1.1
            if stall_clipped_y and g_clipped_y
            else 100
        )
        # --- Add Turn Radius Legend Entry ---
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="lines",
            name="Turn Radius",
            line=dict(color="blue", width=1, dash="dash"),
            showlegend=True
        ))

        # --- NEGATIVE TURN RADIUS LINES ---
        if "negative_g" in overlay_toggle:
            neg_min_radius = None
            neg_max_radius = 0

            # Step 1a: Find tightest valid negative radius
            for ias in np.arange(ias_start, max_speed + 1, 0.5):
                v_fts = ias * 1.68781
                for tr_candidate in np.arange(60, 1, -0.5):
                    omega_rad = tr_candidate * (np.pi / 180)
                    r = v_fts / omega_rad

                    n = np.sqrt(1 + (v_fts * omega_rad / g) ** 2)
                    stall_v_fts = np.sqrt((2 * weight * n) / (rho * wing_area * cl_max))
                    stall_ias = stall_v_fts / 1.68781
                    tr_limit = g * np.sqrt(g_limit_neg**2 - 1) / v_fts * 180 / np.pi

                    if ias >= stall_ias and tr_candidate <= tr_limit and ias <= max_speed:
                        neg_min_radius = round(r * 1.017 / 100.0) * 100
                        break
                if neg_min_radius:
                    break

            # Step 1b: Max radius using 3 deg/sec
            for ias in ias_vals:
                v_fts = ias * 1.68781
                omega_3deg = 3 * (np.pi / 180)
                r = v_fts / omega_3deg

                n = np.sqrt(1 + (v_fts * omega_3deg / g) ** 2)
                stall_v_fts = np.sqrt((2 * weight * n) / (rho * wing_area * cl_max))
                stall_ias = stall_v_fts / 1.68781
                tr_limit = g * np.sqrt(g_limit_neg**2 - 1) / v_fts * 180 / np.pi

                if ias >= stall_ias and 3 <= tr_limit and ias <= max_speed:
                    neg_max_radius = max(neg_max_radius, r)

            neg_max_radius = round(neg_max_radius / 100.0) * 100

            # Step 2: Plot both radii
            for radius in [neg_min_radius, neg_max_radius]:
                if not radius:
                    continue
                neg_valid_x, neg_valid_y = [], []

                for ias in ias_vals:
                    v_fts = ias * 1.68781
                    omega_rad = v_fts / radius
                    tr_deg = -omega_rad * 180 / pi

                    n = np.sqrt(1 + (v_fts * omega_rad / g) ** 2)
                    stall_v = np.sqrt((2 * weight * n) / (rho * wing_area * cl_max))
                    stall_ias = stall_v / 1.68781
                    tr_limit = g * np.sqrt(g_limit_neg**2 - 1) / v_fts * 180 / pi

                    if ias >= stall_ias and abs(tr_deg) <= tr_limit and ias <= max_speed:
                        neg_valid_x.append(convert_display_airspeed(ias, unit))
                        neg_valid_y.append(tr_deg)

                if len(neg_valid_x) > 5:
                    fig.add_trace(go.Scatter(
                        x=neg_valid_x,
                        y=neg_valid_y,
                        mode="lines",
                        line=dict(color="blue", width=1.5, dash="dot"),
                        showlegend=False,
                        hoverinfo="skip"
                    ))
                    mid = len(neg_valid_x) // 2
                    fig.add_annotation(
                        x=neg_valid_x[mid],
                        y=neg_valid_y[mid],
                        text=f"{radius} ft",
                        showarrow=False,
                        font=dict(color="blue", size=10),
                        bgcolor="rgba(255,255,255,0.5)",
                        borderpad=1,
                    )
    # --- Ps CONTOURS (calculation and envelope masking) ---
    ias_vals_ps_internal = np.arange(ias_start, max_speed + 1, 1)
    tr_vals_ps = np.arange(-100, 100, 1)

    IAS, TR = np.meshgrid(ias_vals_ps_internal, tr_vals_ps)
    V = IAS * 1.68781  # ft/s

    omega_rad = TR * (np.pi / 180)
    n = np.sqrt(1 + (V * omega_rad / g) ** 2)

    q = 0.5 * rho * V**2
    CD0 = ac.get("CD0", 0.025)
    e = ac.get("e", 0.8)
    AR = ac.get("aspect_ratio", 7.5)
    CL = weight * n / (q * wing_area)
    CD = CD0 + (CL**2) / (np.pi * e * AR)
    D = q * wing_area * CD

    # === Realistic Propeller Thrust Model ===
    V_kts = IAS  # already in knots indicated
    # === Refined Prop Thrust Model ===
    V_max_kts = 160  # approximate top speed for full power
    T_static = 2.6 * hp  # DA20-specific static thrust factor
    V_fraction = np.clip(V_kts / V_max_kts, 0, 1)

    T_available = T_static * (1 - V_fraction**2)
    T_available = np.maximum(T_available, 0)

    # Apply pitch correction here too
    gamma_rad = np.radians(pitch_angle)
    Ps = ((T_available - D) * V / weight - g * np.sin(gamma_rad)) / 1.68781

    # Envelope mask
    mask = np.ones_like(Ps, dtype=bool)
    for i in range(len(tr_vals_ps)):
        for j in range(len(ias_vals_ps_internal)):
            ias = ias_vals_ps_internal[j]
            tr = tr_vals_ps[i]
            v_fts = ias * 1.68781
            omega_rad = tr * (np.pi / 180)
            n_val = np.sqrt(1 + (v_fts * omega_rad / g) ** 2)
            stall_v_fts = np.sqrt((2 * weight * n_val) / (rho * wing_area * cl_max))
            stall_ias = stall_v_fts / 1.68781
            tr_limit_pos = g * np.sqrt(g_limit**2 - 1) / v_fts * 180 / np.pi
            tr_limit_neg = g * np.sqrt(g_limit_neg**2 - 1) / v_fts * 180 / np.pi

            if (
                ias >= stall_ias and
                (
                    (tr >= 0 and tr <= tr_limit_pos) or
                    (tr < 0 and abs(tr) <= tr_limit_neg)
                ) and
                ias <= max_speed
            ):
                mask[i, j] = False

    Ps_masked = np.where(mask, np.nan, Ps)

     # --- Dynamic Vmca Curve (bank angle vs adjusted Vmca + turn rate) ---
    if "vmca" in all_overlays and ac.get("engine_count", 1) > 1 and oei_active:
        published_vmca = ac.get("single_engine_limits", {}).get("Vmca", 70)
        reference_weight = ac.get("max_weight", 3600)
        cg_range = ac.get("cg_range", [10, 20])

        # Sweep bank angle from -5° to 90° (beyond published + best-case)
        bank_angles = np.linspace(5, 90, 150)

        _, vmca_vals_kias = calculate_vmca(
            published_vmca=published_vmca,
            power_fraction=power_fraction,
            total_weight=weight,
            reference_weight=reference_weight,
            cg=cg,
            cg_range=cg_range,
            prop_condition=prop_mode,
            bank_angles_deg=bank_angles
        )

        vmca_vals_display = convert_display_airspeed(vmca_vals_kias, unit)

        # Convert bank angle to turn rate
        v_fts = vmca_vals_kias * 1.68781
        bank_rad = np.radians(bank_angles)
        omega_rad = g * np.tan(bank_rad) / v_fts
        turn_rates = np.degrees(omega_rad)

        # ✅ Clip to envelope before plotting
        envelope_mask = (vmca_vals_display >= corner_ias_display) & (vmca_vals_display <= max_speed_display)
        valid_mask = (turn_rates >= y_min) & (turn_rates <= y_max)
        vmca_vals_display = vmca_vals_display[valid_mask]
        turn_rates = turn_rates[valid_mask]

        fig.add_trace(go.Scatter(
            x=vmca_vals_display,
            y=turn_rates,
            mode="lines",
            name="Dynamic Vmc",
            line=dict(color="red", width=2.5, dash="dash"),
            hoverinfo="skip",
            showlegend=True
        ))

        if len(vmca_vals_display) > 0:
            fig.add_annotation(
                x=vmca_vals_display[-1],
                y=turn_rates[-1] + 2,
                text="Vmca ↑",
                showarrow=False,
                font=dict(size=10, color="red"),
                bgcolor="rgba(255,255,255,0.8)",
                xanchor="left"
            )

            first_vmca_display = vmca_vals_display[0]
            first_turn_rate = turn_rates[0]

            fig.add_trace(go.Scatter(
                x=[first_vmca_display],
                y=[first_turn_rate],
                mode="markers",
                marker=dict(color="red", size=8, symbol="circle"),
                name="Dynamic Vmca",
                showlegend=False,
                hoverinfo="skip"
            ))

            fig.add_annotation(
                x=first_vmca_display + 2,
                y=first_turn_rate,
                text=f"DVmc: {first_vmca_display:.0f} {unit}",
                showarrow=True,
                arrowhead=1,
                ax=40,
                ay=-20,
                font=dict(size=10, color="red"),
                bgcolor="rgba(255,255,255,0.8)",
                borderpad=3
            )
    # === Dynamic Vyse Marker and Curve ===
    if "dynamic_vyse" in all_overlays and ac.get("engine_count", 1) > 1 and oei_active:
        vyse_block = ac.get("single_engine_limits", {}).get("Vyse", {})
        if isinstance(vyse_block, dict):
            published_vyse = vyse_block.get("clean_up") or next(iter(vyse_block.values()), 100)
        else:
            published_vyse = vyse_block if isinstance(vyse_block, (int, float)) else 100
        reference_weight = ac.get("max_weight", 3600)

        # --- Sweep bank angle to visualize how Vyse performance changes with AOB
        bank_angles = np.linspace(5, 60, 120)
        vyse_curve = []

        for angle in bank_angles:
            angle_penalty = 1.0 + 0.003 * (angle - 5)
            vyse_val = calculate_dynamic_vyse(
                published_vyse=published_vyse,
                total_weight=weight,
                reference_weight=reference_weight,
                altitude_ft=altitude_ft,
                gear_position=gear,
                flap_config=config,
                prop_condition=prop_mode
            )
            vyse_curve.append(vyse_val * angle_penalty)

        vyse_curve = np.clip(vyse_curve, min(g_curve_x), max(g_curve_x))
        vyse_display_curve = convert_display_airspeed(np.array(vyse_curve), unit)

        v_fts = np.array(vyse_curve) * 1.68781
        bank_rad = np.radians(bank_angles)
        omega_rad = g * np.tan(bank_rad) / v_fts
        turn_rates = np.degrees(omega_rad)

        # ✅ NOW apply valid_mask after definitions
        envelope_mask = (vyse_display_curve >= corner_ias_display) & (vyse_display_curve <= max_speed_display)
        valid_mask = (turn_rates >= y_min) & (turn_rates <= y_max)
        vyse_display_curve = vyse_display_curve[valid_mask]
        turn_rates = turn_rates[valid_mask]

        # --- Plot
        fig.add_trace(go.Scatter(
            x=vyse_display_curve,
            y=turn_rates,
            mode="lines",
            name="Dynamic Vyse Curve",
            line=dict(color="deepskyblue", width=2, dash="dot"),
            hoverinfo="skip",
            showlegend=True
        ))

        if len(vyse_display_curve) > 0:
            first_vyse_display = vyse_display_curve[0]
            first_vyse_tr = turn_rates[0]
            x_max = max(x_max, first_vyse_display * 1.05)
            y_max = max(y_max, first_vyse_tr * 1.05)

            fig.add_trace(go.Scatter(
                x=[first_vyse_display],
                y=[first_vyse_tr],
                mode="markers",
                marker=dict(color="deepskyblue", size=8, symbol="circle"),
                name="Dynamic Vyse",
                showlegend=False,
                hoverinfo="skip"
            ))

            fig.add_annotation(
                x=first_vyse_display + 2,
                y=first_vyse_tr,
                text=f"DVyse: {first_vyse_display:.0f} {unit}",
                showarrow=True,
                arrowhead=2,
                ax=40,
                ay=-20,
                font=dict(size=10, color="deepskyblue"),
                bgcolor="rgba(255,255,255,0.8)",
                borderpad=3
            )    

    # --- Published Vyse Line ---
        # Published Vyse (Clipped)
        if oei_active and published_vyse:
            vyse_display = convert_display_airspeed(published_vyse, unit)

            vyse_y_top = np.interp(published_vyse, g_clipped_x, g_clipped_y) if g_clipped_x else 0
            vyse_y_bot = np.interp(published_vyse, neg_g_x_clip, neg_g_y_clip) if "negative_g" in overlay_toggle and 'neg_g_x_clip' in locals() else 0

            fig.add_trace(go.Scatter(
                x=[vyse_display, vyse_display],
                y=[0, vyse_y_top],
                mode="lines",
                name=f"Vyse ({vyse_display:.0f} {unit})",
                line=dict(color="#00BFFF", width=2, dash="dashdot"),
                hoverinfo="skip"
            ))

            fig.add_annotation(
                x=vyse_display,
                y=y_max * 0.95,
                text="Vyse",
                showarrow=False,
                font=dict(size=10, color="#00BFFF"),
                bgcolor="rgba(255,255,255,0.8)",
                xanchor="center"
            )

    # --- Published Vxse Line ---
    # Published Vxse (Clipped)
        vxse_block = ac.get("single_engine_limits", {}).get("Vxse", {})
        if isinstance(vxse_block, dict):
            published_vxse = vxse_block.get("clean_up") or next(iter(vxse_block.values()), None)
        else:
            published_vxse = vxse_block if isinstance(vxse_block, (int, float)) else None
        if oei_active and published_vxse:
            vxse_display = convert_display_airspeed(published_vxse, unit)

            vxse_y_top = np.interp(published_vxse, g_clipped_x, g_clipped_y) if g_clipped_x else 0
            vxse_y_bot = np.interp(published_vxse, neg_g_x_clip, neg_g_y_clip) if "negative_g" in overlay_toggle and 'neg_g_x_clip' in locals() else 0

            fig.add_trace(go.Scatter(
                x=[vxse_display, vxse_display],
                y=[0, vxse_y_top],
                mode="lines",
                name=f"Vxse ({vxse_display:.0f} {unit})",
                line=dict(color="#00CC66", width=2, dash="dash"),
                hoverinfo="skip"
            ))

            fig.add_annotation(
                x=vxse_display,
                y=y_max * 0.90,
                text="Vxse",
                showarrow=False,
                font=dict(size=10, color="#00CC66"),
                bgcolor="rgba(255,255,255,0.8)",
                xanchor="center"
            )
        
# --- Dynamic Hover Template ---
    hover_ias = []
    hover_tr = []
    hover_aob = []

    for i in range(len(tr_vals_ps)):
        for j in range(len(ias_vals_ps_internal)):
            if not np.isnan(Ps_masked[i, j]):
                ias = ias_vals_ps_internal[j]   # use internal value
                tr = tr_vals_ps[i]
                v_fts = ias * 1.68781
                omega_rad = tr * (np.pi / 180)
                aob_deg = np.degrees(np.arctan(omega_rad * v_fts / g))

                display_ias = convert_display_airspeed(ias, unit)  # convert only for x-axis display
                hover_ias.append(display_ias)
                hover_tr.append(tr)
                hover_aob.append(aob_deg)

    # Determine hover template
    if "aob" in overlay_toggle:
        hovertemplate=f"IAS: %{{x:.0f}} {unit}<br>Turn Rate: %{{y:.0f}}°/s<br>AOB: %{{customdata:.0f}}°<extra></extra>"
        
        
        fig.add_trace(go.Scatter(
            x=hover_ias,
            y=hover_tr,
            customdata=np.array(hover_aob),
            mode="markers",
            marker=dict(size=6, color="rgba(0,0,0,0)"),
            hovertemplate=hovertemplate,
            name="",
            showlegend=False
        ))
    else:
        fig.add_trace(go.Scatter(
            x=hover_ias,
            y=hover_tr,
            mode="markers",
            marker=dict(size=6, color="rgba(0,0,0,0)"),
            hovertemplate=f"IAS: %{{x:.0f}} {unit}<br>Turn Rate: %{{y:.0f}}°/s<extra></extra>",
            name="",
            showlegend=False
        ))

    # --- Ps Plotting (Toggle Controlled) ---

    if "ps" in overlay_toggle:
        try:
            ps_min = int(np.floor(np.nanmin(Ps_masked) / 10.0)) * 10
            ps_max = int(np.ceil(np.nanmax(Ps_masked) / 10.0)) * 10
            ps_levels = list(range(ps_min, ps_max + 1, 10))
        
            fig.add_trace(go.Contour(
                x=ias_vals_ps_display,
                y=tr_vals_ps,
                z=Ps_masked,
                contours=dict(
                    coloring="none", showlabels=False,
                    start=ps_min, end=ps_max, size=10
                ),
                line=dict(width=1, color="gray", dash="dot"),
                connectgaps=False,
                showscale=False,
                hoverinfo="skip",
                name="Ps"
            ))

            # Bold Ps = 0 overlay
            if 0 in ps_levels:
                fig.add_trace(go.Contour(
                    x=ias_vals_ps_display,
                    y=tr_vals_ps,
                    z=Ps_masked,
                    contours=dict(
                        coloring="none", showlabels=False,
                        start=0, end=0, size=1
                    ),
                    line=dict(width=3, color="gray", dash="dot"),
                    connectgaps=False,
                    showscale=False,
                    hoverinfo="skip",
                    showlegend=False
                ))

            # Ps labels (anchor left side of envelope)
            for level in ps_levels:
                found = False
                for j in range(len(ias_vals_ps_display)):
                    for i in range(len(tr_vals_ps)):
                        ps_val = Ps_masked[i, j]
                        if np.isnan(ps_val):
                            continue
                        if np.isclose(ps_val, level, atol=2):
                            fig.add_annotation(
                                x=ias_vals_ps_display[j] + 3,
                                y=tr_vals_ps[i],
                                text=f"{level}",
                                showarrow=False,
                                font=dict(color="gray", size=10),
                                bgcolor="rgba(255,255,255,0.6)",
                                borderpad=1,
                            )
                            found = True
                            break
                    if found:
                        break
        except Exception as e:
            dprint(f"[DEBUG] Ps toggle failed: {e}")


        ###---Vmc published line----###

        if ac.get("engine_count", 1) > 1 and "enabled" in oei_toggle:
            vmca = ac.get("single_engine_limits", {}).get("Vmca", None)

            # Handle new-style dict Vmca format
            if isinstance(vmca, dict):
                # Choose the config to display (default to "clean_up" if available)
                selected_config = "clean_up" if "clean_up" in vmca else next(iter(vmca), None)
                vmca_value = vmca.get(selected_config)
            else:
                # Fallback if older float-style Vmca
                vmca_value = vmca

            if isinstance(vmca_value, (int, float)):
                vmca_converted = convert_display_airspeed(vmca_value, unit)

                fig.add_trace(go.Scatter(
                    x=[vmca_converted, vmca_converted],
                    y=[0, y_max],
                    mode="lines",
                    name=f"Vmca ({int(vmca_converted)} {unit})",
                    line=dict(color="red", width=2, dash="dash"),
                    hoverinfo="skip"
                ))

                fig.add_annotation(
                    x=vmca_converted,
                    y=y_max * 0.90,
                    text="Vmca",
                    showarrow=False,
                    font=dict(size=10, color="red"),
                    bgcolor="rgba(255,255,255,0.8)",
                    xanchor="center"
                )
 
    
    # Final layout and return (outside toggle block!)
    x_min = max(0, min(ias_vals_display) - 2)  # two knot padding below ias_start
    x_max = max_speed_display * 1.1

# ✅ Final Y-Axis Limits Based on All Plotted TR Values
    turn_rate_values = []
    if stall_clipped_y: turn_rate_values += stall_clipped_y
    if g_clipped_y: turn_rate_values += g_clipped_y
    if "negative_g" in overlay_toggle:
        if 'neg_stall_y_clip' in locals(): turn_rate_values += neg_stall_y_clip
        if 'neg_g_y_clip' in locals(): turn_rate_values += neg_g_y_clip
    if "dynamic_vyse" in all_overlays and 'turn_rates' in locals():
        turn_rate_values += list(turn_rates)

    if turn_rate_values:
        y_max = max(turn_rate_values) * 1.1
        y_min = min(turn_rate_values) * 1.1 if min(turn_rate_values) < 0 else 0
    else:
        y_max = 100
        y_min = 0

    is_mobile = screen_width and screen_width < 768

    legend_font_size = 10 if is_mobile else 12
    
        # Format into title (HTML-style for multi-line)
    fig.update_layout(
        title=dict(
            text=f"<b>{ac_name}</b>" if not is_mobile else ac_name,
            font=dict(size=22 if not is_mobile else 14, color="#005F8C"),
            x=0.5,
            y=0.95,
            xanchor="center",
            yanchor="top"
        ),
        xaxis=dict(
            title=f"Indicated Airspeed ({unit})",
            title_font=dict(size=14 if not is_mobile else 10),
            tickfont=dict(size=12 if not is_mobile else 9),
            dtick=10,
            range=[x_min, x_max],
            showgrid=True,
            showspikes=False,
            spikemode="across",
            spikesnap="cursor"
        ),
        yaxis=dict(
            title="Turn Rate (deg/sec)",
            title_font=dict(size=14 if not is_mobile else 10),
            tickfont=dict(size=12 if not is_mobile else 9),
            dtick=5,
            range=[y_min, y_max],
            showgrid=True,
            showspikes=False,
            spikemode="across",
            spikesnap="cursor"
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.25,  # Push legend below x-axis
            xanchor="center",
            x=0.5,
            font=dict(size=legend_font_size)
        ),
        margin=dict(
            t=60 if is_mobile else 100,
            b=100 if is_mobile else 80,
            l=40,
            r=40
        ),
        paper_bgcolor="#f7f9fc",
        plot_bgcolor="#f7f9fc",
        font=dict(color="#1b1e23"),
        hovermode="closest"
    )
    # === STEEP TURN MANEUVER TRACE ===
    if aob_values and ias_values and len(aob_values) > 0 and len(ias_values) > 0:
        aob_input = aob_values[0]
        ias_input = ias_values[0]

        v_fts = ias_input * 1.68781
        bank_rad = np.radians(aob_input)
        tr_deg = np.degrees(32.174 * np.tan(bank_rad) / v_fts)

        # --- Energy Rate (Ps) at this point ---
        n = 1 / np.cos(bank_rad)  # load factor for level constant altitude turn
        q = 0.5 * rho * v_fts ** 2
        CL = weight * n / (q * wing_area)
        CD = CD0 + (CL ** 2) / (np.pi * e * AR)
        D = q * wing_area * CD

        # Apply prop thrust model (same as Ps logic)
        V_max_kts = ac.get("prop_thrust_decay", {}).get("V_max_kts", 160)
        T_static = ac.get("prop_thrust_decay", {}).get("T_static_factor", 2.6) * hp
        V_fraction = np.clip(ias_input / V_max_kts, 0, 1)
        T_avail = T_static * (1 - V_fraction**2)

        gamma_rad = np.radians(pitch_angle)
        Ps_steep = ((T_avail - D) * v_fts / weight - g * np.sin(gamma_rad)) / 1.68781

        dprint("[STEEP TURN DEBUG]")
        dprint(f"  IAS: {ias_input} KIAS, AOB: {aob_input}°")
        dprint(f"  Turn Rate: {tr_deg:.1f}°/s")
        dprint(f"  Ps: {Ps_steep:.2f} knots/sec")

        arc_tr = [0.0, tr_deg, tr_deg, 0.0, 0.0]
        arc_ias = [ias_input] * len(arc_tr)
        arc_ias_display = [ias * 1.15078 if unit == "MPH" else ias for ias in arc_ias]

        fig.add_trace(go.Scatter(
            x=arc_ias_display,
            y=arc_tr,
            mode="lines+markers",
            line=dict(color="darkgreen", width=3),
            marker=dict(size=6),
            name="Steep Turn",
            hoverinfo="text",
            hovertext=[
                f"AOB: {aob_input}°<br>IAS: {ias_input} {unit}<br>Turn Rate: {tr:.1f}°/s<br>Ps: {Ps_steep:.1f}"
                for tr in arc_tr
            ],
            showlegend=True
        ))
    #------Ghost Trace------#
# === GHOST TRACE (Ideal AOB)
    if ghost_mode_values and ghost_mode_values[0] != "off":
        ghost_aob = 45 if ghost_mode_values[0] == "private" else 50
        ghost_ias = ias_values[0] if ias_values else 110  # fallback if none provided

        v_fts = ghost_ias * 1.68781
        bank_rad = np.radians(ghost_aob)
        ghost_tr = np.degrees(32.174 * np.tan(bank_rad) / v_fts)

        ghost_tr_array = [0.0, ghost_tr, ghost_tr, 0.0, 0.0]
        ghost_ias_array = [ghost_ias] * len(ghost_tr_array)
        ghost_ias_display = [ias * 1.15078 if unit == "MPH" else ias for ias in ghost_ias_array]

        fig.add_trace(go.Scatter(
            x=ghost_ias_display,
            y=ghost_tr_array,
            mode="lines",
            line=dict(color="white", width=2, dash="dot"),
            name=f"Ideal ({ghost_aob}°)",
            hoverinfo="skip",
            showlegend=True
        ))
        fig.add_trace(go.Scatter(
            x=[ghost_ias_display[1]],
            y=[ghost_tr_array[1]],
            mode="markers",
            marker=dict(color="white", size=7, symbol="circle"),
            name="",
            hoverinfo="skip",
            showlegend=False
        ))
        
# === CHANDELLE MANEUVER TRACE ===
    def plot_chandelle(
        fig,
        chandelle_ias_start,
        chandelle_bank,
        stall_ias_kias,
        unit,
        color="darkgreen",
        dash="solid",
        label="Chandelle"
    ):
        from plotly.graph_objects import Scatter
        from math import radians, tan, degrees

        g = 32.174
        v_start = chandelle_ias_start * 1.68781  # ft/s
        v_end = (stall_ias_kias + 5) * 1.68781   # ft/s
        delta_v = v_start - v_end

        # Airspeed lost more aggressively with higher AOB
        energy_bias = min(0.8, max(0.5, chandelle_bank / 60))  # realistic range: 0.5–0.8
        v_90 = v_start - (delta_v * energy_bias)

        dt = 0.1
        max_turn_deg = 180.0
        angle = 0.0
        steps = 0
        max_steps = 1000

        airspeeds = []
        turn_rates = []

        while angle < max_turn_deg and steps < max_steps:
            if angle <= 90:
                # First half: lose 'energy_bias' fraction of Δv by 90°
                v = v_start - ((angle / 90.0) * (delta_v * energy_bias))
                aob_deg = chandelle_bank
            else:
                # Second half: lose remaining Δv after 90°, reduce AOB 1° per 3° turn
                v = v_90 - (((angle - 90) / 90.0) * (delta_v * (1 - energy_bias)))
                aob_deg = max(0, chandelle_bank - ((angle - 90) / 3.0))

            v = max(v, v_end)  # Never dip below final airspeed
            aob_rad = radians(aob_deg)
            omega_rad = g * tan(aob_rad) / v
            tr = degrees(omega_rad)

            airspeeds.append(v / 1.68781)
            turn_rates.append(tr)

            angle += tr * dt
            steps += 1

        if not airspeeds:
            dprint("[WARN] No chandelle points generated.")
            return fig

        airspeeds_display = [ias * 1.15078 if unit == "MPH" else ias for ias in airspeeds]

        fig.add_trace(Scatter(
            x=airspeeds_display,
            y=turn_rates,
            mode="lines+markers",
            line=dict(color=color, width=3, dash=dash),
            marker=dict(size=6),
            name=label,
            hoverinfo="text",
            hovertext=[
                f"IAS: {ias:.1f} {unit}<br>Turn Rate: {tr:.1f}°/s<br>AOB: {aob:.1f}°"
                for ias, tr, aob in zip(airspeeds_display, turn_rates, [chandelle_bank if angle <= 90 else max(0, chandelle_bank - ((angle - 90) / 3)) for angle in np.linspace(0, 180, len(turn_rates))])
            ]
        ))

        return fig

    if maneuver == "chandelle" and chandelle_ias_values and chandelle_bank_values:
        chandelle_ias = chandelle_ias_values[0]
        chandelle_bank = chandelle_bank_values[0]
        # Compute dynamic stall speed at 1G level turn
        v_stall_1g = np.sqrt((2 * weight) / (rho * wing_area * cl_max)) / 1.68781
        stall_ias_kias = v_stall_1g

        fig = plot_chandelle(
            fig,
            chandelle_ias_start=chandelle_ias,
            chandelle_bank=chandelle_bank,
            stall_ias_kias=stall_ias_kias,
            unit=unit,
            color="darkgreen",
            dash="solid",
            label="Chandelle"
        )

        if chandelle_ghost_values and chandelle_ghost_values[0] == "on":
            fig = plot_chandelle(
                fig,
                chandelle_ias_start=chandelle_ias,
                chandelle_bank=30,
                stall_ias_kias=stall_ias_kias,
                unit=unit,
                color="white",
                dash="dot",
                label="Chandelle Ghost"
            )

    fig.add_annotation(
        text="© 2025 Nicholas Len, AEROEDGE. All rights reserved.<br>Not FAA-approved. For educational and reference use only.",
        xref="paper", yref="paper",
        x=0.5, y=-0.15,
        xanchor="center", yanchor="top",
        showarrow=False,
        font=dict(size=9, color="gray"),
        align="center",
        name="png-only-disclaimer"
    )
    t_end = time.perf_counter()
    dprint(f"[PERF] update_graph total: {(t_end - t_start):.3f} sec")
    
    return fig

import tempfile
import plotly.io as pio
from dash import ctx, State
from dash.dcc import send_file
import re

@app.callback(
    Output("maneuver-options-container", "children"),
    Input("maneuver-select", "value")
)
def render_maneuver_options(maneuver):
    if maneuver == "steep_turn":
        return html.Div([
            html.Div([
                html.Label("Angle of Bank (°)", style={"marginLeft": "10px"}),
                dcc.Slider(
                    id={"type": "steepturn-aob", "index": 0},
                    min=10,
                    max=90,
                    step=5,
                    value=45,
                    marks={i: f"{i}°" for i in range(10, 91, 10)},
                    tooltip={"always_visible": True},
                    included=False,
                )
            ], style={"display": "inline-block", "width": "300px", "marginRight": "30px"}),

            html.Div([
                html.Label("Ghost Trace"),
                dcc.RadioItems(
                    id={"type": "steepturn-ghost", "index": 0},
                    options=[
                        {"label": "Off", "value": "off"},
                        {"label": "Private (45°)", "value": "private"},
                        {"label": "Commercial (50°)", "value": "commercial"},
                    ],
                    value="off",
                    labelStyle={"display": "inline-block", "marginRight": "15px"}
                )
            ], style={"display": "inline-block", "verticalAlign": "top"}),

            html.Div([
                html.Label("Airspeed (KIAS)", style={"marginLeft": "10px"}),
                dcc.Input(
                    id={"type": "steepturn-ias", "index": 0},
                    type="number",
                    value=110,
                    min=40,
                    max=200,
                    step=1,
                    style={"width": "80px", "marginLeft": "10px"}
                )
            ], style={"marginTop": "10px"})
        ])
    elif maneuver == "chandelle":
        return html.Div([
            dbc.Row([
                dbc.Col([
                    html.Label("Initial Airspeed (KIAS)", className="input-label"),
                    dcc.Input(
                        id={"type": "chandelle-ias", "index": 0},
                        type="number",
                        value=105,
                        min=40,
                        max=200,
                        step=1,
                        style={"width": "100px"}
                    )
                ], width="auto")
            ], className="mb-3"),

            dbc.Row([
                dbc.Col([
                    html.Label("Initial Bank (°)", className="input-label"),
                    dcc.Slider(
                        id={"type": "chandelle-bank", "index": 0},
                        min=10,
                        max=45,
                        step=1,
                        value=30,
                        marks={i: f"{i}°" for i in range(10, 46, 5)},
                        tooltip={"always_visible": True},
                        included=False
                    )
                ])
            ], className="mb-3"),

            dbc.Row([
                dbc.Col([
                    html.Label("Show Ghost Trace", className="input-label"),
                    dcc.RadioItems(
                        id={"type": "chandelle-ghost", "index": 0},
                        options=[
                            {"label": "Off", "value": "off"},
                            {"label": "On", "value": "on"}
                        ],
                        value="on",
                        inline=True,
                        labelStyle={"marginRight": "15px"}
                    )
                ])
            ])
        ])

def get_summary_text(ac_name, engine_name, config, gear, occupants, fuel, total_weight, power_fraction, altitude):
    return (
        f"Aircraft: {ac_name}\n"
        f"Engine: {engine_name}\n"
        f"Flap Configuration: {config}\n"
        f"Gear: {gear if gear else 'N/A'}\n"
        f"Occupants: {occupants}\n"
        f"Fuel: {fuel} gal\n"
        f"Power: {int(power_fraction * 100)}%\n"
        f"Altitude: {altitude} ft\n"
        f"Total Weight: {int(total_weight)} lbs"
    )



###----Generate PDF-----####

@app.callback(
    Output("pdf-download", "data"),
    Input("pdf-button", "n_clicks"),
    Input("em-graph", "figure"),
    State("aircraft-select", "value"),
    State("engine-select", "value"),
    State("config-select", "value"),
    State("gear-select", "value"),
    State("occupants-select", "value"),
    State("passenger-weight-input", "value"),
    State("fuel-slider", "value"),
    State("stored-total-weight", "data"),
    State("power-setting", "value"),
    State("altitude-slider", "value"),
    State("pitch-angle", "value"),
    State("oei-toggle", "value"),
    State("prop-condition", "value"),
    State("maneuver-select", "value"),
    prevent_initial_call=True
)
def generate_pdf(n_clicks, fig_data, ac_name, engine_name, config, gear, occupants, pax_weight, fuel, total_weight,
                 power_fraction, altitude, pitch, oei_toggle, prop_condition, maneuver):
    if ctx.triggered_id != "pdf-button":
        return dash.no_update

    fig = go.Figure(fig_data)
    


    # ✅ Add Logo (logo2.png in top-left)
    try:
        logo_path = os.path.join("assets", "logo2.png")
        if os.path.exists(logo_path):
            from PIL import Image
            logo_img = Image.open(logo_path)
            fig.add_layout_image(
                dict(
                    source=logo_img,
                    xref="paper", yref="paper",
                    x=-0.05, y=1.25,
                    sizex=0.25, sizey=0.25,
                    xanchor="left", yanchor="top",
                    layer="above"
                )
            )
    except Exception as e:
        dprint(f"[LOGO WARNING] Failed to add logo2.png: {e}")

    # ✅ Summary Text
    oei_status = "YES" if oei_toggle and "enabled" in oei_toggle else "NO"
    maneuver_text = f"Maneuver: {maneuver}" if maneuver else ""

    summary_lines = [
        f"Engine: {engine_name} | Category: {config} | Gear: {gear}",
        f"Occupants: {occupants} x {pax_weight or 180} lbs | Fuel: {fuel} gal",
        f"Power: {int(power_fraction * 100)}% | Altitude: {altitude} ft | Pitch: {pitch}°",
        f"Total Weight: {int(total_weight)} lbs | OEI: {oei_status}",
        f"Prop Condition: {prop_condition if oei_status == 'YES' else 'N/A'}",
        maneuver_text
    ]

    fig.add_annotation(
        text="<br>".join(summary_lines),
        xref="paper", yref="paper",
        x=0.5, y=1.01,
        xanchor="center", yanchor="bottom",
        showarrow=False,
        font=dict(size=10, color="#1b1e23"),
        align="center"
    )

    # ✅ Footer
    fig.add_annotation(
        text="© 2025 Nicholas Len, AEROEDGE. All rights reserved.<br>Not FAA-approved. For educational and reference use only.",
        xref="paper", yref="paper",
        x=0.5, y=-0.15,  # x=0.5 centers it; adjust y to avoid x-axis overlap
        xanchor="center", yanchor="top",
        showarrow=False,
        font=dict(size=9, color="gray"),
        align="center"
    )
    # ✅ Clean layout margin
    fig.update_layout(margin=dict(t=160, b=80))

    # ✅ Save PDF to temp and return
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pio.write_image(fig, tmp.name, format="pdf", width=1100, height=800)
        return send_file(tmp.name, filename="EMdiagram.pdf")
    
# When you click "Edit / Create Aircraft"
@app.callback(
    Output("url", "pathname"),
    Input("edit-aircraft-button", "n_clicks"),
    prevent_initial_call=True
)
def go_to_edit_page(n_clicks):
    if n_clicks:
        return "/edit-aircraft"
    raise PreventUpdate

@app.callback(
    Output("url", "pathname", allow_duplicate=True),
    Input("back-button", "n_clicks"),
    prevent_initial_call=True
)
def go_to_main_page(n_clicks):
    if n_clicks:
        return "/"
    raise PreventUpdate

@app.callback(
    Output("aircraft-select", "value", allow_duplicate=True),
    Input("url", "pathname"),
    State("last-saved-aircraft", "data"),
    prevent_initial_call=True
)
def load_last_saved_on_nav(path, last_saved):
    if path == "/" and last_saved:
        return last_saved
    raise PreventUpdate

@app.callback(
    Output("browser-width", "data"),
    Input("url", "pathname")
)
def get_browser_width(_):
    import flask
    try:
        width = flask.request.headers.get('User-Agent')
        return width
    except:
        return "unknown"



@app.callback(
    [
        Output("aircraft-name", "value"),
        Output("aircraft-type", "value"),
        Output("gear-type", "value"),
        Output("engine-count", "value"),
        Output("wing-area", "value"),
        Output("aspect-ratio", "value"),
        Output("cd0", "value"),
        Output("oswald-efficiency", "value"),
        Output("stored-flap-configs", "data"),
        Output("stored-g-limits", "data"),
        Output("g-limits-container", "children"),
        Output("stored-stall-speeds", "data"),
        Output("stall-speeds-container", "children"),
        Output("stored-single-engine-limits", "data"),
        Output("stored-engine-options", "data"),
        Output("engine-options-container", "children"),
        Output("empty-weight", "value"),
        Output("max-weight", "value"),
        Output("best-glide", "value"),
        Output("best-glide-ratio", "value"),
        Output("seats", "value"),
        Output("cg-fwd", "value"),
        Output("cg-aft", "value"),
        Output({"type": "vfe-input", "config": "takeoff"}, "value"),
        Output({"type": "vfe-input", "config": "landing"}, "value"),
        Output({"type": "clmax-input", "config": "clean"}, "value"),
        Output({"type": "clmax-input", "config": "takeoff"}, "value"),
        Output({"type": "clmax-input", "config": "landing"}, "value"),
        Output("fuel-capacity-gal", "value"),
        Output("fuel-weight-per-gal", "value"),
        Output("arc-white-bottom", "value"),
        Output("arc-white-top", "value"),
        Output("arc-green-bottom", "value"),
        Output("arc-green-top", "value"),
        Output("arc-yellow-bottom", "value"),
        Output("arc-yellow-top", "value"),
        Output("arc-red", "value"),
        Output("prop-static-factor", "value"),
        Output("prop-vmax-kts", "value"),
        Output("stored-oei-performance", "data"),
        Output("max-altitude", "value"),
        Output("vne", "value"),
        Output("vno", "value"),
        Output("search-result", "children", allow_duplicate=True),
    ],
    Input("aircraft-search", "value"),
    prevent_initial_call=True,
)
def load_aircraft_full(selected_name):
    if not selected_name or selected_name not in aircraft_data:
        raise PreventUpdate

    ac = aircraft_data[selected_name]
    
    stored_flap_configs = ac.get("configuration_options", {}).get("flaps", [])

    stored_g_limits = []
    for category, configs in ac.get("G_limits", {}).items():
        for config_name, values in configs.items():
            if isinstance(values, dict):  # new format
                stored_g_limits.append({
                    "category": category,
                    "config": config_name,
                    "positive": values.get("positive"),
                    "negative": values.get("negative")
                })
            else:  # old format fallback (single float)
                stored_g_limits.append({
                    "category": category,
                    "config": config_name,
                    "positive": values,
                    "negative": None
                })

    # --- Stall Speeds
    stored_stall_speeds = []
    stall_data = ac.get("stall_speeds", {})
    for config_name, config_data in stall_data.items():
        weights = config_data.get("weights", [])
        speeds = config_data.get("speeds", [])
        for w, s in zip(weights, speeds):
            stored_stall_speeds.append({
                "config": config_name,
                "gear": "up",
                "weight": w,
                "speed": s
            })

    # --- Single Engine Limits
    stored_single_engine_limits = []

    # Only populate if aircraft has more than 1 engine
    if ac.get("engine_count", 1) >= 2:
        se_data = ac.get("single_engine_limits", {})
        for limit_type, values in se_data.items():
            if limit_type not in ("Vmca", "Vyse", "Vxse"):
                continue  # 🔧 Skip best_glide, best_glide_ratio, etc.

            if isinstance(values, dict):
                for config_key, val in values.items():
                    parts = config_key.split("_")
                    flap = parts[0] if len(parts) > 0 else ""
                    gear = parts[1] if len(parts) > 1 else ""
                    stored_single_engine_limits.append({
                        "limit_type": limit_type,
                        "value": val,
                        "flap_config": flap,
                        "gear_config": gear
                    })
            else:
                stored_single_engine_limits.append({
                    "limit_type": limit_type,
                    "value": values,
                    "flap_config": "",
                    "gear_config": ""
                })

            
    # --- Engine Options
    stored_engine_options = []
    for eng_name, eng_info in ac.get("engine_options", {}).items():
        power = eng_info.get("power_curve", {})
        stored_engine_options.append({
            "name": eng_name,
            "horsepower": eng_info.get("horsepower"),
            "power_curve_sea_level": power.get("sea_level_max"),
            "power_curve_derate": power.get("derate_per_1000ft"),
        })


    # --- Populate text inputs
    aircraft_name = selected_name
    wing_area = ac.get("wing_area")
    aspect_ratio = ac.get("aspect_ratio")
    cd0 = ac.get("CD0")
    oswald = ac.get("e")

    # --- Populate G Limits
    g_limits = ac.get("G_limits", {})
    g_limit_fields = [
        dcc.Textarea(
            id="g-limits",
            value=json.dumps(g_limits, indent=2),
            style={"width": "400px", "height": "200px"},
        )
    ]

    # --- Populate Stall Speeds
    stall_speeds = list(ac.get("stall_speeds", {}).keys())
    stall_speed_fields = [
        dcc.Textarea(
            id="stall-speeds",
            value=json.dumps(stall_speeds, indent=2),
            style={"width": "400px", "height": "200px"},
        )
    ]


    # --- Populate Engine Options
    engine_options = ac.get("engine_options", {})
    engine_fields = [
        dcc.Textarea(
            id="engine-options",
            value=json.dumps(engine_options, indent=2),
            style={"width": "400px", "height": "200px"},
        )
    ]


    
    
    # --- Flap CLmax and Vfe (Standardized)
    clmax_data = ac.get("CL_max", {})
    vfe_data = ac.get("Vfe", {})
    
    vfe_clean = ac.get("Vfe", {}).get("clean", None)
    vfe_takeoff = ac.get("Vfe", {}).get("takeoff", None)
    vfe_landing = ac.get("Vfe", {}).get("landing", None)

    clmax_clean = ac.get("CL_max", {}).get("clean", None)
    clmax_takeoff = ac.get("CL_max", {}).get("takeoff", None)
    clmax_landing = ac.get("CL_max", {}).get("landing", None)

    # --- Prop Thrust Decay
    prop_decay = ac.get("prop_thrust_decay", {})
    t_static = prop_decay.get("T_static_factor")
    v_max_kts = prop_decay.get("V_max_kts")

    # --- Fuel
    fuel_capacity = ac.get("fuel_capacity_gal")
    fuel_weight = ac.get("fuel_weight_per_gal")

    # --- Airspeed Arcs
    arcs = ac.get("arcs", {})
    white_bottom, white_top = (arcs.get("white", [None, None]) + [None, None])[:2]
    green_bottom, green_top = (arcs.get("green", [None, None]) + [None, None])[:2]
    yellow_bottom, yellow_top = (arcs.get("yellow", [None, None]) + [None, None])[:2]
    red = arcs.get("red")

    # --- Service Ceiling
    max_altitude = next(iter(ac.get("engine_options", {}).values()), {}).get("power_curve", {}).get("max_altitude", None)

    # --- Flatten OEI Performance
    oei_flat = []
    for eng_name, eng_data in ac.get("engine_options", {}).items():
        for config_key, config_data in eng_data.get("oei_performance", {}).items():
            for prop_condition, values in config_data.items():
                oei_flat.append({
                    "engine": eng_name,
                    "config_key": config_key,
                    "prop_condition": prop_condition,
                    "max_power_fraction": values.get("max_power_fraction"),
                })
    
    # --- Return everything
    return (
        selected_name,  # aircraft-name
        ac.get("type"),
        ac.get("gear_type", "fixed"),
        ac.get("engine_count"),
        ac.get("wing_area"),  # wing-area
        ac.get("aspect_ratio"),  # aspect-ratio
        ac.get("CD0"),  # cd0
        ac.get("e"),  # oswald-efficiency
        stored_flap_configs,  # stored-flap-configs
        stored_g_limits,  # stored-g-limits
        g_limit_fields,  # g-limits-container
        stored_stall_speeds,  # stored-stall-speeds
        stall_speed_fields,  # stall-speeds-container
        stored_single_engine_limits,  # stored-single-engine-limits
        stored_engine_options,  # stored-engine-options
        engine_fields,  # engine-options-container
        ac.get("empty_weight"),  # empty-weight
        ac.get("max_weight"),
        ac.get("single_engine_limits", {}).get("best_glide"),
        ac.get("single_engine_limits", {}).get("best_glide_ratio"),
        ac.get("seats"),  # seats
        ac.get("cg_range", [None, None])[0],  # cg-fwd
        ac.get("cg_range", [None, None])[1],  # cg-aft
        ac.get("Vfe", {}).get("takeoff"),  # vfe-input (takeoff)
        ac.get("Vfe", {}).get("landing"),  # vfe-input (landing)
        ac.get("CL_max", {}).get("clean"),  # clmax-input (clean)
        ac.get("CL_max", {}).get("takeoff"),  # clmax-input (takeoff)
        ac.get("CL_max", {}).get("landing"),  # clmax-input (landing)
        ac.get("fuel_capacity_gal"),  # fuel-capacity-gal
        ac.get("fuel_weight_per_gal"),  # fuel-weight-per-gal
        ac.get("arcs", {}).get("white", [None, None])[0],  # arc-white-bottom
        ac.get("arcs", {}).get("white", [None, None])[1],  # arc-white-top
        ac.get("arcs", {}).get("green", [None, None])[0],  # arc-green-bottom
        ac.get("arcs", {}).get("green", [None, None])[1],  # arc-green-top
        ac.get("arcs", {}).get("yellow", [None, None])[0],  # arc-yellow-bottom
        ac.get("arcs", {}).get("yellow", [None, None])[1],  # arc-yellow-top
        ac.get("arcs", {}).get("red"),  # arc-red
        ac.get("prop_thrust_decay", {}).get("T_static_factor"),  # prop-static-factor
        ac.get("prop_thrust_decay", {}).get("V_max_kts"),  # prop-vmax-kts
        oei_flat,  # stored-oei-performance
        ac.get("max_altitude"),
        ac.get("Vne"),  # vne
        ac.get("Vno"),  # vno
        f"✅ Loaded: {selected_name}",  # search-result
    )

@app.callback(
    Output("cd0", "value", allow_duplicate=True),
    Output("oswald-efficiency", "value", allow_duplicate=True),
    Output("prop-static-factor", "value", allow_duplicate=True),
    Output("prop-vmax-kts", "value", allow_duplicate=True),
    Output("fuel-weight-per-gal", "value", allow_duplicate=True),
    Output("stored-engine-options", "data", allow_duplicate=True),
    Output("stored-flap-configs", "data", allow_duplicate=True),
    Output("stored-oei-performance", "data", allow_duplicate=True),
    Output({"type": "clmax-input", "config": "clean"}, "value", allow_duplicate=True),
    Output({"type": "clmax-input", "config": "takeoff"}, "value", allow_duplicate=True),
    Output({"type": "clmax-input", "config": "landing"}, "value", allow_duplicate=True),
    Input("default-single", "n_clicks"),
    Input("default-multi", "n_clicks"),
    Input("default-aerobatic", "n_clicks"),
    Input("default-trainer", "n_clicks"),
    Input("default-mil-trainer", "n_clicks"),
    Input("default-experimental", "n_clicks"),
    State("stored-flap-configs", "data"),
    State("stored-oei-performance", "data"),
    State("engine-count", "value"),
    prevent_initial_call=True
)
def apply_default_performance(single, multi, aero, trainer, mil, exp, flap_data, oei_data, engine_count):
    triggered = ctx.triggered_id

    if triggered == "default-single":
        cd0, e, t_static, vmax, fuel_wt = 0.025, 0.80, 2.6, 160, 6.0
        engine = {
            "name": "Lycoming O-320",
            "horsepower": 150,
            "power_curve_sea_level": 150,
            "power_curve_derate": 0.03
        }
        clmax = {"clean": 1.4, "takeoff": 1.7, "landing": 2.0}

    elif triggered == "default-multi":
        cd0, e, t_static, vmax, fuel_wt = 0.028, 0.82, 2.6, 180, 6.0
        engine = {
            "name": "Lycoming TIO-540",
            "horsepower": 220,
            "power_curve_sea_level": 220,
            "power_curve_derate": 0.035
        }
        clmax = {"clean": 1.3, "takeoff": 1.6, "landing": 2.0}

    elif triggered == "default-aerobatic":
        cd0, e, t_static, vmax, fuel_wt = 0.030, 0.75, 2.6, 200, 6.0
        engine = {
            "name": "Lycoming AEIO-360",
            "horsepower": 200,
            "power_curve_sea_level": 200,
            "power_curve_derate": 0.03
        }
        clmax = {"clean": 1.6, "takeoff": 1.8, "landing": 2.2}

    elif triggered == "default-trainer":
        cd0, e, t_static, vmax, fuel_wt = 0.027, 0.78, 2.6, 140, 6.0        
        engine = {
            "name": "Continental O-200",
            "horsepower": 100,
            "power_curve_sea_level": 100,
            "power_curve_derate": 0.03
        }
        clmax = {"clean": 1.3, "takeoff": 1.6, "landing": 2.0}

    elif triggered == "default-mil-trainer":
        cd0, e, t_static, vmax, fuel_wt = 0.030, 0.72, 2.6, 300, 6.7        
        engine = {
            "name": "Pratt & Whitney R-1340",
            "horsepower": 600,
            "power_curve_sea_level": 600,
            "power_curve_derate": 0.02
        }
        clmax = {"clean": 1.4, "takeoff": 1.6, "landing": 2.2}

    elif triggered == "default-experimental":
        cd0, e, t_static, vmax, fuel_wt = 0.026, 0.80, 2.6, 180, 6.0        
        engine = {
            "name": "Rotax 912 ULS",
            "horsepower": 100,
            "power_curve_sea_level": 100,
            "power_curve_derate": 0.03
        }
        clmax = {"clean": 1.4, "takeoff": 1.7, "landing": 2.1}

    else:
        raise PreventUpdate

    # One engine entry only
    updated_engines = [engine]

    # Update flap configs (set clmax if not present)
    updated_flaps = []
    for f in ["clean", "takeoff", "landing"]:
        updated_flaps.append({"name": f, "clmax": clmax[f]})

    # OEI logic (only for multi)
    if (engine_count and engine_count >= 2) or triggered == "default-multi":
        updated_oei = [
            {"config": "clean_up", "prop_condition": "stationary", "max_power_fraction": 0.5},
            {"config": "clean_up", "prop_condition": "windmilling", "max_power_fraction": 0.5},
            {"config": "clean_up", "prop_condition": "normal", "max_power_fraction": 0.5}
        ]
    else:
        updated_oei = dash.no_update

    return (
        cd0, e, t_static, vmax, fuel_wt,
        updated_engines,
        updated_flaps,
        updated_oei,
        clmax["clean"], clmax["takeoff"], clmax["landing"]
    )

# ---- G LIMITS ----

import copy
from dash import ctx

# === G LIMITS SECTION ===

@app.callback(
    Output("stored-g-limits", "data", allow_duplicate=True),
    Input("add-g-limit", "n_clicks"),
    State("stored-g-limits", "data"),
    prevent_initial_call=True
)
def add_g_limit(n_clicks, current_data):
    if current_data is None:
        current_data = []
    updated = copy.deepcopy(current_data)
    updated.append({"category": "normal", "config": "clean", "g_value": None})
    return updated

@app.callback(
    Output("g-limits-container", "children", allow_duplicate=True),
    Input("stored-g-limits", "data"),
    prevent_initial_call=True
)
def render_g_limits(g_limits):
    if not g_limits:
        return []

    return [
        html.Div([
            dcc.Dropdown(
                id={"type": "g-category", "index": idx},
                options=[
                    {"label": "Normal", "value": "normal"},
                    {"label": "Utility", "value": "utility"},
                    {"label": "Aerobatic", "value": "aerobatic"}
                ],
                value=item.get("category", "normal"),
                style={"width": "120px", "marginRight": "10px"}
            ),
            dcc.Dropdown(
                id={"type": "g-config", "index": idx},
                options=[
                    {"label": "Clean/Up", "value": "clean"},
                    {"label": "TO/APP/10-20°", "value": "takeoff"},
                    {"label": "LDG/FULL/30-40°", "value": "landing"},
                ],
                value=item.get("config", "clean"),
                style={"width": "200px", "marginRight": "10px"}
            ),
            dcc.Input(
                id={"type": "g-positive", "index": idx},
                value=item.get("positive", ""),
                type="number",
                placeholder="+G",
                style={"width": "80px", "marginRight": "5px"}
            ),
            dcc.Input(
                id={"type": "g-negative", "index": idx},
                value=item.get("negative", ""),
                type="number",
                placeholder="-G",
                style={"width": "80px", "marginRight": "5px"}
            ),
            html.Button("❌", id={"type": "remove-g-limit", "index": idx}, n_clicks=0)
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "10px"})
        for idx, item in enumerate(g_limits)
    ]

@app.callback(
    Output("stored-g-limits", "data", allow_duplicate=True),
    Input({"type": "g-category", "index": ALL}, "value"),
    Input({"type": "g-config", "index": ALL}, "value"),
    Input({"type": "g-positive", "index": ALL}, "value"),
    Input({"type": "g-negative", "index": ALL}, "value"),
    Input({"type": "remove-g-limit", "index": ALL}, "n_clicks"),
    State("stored-g-limits", "data"),
    prevent_initial_call=True
)
def update_or_remove_g_limits(categories, configs, positives, negatives, remove_clicks, current_data):
    triggered = ctx.triggered_id

    if current_data is None:
        return []

    # Handle delete
    if isinstance(triggered, dict) and triggered.get("type") == "remove-g-limit":
        idx = triggered["index"]
        if 0 <= idx < len(current_data):
            return current_data[:idx] + current_data[idx + 1:]

    # Handle edit
    if not all(len(lst) == len(current_data) for lst in [categories, configs, positives, negatives]):
        raise PreventUpdate

    return [
        {
            "category": cat,
            "config": cfg,
            "positive": pos,
            "negative": neg
        }
        for cat, cfg, pos, neg in zip(categories, configs, positives, negatives)
    ]

# === STALL SPEEDS ===

@app.callback(
    Output("stored-stall-speeds", "data", allow_duplicate=True),
    Input("add-stall-speed", "n_clicks"),
    State("stored-stall-speeds", "data"),
    prevent_initial_call=True
)
def add_stall_speed(n_clicks, current_data):
    if current_data is None:
        current_data = []
    updated = copy.deepcopy(current_data)
    updated.append({
        "config": "clean",
        "gear": "up",
        "weight": None,
        "speed": None
    })
    return updated

@app.callback(
    Output("stall-speeds-container", "children", allow_duplicate=True),
    Input("stored-stall-speeds", "data"),
    prevent_initial_call=True
)
def render_stall_speeds(data):
    if data is None:
        raise PreventUpdate

    config_options = [
        {"label": "Clean/Up", "value": "clean"},
        {"label": "TO/APP/10-20°", "value": "takeoff"},
        {"label": "LDG/FULL/30-40°", "value": "landing"},
    ]
    gear_options = [
        {"label": "Gear Up", "value": "up"},
        {"label": "Gear Down", "value": "down"},
    ]

    return [
        html.Div([
            html.Div([
                dcc.Dropdown(
                    id={"type": "stall-config", "index": idx},
                    options=config_options,
                    value=item.get("config", "clean"),
                    placeholder="Config",
                    style={"width": "200px", "marginRight": "10px"}
                )
            ], style={"display": "inline-block"}),

            html.Div([
                dcc.Dropdown(
                    id={"type": "stall-gear", "index": idx},
                    options=gear_options,
                    value=item.get("gear", "up"),
                    placeholder="Gear",
                    style={"width": "130px", "marginRight": "10px"}
                )
            ], style={"display": "inline-block"}),

            html.Div([
                dcc.Input(
                    id={"type": "stall-weight", "index": idx},
                    value=item.get("weight", ""),
                    type="number",
                    placeholder="Weight",
                    style={"width": "100px", "marginRight": "10px"}
                )
            ], style={"display": "inline-block"}),

            html.Div([
                dcc.Input(
                    id={"type": "stall-speed", "index": idx},
                    value=item.get("speed", ""),
                    type="number",
                    placeholder="Stall Speed",
                    style={"width": "100px", "marginRight": "10px"}
                )
            ], style={"display": "inline-block"}),

            html.Div([
                html.Button("❌", id={"type": "remove-stall-speed", "index": idx}, n_clicks=0)
            ], style={"display": "inline-block"})
        ], style={"marginBottom": "10px", "display": "flex", "flexWrap": "nowrap", "alignItems": "center"})
        for idx, item in enumerate(data)
    ]

@app.callback(
    Output("stored-stall-speeds", "data", allow_duplicate=True),
    Input({"type": "stall-config", "index": ALL}, "value"),
    Input({"type": "stall-gear", "index": ALL}, "value"),
    Input({"type": "stall-weight", "index": ALL}, "value"),
    Input({"type": "stall-speed", "index": ALL}, "value"),
    Input({"type": "remove-stall-speed", "index": ALL}, "n_clicks"),
    State("stored-stall-speeds", "data"),
    prevent_initial_call=True
)
def update_or_remove_stall(configs, gears, weights, speeds, remove_clicks, current_data):
    triggered = ctx.triggered_id
    if current_data is None:
        return []

    if isinstance(triggered, dict) and triggered.get("type") == "remove-stall-speed":
        idx = triggered["index"]
        if 0 <= idx < len(current_data):
            return current_data[:idx] + current_data[idx + 1:]

    if not all(len(x) == len(current_data) for x in [configs, gears, weights, speeds]):
        raise PreventUpdate

    return [
        {"config": c, "gear": g, "weight": w, "speed": s}
        for c, g, w, s in zip(configs, gears, weights, speeds)
    ]

# === SINGLE ENGINE LIMITS ===

@app.callback(
    Output("stored-single-engine-limits", "data", allow_duplicate=True),
    Input("add-single-engine-limit", "n_clicks"),
    State("stored-single-engine-limits", "data"),
    prevent_initial_call=True
)
def add_single_engine_limit(n_clicks, current_data):
    if current_data is None:
        current_data = []
    new_data = copy.deepcopy(current_data)
    new_data.append({
        "limit_type": "Vmca",
        "value": None,
        "flap_config": "clean",
        "gear_config": "up"
    })
    return new_data

@app.callback(
    Output("single-engine-limits-container", "children", allow_duplicate=True),
    Input("stored-single-engine-limits", "data"),
    prevent_initial_call=True
)
def render_single_engine_limits(data):
    if data is None:
        raise PreventUpdate

    type_options = [
        {"label": "Vmca", "value": "Vmca"},
        {"label": "Vyse", "value": "Vyse"},
        {"label": "Vxse", "value": "Vxse"},
    ]
    flap_options = [
        {"label": "Clean/Up", "value": "clean"},
        {"label": "TO/APP/10-20°", "value": "takeoff"},
        {"label": "LDG/FULL/30-40°", "value": "landing"},
    ]
    gear_options = [
        {"label": "Up", "value": "up"},
        {"label": "Down", "value": "down"},
    ]

    return [
        html.Div([
            dcc.Dropdown(
                id={"type": "se-limit-type", "index": idx},
                options=type_options,
                value=item.get("limit_type", "Vmca"),
                style={"width": "120px", "marginRight": "10px"}
            ),

            dcc.Dropdown(
                id={"type": "se-limit-flap", "index": idx},
                options=flap_options,
                value=item.get("flap_config", "clean"),
                style={"width": "200px", "marginRight": "10px"}
            ),
            dcc.Dropdown(
                id={"type": "se-limit-gear", "index": idx},
                options=gear_options,
                value=item.get("gear_config", "up"),
                style={"width": "100px", "marginRight": "10px"}
            ),
            dcc.Input(
                id={"type": "se-limit-value", "index": idx},
                value=item.get("value", ""),
                type="number",
                placeholder="KIAS",
                style={"width": "100px", "marginRight": "10px"}
            ),
            html.Button("❌", id={"type": "remove-se-limit", "index": idx}, n_clicks=0)
        ], style={"marginBottom": "10px", "display": "flex", "alignItems": "center"})
        for idx, item in enumerate(data)
    ]
@app.callback(
    Output("stored-single-engine-limits", "data", allow_duplicate=True),
    Input({"type": "se-limit-type", "index": ALL}, "value"),
    Input({"type": "se-limit-value", "index": ALL}, "value"),
    Input({"type": "se-limit-flap", "index": ALL}, "value"),
    Input({"type": "se-limit-gear", "index": ALL}, "value"),
    Input({"type": "remove-se-limit", "index": ALL}, "n_clicks"),
    State("stored-single-engine-limits", "data"),
    prevent_initial_call=True
)
def update_or_remove_se_limits(types, values, flaps, gears, remove_clicks, current_data):
    triggered = ctx.triggered_id
    if current_data is None:
        return []

    if isinstance(triggered, dict) and triggered.get("type") == "remove-se-limit":
        idx = triggered.get("index")
        if 0 <= idx < len(current_data):
            return current_data[:idx] + current_data[idx + 1:]

    if not all(len(x) == len(current_data) for x in [types, values, flaps, gears]):
        raise PreventUpdate

    return [
        {
            "limit_type": t,
            "value": v,
            "flap_config": f,
            "gear_config": g
        }
        for t, v, f, g in zip(types, values, flaps, gears)
    ]
#----- OEI Performance----

@app.callback(
    Output("stored-oei-performance", "data", allow_duplicate=True),
    Input("add-oei-performance", "n_clicks"),
    State("stored-oei-performance", "data"),
    prevent_initial_call=True
)
def add_oei_entry(n_clicks, current_data):
    if current_data is None:
        current_data = []
    new_data = copy.deepcopy(current_data)
    new_data.append({
        "config": "clean_up",
        "prop_condition": "normal",
        "max_power_fraction": None,
    })
    return new_data

@app.callback(
    Output("oei-performance-container", "children", allow_duplicate=True),
    Input("stored-oei-performance", "data"),
    prevent_initial_call=True
)
def render_oei_entries(data):
    if not data:
        return []

    prop_options = [
        {"label": "Feathered", "value": "Feathered"},
        {"label": "Windmilling", "value": "windmilling"},
        {"label": "Stationary", "value": "stationary"}
    ]

    config_options = [
        {"label": "Clean / Up", "value": "clean_up"},
        {"label": "Landing / Down", "value": "landing_down"}
    ]

    return [
        html.Div([
            dcc.Dropdown(
                id={"type": "oei-config", "index": idx},
                options=config_options,
                value=item.get("config", "clean_up"),
                style={"width": "150px", "marginRight": "10px"}
            ),
            dcc.Dropdown(
                id={"type": "oei-prop", "index": idx},
                options=prop_options,
                value=item.get("prop_condition", "normal"),
                style={"width": "150px", "marginRight": "10px"}
            ),
            dcc.Input(
                id={"type": "oei-power", "index": idx},
                type="number",
                value=item.get("max_power_fraction"),
                placeholder="Power Fraction",
                step=0.01,
                style={"width": "140px", "marginRight": "10px"}
            ),
            html.Button("❌", id={"type": "remove-oei", "index": idx}, n_clicks=0)
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "10px"})
        for idx, item in enumerate(data)
    ]

@app.callback(
    Output("stored-oei-performance", "data", allow_duplicate=True),
    Input({"type": "oei-config", "index": ALL}, "value"),
    Input({"type": "oei-prop", "index": ALL}, "value"),
    Input({"type": "oei-power", "index": ALL}, "value"),
    Input({"type": "oei-efficiency", "index": ALL}, "value"),
    Input({"type": "remove-oei", "index": ALL}, "n_clicks"),
    State("stored-oei-performance", "data"),
    prevent_initial_call=True
)
def update_oei_entries(configs, props, powers, effs, remove_clicks, current_data):
    triggered = ctx.triggered_id
    if current_data is None:
        return []

    # Deletion case
    if isinstance(triggered, dict) and triggered.get("type") == "remove-oei":
        idx = triggered["index"]
        if 0 <= idx < len(current_data):
            return current_data[:idx] + current_data[idx + 1:]

    # Edit case
    if not all(len(x) == len(current_data) for x in [configs, props, powers, effs]):
        raise PreventUpdate

    return [
        {
            "config": c,
            "prop_condition": p,
            "max_power_fraction": f,
        }
        for c, p, f, in zip(configs, props, powers)
    ]

# === ENGINE OPTIONS ===

@app.callback(
    Output("stored-engine-options", "data", allow_duplicate=True),
    Input("add-engine-option", "n_clicks"),
    State("stored-engine-options", "data"),
    prevent_initial_call=True
)
def add_engine_option(n_clicks, current_engines):
    if current_engines is None:
        current_engines = []
    new_data = copy.deepcopy(current_engines)
    new_data.append({
        "name": "",
        "horsepower": None,
        "power_curve_sea_level": None,
        "power_curve_derate": 0.03,
    })
    return new_data

@app.callback(
    Output("engine-options-container", "children", allow_duplicate=True),
    Input("stored-engine-options", "data"),
    prevent_initial_call=True
)
def render_engine_options(engine_data):
    if engine_data is None:
        raise PreventUpdate

    return [
        html.Div([
            dcc.Input(
                id={"type": "engine-name", "index": idx},
                value=item.get("name", ""),
                type="text",
                placeholder="Engine Name",
                style={"width": "180px", "marginRight": "5px"}
            ),
            dcc.Input(
                id={"type": "engine-hp", "index": idx},
                value=item.get("horsepower", 0),
                type="number",
                placeholder="Horsepower",
                style={"width": "100px", "marginRight": "5px"}
            ),
            dcc.Input(
                id={"type": "power-curve-sea-level", "index": idx},
                value=item.get("power_curve_sea_level", ""),
                type="number",
                placeholder="Sea Level HP",
                style={"width": "120px", "marginRight": "5px"}
            ),
            dcc.Input(
                id={"type": "power-curve-derate", "index": idx},
                value=item.get("power_curve_derate", 0.03),
                type="number",
                step="0.001",
                placeholder="Derate / 1000 ft",
                style={"width": "130px", "marginRight": "5px"}
            ),
            html.Button("❌", id={"type": "remove-engine", "index": idx}, n_clicks=0)
        ], style={"marginBottom": "12px", "display": "flex", "flexWrap": "wrap"})
        for idx, item in enumerate(engine_data)
    ]

@app.callback(
    Output("stored-engine-options", "data", allow_duplicate=True),
    Input({"type": "engine-name", "index": ALL}, "value"),
    Input({"type": "engine-hp", "index": ALL}, "value"),
    Input({"type": "power-curve-sea-level", "index": ALL}, "value"),
    Input({"type": "power-curve-derate", "index": ALL}, "value"),
    Input({"type": "remove-engine", "index": ALL}, "n_clicks"),
    State("stored-engine-options", "data"),
    prevent_initial_call=True
)
def update_or_remove_engines(names, hps, sea_levels, derates, remove_clicks, current_data):
    triggered = ctx.triggered_id
    if current_data is None:
        return []

    if isinstance(triggered, dict) and triggered.get("type") == "remove-engine":
        idx = triggered.get("index")
        if 0 <= idx < len(current_data):
            return current_data[:idx] + current_data[idx + 1:]

    if not all(len(x) == len(current_data) for x in [names, hps, sea_levels, derates]):
        raise PreventUpdate

    return [
        {
            "name": n,
            "horsepower": hp,
            "power_curve_sea_level": sea,
            "power_curve_derate": derate
        }
        for n, hp, sea, derate in zip(names, hps, sea_levels, derates)
    ]


@app.callback(
    [
        Output("aircraft-name", "value", allow_duplicate=True),
        Output("aircraft-type", "value", allow_duplicate=True),
        Output("engine-count", "value", allow_duplicate=True),
        Output("wing-area", "value", allow_duplicate=True),
        Output("aspect-ratio", "value", allow_duplicate=True),
        Output("cd0", "value", allow_duplicate=True),
        Output("oswald-efficiency", "value", allow_duplicate=True),
        Output("stored-flap-configs", "data", allow_duplicate=True),
        Output("stored-g-limits", "data", allow_duplicate=True),
        Output("g-limits-container", "children", allow_duplicate=True),
        Output("stored-stall-speeds", "data", allow_duplicate=True),
        Output("stall-speeds-container", "children", allow_duplicate=True),
        Output("stored-single-engine-limits", "data", allow_duplicate=True),
        Output("stored-engine-options", "data", allow_duplicate=True),
        Output("engine-options-container", "children", allow_duplicate=True),
        Output("empty-weight", "value", allow_duplicate=True),
        Output("max-weight", "value", allow_duplicate=True),
        Output("best-glide", "value", allow_duplicate=True),
        Output("best-glide-ratio", "value", allow_duplicate=True),
        Output("seats", "value", allow_duplicate=True),
        Output("cg-fwd", "value", allow_duplicate=True),
        Output("cg-aft", "value", allow_duplicate=True),
        Output({"type": "vfe-input", "config": "takeoff"}, "value", allow_duplicate=True),
        Output({"type": "vfe-input", "config": "landing"}, "value", allow_duplicate=True),
        Output({"type": "clmax-input", "config": "clean"}, "value", allow_duplicate=True),
        Output({"type": "clmax-input", "config": "takeoff"}, "value", allow_duplicate=True),
        Output({"type": "clmax-input", "config": "landing"}, "value", allow_duplicate=True),
        Output("fuel-capacity-gal", "value", allow_duplicate=True),
        Output("fuel-weight-per-gal", "value", allow_duplicate=True),
        Output("arc-white-bottom", "value", allow_duplicate=True),
        Output("arc-white-top", "value", allow_duplicate=True),
        Output("arc-green-bottom", "value", allow_duplicate=True),
        Output("arc-green-top", "value", allow_duplicate=True),
        Output("arc-yellow-bottom", "value", allow_duplicate=True),
        Output("arc-yellow-top", "value", allow_duplicate=True),
        Output("arc-red", "value", allow_duplicate=True),
        Output("prop-static-factor", "value", allow_duplicate=True),
        Output("prop-vmax-kts", "value", allow_duplicate=True),
        Output("stored-oei-performance", "data", allow_duplicate=True),
        Output("max-altitude", "value", allow_duplicate=True),
        Output("vne", "value", allow_duplicate=True),
        Output("vno", "value", allow_duplicate=True),
        Output("search-result", "children", allow_duplicate=True),
    ],
    Input("new-aircraft-button", "n_clicks"),
    prevent_initial_call=True
)
def clear_all_fields(n_clicks):
    return (
        "",  # aircraft-name
        "",  # aircraft-type
        1,   # engine-count
        None,  # wing-area
        None,  # aspect-ratio
        None,  # cd0
        None,  # oswald-efficiency
        [],    # stored-flap-configs
        [],    # stored-g-limits
        [],    # g-limits-container (children)
        [],    # stored-stall-speeds
        [],    # stall-speeds-container (children)
        [],    # stored-single-engine-limits
        [],    # stored-engine-options
        [],    # engine-options-container (children)
        None,  # empty-weight
        None,  # max-weight
        None,  # best-glide
        None,  # best-glide-ratio
        None,  # seats
        None,  # cg-fwd
        None,  # cg-aft
        None,  # vfe takeoff
        None,  # vfe landing
        None,  # clmax clean
        None,  # clmax takeoff
        None,  # clmax landing
        None,  # fuel-capacity-gal
        None,  # fuel-weight-per-gal
        None,  # arc-white-bottom
        None,  # arc-white-top
        None,  # arc-green-bottom
        None,  # arc-green-top
        None,  # arc-yellow-bottom
        None,  # arc-yellow-top
        None,  # arc-red
        None,  # prop-static-factor
        None,  # prop-vmax-kts
        [],    # stored-oei-performance
        None,  # max-altitude
        None,  # vne
        None,  # vno
        "⬜ New aircraft ready"  # search-result.children
    )


@app.callback(
    Output("vne", "value", allow_duplicate=True),
    Output("vno", "value", allow_duplicate=True),
    Output({"type": "vfe-input", "config": "takeoff"}, "value", allow_duplicate=True),
    Output({"type": "vfe-input", "config": "landing"}, "value", allow_duplicate=True),
    Output("arc-white-bottom", "value", allow_duplicate=True),
    Output("arc-white-top", "value", allow_duplicate=True),
    Output("arc-green-bottom", "value", allow_duplicate=True),
    Output("arc-green-top", "value", allow_duplicate=True),
    Output("arc-yellow-bottom", "value", allow_duplicate=True),
    Output("arc-yellow-top", "value", allow_duplicate=True),
    Output("arc-red", "value", allow_duplicate=True),
    Output("stored-stall-speeds", "data", allow_duplicate=True),
    Output("stored-single-engine-limits", "data", allow_duplicate=True),
    Input("units-toggle", "value"),
    State("vne", "value"),
    State("vno", "value"),
    State({"type": "vfe-input", "config": "takeoff"}, "value"),
    State({"type": "vfe-input", "config": "landing"}, "value"),
    State("arc-white-bottom", "value"),
    State("arc-white-top", "value"),
    State("arc-green-bottom", "value"),
    State("arc-green-top", "value"),
    State("arc-yellow-bottom", "value"),
    State("arc-yellow-top", "value"),
    State("arc-red", "value"),
    State("stored-stall-speeds", "data"),
    State("stored-single-engine-limits", "data"),
    prevent_initial_call=True
)
def convert_units_toggle(units,
    vne, vno, vfe_to, vfe_ldg,
    arc_white_btm, arc_white_top,
    arc_green_btm, arc_green_top,
    arc_yellow_btm, arc_yellow_top,
    arc_red,
    stall_data, se_limits
):
    # Prevent meaningless toggles
    if units not in ("MPH", "KIAS"):
        raise PreventUpdate

    # Conversion functions
    def to_mph(val): return round(val * 1.15078, 1) if val is not None else None
    def to_kias(val): return round(val / 1.15078, 1) if val is not None else None
    convert = to_mph if units == "MPH" else to_kias

    # Convert airspeeds
    vne_new = convert(vne)
    vno_new = convert(vno)
    vfe_to_new = convert(vfe_to)
    vfe_ldg_new = convert(vfe_ldg)
    arc_white_btm_new = convert(arc_white_btm)
    arc_white_top_new = convert(arc_white_top)
    arc_green_btm_new = convert(arc_green_btm)
    arc_green_top_new = convert(arc_green_top)
    arc_yellow_btm_new = convert(arc_yellow_btm)
    arc_yellow_top_new = convert(arc_yellow_top)
    arc_red_new = convert(arc_red)

    # Stall speeds
    updated_stalls = []
    for item in stall_data or []:
        item = item.copy()
        if item.get("speed") is not None:
            item["speed"] = convert(item["speed"])
        updated_stalls.append(item)

    # Single engine limits
    updated_se = []
    for entry in se_limits or []:
        entry = entry.copy()
        if entry.get("limit_type") in ("Vmca", "Vyse", "Vxse"):
            if entry.get("value") is not None:
                entry["value"] = convert(entry["value"])
        updated_se.append(entry)

    return (
        vne_new, vno_new,
        vfe_to_new, vfe_ldg_new,
        arc_white_btm_new, arc_white_top_new,
        arc_green_btm_new, arc_green_top_new,
        arc_yellow_btm_new, arc_yellow_top_new,
        arc_red_new,
        updated_stalls,
        updated_se
    )



@app.callback(
    [
        Output("save-status", "children", allow_duplicate=True),
        Output("aircraft-data-store", "data", allow_duplicate=True),
        Output("last-saved-aircraft", "data", allow_duplicate=True),
        Output("download-aircraft", "data", allow_duplicate=True),
    ],
    Input("save-aircraft-button", "n_clicks"),
    State("aircraft-name", "value"),
    State("wing-area", "value"),
    State("aspect-ratio", "value"),
    State("cd0", "value"),
    State("oswald-efficiency", "value"),
    State("stored-flap-configs", "data"),
    State("stored-g-limits", "data"),
    State("stored-stall-speeds", "data"),
    State("stored-single-engine-limits", "data"),
    State("stored-engine-options", "data"),
    State("units-toggle", "value"),
    State("empty-weight", "value"),
    State("max-weight", "value"),
    State("seats", "value"),
    State("cg-fwd", "value"),
    State("cg-aft", "value"),
    State("fuel-capacity-gal", "value"),
    State("fuel-weight-per-gal", "value"),
    State("arc-white-bottom", "value"),
    State("arc-white-top", "value"),
    State("arc-green-bottom", "value"),
    State("arc-green-top", "value"),
    State("arc-yellow-bottom", "value"),
    State("arc-yellow-top", "value"),
    State("arc-red", "value"),
    State("prop-static-factor", "value"),
    State("prop-vmax-kts", "value"),
    State("best-glide", "value"),
    State("best-glide-ratio", "value"),
    State("aircraft-type", "value"),
    State("engine-count", "value"),
    State("vne", "value"),
    State("vno", "value"),
    State({"type": "vfe-input", "config": "takeoff"}, "value"),
    State({"type": "vfe-input", "config": "landing"}, "value"),
    State({"type": "clmax-input", "config": "clean"}, "value"),
    State({"type": "clmax-input", "config": "takeoff"}, "value"),
    State({"type": "clmax-input", "config": "landing"}, "value"),
    State("max-altitude", "value"),
    State("gear-type", "value"),
    prevent_initial_call=True
)
def save_aircraft_to_file(
    n_clicks, name, wing_area, ar, cd0, e,
    flaps, g_limits, stall_speeds, se_limits, engines,
    units, empty_weight, max_weight, seats, cg_fwd, cg_aft, fuel_capacity, fuel_weight,
    white_btm, white_top, green_btm, green_top, yellow_btm, yellow_top, red,
    t_static, v_max_kts, best_glide, best_glide_ratio, aircraft_type, engine_count, vne, vno, vfe_takeoff, vfe_landing, 
    clmax_clean, clmax_takeoff, clmax_landing, max_altitude, gear_type
):
    if not name:
        return "❌ Aircraft name is required.", dash.no_update, dash.no_update, dash.no_update

    try:
        def convert_speed(val):
            return round(val / 1.15078, 1) if units == "MPH" and isinstance(val, (int, float)) else val

        converted_stalls = [
            {
                "config": s["config"],
                "gear": s["gear"],
                "weight": s["weight"],
                "speed": convert_speed(s["speed"])
            } for s in stall_speeds
        ]

        converted_se_limits = [
            {
                "limit_type": s["limit_type"],
                "flap_config": s["flap_config"],
                "gear_config": s["gear_config"],
                "value": convert_speed(s["value"])
            } for s in se_limits
        ]


        engine_dict = {}
        if engines:
            for eng in engines:
                engine_dict[eng.get("name", "Unnamed Engine")] = {
                    "horsepower": eng.get("horsepower"),
                    "power_curve": {
                        "sea_level_max": eng.get("power_curve_sea_level"),
                        "derate_per_1000ft": eng.get("power_curve_derate")
                    }
                }

        g_structured = {}
        for g in g_limits:
            cat = g.get("category")
            cfg = g.get("config")
            pos = g.get("positive")
            neg = g.get("negative")

            # Inject global default if negative G not provided
            if neg is None:
                neg = g_neg  # <- From UI field "g-negative"

            if cat and cfg:
                g_structured.setdefault(cat, {})[cfg] = {
                    "positive": pos,
                    "negative": neg
                }

        stall_structured = {}
        for s in converted_stalls:
            cfg = s["config"]
            if cfg not in stall_structured:
                stall_structured[cfg] = {"weights": [], "speeds": []}
            stall_structured[cfg]["weights"].append(s["weight"])
            stall_structured[cfg]["speeds"].append(s["speed"])

        flap_names = [f["name"] for f in flaps if isinstance(f, dict) and f.get("name")]
        # Fallback to standard configs if none defined
        if not flap_names:
            flap_names = ["clean", "takeoff", "landing"]
            
        vfe_dict = {
            f["name"]: convert_speed(f["vfe"])
            for f in flaps if isinstance(f, dict) and f.get("name") and f.get("vfe") is not None
        }

        arcs = {
            "white": [convert_speed(white_btm), convert_speed(white_top)],
            "green": [convert_speed(green_btm), convert_speed(green_top)],
            "yellow": [convert_speed(yellow_btm), convert_speed(yellow_top)],
            "red": convert_speed(red)
        }
        vfe_dict = {}
        if vfe_takeoff is not None:
            vfe_dict["takeoff"] = convert_speed(vfe_takeoff)
        if vfe_landing is not None:
            vfe_dict["landing"] = convert_speed(vfe_landing)

        clmax_dict = {}
        if clmax_clean is not None:
            clmax_dict["clean"] = clmax_clean
        if clmax_takeoff is not None:
            clmax_dict["takeoff"] = clmax_takeoff
        if clmax_landing is not None:
            clmax_dict["landing"] = clmax_landing

        ac_dict = {
            "name": name,
            "type": aircraft_type,
            "gear_type": gear_type,
            "engine_count": engine_count,
            "wing_area": wing_area,
            "aspect_ratio": ar,
            "CD0": cd0,
            "e": e,
            "configuration_options": {"flaps": flap_names},
            "G_limits": g_structured,
            "stall_speeds": stall_structured,
            "single_engine_limits": {
                s["limit_type"]: convert_speed(s["value"])
                for s in converted_se_limits if s["limit_type"]
            },
            "engine_options": engine_dict,
            "max_altitude": max_altitude,
            "Vne": convert_speed(vne),
            "Vno": convert_speed(vno),
            "Vfe": vfe_dict,
            "CL_max": clmax_dict,
            "arcs": arcs,
            "empty_weight": empty_weight,
            "max_weight": max_weight,
            "single_engine_limits": {
                **{
                    s["limit_type"]: convert_speed(s["value"])
                    for s in converted_se_limits if s["limit_type"]
                },
                "best_glide": best_glide,
                "best_glide_ratio": best_glide_ratio
            },
            "seats": seats,
            "cg_range": [cg_fwd, cg_aft],
            "fuel_capacity_gal": fuel_capacity,
            "fuel_weight_per_gal": fuel_weight,
            "prop_thrust_decay": {
                "T_static_factor": t_static,
                "V_max_kts": v_max_kts
            }
        }

        filename = name.replace(" ", "_") + ".json"
        filepath = os.path.join("aircraft_data", filename)

        if os.path.exists(filepath):
            return "❌ That aircraft already exists. Please enter a new name.", dash.no_update

        with open(filepath, "w") as f:
            json.dump(ac_dict, f, indent=2)

        updated = load_aircraft_data_from_folder()
        return f"✅ Saved as {filename}", updated, name,dcc.send_string(json.dumps(ac_dict, indent=2), filename)

    except Exception as e:
        return (f"❌ Error saving: {str(e)}", dash.no_update, dash.no_update, dash.no_update)


from flask import send_from_directory

from dash import Output, Input, State, ctx, dcc
import json

import base64
import json
from dash import Input, Output, State
from dash.exceptions import PreventUpdate

@app.callback(
    [
        Output("aircraft-data-store", "data", allow_duplicate=True),
        Output("aircraft-select", "value", allow_duplicate=True),  # ✅ correct dropdown
        Output("last-saved-aircraft", "data", allow_duplicate=True)
    ],
    Input("upload-aircraft", "contents"),
    State("upload-aircraft", "filename"),
    State("aircraft-data-store", "data"),
    prevent_initial_call=True
)
def load_aircraft_from_upload(contents, filename, current_data):
    if not contents or not filename:
        raise PreventUpdate

    try:
        # Decode base64-encoded JSON string
        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string)
        aircraft_json = json.loads(decoded.decode("utf-8"))

        # Use 'name' key from JSON if present, else fallback to filename
        name = aircraft_json.get("name") or filename.replace(".json", "").replace("_", " ").strip()

        # Inject aircraft into stored dict
        current_data = current_data or {}
        current_data[name] = aircraft_json

        dprint(f"[UPLOAD] Loaded aircraft: {name}")
        return current_data, name, name

    except Exception as e:
        dprint(f"[UPLOAD ERROR]: {e}")
        raise PreventUpdate

@app.callback(
    Output("disclaimer-modal", "is_open"),
    Output("terms-policy-modal", "is_open"),
    Input("open-disclaimer", "n_clicks"),
    Input("close-disclaimer", "n_clicks"),
    Input("open-terms-policy", "n_clicks"),
    Input("close-terms-policy", "n_clicks"),
    State("disclaimer-modal", "is_open"),
    State("terms-policy-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_disclaimer_and_terms(open_disc, close_disc, open_terms, close_terms, disc_open, terms_open):
    ctx_id = ctx.triggered_id

    if ctx_id == "open-disclaimer":
        return True, False
    elif ctx_id == "close-disclaimer":
        return False, terms_open
    elif ctx_id == "open-terms-policy":
        return False, True
    elif ctx_id == "close-terms-policy":
        return disc_open, False

    raise PreventUpdate





@app.server.route("/robots.txt")
def serve_robots():
    return send_from_directory('.', 'robots.txt')

@app.server.route("/sitemap.xml")
def serve_sitemap():
    return send_from_directory('.', 'sitemap.xml')



import os

if __name__ == "__main__":
    # Use env var to control debug (1 = on, 0 = off)
    debug_mode = os.environ.get("AEROEDGE_DEBUG", "1") == "1"

    # Local: 127.0.0.1 is fine, Render will override host/port anyway
    app.run(debug=debug_mode, host="127.0.0.1", port=8050)
