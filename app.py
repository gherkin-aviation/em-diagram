# =============================================================================
# EM Diagram Generator - Main Application
# =============================================================================
"""
Energy Maneuverability Diagram Generator
Visualization tool for aircraft performance analysis.

Module structure:
- core/           Physics calculations, constants, data loading
- pages/          Page layouts (future)
- callbacks/      Dash callbacks (future)
- components/     Reusable UI components (future)
"""

import dash
from dash import dcc, html, Input, Output, State, ctx
from dash.dependencies import ALL
import plotly.graph_objects as go
import numpy as np
import webbrowser
import threading
import copy
import time
import sys
import os
import json
from itertools import zip_longest
from dash.exceptions import PreventUpdate

# Import from modular core package
from core import (
    # App settings
    DEBUG_LOG,
    dprint,
    # Physical constants
    g, G_FT_S2, KTS_TO_FPS, FPS_TO_KTS, KTS_TO_MPH, RHO_SL, TEMP_SL_K, TEMP_SL_C, LAPSE_RATE_K_FT,
    # Drag/Lift calculations
    compute_dynamic_pressure,
    compute_cl,
    compute_cd,
    compute_drag,
    compute_thrust_available,
    compute_ps_knots_per_sec,
    # Atmosphere
    compute_air_density,
    compute_density_altitude,
    compute_pressure_altitude,
    compute_true_airspeed,
    # Turn physics
    compute_load_factor,
    compute_turn_rate_from_bank,
    compute_turn_rate_from_load_factor,
    compute_turn_radius,
    compute_bank_from_turn_rate,
    # Stall
    compute_stall_speed_at_load_factor,
    interpolate_stall_speed,
    # Aircraft data
    AIRCRAFT_DATA,
    aircraft_data,
    extract_vmca_value,
    resource_path,
    # Airport data
    AIRPORT_DATA,
    AIRPORT_OPTIONS,
    get_airport_by_id,
)

from edit_aircraft_page import edit_aircraft_layout
import dash_bootstrap_components as dbc

# ✅ Initialize Dash app
app = dash.Dash(__name__, suppress_callback_exceptions=True, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

# Initialize usage tracking
from aeroedge_tracker import init_tracking, log_feature
init_tracking(server)




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
    dcc.Store(id="aircraft-data-store", data=AIRCRAFT_DATA),
    dcc.Store(id="last-saved-aircraft"),
    dcc.Store(id="stored-total-weight"),
    dcc.Store(id="screen-width"),
    dcc.Store(id="sidebar-collapsed", data=False),
    html.Div(id="page-content"),
    dcc.Download(id="download-aircraft"),

    # Global Modals (shared between desktop and mobile)
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("AeroEdge Disclaimer"), close_button=True),
        dbc.ModalBody([
            html.P("This tool supplements—not replaces—FAA-published documentation.", style={"marginBottom": "8px"}),
            html.P("It is intended for educational and reference use only, and has not been approved or endorsed by the Federal Aviation Administration (FAA).", style={"marginBottom": "8px"}),
            html.P("While AeroEdge is aligned with FAA safety principles, it is not an official source of operational data. Users must consult certified instructors and approved aircraft documentation when making flight decisions.", style={"marginBottom": "8px"}),
            html.P("The data presented may be incomplete, inaccurate, outdated, or derived from public or user-submitted sources. No warranties, express or implied, are made regarding its accuracy, completeness, or fitness for purpose.", style={"marginBottom": "8px"}),
            html.P("Instructors and users are encouraged to verify all EM diagram outputs against certified POH/AFM values. This tool is not a substitute for competent flight instruction, or for compliance with applicable regulations, including Airworthiness Directives (ADs), Federal Aviation Regulations (FARs), or Advisory Circulars (ACs).", style={"marginBottom": "8px"}),
            html.P("If any information conflicts with the aircraft's FAA-approved AFM or POH, the official documentation shall govern.", style={"marginBottom": "8px"}),
            html.P("AeroEdge disclaims all liability for errors, omissions, injuries, or damages resulting from the use of this application or website. Use of this tool constitutes acceptance of these terms.", style={"marginBottom": "8px"})
        ]),
        dbc.ModalFooter(
            dbc.Button("Close", id="close-disclaimer", className="ms-auto", color="secondary")
        )
    ], id="disclaimer-modal", is_open=False, centered=True, size="lg"),

    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Terms of Use & Privacy Policy"), close_button=True),
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
    ], id="terms-policy-modal", is_open=False, centered=True, size="lg"),

    # Quick Start Modal
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Quick Start Guide"), close_button=True),
        dbc.ModalBody([
            html.P([
                html.Strong("What is an EM Diagram? "),
                "An Energy-Maneuverability diagram visualizes your aircraft's performance envelope—showing the relationship between airspeed, load factor (G), and turn rate at any given configuration."
            ], style={"marginBottom": "8px"}),
            html.P([
                html.Strong("Why it matters: "),
                "Understanding these limits is critical for safe and effective flight training:"
            ], style={"marginBottom": "6px"}),
            html.Ul([
                html.Li([html.Strong("Stall/Spin Training: "), "See exactly how stall speed increases with bank angle and G-load"]),
                html.Li([html.Strong("Steep Turns: "), "Visualize the energy cost of maintaining altitude in 45°+ banks"]),
                html.Li([html.Strong("Emergency Maneuvers: "), "Know your corner speed and maximum instantaneous turn rate"]),
                html.Li([html.Strong("Multi-Engine: "), "Understand Vmc variations with weight, altitude, and configuration"]),
                html.Li([html.Strong("CFI/CFII Instruction: "), "Demonstrate performance concepts with real aircraft data"]),
            ], style={"paddingLeft": "20px", "marginBottom": "10px", "fontSize": "13px"}),
            html.Hr(style={"margin": "10px 0"}),
            html.P(html.Strong("Getting Started:"), style={"marginBottom": "6px"}),
            html.Ol([
                html.Li("Select an aircraft or load a custom JSON file"),
                html.Li("Adjust weight, altitude, and power settings"),
                html.Li("Toggle overlays (Ps contours, G-lines, turn radius, etc.)"),
                html.Li("Hover over the graph for detailed values"),
                html.Li("Export with PNG/PDF buttons"),
            ], style={"paddingLeft": "20px", "marginBottom": "10px", "fontSize": "13px"}),
            html.Hr(style={"margin": "10px 0"}),
            html.P([
                html.Strong("Tip: "),
                "Click the ", html.Span("?", style={"backgroundColor": "#2980B9", "color": "white", "borderRadius": "50%", "padding": "1px 5px", "fontSize": "10px"}),
                " icons next to any option for detailed explanations."
            ], style={"marginBottom": "0", "fontSize": "13px"})
        ]),
        dbc.ModalFooter(
            dbc.Button("Close", id="close-readme", className="ms-auto", color="secondary")
        )
    ], id="readme-modal", is_open=False, centered=True, size="lg"),

    # Help Modal for feature explanations
    dcc.Store(id="help-topic", data=None),
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(id="help-modal-title"), close_button=True),
        dbc.ModalBody(id="help-modal-body"),
        dbc.ModalFooter(
            dbc.Button("Close", id="close-help-modal", className="ms-auto", color="secondary")
        )
    ], id="help-modal", is_open=False, centered=True, size="lg"),
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

# Callback to forward ghost help trigger clicks to the hidden help-ghost element
@app.callback(
    Output("help-ghost", "n_clicks"),
    Input({"type": "ghost-help-trigger", "index": ALL}, "n_clicks"),
    State("help-ghost", "n_clicks"),
    prevent_initial_call=True
)
def forward_ghost_help_clicks(trigger_clicks, current_clicks):
    """Forward clicks from dynamic ghost help triggers to the static help-ghost element."""
    if trigger_clicks and any(c and c > 0 for c in trigger_clicks):
        return (current_clicks or 0) + 1
    raise PreventUpdate



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

            # Warning Banner
            html.Div(
                "\u26a0\ufe0f This tool visualizes performance data based on public or user-submitted values and is for educational use only. It is not FAA-approved and may not reflect actual aircraft capabilities. Always verify against the aircraft's POH/AFM. \u26a0\ufe0f",
                className="warning-banner"
            ),

            # Quick Links Bar
            html.Div([
                html.Span("Quick Start", id="open-readme", className="quick-link link-blue", style={"cursor": "pointer"}),
                html.Span("|", className="separator"),
                html.A("Report Issue", href="https://forms.gle/1xP29PwFze5MHCTZ7", target="_blank", className="quick-link link-danger"),
                html.Span("|", className="separator"),
                html.A("Contact AeroEdge", href="https://forms.gle/AqS1uuTgcY6sRHob9", target="_blank", className="quick-link link-blue"),
                html.Span("|", className="separator"),
                html.A("Maneuver Overlay Tool", href="https://overlay.flyaeroedge.com", target="_blank", className="quick-link link-orange"),
            ], className="quick-links-bar-slim"),

        # Two-Column Flex Layout: Sidebar + Graph
        html.Div([
            # Sidebar Left
            dbc.Col([
                html.Div(id="resize-handle", className="resize-handle"),
                # Sidebar header with collapse button
                html.Div([
                    html.Div("EM Diagram Generator", style={
                        "fontWeight": "600",
                        "fontSize": "18px",
                        "color": "#1b1e23"
                    }),
                    html.Button("«", id="sidebar-collapse-btn", className="sidebar-collapse-btn", title="Collapse sidebar"),
                ], className="sidebar-header"),
                dbc.Row([
                    dbc.Col(
                        dbc.Button(
                            "Edit / Create Aircraft",
                            id="edit-aircraft-button",
                            className="btn-standard btn-primary-orange w-100",
                        ), width=6
                    ),
                    dbc.Col(
                        dcc.Upload(
                            id="upload-aircraft",
                            children=dbc.Button(
                                "Load Aircraft File",
                                className="btn-standard btn-primary-orange w-100",
                            ),
                            multiple=False,
                            accept=".json",
                            className="w-100"
                        ), width=6
                    )
                ], className="mb-2 g-1"),

                # Accordion Sections
                dbc.Accordion([
                    # Aircraft Configuration
                    dbc.AccordionItem([
                        html.Div([
                            html.Label("Aircraft", className="input-label-sm"),
                            dcc.Dropdown(id="aircraft-select", options=[], placeholder="Select an Aircraft...", className="dropdown")
                        ], className="mb-2"),
                        # Hidden until aircraft is selected
                        html.Div([
                            html.Div([
                                html.Label("Engine", className="input-label-sm"),
                                dcc.Dropdown(id="engine-select", className="dropdown"),
                            ], className="mb-2"),
                            html.Div([
                                html.Label("Category", className="input-label-sm"),
                                dcc.Dropdown(id="category-select", className="dropdown")
                            ], className="mb-2"),
                            html.Div([
                                html.Label("Flap Configuration", className="input-label-sm"),
                                dcc.Dropdown(id="config-select", className="dropdown")
                            ], className="mb-2"),
                            html.Div([
                                html.Label("Landing Gear", className="input-label-sm"),
                                dcc.Dropdown(id="gear-select", className="dropdown")
                            ], id="gear-select-container", className="mb-2", style={"display": "none"}),
                            html.Div([
                                html.Label("Total Weight", className="input-label-sm"),
                                html.Div(id="total-weight-display", className="weight-box")
                            ], className="mb-2"),
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Occupants", className="input-label-sm"),
                                    dcc.Dropdown(id="occupants-select", className="dropdown-small")
                                ], width=6),
                                dbc.Col([
                                    html.Label("Occ. Weight", className="input-label-sm"),
                                    dcc.Input(id="passenger-weight-input", type="number", value=180, min=50, max=400, step=1, className="input-small")
                                ], width=6)
                            ], className="mb-2"),
                            html.Div([
                                html.Label("Fuel (gal)", className="input-label-sm"),
                                dcc.Slider(id="fuel-slider", min=0, max=50, step=1, value=20, marks={}, tooltip={"always_visible": True})
                            ], className="mb-2"),
                            html.Div([
                                html.Label("Power Setting", className="input-label-sm"),
                                dcc.Slider(
                                    id="power-setting",
                                    min=0.05, max=1.0, step=0.05, value=0.50,
                                    marks={0.05: "IDLE", 0.2: "20%", 0.4: "40%", 0.6: "60%", 0.8: "80%", 1: "100%"},
                                    tooltip={"always_visible": True}
                                )
                            ], className="mb-2"),
                            html.Div([
                                dcc.Slider(id="cg-slider", min=0, max=1, value=0.5, step=0.01)
                            ], id="cg-slider-container", className="mb-2"),
                            html.Div([
                                html.Div([
                                    html.Label("Flight Path Angle (deg)", className="input-label-sm"),
                                    html.Span("?", id="help-fpa", className="help-icon", n_clicks=0)
                                ], style={"display": "flex", "alignItems": "center"}),
                                dcc.Slider(
                                    id="pitch-angle",
                                    min=-15, max=25, step=1, value=0,
                                    marks={-15: "-15°", -10: "-10°", -5: "-5°", 0: "0°", 5: "5°", 10: "10°", 15: "15°", 20: "20°", 25: "25°"},
                                    tooltip={"always_visible": True}
                                )
                            ], className="mb-2")
                        ], id="config-details", style={"display": "none"})
                    ], title="Aircraft Configuration", item_id="config"),

                    # Environment
                    dbc.AccordionItem([
                        html.Div([
                            html.Label("Airport", className="input-label-sm"),
                            dcc.Dropdown(
                                id="airport-select",
                                options=AIRPORT_OPTIONS,
                                placeholder="Search airport...",
                                searchable=True,
                                clearable=True,
                                style={"fontSize": "12px"}
                            )
                        ], className="mb-2"),
                        html.Div([
                            html.Label("Altitude (ft MSL)", className="input-label-sm"),
                            dcc.Slider(id="altitude-slider", min=0, max=35000, step=500, value=0, marks={}, tooltip={"always_visible": True})
                        ], className="mb-2"),
                        dbc.Row([
                            dbc.Col([
                                html.Label("OAT (°C)", className="input-label-sm"),
                                dcc.Input(id="oat-input", type="number", value=15, min=-50, max=50, step=1, className="input-small", style={"width": "100%"})
                            ], width=3),
                            dbc.Col([
                                html.Label("OAT (°F)", className="input-label-sm"),
                                dcc.Input(id="oat-fahrenheit-display", type="text", value="59", disabled=True, className="input-small", style={"width": "100%", "backgroundColor": "#f5f5f5"})
                            ], width=3),
                            dbc.Col([
                                html.Label("Altimeter", className="input-label-sm"),
                                dcc.Input(id="altimeter-input", type="number", value=29.92, min=28.0, max=31.0, step=0.01, className="input-small", style={"width": "100%"})
                            ], width=6)
                        ], className="mb-2"),
                        html.Div([
                            html.Div(id="pa-da-display", className="pa-da-box", children=[
                                html.Span("PA: 0 ft | DA: 0 ft", style={"fontSize": "11px", "color": "#666"})
                            ])
                        ], className="mb-2"),
                    ], title="Environment", item_id="environment"),

                    # Overlay Options
                    dbc.AccordionItem([
                        html.Div([
                            html.Label("Airspeed Units", className="input-label-sm", style={"marginRight": "10px"}),
                            dbc.ButtonGroup([
                                dbc.Button("KIAS", id="btn-kias", className="segment-btn active", n_clicks=0),
                                dbc.Button("MPH", id="btn-mph", className="segment-btn", n_clicks=0),
                            ], className="segment-control"),
                            dcc.Store(id="unit-select", data="KIAS"),
                        ], className="mb-2 d-flex align-items-center"),
                        # Overlay toggles with help icons
                        html.Div([
                            html.Div([
                                html.Div([
                                    html.Span("Ps Contours", className="overlay-label"),
                                    html.Span("?", id="help-ps", className="help-icon", n_clicks=0)
                                ], className="label-group"),
                                dbc.Switch(id="toggle-ps", value=False, className="form-switch")
                            ], className="overlay-row"),
                            html.Div([
                                html.Div([
                                    html.Span("Intermediate G Lines", className="overlay-label"),
                                    html.Span("?", id="help-g", className="help-icon", n_clicks=0)
                                ], className="label-group"),
                                dbc.Switch(id="toggle-g", value=True, className="form-switch")
                            ], className="overlay-row"),
                            html.Div([
                                html.Div([
                                    html.Span("Turn Radius Lines", className="overlay-label"),
                                    html.Span("?", id="help-radius", className="help-icon", n_clicks=0)
                                ], className="label-group"),
                                dbc.Switch(id="toggle-radius", value=True, className="form-switch")
                            ], className="overlay-row"),
                            html.Div([
                                html.Div([
                                    html.Span("Angle of Bank Shading", className="overlay-label"),
                                    html.Span("?", id="help-aob", className="help-icon", n_clicks=0)
                                ], className="label-group"),
                                dbc.Switch(id="toggle-aob", value=True, className="form-switch")
                            ], className="overlay-row"),
                            html.Div([
                                html.Div([
                                    html.Span("Negative G Envelope", className="overlay-label"),
                                    html.Span("?", id="help-negative-g", className="help-icon", n_clicks=0)
                                ], className="label-group"),
                                dbc.Switch(id="toggle-negative-g", value=False, className="form-switch")
                            ], className="overlay-row"),
                        ], className="mb-2"),
                        # Hidden store to maintain compatibility with existing callbacks
                        dcc.Store(id="overlay-toggle", data=["g", "radius", "aob"]),
                        html.Div([
                            html.Label("Engine Failure Simulation", className="input-label-sm"),
                            dbc.Checklist(
                                id="oei-toggle",
                                options=[{"label": "Simulate One Engine Inoperative", "value": "enabled"}],
                                value=[],
                                switch=True,
                                className="switch-list"
                            )
                        ], id="oei-container", className="mb-2"),
                        html.Div([
                            html.Div([
                                html.Div([
                                    html.Span("Dynamic Vmc", className="overlay-label"),
                                    html.Span("?", id="help-dvmc", className="help-icon", n_clicks=0)
                                ], className="label-group"),
                                dbc.Switch(id="toggle-vmca", value=False, className="form-switch")
                            ], className="overlay-row"),
                            html.Div([
                                html.Div([
                                    html.Span("Dynamic Vyse", className="overlay-label"),
                                    html.Span("?", id="help-dvyse", className="help-icon", n_clicks=0)
                                ], className="label-group"),
                                dbc.Switch(id="toggle-vyse", value=False, className="form-switch")
                            ], className="overlay-row"),
                        ], id="multi-engine-toggles", style={"display": "none"}, className="mb-2"),
                        # Hidden store for multi-engine options
                        dcc.Store(id="multi-engine-toggle-options", data=[]),
                        html.Div([
                            html.Label("Propeller Condition", className="input-label-sm", style={"marginBottom": "6px"}),
                            dbc.ButtonGroup([
                                dbc.Button("Feathered", id="btn-feathered", className="segment-btn active", n_clicks=0),
                                dbc.Button("Stationary", id="btn-stationary", className="segment-btn", n_clicks=0),
                                dbc.Button("Windmilling", id="btn-windmilling", className="segment-btn", n_clicks=0),
                            ], className="segment-control"),
                            dcc.Store(id="prop-condition", data="feathered"),
                        ], id="prop-condition-container", style={"display": "none"})
                    ], title="Overlay Options", item_id="overlays"),

                    # Maneuver Overlays
                    dbc.AccordionItem([
                        html.Div([
                            html.Div([
                                html.Label("Maneuver", className="input-label-sm"),
                                html.Span("?", id="help-maneuver", className="help-icon", n_clicks=0)
                            ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}),
                            dcc.Dropdown(
                                id="maneuver-select", className="dropdown",
                                options=[
                                    {"label": "Steep Turn", "value": "steep_turn"},
                                    {"label": "Chandelle", "value": "chandelle"}
                                ],
                                placeholder="Select a Maneuver",
                                style={"width": "100%"}
                            )
                        ], className="mb-2"),
                        html.Div(id="maneuver-options-container"),
                        # Hidden help-ghost element for callback
                        html.Span("?", id="help-ghost", className="help-icon", n_clicks=0, style={"display": "none"})
                    ], title="Maneuver Overlays", item_id="maneuvers"),
                ], id="sidebar-accordion", active_item=["config"], always_open=True, className="sidebar-accordion"),
            ], id="sidebar-container", xs=12, md=4, className="resizable-sidebar"),

            # Graph Column
            dbc.Col([
                html.Div([
                    # Export toolbar (overlays on graph)
                    html.Div([
                        html.Button("PNG", id="png-button", className="btn-export"),
                        html.Button("PDF", id="pdf-button", className="btn-export"),
                        dcc.Download(id="png-download"),
                        dcc.Download(id="pdf-download"),
                    ], className="export-toolbar"),

                    html.Div([
                        dcc.Graph(
                            id="em-graph",
                            config={
                                "staticPlot": False,
                                "displaylogo": False,
                                "displayModeBar": False,
                                "responsive": True,
                                "scrollZoom": False,
                            },
                            figure={"layout": {"paper_bgcolor": "#f7f9fc", "plot_bgcolor": "#f7f9fc", "autosize": True, "hovermode": "closest"}},
                            className="dash-graph"
                        )
                    ], className="graph-panel"),

                    # Legal Section (below graph)
                    html.Div([
                        html.Span("Full Legal Disclaimer", id="open-disclaimer", className="legal-link"),
                        html.Span("|", className="separator"),
                        html.Span("Terms of Use & Privacy Policy", id="open-terms-policy", className="legal-link"),
                        html.Span("|", className="separator"),
                        html.Span("\u00a9 2026 Nicholas Len, AEROEDGE. All rights reserved.", style={"color": "#888", "fontSize": "12px"}),
                    ], className="legal-links"),
                ], className="graph-wrapper"),
            ], className="graph-column"),
        ], className="main-row"),
    ], className="full-height-container")

def mobile_layout():
    return html.Div([
        # Single Column Layout
        html.Div([
            # Header banner with centered logo (same style as desktop)
            html.Div([
                html.Div([
                    html.A(
                        html.Img(src="/assets/logo.png", className="banner-logo", style={"height": "40px"}),
                        href="https://flyaeroedge.com",
                    )
                ], className="banner-inner")
            ], className="banner-header"),

            # Quick links row
            html.Div([
                html.Span("Quick Start", id="open-readme", className="quick-link link-blue", style={"cursor": "pointer"}),
                html.Span("|", className="separator"),
                html.A("Report Issue", href="https://forms.gle/1xP29PwFze5MHCTZ7", target="_blank", className="quick-link link-danger"),
                html.Span("|", className="separator"),
                html.A("Contact", href="https://forms.gle/AqS1uuTgcY6sRHob9", target="_blank", className="quick-link link-blue"),
                html.Span("|", className="separator"),
                html.A("Maneuver Overlay", href="https://overlay.flyaeroedge.com", target="_blank", className="quick-link link-orange"),
            ], className="quick-links-bar-slim"),

            # Configuration toggle bar
            html.Div([
                html.Span("Configuration"),
                html.Button("▼", id="mobile-settings-toggle", className="mobile-config-btn"),
            ], className="mobile-config-bar"),

            # Collapsible Settings Content
            dbc.Collapse([
                html.Div([
                    # Action buttons
                    html.Div([
                        dbc.Button("Edit/Create Aircraft", id="edit-aircraft-button", className="btn-sm btn-primary-orange", size="sm"),
                        dcc.Upload(id="upload-aircraft", children=dbc.Button("Load Aircraft File", className="btn-sm btn-primary-orange", size="sm"), multiple=False, accept=".json"),
                    ], className="mobile-action-btns"),

                    # Aircraft Selection
                    html.Div([
                        html.Label("Aircraft", className="input-label-sm"),
                        dcc.Dropdown(id="aircraft-select", options=[], placeholder="Select Aircraft...", className="dropdown")
                    ], className="mb-2"),

                    # Compact config section
                    html.Div([
                        html.Div([
                            html.Label("Engine", className="input-label-sm"),
                            dcc.Dropdown(id="engine-select", className="dropdown"),
                        ], className="mb-2"),
                        html.Div([
                            html.Label("Category", className="input-label-sm"),
                            dcc.Dropdown(id="category-select", className="dropdown")
                        ], className="mb-2"),
                        html.Div([
                            html.Label("Flaps", className="input-label-sm"),
                            dcc.Dropdown(id="config-select", className="dropdown")
                        ], className="mb-2"),
                        html.Div([
                            html.Label("Gear", className="input-label-sm"),
                            dcc.Dropdown(id="gear-select", className="dropdown")
                        ], id="gear-select-container", className="mb-2", style={"display": "none"}),
                        html.Div([
                            html.Label("Weight", className="input-label-sm"),
                            html.Div(id="total-weight-display", className="weight-box-sm")
                        ], className="mb-2"),
                        dbc.Row([
                            dbc.Col([
                                html.Label("Pax", className="input-label-sm"),
                                dcc.Dropdown(id="occupants-select", className="dropdown-small")
                            ], width=6),
                            dbc.Col([
                                html.Label("Pax Wt", className="input-label-sm"),
                                dcc.Input(id="passenger-weight-input", type="number", value=180, min=50, max=400, step=1, className="input-small")
                            ], width=6)
                        ], className="mb-2"),
                        html.Div([
                            html.Label("Fuel (gal)", className="input-label-sm"),
                            dcc.Slider(id="fuel-slider", min=0, max=50, step=1, value=20, marks={}, tooltip={"always_visible": True})
                        ], className="mb-2"),
                        html.Div([
                            html.Label("Power", className="input-label-sm"),
                            dcc.Slider(id="power-setting", min=0.05, max=1.0, step=0.05, value=0.50,
                                marks={0.05: "IDLE", 0.5: "50%", 1: "100%"}, tooltip={"always_visible": True})
                        ], className="mb-2"),
                        html.Div([
                            dcc.Slider(id="cg-slider", min=0, max=1, value=0.5, step=0.01)
                        ], id="cg-slider-container", className="mb-2"),
                        html.Div([
                            html.Label("FPA (deg)", className="input-label-sm"),
                            dcc.Slider(id="pitch-angle", min=-15, max=25, step=1, value=0,
                                marks={-15: "-15", 0: "0", 25: "25"}, tooltip={"always_visible": True})
                        ], className="mb-2"),
                    ], id="config-details"),

                    # Environment (compact)
                    html.Div([
                        html.Label("Airport", className="input-label-sm"),
                        dcc.Dropdown(id="airport-select", options=AIRPORT_OPTIONS, placeholder="Search...", searchable=True, clearable=True)
                    ], className="mb-2"),
                    html.Div([
                        html.Label("Altitude (ft)", className="input-label-sm"),
                        dcc.Slider(id="altitude-slider", min=0, max=35000, step=500, value=0, marks={}, tooltip={"always_visible": True})
                    ], className="mb-2"),
                    dbc.Row([
                        dbc.Col([
                            html.Label("OAT °C", className="input-label-sm"),
                            dcc.Input(id="oat-input", type="number", value=15, min=-50, max=50, step=1, className="input-small", style={"width": "100%"})
                        ], width=4),
                        dbc.Col([
                            html.Label("°F", className="input-label-sm"),
                            dcc.Input(id="oat-fahrenheit-display", type="text", value="59", disabled=True, className="input-small", style={"width": "100%", "backgroundColor": "#eee"})
                        ], width=4),
                        dbc.Col([
                            html.Label("Altim", className="input-label-sm"),
                            dcc.Input(id="altimeter-input", type="number", value=29.92, min=28.0, max=31.0, step=0.01, className="input-small", style={"width": "100%"})
                        ], width=4)
                    ], className="mb-2"),
                    html.Div(id="pa-da-display", className="pa-da-box-sm", children=[
                        html.Span("PA: 0 ft | DA: 0 ft", style={"fontSize": "10px", "color": "#666"})
                    ]),

                    # Overlays (compact)
                    html.Div([
                        html.Label("Units", className="input-label-sm", style={"marginRight": "8px"}),
                        dbc.RadioItems(id="unit-select", options=[{"label": "KIAS", "value": "KIAS"}, {"label": "MPH", "value": "MPH"}],
                            value="KIAS", inline=True, className="radio-sm")
                    ], className="mb-2 d-flex align-items-center"),
                    dcc.Checklist(id="mobile-overlay-checklist",
                        options=[
                            {"label": "Ps", "value": "ps"},
                            {"label": "G Lines", "value": "g"},
                            {"label": "Radius", "value": "radius"},
                            {"label": "AoB", "value": "aob"},
                            {"label": "Neg G", "value": "negative_g"}
                        ],
                        value=["g", "radius", "aob"],
                        inline=True, className="checklist-compact mb-2"
                    ),
                    dcc.Store(id="overlay-toggle", data=["g", "radius", "aob"]),
                    html.Div([
                        dcc.Checklist(id="oei-toggle", options=[{"label": "OEI Sim", "value": "enabled"}], value=[], inline=True)
                    ], id="oei-container", className="mb-2"),
                    html.Div([
                        dcc.Checklist(id="multi-engine-toggle-options",
                            options=[{"label": "Dyn Vmc", "value": "vmca"}, {"label": "Dyn Vyse", "value": "dynamic_vyse"}],
                            value=[], inline=True)
                    ], id="multi-engine-toggles", style={"display": "none"}),
                    html.Div([
                        dcc.RadioItems(id="prop-condition",
                            options=[{"label": "Feath", "value": "feathered"}, {"label": "Stat", "value": "stationary"}, {"label": "Wmill", "value": "windmilling"}],
                            value="feathered", inline=True, className="radio-sm")
                    ], id="prop-condition-container", style={"display": "none"}),

                    # Maneuver
                    html.Div([
                        html.Label("Maneuver", className="input-label-sm"),
                        dcc.Dropdown(id="maneuver-select", options=[{"label": "Steep Turn", "value": "steep_turn"}, {"label": "Chandelle", "value": "chandelle"}], placeholder="Select...")
                    ], className="mb-2"),
                    html.Div(id="maneuver-options-container"),
                ], className="mobile-settings-content")
            ], id="mobile-settings-collapse", is_open=False),

            # Graph (always visible)
            html.Div([
                html.Div([
                    html.Button("PNG", id="png-button", className="btn-export-sm"),
                    html.Button("PDF", id="pdf-button", className="btn-export-sm"),
                    dcc.Download(id="png-download"),
                    dcc.Download(id="pdf-download"),
                ], className="export-toolbar-mobile"),
                dcc.Graph(
                    id="em-graph",
                    config={
                        "staticPlot": False,
                        "displaylogo": False,
                        "displayModeBar": False,
                        "responsive": True,
                        "scrollZoom": False,
                        "doubleClick": False,
                    },
                    figure={"layout": {
                        "paper_bgcolor": "#f7f9fc",
                        "plot_bgcolor": "#f7f9fc",
                        "autosize": True,
                        "hovermode": "closest",
                        "dragmode": False,
                        "xaxis": {"fixedrange": True},
                        "yaxis": {"fixedrange": True},
                    }},
                    className="dash-graph",
                    style={"height": "60vh", "width": "100%"}
                )
            ], className="mobile-graph-container"),

            # Legal footer
            html.Div([
                html.Span("Disclaimer", id="open-disclaimer", className="legal-link-sm"),
                html.Span(" | ", style={"color": "#999"}),
                html.Span("Terms", id="open-terms-policy", className="legal-link-sm"),
                html.Span(" | © 2025 AeroEdge", style={"color": "#999", "fontSize": "9px"})
            ], className="mobile-legal"),

            # Hidden placeholders for desktop-only components (prevents callback errors)
            html.Div([
                # Desktop toggle switches - use hidden switches
                dbc.Switch(id="toggle-ps", value=False, style={"display": "none"}),
                dbc.Switch(id="toggle-g", value=True, style={"display": "none"}),
                dbc.Switch(id="toggle-radius", value=True, style={"display": "none"}),
                dbc.Switch(id="toggle-aob", value=True, style={"display": "none"}),
                dbc.Switch(id="toggle-negative-g", value=False, style={"display": "none"}),
                dbc.Switch(id="toggle-vmca", value=False, style={"display": "none"}),
                dbc.Switch(id="toggle-vyse", value=False, style={"display": "none"}),
                # Desktop unit buttons
                html.Button("KIAS", id="btn-kias", style={"display": "none"}),
                html.Button("MPH", id="btn-mph", style={"display": "none"}),
                # Desktop prop condition buttons
                html.Button("Feathered", id="btn-feathered", style={"display": "none"}),
                html.Button("Stationary", id="btn-stationary", style={"display": "none"}),
                html.Button("Windmilling", id="btn-windmilling", style={"display": "none"}),
                # Desktop help icons
                html.Span(id="help-fpa", style={"display": "none"}),
                html.Span(id="help-ps", style={"display": "none"}),
                html.Span(id="help-g", style={"display": "none"}),
                html.Span(id="help-radius", style={"display": "none"}),
                html.Span(id="help-aob", style={"display": "none"}),
                html.Span(id="help-negative-g", style={"display": "none"}),
                html.Span(id="help-dvmc", style={"display": "none"}),
                html.Span(id="help-dvyse", style={"display": "none"}),
                html.Span(id="help-maneuver", style={"display": "none"}),
                html.Span(id="help-ghost", style={"display": "none"}),
                # Desktop sidebar elements
                html.Button("«", id="sidebar-collapse-btn", style={"display": "none"}),
                html.Div(id="sidebar-container", className="resizable-sidebar", style={"display": "none"}),
                dbc.Accordion(id="sidebar-accordion", style={"display": "none"}),
            ], style={"display": "none"}),
        ], className="mobile-main"),
    ], className="mobile-container")


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

    is_mobile = screen_width < 768

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
    # We no longer reload from disk on navigation.
    # The store is initialized at layout time and updated by save/upload.
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
    Input("aircraft-data-store", "data"),
)
def update_aircraft_options(data):
    if not data:
        # No data yet -> no options
        return []
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


@app.callback(
    Output("config-details", "style"),
    Output("sidebar-accordion", "active_item"),
    Input("aircraft-select", "value"),
)
def expand_ui_on_aircraft_select(ac_name):
    """Show config details and expand all accordions when aircraft is selected."""
    if not ac_name:
        return {"display": "none"}, ["config"]
    return {"display": "block"}, ["config", "environment", "overlays", "maneuvers"]

from dash import html
from dash.exceptions import PreventUpdate
from dash.dependencies import Input, Output

# Segmented control for airspeed units
@app.callback(
    Output("unit-select", "data"),
    Output("btn-kias", "className"),
    Output("btn-mph", "className"),
    Input("btn-kias", "n_clicks"),
    Input("btn-mph", "n_clicks"),
    prevent_initial_call=True
)
def toggle_airspeed_units(kias_clicks, mph_clicks):
    triggered = ctx.triggered_id
    if triggered == "btn-kias":
        return "KIAS", "segment-btn active", "segment-btn"
    elif triggered == "btn-mph":
        return "MPH", "segment-btn", "segment-btn active"
    return "KIAS", "segment-btn active", "segment-btn"

# Segmented control for propeller condition
@app.callback(
    Output("prop-condition", "data"),
    Output("btn-feathered", "className"),
    Output("btn-stationary", "className"),
    Output("btn-windmilling", "className"),
    Input("btn-feathered", "n_clicks"),
    Input("btn-stationary", "n_clicks"),
    Input("btn-windmilling", "n_clicks"),
    prevent_initial_call=True
)
def toggle_prop_condition(feathered_clicks, stationary_clicks, windmilling_clicks):
    triggered = ctx.triggered_id
    if triggered == "btn-feathered":
        return "feathered", "segment-btn active", "segment-btn", "segment-btn"
    elif triggered == "btn-stationary":
        return "stationary", "segment-btn", "segment-btn active", "segment-btn"
    elif triggered == "btn-windmilling":
        return "windmilling", "segment-btn", "segment-btn", "segment-btn active"
    return "feathered", "segment-btn active", "segment-btn", "segment-btn"

@app.callback(
    Output("multi-engine-toggles", "style"),
    Output("prop-condition-container", "style"),
    Input("aircraft-select", "value"),
    Input("oei-toggle", "value"),
    Input("multi-engine-toggle-options", "data"),
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

    # Fuel - create intuitive even marks
    fuel_max = ac["fuel_capacity_gal"]

    # Determine a nice step size based on fuel capacity
    if fuel_max <= 20:
        step = 5
    elif fuel_max <= 50:
        step = 10
    elif fuel_max <= 100:
        step = 20
    elif fuel_max <= 200:
        step = 25
    else:
        step = 50

    # Generate marks at even intervals
    fuel_marks = {}
    mark_val = 0
    while mark_val < fuel_max:
        fuel_marks[mark_val] = str(mark_val)
        mark_val += step
    # Always include the max value
    fuel_marks[fuel_max] = str(fuel_max)

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


# =============================================================================
# AIRPORT & ENVIRONMENT CALLBACKS
# =============================================================================

@app.callback(
    Output("altitude-slider", "min"),
    Output("altitude-slider", "value"),
    Output("altitude-slider", "marks", allow_duplicate=True),
    Input("airport-select", "value"),
    State("altitude-slider", "value"),
    State("altitude-slider", "max"),
    prevent_initial_call=True
)
def update_altitude_from_airport(airport_id, current_alt, max_alt):
    """Update altitude slider min and value based on selected airport."""
    if not airport_id:
        # No airport selected - reset to sea level minimum
        marks = {i: str(i) for i in range(0, int(max_alt) + 1, 5000)}
        marks[0] = "Sea Level"
        return 0, 0, marks

    # Find airport elevation
    airport = get_airport_by_id(AIRPORT_DATA, airport_id)
    if not airport:
        return 0, current_alt, dash.no_update

    field_elev = airport.get("elevation_ft", 0)

    # Round to nearest 100 for cleaner slider
    field_elev_rounded = int(round(field_elev / 100) * 100)

    # Generate marks starting from field elevation
    marks = {}
    for i in range(0, int(max_alt) + 1, 5000):
        if i >= field_elev_rounded:
            marks[i] = str(i)
    marks[field_elev_rounded] = f"{field_elev_rounded} (Field)"
    if max_alt not in marks:
        marks[int(max_alt)] = f"{int(max_alt)} ft"

    # Set value to field elevation if current is below
    new_value = max(field_elev_rounded, current_alt) if current_alt else field_elev_rounded

    return field_elev_rounded, new_value, marks


@app.callback(
    Output("pa-da-display", "children"),
    Input("altitude-slider", "value"),
    Input("oat-input", "value"),
    Input("altimeter-input", "value"),
)
def update_pa_da_display(field_elev, oat_c, altimeter):
    """Calculate and display Pressure Altitude and Density Altitude."""
    field_elev = field_elev or 0
    oat_c = oat_c if oat_c is not None else 15
    altimeter = altimeter if altimeter is not None else 29.92

    # Calculate Pressure Altitude
    pa = compute_pressure_altitude(field_elev, altimeter)

    # Calculate Density Altitude
    da = compute_density_altitude(pa, oat_c)

    # Calculate ISA temperature at this altitude for reference
    isa_temp = TEMP_SL_C - (pa * LAPSE_RATE_K_FT)

    # Color code DA based on how much above PA it is
    da_diff = da - pa
    if da_diff > 3000:
        da_color = "#dc3545"  # Red - hot day, significant DA increase
    elif da_diff > 1000:
        da_color = "#fd7e14"  # Orange - warm
    elif da_diff < -1000:
        da_color = "#0d6efd"  # Blue - cold
    else:
        da_color = "#198754"  # Green - near standard

    return html.Div([
        html.Span(f"PA: {int(pa):,} ft", style={"marginRight": "15px", "fontSize": "12px"}),
        html.Span(f"DA: {int(da):,} ft", style={"color": da_color, "fontWeight": "bold", "fontSize": "12px"}),
        html.Span(f" (ISA: {isa_temp:.0f}°C)", style={"fontSize": "10px", "color": "#888", "marginLeft": "8px"})
    ])


@app.callback(
    Output("oat-input", "value"),
    Input("altitude-slider", "value"),
    prevent_initial_call=True
)
def update_default_oat(field_elev):
    """Set default OAT to ISA temperature at field elevation when altitude changes."""
    field_elev = field_elev or 0
    # ISA temperature at altitude
    isa_temp = TEMP_SL_C - (field_elev * LAPSE_RATE_K_FT)
    return round(isa_temp)


@app.callback(
    Output("oat-fahrenheit-display", "value"),
    Input("oat-input", "value"),
)
def update_oat_fahrenheit(oat_c):
    """Convert OAT from Celsius to Fahrenheit for display."""
    oat_c = oat_c if oat_c is not None else 15
    oat_f = (oat_c * 9/5) + 32
    return f"{oat_f:.0f}"


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
    cg_range = cg_max - cg_min

    # Determine step size based on CG range
    if cg_range <= 5:
        step = 0.5
    elif cg_range <= 10:
        step = 1.0
    else:
        step = 2.0

    # Generate marks at even intervals
    import math
    # Start from the first even step value >= cg_min
    first_mark = math.ceil(cg_min / step) * step

    cg_marks = {}
    # Add FWD label at min
    cg_marks[cg_min] = f"FWD"

    # Add intermediate marks
    mark_val = first_mark
    while mark_val < cg_max:
        if mark_val > cg_min:  # Don't duplicate the min
            cg_marks[round(mark_val, 1)] = f"{mark_val:.1f}"
        mark_val += step

    # Add AFT label at max
    cg_marks[cg_max] = f"AFT"

    dprint("CG DEBUG:", {
        "cg_min": cg_min,
        "cg_max": cg_max,
        "step": step,
        "marks": cg_marks
    })

    return html.Div([
        html.Label("Center of Gravity (inches)", className="input-label-sm"),
        dcc.Slider(
            id="cg-slider",
            min=cg_min,
            max=cg_max,
            value=round((cg_min + cg_max) / 2, 2),
            step=0.1,
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
    Output("gear-select-container", "style"),
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
    fuel = fuel if fuel is not None else 0
    fuel_weight = fuel * ac["fuel_weight_per_gal"]
    pax_weight = pax_weight if pax_weight is not None else 180
    occupants = occupants if occupants is not None else 0
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
    pressure_altitude=0,
    oat_c=15,
    unit="KIAS",
    bank_angles_deg=np.linspace(-5, 10, 50)
):
    """
    Returns Vmca values across a range of bank angles based on power, weight, CG,
    prop condition, and density altitude.

    Physics basis:
    - Vmc is the minimum speed at which directional control can be maintained with
      critical engine inoperative and max power on the operating engine
    - Published Vmc is typically at: max gross weight, most aft CG, sea level,
      5° bank into dead engine, critical engine windmilling/feathered

    Args:
        published_vmca: Published Vmca speed (KIAS) - typically at max weight, aft CG
        power_fraction: Power setting on operating engine (0-1)
        total_weight: Current aircraft weight (lbs)
        reference_weight: Weight at which Vmca was published (typically max gross)
        cg: Current CG position
        cg_range: [forward_limit, aft_limit] CG range
        prop_condition: "feathered", "stationary", or "windmilling"
        pressure_altitude: Pressure altitude in feet
        oat_c: Outside air temperature in Celsius
        unit: Output unit ("KIAS" or "MPH")
        bank_angles_deg: Array of bank angles to compute Vmca for

    Returns:
        (bank_angles_deg, vmca_vals): Tuple of bank angles and corresponding Vmca values
    """
    # --- Extract usable numeric Vmca if a dict was passed ---
    if isinstance(published_vmca, dict):
        published_vmca = published_vmca.get("clean_up") or next(iter(published_vmca.values()), None)

    if not isinstance(published_vmca, (int, float)):
        return bank_angles_deg, np.full_like(bank_angles_deg, np.nan)

    # --- Calculate density altitude for altitude effects ---
    isa_temp_c = TEMP_SL_C - (pressure_altitude * LAPSE_RATE_K_FT)
    temp_dev_c = oat_c - isa_temp_c
    density_altitude = pressure_altitude + (120 * temp_dev_c)

    # --- Base modifier (1.0 = no change from published) ---
    modifiers = np.ones_like(bank_angles_deg, dtype=float)

    # --- Power effect ---
    # Lower power = less asymmetric thrust = lower Vmc
    # At full power: modifier = 1.0 (published condition)
    # At 50% power: modifier ≈ 0.85
    # At idle: modifier ≈ 0.70
    power_mod = 0.70 + 0.30 * power_fraction
    modifiers *= np.clip(power_mod, 0.70, 1.05)

    # --- Weight effect ---
    # Lighter weight = less inertia to resist yaw = higher Vmc
    # Published Vmc is at max gross, so lighter = higher Vmc
    # Typical effect: ~1 kt per 100 lbs from max gross
    weight_ratio = total_weight / reference_weight
    # Invert: lighter (ratio < 1) should increase Vmc
    weight_factor = 1.0 + 0.15 * (1.0 - weight_ratio)
    modifiers *= np.clip(weight_factor, 0.90, 1.15)

    # --- CG effect ---
    # Aft CG = shorter moment arm for rudder = higher Vmc
    # Published Vmc is typically at aft CG limit
    # Forward CG improves directional control (lower Vmc)
    cg_span = cg_range[1] - cg_range[0]
    if cg_span > 0:
        # cg_percent: 0 = forward limit, 1 = aft limit
        cg_percent = (cg - cg_range[0]) / cg_span
        # At forward CG: slight reduction; at aft CG: baseline (published condition)
        cg_factor = 0.96 + 0.04 * cg_percent
    else:
        cg_factor = 1.0
    modifiers *= cg_factor

    # --- Density altitude effect ---
    # Higher DA = less power available from operating engine = lower Vmc
    # Also less rudder effectiveness, but power effect dominates
    # Typical: ~1% reduction per 3,000 ft DA
    da_factor = 1.0 - (density_altitude / 30000.0) * 0.10
    modifiers *= np.clip(da_factor, 0.85, 1.0)

    # --- Prop condition effect ---
    # Windmilling: max drag/yaw from dead engine = highest Vmc
    # Feathered: minimum drag = lowest Vmc
    prop_factors = {
        "windmilling": 1.08,   # +8% - significant yaw from windmilling prop
        "stationary": 1.03,    # +3% - some drag, no rotation
        "feathered": 0.92      # -8% - minimum drag, best case
    }
    modifiers *= prop_factors.get(prop_condition, 1.0)

    # --- Bank angle effect (refined model) ---
    # The relationship between bank and Vmc is nonlinear:
    # - Wings level (0°): High sideslip needed, moderate Vmc
    # - 5° into dead engine: Optimal - sideslip eliminated, lowest Vmc
    # - Bank away from dead engine (negative): Dramatically increases Vmc
    # - Excessive bank into dead engine (>5°): Increases Vmc due to increased
    #   load factor and loss of vertical lift component
    bank_mod = np.ones_like(bank_angles_deg, dtype=float)
    for i, bank in enumerate(bank_angles_deg):
        if bank < 0:
            # Banking away from dead engine - significant Vmc increase
            # Up to +15% at -5° bank
            bank_mod[i] = 1.0 + 0.03 * abs(bank)
        elif 0 <= bank <= 5:
            # Optimal range - Vmc decreases as bank approaches 5°
            # Minimum at 5° (published condition)
            bank_mod[i] = 1.0 - 0.04 * (bank / 5.0)
        else:
            # Beyond optimal bank - Vmc increases due to load factor
            # Gradual increase: ~0.5% per degree beyond 5°
            bank_mod[i] = 0.96 + 0.005 * (bank - 5)

    modifiers *= bank_mod

    # --- Final Vmca array ---
    vmca_vals = published_vmca * modifiers

    # Convert to MPH if needed
    if unit == "MPH":
        vmca_vals = vmca_vals * KTS_TO_MPH

    return bank_angles_deg, vmca_vals


def calculate_dynamic_vyse(
    published_vyse,
    total_weight,
    reference_weight,
    pressure_altitude=0,
    oat_c=15,
    gear_position="up",
    flap_config="clean",
    prop_condition="feathered"
):
    """
    Compute dynamic Vyse (best single-engine rate of climb speed) based on weight,
    density altitude, configuration, and prop condition.

    Physics basis:
    - Vyse is the speed that provides best rate of climb with one engine inoperative
    - It's determined by the point where excess thrust power is maximum
    - Weight affects required lift and thus optimal L/D point
    - Density altitude affects available power from operating engine
    - Configuration (gear, flaps) affects drag and optimal speed

    Args:
        published_vyse: Baseline Vyse (KIAS) - typically at max gross, sea level
        total_weight: Current aircraft weight (lbs)
        reference_weight: Weight at which Vyse is published (typically max gross)
        pressure_altitude: Pressure altitude in feet
        oat_c: Outside air temperature in Celsius
        gear_position: "up" or "down"
        flap_config: "clean", "takeoff", or "landing"
        prop_condition: "feathered", "stationary", or "windmilling"

    Returns:
        Adjusted Vyse in KIAS
    """
    # --- Calculate density altitude ---
    isa_temp_c = TEMP_SL_C - (pressure_altitude * LAPSE_RATE_K_FT)
    temp_dev_c = oat_c - isa_temp_c
    density_altitude = pressure_altitude + (120 * temp_dev_c)

    # --- Weight effect ---
    # Heavier aircraft needs to fly faster for optimal L/D
    # Vyse scales approximately with sqrt(weight ratio) for constant L/D
    # Simplified: ~5% change for 10% weight change
    weight_ratio = total_weight / reference_weight
    weight_factor = 1.0 + 0.5 * (weight_ratio - 1.0)
    weight_factor = np.clip(weight_factor, 0.92, 1.08)

    # --- Density altitude effect (refined) ---
    # At higher DA, TAS increases for same IAS, but available power decreases
    # The optimal IAS actually decreases slightly at altitude because:
    # - Less power available means flying at lower speed for best L/D
    # - But also less margin, so slightly higher IAS for safety
    # Net effect: very small change, approximately +0.5% per 5,000 ft DA
    # This is much less than the original 2% per 10,000 ft
    da_factor = 1.0 + (density_altitude / 50000.0) * 0.05
    da_factor = np.clip(da_factor, 1.0, 1.03)

    # --- Gear effect ---
    # Gear down = more drag = shifts L/D curve right = higher Vyse
    # Typical effect: +3-5% with gear down
    gear_factor = 1.04 if gear_position == "down" else 1.0

    # --- Flap effect ---
    # Flaps increase both lift and drag, shifting optimal speed
    # More flaps = more drag penalty = higher optimal speed
    flap_factors = {
        "clean": 1.00,
        "takeoff": 1.02,    # Small increase
        "landing": 1.05     # Larger increase due to more drag
    }
    config_factor = flap_factors.get(flap_config, 1.00)

    # --- Prop condition effect ---
    # Dead engine prop condition affects total drag
    # More drag from dead engine = need to fly slightly faster
    prop_factors = {
        "feathered": 0.98,    # Minimum drag - can fly slightly slower
        "stationary": 1.02,   # Moderate drag
        "windmilling": 1.05   # Maximum drag - need more speed
    }
    prop_factor = prop_factors.get(prop_condition, 1.0)

    # --- Final dynamic Vyse ---
    adjusted_vyse = (
        published_vyse
        * weight_factor
        * da_factor
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
    Input("overlay-toggle", "data"),
    Input("gear-select", "value"),
    Input("oei-toggle", "value"),
    Input("prop-condition", "data"),
    Input("cg-slider", "value"),
    Input("category-select", "value"),
    Input("unit-select", "data"),
    Input("multi-engine-toggle-options", "data"),
    Input("maneuver-select", "value"),
    Input({"type": "steepturn-aob", "index": ALL}, "value"),
    Input({"type": "steepturn-ias", "index": ALL}, "value"),
    Input({"type": "steepturn-standard", "index": ALL}, "value"),
    Input({"type": "steepturn-ghost", "index": ALL}, "value"),
    Input({"type": "chandelle-ias", "index": ALL}, "value"),
    Input({"type": "chandelle-bank", "index": ALL}, "value"),
    Input({"type": "chandelle-ghost", "index": ALL}, "value"),
    Input("pitch-angle", "value"),
    Input("screen-width", "data"),
    Input("oat-input", "value"),
    Input("altimeter-input", "value"),
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
    steepturn_standard_values,
    steepturn_ghost_values,
    chandelle_ias_values,
    chandelle_bank_values,
    chandelle_ghost_values,
    pitch_angle,
    screen_width,
    oat_c,
    altimeter_inhg
):
    t_start = time.perf_counter()
    import plotly.graph_objects as go  # <== you must ensure this is imported here if not at top of file
    
    # ---- existing validation, etc. ----
    if not ac_name or ac_name not in aircraft_data:
        return go.Figure()

    # === Resolution tuning based on screen width ===
    if screen_width is None:
        screen_width = 1400  # fallback for server-side calls

    if screen_width < 1200:
        aob_ias_step = 1.0     # 1 kt increments
        aob_tr_step = 1.0      # 1 deg/s increments
    else:
        aob_ias_step = 0.5     # 0.5 kt increments
        aob_tr_step = 0.5      # 0.5 deg/s increments

    # Handle None values for overlay lists
    overlay_toggle = overlay_toggle if overlay_toggle is not None else []
    multi_engine_toggle_options = multi_engine_toggle_options if multi_engine_toggle_options is not None else []

    all_overlays = overlay_toggle + multi_engine_toggle_options

    if not ac_name or ac_name not in aircraft_data:
        return go.Figure()  # Return an empty graph if no aircraft is selected

    if engine_name is None or engine_name not in aircraft_data[ac_name]["engine_options"]:
        raise PreventUpdate

    def convert_display_airspeed(ias_vals, unit):
        return ias_vals * KTS_TO_MPH if unit == "MPH" else ias_vals
    def convert_input_airspeed(ias_vals, unit):
        return ias_vals / KTS_TO_MPH if unit == "MPH" else ias_vals
    
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
        hovermode="closest",        # ✅ enables hover tooltips
        autosize=True               # ✅ responsive sizing
    )
    
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
    # Aircraft drag/lift parameters - used throughout update_graph
    CD0 = ac.get("CD0", 0.025)
    e = ac.get("e", 0.8)
    AR = ac.get("aspect_ratio", 7.5)

    # === Environment calculations using OAT and altimeter ===
    # Default values if not provided
    oat_c = oat_c if oat_c is not None else 15
    altimeter_inhg = altimeter_inhg if altimeter_inhg is not None else 29.92

    # Calculate pressure altitude from field elevation and altimeter
    pressure_altitude = compute_pressure_altitude(altitude_ft, altimeter_inhg)

    # Use centralized air density calculation with OAT for accurate density
    rho = compute_air_density(pressure_altitude, oat_c)

    dprint("ENVIRONMENT DEBUG:", {
        "field_elev_ft": altitude_ft,
        "oat_c": oat_c,
        "altimeter_inhg": altimeter_inhg,
        "pressure_altitude": pressure_altitude,
        "density_altitude": compute_density_altitude(pressure_altitude, oat_c),
        "rho": rho
    })

    stall_data = ac.get("stall_speeds", {}).get(config, {})
    # Use weight-interpolated stall speed instead of just minimum
    vs_1g = interpolate_stall_speed(stall_data, weight) if stall_data else 30
    ias_start = max(0, int(vs_1g * 0.7))

    if config == "clean":
        max_speed = ac.get("Vne", 200)
        label = "Vne"
    else:
        max_speed = ac.get("Vfe", {}).get(config, 120)
        label = f"Vfe ({config})"

    max_speed_internal = max_speed  # always in KIAS for physics
    max_speed_display = convert_display_airspeed(max_speed, unit)

    ias_start = max(0, int(vs_1g * 0.8))  # Add dynamic padding (20% below Vs)
    ias_vals = np.arange(ias_start, max_speed + 1, 1)
    ias_vals_display = convert_display_airspeed(ias_vals, unit)
    
    g_curve_x, g_curve_y = [], []
    for ias in ias_vals:
        v = ias * KTS_TO_FPS
        omega = g * ((g_limit**2 - 1) ** 0.5) / v
        tr = omega * 180 / pi
        g_curve_x.append(ias)
        g_curve_y.append(tr)

    stall_x, stall_y = [], []
    # Use finer steps near stall speed for smoother curve, coarser elsewhere
    stall_ias_fine = np.concatenate([
        np.arange(ias_start, vs_1g + 15, 0.5),  # Fine steps near stall
        np.arange(vs_1g + 15, max_speed + 1, 2)  # Coarser steps elsewhere
    ])
    for ias in stall_ias_fine:
        v = ias * KTS_TO_FPS
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

    # === Early DVmc calculation to modify flight envelope ===
    dvmc_active = False
    if "vmca" in all_overlays and ac.get("engine_count", 1) > 1 and oei_active:
        dvmc_active = True
        published_vmca_early = ac.get("single_engine_limits", {}).get("Vmca", 70)
        reference_weight_early = ac.get("max_weight", 3600)
        cg_range_early = ac.get("cg_range", [10, 20])

        # Calculate DVmc curve
        bank_angles_early = np.linspace(5, 90, 150)
        _, vmca_vals_kias_early = calculate_vmca(
            published_vmca=published_vmca_early,
            power_fraction=power_fraction,
            total_weight=weight,
            reference_weight=reference_weight_early,
            cg=cg,
            cg_range=cg_range_early,
            prop_condition=prop_mode,
            pressure_altitude=pressure_altitude,
            oat_c=oat_c,
            bank_angles_deg=bank_angles_early
        )

        # Convert to turn rates
        v_fts_early = vmca_vals_kias_early * KTS_TO_FPS
        bank_rad_early = np.radians(bank_angles_early)
        omega_rad_early = g * np.tan(bank_rad_early) / v_fts_early
        turn_rates_early = np.degrees(omega_rad_early)

        # Modify stall boundary where DVmc is more restrictive
        stall_clipped_x_modified = []
        stall_clipped_y_modified = []

        for ias_stall, tr_stall in zip(stall_clipped_x, stall_clipped_y):
            # Interpolate DVmc speed at this turn rate
            if tr_stall >= min(turn_rates_early) and tr_stall <= max(turn_rates_early):
                dvmc_at_tr = np.interp(tr_stall, turn_rates_early, vmca_vals_kias_early)
                # Use max(stall, dvmc) as the effective boundary
                effective_ias = max(ias_stall, dvmc_at_tr)
            else:
                effective_ias = ias_stall
            stall_clipped_x_modified.append(effective_ias)
            stall_clipped_y_modified.append(tr_stall)

        # Replace stall boundary with modified version
        stall_clipped_x = stall_clipped_x_modified
        stall_clipped_y = stall_clipped_y_modified

    stall_clipped_x_display = convert_display_airspeed(np.array(stall_clipped_x), unit)
    g_clipped_x_display = convert_display_airspeed(np.array(g_clipped_x), unit)
    corner_ias_display = convert_display_airspeed(corner_ias, unit)

    if "negative_g" in overlay_toggle:
        # === Negative Lift Limit Curve ===
        # Use same fine steps near stall as positive boundary for consistency
        neg_stall_x, neg_stall_y = [], []
        for ias in stall_ias_fine:
            v = ias * KTS_TO_FPS
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
            v = ias * KTS_TO_FPS
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

    # Lift Limit - color changes when DVmc modifies the boundary
    lift_limit_color = "#DC143C" if dvmc_active else "red"
    lift_limit_name = "Lift Limit (DVmc)" if dvmc_active else "Lift Limit"
    fig.add_trace(go.Scatter(x=stall_clipped_x_display, y=stall_clipped_y,
        mode="lines", name=lift_limit_name, line=dict(color=lift_limit_color, width=3), hoverinfo="skip")),
    fig.add_trace(go.Scatter(x=g_clipped_x_display, y=g_clipped_y,
        mode="lines", name=f"Load Limit ({g_limit:.1f} G)", line=dict(color="black", width=3, dash="solid"), hoverinfo="skip")),
    fig.add_trace(go.Scatter(x=[corner_ias_display], y=[corner_tr],
        mode="markers", name=f"Corner Speed ({corner_ias_display:.0f} {unit})", marker=dict(color="orange", size=9, symbol="x"), hoverinfo="skip")),

    # Corner speed tick mark on x-axis
    fig.add_shape(
        type="line",
        x0=corner_ias_display, x1=corner_ias_display,
        y0=0, y1=-0.015,
        xref="x", yref="paper",
        line=dict(color="orange", width=1.5)
    )
    # Corner speed annotation on x-axis (inline with tick labels)
    fig.add_annotation(
        x=corner_ias_display,
        y=-0.06,
        yref="paper",
        xref="x",
        text=f"<b>{corner_ias_display:.0f}</b>",
        showarrow=False,
        font=dict(size=11, color="orange"),
    )

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
                v = ias * KTS_TO_FPS
                stall_v = np.sqrt((2 * weight * g_inter) / (rho * wing_area * cl_max))
                if v < stall_v:
                    continue
                omega = g * np.sqrt(g_inter**2 - 1) / v
                tr = omega * 180 / pi

                # Check DVmc limit when active
                dvmc_ok = True
                if dvmc_active:
                    dvmc_at_tr = np.interp(tr, turn_rates_early, vmca_vals_kias_early)
                    dvmc_ok = ias >= dvmc_at_tr

                if dvmc_ok:
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
                v = ias * KTS_TO_FPS
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

    # --- Ps GRID CALCULATION (only if Ps overlay enabled) ---
    Ps_masked = None
    ias_vals_ps_display = None
    tr_vals_ps = None

    if "ps" in overlay_toggle:
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
            V = ias_vals_ps_internal * KTS_TO_FPS
            TR_fixed = np.degrees(g * np.tan(aob_rad) / V)  # TR as a function of IAS
            TR = np.tile(TR_fixed, (len(ias_vals_ps_internal), 1)).T  # 2D grid shape
            IAS = np.tile(ias_vals_ps_internal, (len(TR), 1))
            tr_vals_ps = TR[:, 0]  # save for mask / plotting
        else:
            tr_vals_ps = np.arange(-100, 100, 1)
            IAS, TR = np.meshgrid(ias_vals_ps_internal, tr_vals_ps)

        V = IAS * KTS_TO_FPS  # convert to ft/s
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

        # Vertical speed term (ft/s); for gamma=0 this is just 0
        V_vertical = V * np.sin(gamma_rad)

        # Ps in knots per second
        Ps = ((T_available - D) * V / weight - V_vertical) * FPS_TO_KTS

        # Envelope mask (vectorized)
        v_fts_env = IAS * KTS_TO_FPS
        omega_rad_env = TR * (np.pi / 180)

        n_env = np.sqrt(1 + (v_fts_env * omega_rad_env / g) ** 2)
        stall_v_fts_env = np.sqrt((2 * weight * n_env) / (rho * wing_area * cl_max))
        stall_ias_env = stall_v_fts_env * FPS_TO_KTS

        tr_limit_pos_env = g * np.sqrt(g_limit**2 - 1) / v_fts_env * 180 / np.pi
        tr_limit_neg_env = g * np.sqrt(g_limit_neg**2 - 1) / v_fts_env * 180 / np.pi

        valid_pos = (TR >= 0) & (TR <= tr_limit_pos_env)
        valid_neg = (TR < 0) & (TR >= -tr_limit_neg_env)  # Negate limit for negative TR region

        # Base envelope mask
        within_env = (
            (IAS >= stall_ias_env) &
            (IAS <= max_speed_internal) &
            (valid_pos | valid_neg)
        )

        # Add DVmc masking when active
        if dvmc_active:
            # For each point, check if IAS >= DVmc at that turn rate
            dvmc_ias_at_tr = np.interp(TR, turn_rates_early, vmca_vals_kias_early)
            dvmc_mask = IAS >= dvmc_ias_at_tr
            within_env = within_env & dvmc_mask

        # Ps_masked = usable Ps; outside envelope = NaN
        Ps_masked = np.where(within_env, Ps, np.nan)

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
        IAS_vals = np.arange(ias_start, max_speed + 1, aob_ias_step)
        IAS_vals_display = convert_display_airspeed(IAS_vals, unit)
        ias_vals_display = convert_display_airspeed(ias_vals, unit)
        TR_vals = np.arange(0.1, 100, aob_tr_step)  # Start near 0 for full coverage
        IAS, TR = np.meshgrid(IAS_vals, TR_vals)
        V = IAS * KTS_TO_FPS
        omega_rad = TR * (np.pi / 180)

        # Compute angle of bank at each point
        AOB_rad = np.arctan(omega_rad * V / g)
        AOB_deg = np.degrees(AOB_rad)

        # Mask: only show valid points (stall + G-limit + Vne)
        n = np.sqrt(1 + (V * omega_rad / g) ** 2)
        n = np.maximum(n, 1.001)  # Enforce minimum 1 G load factor

        stall_v = np.sqrt((2 * weight * n) / (rho * wing_area * cl_max))
        stall_IAS = stall_v * FPS_TO_KTS
        tr_limit = g * np.sqrt(g_limit**2 - 1) / V * 180 / pi

        mask = (IAS >= stall_IAS) & (TR <= tr_limit) & (IAS <= max_speed)

        # Add DVmc masking when active
        if dvmc_active:
            dvmc_ias_at_tr = np.interp(TR, turn_rates_early, vmca_vals_kias_early)
            dvmc_mask = IAS >= dvmc_ias_at_tr
            mask = mask & dvmc_mask

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
            TR_vals_neg = np.arange(-100, -0.1, aob_tr_step)  # End near 0 for full coverage
            IAS_vals_neg = np.arange(ias_start, max_speed + 1, aob_ias_step)
            IAS_neg, TR_neg = np.meshgrid(IAS_vals_neg, TR_vals_neg)
            V_neg = IAS_neg * KTS_TO_FPS
            omega_rad_neg = np.abs(TR_neg) * (np.pi / 180)  # use absolute to mirror

            AOB_rad_neg = np.arctan(omega_rad_neg * V_neg / g)
            AOB_deg_neg = np.degrees(AOB_rad_neg)  # keep positive AOB for mirror color scale

            n_neg = np.sqrt(1 + (V_neg * omega_rad_neg / g) ** 2)
            n_neg = np.maximum(n_neg, 1.001)
            stall_v_neg = np.sqrt((2 * weight * n_neg) / (rho * wing_area * cl_max))
            stall_IAS_neg = stall_v_neg * FPS_TO_KTS
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
        ias_range = np.arange(ias_start, max_speed + 1, 2)
        min_radius = None
        max_radius = 0

        # --- Step 1a: Dynamically find smallest valid turn radius inside envelope
        min_radius = None
        for ias in np.arange(ias_start, max_speed + 1, 0.5):  # fine IAS sweep
            v_fts = ias * KTS_TO_FPS
            for tr_candidate in np.arange(60, 1, -0.5):  # from tightest turns down
                omega_rad = tr_candidate * (np.pi / 180)
                r = v_fts / omega_rad

                n = np.sqrt(1 + (v_fts * omega_rad / g) ** 2)
                stall_v_fts = np.sqrt((2 * weight * n) / (rho * wing_area * cl_max))
                stall_ias = stall_v_fts * FPS_TO_KTS
                tr_limit = g * np.sqrt(g_limit**2 - 1) / v_fts * 180 / np.pi

                if ias >= stall_ias and tr_candidate <= tr_limit and ias <= max_speed:
                    if min_radius is None or r < min_radius:
                        min_radius = r * 1.017
                    break  # first valid tightest radius is enough for this IAS

        # --- Step 1b: Compute max radius using 3 deg/sec
        max_radius = 0
        for ias in ias_range:
            v_fts = ias * KTS_TO_FPS
            omega_3deg = 3 * (np.pi / 180)
            r = v_fts / omega_3deg

            n = np.sqrt(1 + (v_fts * omega_3deg / g) ** 2)
            stall_v_fts = np.sqrt((2 * weight * n) / (rho * wing_area * cl_max))
            stall_ias = stall_v_fts * FPS_TO_KTS
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
                v_fts = ias * KTS_TO_FPS
                omega_rad = v_fts / radius
                tr_deg = omega_rad * 180 / pi

                n = np.sqrt(1 + (v_fts * omega_rad / g) ** 2)
                stall_v_fts = np.sqrt((2 * weight * n) / (rho * wing_area * cl_max))
                stall_ias = stall_v_fts * FPS_TO_KTS
                tr_limit = g * np.sqrt(g_limit**2 - 1) / v_fts * 180 / pi

                # Check DVmc limit when active
                dvmc_ok = True
                if dvmc_active:
                    dvmc_at_tr = np.interp(tr_deg, turn_rates_early, vmca_vals_kias_early)
                    dvmc_ok = ias >= dvmc_at_tr

                if ias >= stall_ias and tr_deg <= tr_limit and ias <= max_speed and dvmc_ok:
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
                v_fts = ias * KTS_TO_FPS
                for tr_candidate in np.arange(60, 1, -0.5):
                    omega_rad = tr_candidate * (np.pi / 180)
                    r = v_fts / omega_rad

                    n = np.sqrt(1 + (v_fts * omega_rad / g) ** 2)
                    stall_v_fts = np.sqrt((2 * weight * n) / (rho * wing_area * cl_max))
                    stall_ias = stall_v_fts * FPS_TO_KTS
                    tr_limit = g * np.sqrt(g_limit_neg**2 - 1) / v_fts * 180 / np.pi

                    if ias >= stall_ias and tr_candidate <= tr_limit and ias <= max_speed:
                        neg_min_radius = round(r * 1.017 / 100.0) * 100
                        break
                if neg_min_radius:
                    break

            # Step 1b: Max radius using 3 deg/sec
            for ias in ias_vals:
                v_fts = ias * KTS_TO_FPS
                omega_3deg = 3 * (np.pi / 180)
                r = v_fts / omega_3deg

                n = np.sqrt(1 + (v_fts * omega_3deg / g) ** 2)
                stall_v_fts = np.sqrt((2 * weight * n) / (rho * wing_area * cl_max))
                stall_ias = stall_v_fts * FPS_TO_KTS
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
                    v_fts = ias * KTS_TO_FPS
                    omega_rad = v_fts / radius
                    tr_deg = -omega_rad * 180 / pi

                    n = np.sqrt(1 + (v_fts * omega_rad / g) ** 2)
                    stall_v = np.sqrt((2 * weight * n) / (rho * wing_area * cl_max))
                    stall_ias = stall_v * FPS_TO_KTS
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
    

    
     # --- Dynamic Vmca Curve (bank angle vs adjusted Vmca + turn rate) ---
    if "vmca" in all_overlays and ac.get("engine_count", 1) > 1 and oei_active:
        published_vmca = ac.get("single_engine_limits", {}).get("Vmca", 70)
        reference_weight = ac.get("max_weight", 3600)
        cg_range = ac.get("cg_range", [10, 20])

        # Sweep bank angle from 5° to 90°
        bank_angles = np.linspace(5, 90, 150)

        _, vmca_vals_kias = calculate_vmca(
            published_vmca=published_vmca,
            power_fraction=power_fraction,
            total_weight=weight,
            reference_weight=reference_weight,
            cg=cg,
            cg_range=cg_range,
            prop_condition=prop_mode,
            pressure_altitude=pressure_altitude,
            oat_c=oat_c,
            bank_angles_deg=bank_angles
        )

        vmca_vals_display_full = convert_display_airspeed(vmca_vals_kias, unit)

        # Convert bank angle to turn rate
        v_fts = vmca_vals_kias * KTS_TO_FPS
        bank_rad = np.radians(bank_angles)
        omega_rad = g * np.tan(bank_rad) / v_fts
        turn_rates_full = np.degrees(omega_rad)

        # Save first point for label (before clipping)
        dvmc_label_value = vmca_vals_display_full[0]
        dvmc_label_tr = turn_rates_full[0]

        # ✅ Clip to envelope before plotting - must be within lift limit (stall boundary)
        stall_tr_limit = np.interp(vmca_vals_kias, stall_clipped_x, stall_clipped_y)
        valid_mask = (turn_rates_full >= y_min) & (turn_rates_full <= y_max) & (turn_rates_full <= stall_tr_limit)
        vmca_vals_display = vmca_vals_display_full[valid_mask]
        turn_rates = turn_rates_full[valid_mask]

        # Build hover text with bank angle info
        bank_angles_masked = bank_angles[valid_mask]
        vmca_hover = [
            f"<b>DVmc</b><br>Bank: {bank:.0f}°<br>Vmca: {spd:.0f} {unit}<br>Turn Rate: {tr:.1f}°/s"
            for bank, spd, tr in zip(bank_angles_masked, vmca_vals_display, turn_rates)
        ]

        # Plot DVmc line (clipped portion only)
        if len(vmca_vals_display) > 0:
            fig.add_trace(go.Scatter(
                x=vmca_vals_display,
                y=turn_rates,
                mode="lines",
                name="DVmc",
                line=dict(color="#DC143C", width=2.5, dash="dash"),
                hoverinfo="text",
                hovertext=vmca_hover,
                showlegend=True
            ))

        # Always show DVmc label with calculated value (even if off scale)
        # Position at edge of graph if value is beyond visible range
        estimated_x_max = max_speed * 1.1 if unit == "KIAS" else max_speed * KTS_TO_MPH * 1.1

        if dvmc_label_value > estimated_x_max:
            # DVmc is off scale - position label at right edge with actual value
            label_x_pos = estimated_x_max * 0.95
            label_text = f"<b>DVmc {dvmc_label_value:.0f}</b> →"
            arrow_x = 30  # Point arrow to the right
        else:
            label_x_pos = dvmc_label_value
            label_text = f"<b>DVmc</b> {dvmc_label_value:.0f}"
            arrow_x = -45

        fig.add_annotation(
            x=label_x_pos,
            y=min(dvmc_label_tr, y_max * 0.95),  # Keep label visible within plot
            text=label_text,
            showarrow=True,
            arrowhead=2,
            ax=arrow_x,
            ay=15,
            font=dict(size=10, color="#DC143C"),
            bgcolor="rgba(255,255,255,0.9)",
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
                pressure_altitude=pressure_altitude,
                oat_c=oat_c,
                gear_position=gear,
                flap_config=config,
                prop_condition=prop_mode
            )
            vyse_curve.append(vyse_val * angle_penalty)

        vyse_curve = np.clip(vyse_curve, min(g_curve_x), max(g_curve_x))
        vyse_display_curve_full = convert_display_airspeed(np.array(vyse_curve), unit)

        v_fts = np.array(vyse_curve) * KTS_TO_FPS
        bank_rad = np.radians(bank_angles)
        omega_rad = g * np.tan(bank_rad) / v_fts
        turn_rates_full = np.degrees(omega_rad)

        # Save first point for label (before clipping)
        dvyse_label_value = vyse_display_curve_full[0]
        dvyse_label_tr = turn_rates_full[0]

        # ✅ Clip to envelope - must be within lift limit (stall boundary)
        vyse_curve_arr = np.array(vyse_curve)
        stall_tr_limit = np.interp(vyse_curve_arr, stall_clipped_x, stall_clipped_y)

        valid_mask = (turn_rates_full >= y_min) & (turn_rates_full <= y_max) & (turn_rates_full <= stall_tr_limit)
        bank_angles_masked = bank_angles[valid_mask]
        vyse_display_curve = vyse_display_curve_full[valid_mask]
        turn_rates = turn_rates_full[valid_mask]

        # Build hover text
        vyse_hover = [
            f"<b>DVyse</b><br>Bank: {bank:.0f}°<br>Vyse: {spd:.0f} {unit}<br>Turn Rate: {tr:.1f}°/s"
            for bank, spd, tr in zip(bank_angles_masked, vyse_display_curve, turn_rates)
        ]

        # --- Plot DVyse line (clipped portion only)
        if len(vyse_display_curve) > 0:
            fig.add_trace(go.Scatter(
                x=vyse_display_curve,
                y=turn_rates,
                mode="lines",
                name="DVyse",
                line=dict(color="#00BFFF", width=2.5, dash="dot"),
                hoverinfo="text",
                hovertext=vyse_hover,
                showlegend=True
            ))

            x_max = max(x_max, vyse_display_curve[0] * 1.05)
            y_max = max(y_max, turn_rates[0] * 1.05)

        # Always show DVyse label at calculated value (even if clipped)
        fig.add_annotation(
            x=dvyse_label_value,
            y=min(dvyse_label_tr, y_max * 0.90),
            text=f"<b>DVyse</b> {dvyse_label_value:.0f}",
            showarrow=True,
            arrowhead=2,
            ax=-45,
            ay=15,
            font=dict(size=10, color="#00BFFF"),
            bgcolor="rgba(255,255,255,0.9)",
            borderpad=3
        )    

    # --- Published Vyse Line (Static Reference) ---
        if oei_active and published_vyse:
            vyse_display = convert_display_airspeed(published_vyse, unit)
            vyse_y_top = np.interp(published_vyse, g_clipped_x, g_clipped_y) if g_clipped_x else 0

            fig.add_trace(go.Scatter(
                x=[vyse_display, vyse_display],
                y=[0, vyse_y_top],
                mode="lines",
                name="Vyse",
                line=dict(color="#87CEEB", width=2, dash="dashdot"),
                hoverinfo="text",
                hovertext=f"<b>Vyse</b><br>{vyse_display:.0f} {unit}<br>(Best rate SE climb)"
            ))

            # Annotation offset to the right to avoid overlap
            fig.add_annotation(
                x=vyse_display,
                y=vyse_y_top,
                text=f"<b>Vyse</b> {vyse_display:.0f}",
                showarrow=True,
                arrowhead=2,
                ax=35,
                ay=-15,
                font=dict(size=9, color="#87CEEB"),
                bgcolor="rgba(255,255,255,0.9)",
                borderpad=2
            )

    # --- Published Vxse Line (Static Reference) ---
        vxse_block = ac.get("single_engine_limits", {}).get("Vxse", {})
        if isinstance(vxse_block, dict):
            published_vxse = vxse_block.get("clean_up") or next(iter(vxse_block.values()), None)
        else:
            published_vxse = vxse_block if isinstance(vxse_block, (int, float)) else None
        if oei_active and published_vxse:
            vxse_display = convert_display_airspeed(published_vxse, unit)
            vxse_y_top = np.interp(published_vxse, g_clipped_x, g_clipped_y) if g_clipped_x else 0

            fig.add_trace(go.Scatter(
                x=[vxse_display, vxse_display],
                y=[0, vxse_y_top],
                mode="lines",
                name="Vxse",
                line=dict(color="#00CC66", width=2, dash="dash"),
                hoverinfo="text",
                hovertext=f"<b>Vxse</b><br>{vxse_display:.0f} {unit}<br>(Best angle SE climb)"
            ))

            # Annotation offset to the left to avoid overlap
            fig.add_annotation(
                x=vxse_display,
                y=vxse_y_top,
                text=f"<b>Vxse</b> {vxse_display:.0f}",
                showarrow=True,
                arrowhead=2,
                ax=-35,
                ay=-15,
                font=dict(size=9, color="#00CC66"),
                bgcolor="rgba(255,255,255,0.9)",
                borderpad=2
            )
        
    # --- Enhanced Hover Grid (Always Present) ---
    # Generate hover data grid covering the flight envelope
    hover_ias_step = 5  # IAS increment for hover grid
    hover_tr_step = 2   # Turn rate increment for hover grid

    # Create grid spanning the envelope
    hover_ias_range = np.arange(ias_start, max_speed_internal + 1, hover_ias_step)
    hover_tr_range = np.arange(0, 50, hover_tr_step)  # Positive turn rates

    hover_ias_list = []
    hover_tr_list = []
    hover_data = []  # Will hold [AOB, G, Ps, Radius] for each point

    for ias in hover_ias_range:
        for tr in hover_tr_range:
            v_fps = ias * KTS_TO_FPS
            omega_rad = tr * (np.pi / 180)

            # Calculate AOB from turn rate
            aob_deg = np.degrees(np.arctan(omega_rad * v_fps / g))

            # Calculate load factor (G)
            n = np.sqrt(1 + (v_fps * omega_rad / g) ** 2)

            # Calculate turn radius (ft -> nm for display)
            if omega_rad > 0.001:
                radius_ft = (v_fps ** 2) / (g * np.tan(np.radians(aob_deg))) if aob_deg > 0.5 else float('inf')
                radius_nm = radius_ft / 6076.12 if radius_ft < 1e6 else float('inf')
            else:
                radius_ft = float('inf')
                radius_nm = float('inf')

            # Calculate Ps at this point
            q = 0.5 * rho * v_fps ** 2
            CL_hover = weight * n / (q * wing_area) if q > 0 else 0
            CL_hover = min(CL_hover, cl_max)
            CD_hover = (CD0 + (CL_hover ** 2) / (np.pi * e * AR)) * cg_drag_factor * gear_drag_factor
            D_hover = q * wing_area * CD_hover

            V_max_kts = ac.get("prop_thrust_decay", {}).get("V_max_kts", 160)
            T_static = ac.get("prop_thrust_decay", {}).get("T_static_factor", 2.6) * hp
            V_fraction = np.clip(ias / V_max_kts, 0, 1)
            T_hover = T_static * (1 - V_fraction ** 2)

            Ps_hover = ((T_hover - D_hover) * v_fps / weight) * FPS_TO_KTS

            # Check if point is within envelope (above stall, below G limit)
            stall_n = (0.5 * rho * v_fps**2 * wing_area * cl_max) / weight
            n_limit = g_limit

            if n <= min(stall_n, n_limit) and n >= 1.0 and ias <= max_speed_internal:
                display_ias = convert_display_airspeed(ias, unit)
                hover_ias_list.append(display_ias)
                hover_tr_list.append(tr)
                hover_data.append([aob_deg, n, Ps_hover, radius_nm])

    # Add hover trace with enhanced tooltip
    if hover_ias_list:
        hover_customdata = np.array(hover_data)

        fig.add_trace(go.Scatter(
            x=hover_ias_list,
            y=hover_tr_list,
            customdata=hover_customdata,
            mode="markers",
            marker=dict(size=8, color="rgba(0,0,0,0)"),
            hovertemplate=(
                f"<b>IAS:</b> %{{x:.0f}} {unit}<br>"
                f"<b>Turn Rate:</b> %{{y:.1f}}°/s<br>"
                f"<b>Bank:</b> %{{customdata[0]:.0f}}°<br>"
                f"<b>Load Factor:</b> %{{customdata[1]:.2f}} G<br>"
                f"<b>Ps:</b> %{{customdata[2]:.1f}} kts/s<br>"
                f"<b>Turn Radius:</b> %{{customdata[3]:.2f}} nm"
                f"<extra></extra>"
            ),
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
                # Clip to envelope top
                vmca_y_top = np.interp(vmca_value, g_clipped_x, g_clipped_y) if g_clipped_x else y_max

                fig.add_trace(go.Scatter(
                    x=[vmca_converted, vmca_converted],
                    y=[0, vmca_y_top],
                    mode="lines",
                    name="Published Vmca",
                    line=dict(color="#FF6B6B", width=2, dash="dash"),
                    hoverinfo="text",
                    hovertext=f"<b>Published Vmca</b><br>{vmca_converted:.0f} {unit}<br>(Minimum controllable airspeed)"
                ))

                fig.add_annotation(
                    x=vmca_converted,
                    y=vmca_y_top,
                    text=f"<b>Vmca</b> {vmca_converted:.0f}",
                    showarrow=False,
                    yshift=12,
                    font=dict(size=9, color="#FF6B6B"),
                    bgcolor="rgba(255,255,255,0.9)",
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

        # Guard against None values
        if ias_input is None or aob_input is None:
            ias_input = 110  # default
            aob_input = 45   # default

        v_fts = ias_input * KTS_TO_FPS
        bank_rad = np.radians(aob_input)
        tr_deg = np.degrees(G_FT_S2 * np.tan(bank_rad) / v_fts)

        # --- Energy Rate (Ps) at this point ---
        n = 1 / np.cos(bank_rad)  # load factor for level constant altitude turn
        q = 0.5 * rho * v_fts ** 2
        CL = weight * n / (q * wing_area)
        CL = min(CL, cl_max)  # Clip to CL_max like Ps grid does
        CD = (CD0 + (CL ** 2) / (np.pi * e * AR)) * cg_drag_factor * gear_drag_factor
        D = q * wing_area * CD

        # Apply prop thrust model (same as Ps logic)
        V_max_kts = ac.get("prop_thrust_decay", {}).get("V_max_kts", 160)
        T_static = ac.get("prop_thrust_decay", {}).get("T_static_factor", 2.6) * hp
        V_fraction = np.clip(ias_input / V_max_kts, 0, 1)
        T_avail = T_static * (1 - V_fraction**2)

        gamma_rad = np.radians(pitch_angle)
        Ps_steep = ((T_avail - D) * v_fts / weight - v_fts * np.sin(gamma_rad)) * FPS_TO_KTS

        dprint("[STEEP TURN DEBUG]")
        dprint(f"  IAS: {ias_input} KIAS, AOB: {aob_input}°")
        dprint(f"  Turn Rate: {tr_deg:.1f}°/s")
        dprint(f"  Ps: {Ps_steep:.2f} knots/sec")

        # Simplified steep turn trace: vertical line from 0 to operating point
        arc_tr = [0.0, tr_deg]
        arc_ias = [ias_input, ias_input]
        arc_ias_display = [ias * KTS_TO_MPH if unit == "MPH" else ias for ias in arc_ias]

        # Contextual hover text for each point
        steep_hover = [
            f"<b>Roll In (Wings Level)</b><br>AOB: 0°<br>IAS: {arc_ias_display[0]:.0f} {unit}<br>Turn Rate: 0°/s<br>G: 1.00",
            f"<b>Operating Point</b><br>AOB: {aob_input}°<br>IAS: {arc_ias_display[1]:.0f} {unit}<br>Turn Rate: {tr_deg:.1f}°/s<br>G: {n:.2f}<br>Ps: {Ps_steep:.1f} kts/s"
        ]

        fig.add_trace(go.Scatter(
            x=arc_ias_display,
            y=arc_tr,
            mode="lines+markers",
            line=dict(color="darkgreen", width=3),
            marker=dict(size=8, symbol=["circle", "diamond"]),
            name="Steep Turn",
            hoverinfo="text",
            hovertext=steep_hover,
            showlegend=True
        ))

        # Annotation at operating point showing key values
        fig.add_annotation(
            x=arc_ias_display[1],
            y=tr_deg,
            text=f"<b>{aob_input}° AOB</b><br>{n:.1f}G | Ps: {Ps_steep:.1f}",
            showarrow=True,
            arrowhead=2,
            ax=50,
            ay=-25,
            font=dict(size=10, color="darkgreen"),
            bgcolor="rgba(255,255,255,0.85)",
            borderpad=3
        )

        # Annotation at wings level
        fig.add_annotation(
            x=arc_ias_display[0],
            y=0,
            text="Wings Level",
            showarrow=False,
            yshift=-15,
            font=dict(size=9, color="darkgreen"),
            bgcolor="rgba(255,255,255,0.7)",
            borderpad=2
        )
    #------Ghost Trace------#
# === GHOST TRACE (Ideal AOB based on ACS Standard)
    # Check if ghost trace is enabled and a standard is selected
    # Handle both boolean (from Switch) and list (from Checklist)
    ghost_val = steepturn_ghost_values[0] if steepturn_ghost_values else False
    ghost_enabled = ghost_val is True or (isinstance(ghost_val, list) and "on" in ghost_val)
    standard_selected = steepturn_standard_values and len(steepturn_standard_values[0]) > 0

    if ghost_enabled and standard_selected:
        # Determine AOB based on selected standard(s) - use first selection
        selected_standard = steepturn_standard_values[0][0]  # "private" or "commercial"
        ghost_aob = 45 if selected_standard == "private" else 50
        ghost_ias = ias_values[0] if ias_values else 110  # fallback if none provided

        v_fts = ghost_ias * KTS_TO_FPS
        bank_rad = np.radians(ghost_aob)
        ghost_tr = np.degrees(G_FT_S2 * np.tan(bank_rad) / v_fts)

        ghost_tr_array = [0.0, ghost_tr, ghost_tr, 0.0, 0.0]
        ghost_ias_array = [ghost_ias] * len(ghost_tr_array)
        ghost_ias_display = [ias * KTS_TO_MPH if unit == "MPH" else ias for ias in ghost_ias_array]

        standard_label = "Private" if selected_standard == "private" else "Commercial"
        fig.add_trace(go.Scatter(
            x=ghost_ias_display,
            y=ghost_tr_array,
            mode="lines",
            line=dict(color="white", width=2, dash="dot"),
            name=f"{standard_label} ({ghost_aob}°)",
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
        label="Chandelle",
        show_annotations=True
    ):
        from plotly.graph_objects import Scatter
        from math import radians, tan, degrees, cos

        v_start = chandelle_ias_start * KTS_TO_FPS  # ft/s
        v_end = (stall_ias_kias + 5) * KTS_TO_FPS   # ft/s
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
        aob_list = []
        heading_list = []

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
            omega_rad = G_FT_S2 * tan(aob_rad) / v
            tr = degrees(omega_rad)

            airspeeds.append(v * FPS_TO_KTS)
            turn_rates.append(tr)
            aob_list.append(aob_deg)
            heading_list.append(angle)

            angle += tr * dt
            steps += 1

        if not airspeeds:
            dprint("[WARN] No chandelle points generated.")
            return fig

        airspeeds_display = [ias * KTS_TO_MPH if unit == "MPH" else ias for ias in airspeeds]

        # Build contextual hover text with G load factor and heading progress
        hover_texts = []
        for i, (ias, tr, aob, hdg) in enumerate(zip(airspeeds_display, turn_rates, aob_list, heading_list)):
            g_load = 1 / cos(radians(aob)) if aob > 0 else 1.0
            if i == 0:
                phase = "<b>START</b>"
            elif hdg >= 175:
                phase = "<b>END</b>"
            elif hdg < 90:
                phase = f"First Half ({hdg:.0f}°)"
            else:
                phase = f"Second Half ({hdg:.0f}°)"
            hover_texts.append(
                f"{phase}<br>IAS: {ias:.0f} {unit}<br>Turn Rate: {tr:.1f}°/s<br>AOB: {aob:.0f}°<br>G: {g_load:.2f}<br>Heading: {hdg:.0f}°"
            )

        fig.add_trace(Scatter(
            x=airspeeds_display,
            y=turn_rates,
            mode="lines+markers",
            line=dict(color=color, width=3, dash=dash),
            marker=dict(size=4),
            name=label,
            hoverinfo="text",
            hovertext=hover_texts
        ))

        # Add START and END annotations (only for main trace, not ghost)
        if show_annotations and len(airspeeds_display) > 1:
            # START annotation (right side - high airspeed)
            fig.add_annotation(
                x=airspeeds_display[0],
                y=turn_rates[0],
                text="<b>START</b>",
                showarrow=True,
                arrowhead=2,
                ax=30,
                ay=-20,
                font=dict(size=10, color=color),
                bgcolor="rgba(255,255,255,0.85)",
                borderpad=2
            )
            # END annotation (left side - low airspeed)
            fig.add_annotation(
                x=airspeeds_display[-1],
                y=turn_rates[-1],
                text="<b>END</b>",
                showarrow=True,
                arrowhead=2,
                ax=-30,
                ay=-20,
                font=dict(size=10, color=color),
                bgcolor="rgba(255,255,255,0.85)",
                borderpad=2
            )
            # Direction indicator in middle
            mid_idx = len(airspeeds_display) // 2
            fig.add_annotation(
                x=airspeeds_display[mid_idx],
                y=turn_rates[mid_idx] + 1.5,
                text="← Energy Flow →",
                showarrow=False,
                font=dict(size=9, color="gray"),
                bgcolor="rgba(255,255,255,0.7)",
                borderpad=2
            )

        return fig

    if maneuver == "chandelle" and chandelle_ias_values and chandelle_bank_values:
        chandelle_ias = chandelle_ias_values[0]
        chandelle_bank = chandelle_bank_values[0]
        # Compute dynamic stall speed at 1G level turn
        v_stall_1g = np.sqrt((2 * weight) / (rho * wing_area * cl_max)) * FPS_TO_KTS
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

        # Handle both boolean (from Switch) and list (from Checklist)
        chandelle_ghost_val = chandelle_ghost_values[0] if chandelle_ghost_values else False
        chandelle_ghost_on = chandelle_ghost_val is True or (isinstance(chandelle_ghost_val, list) and "on" in chandelle_ghost_val)
        if chandelle_ghost_on:
            fig = plot_chandelle(
                fig,
                chandelle_ias_start=chandelle_ias,
                chandelle_bank=30,
                stall_ias_kias=stall_ias_kias,
                unit=unit,
                color="white",
                dash="dot",
                label="Chandelle Ghost",
                show_annotations=False
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
            # Row 1: Airspeed input
            dbc.Row([
                dbc.Col([
                    html.Label("Airspeed (KIAS)", className="input-label-sm"),
                    dcc.Input(
                        id={"type": "steepturn-ias", "index": 0},
                        type="number",
                        value=110,
                        min=40,
                        max=200,
                        step=1,
                        style={"width": "100px"}
                    )
                ], width="auto")
            ], className="mb-3"),

            # Row 2: AOB Slider
            dbc.Row([
                dbc.Col([
                    html.Label("Angle of Bank (°)", className="input-label-sm"),
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
                ])
            ], className="mb-3"),

            # Row 3: Ghost Trace Toggle
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Div([
                            html.Span("Ghost Trace", className="overlay-label"),
                            html.Span("?", id={"type": "ghost-help-trigger", "index": "steep"}, className="help-icon", n_clicks=0)
                        ], className="label-group"),
                        dbc.Switch(
                            id={"type": "steepturn-ghost", "index": 0},
                            value=False,
                            className="form-switch"
                        )
                    ], className="overlay-row")
                ])
            ], className="mb-2"),

            # Row 4: ACS Standard Selection (only visible when ghost trace is on)
            html.Div(
                id="acs-standard-container",
                children=[
                    dbc.Row([
                        dbc.Col([
                            html.Label("ACS Standard", className="input-label-sm", style={"marginLeft": "20px"}),
                            dbc.Checklist(
                                id={"type": "steepturn-standard", "index": 0},
                                options=[
                                    {"label": "Private (45°)", "value": "private"},
                                    {"label": "Commercial (50°)", "value": "commercial"},
                                ],
                                value=[],
                                switch=True,
                                className="switch-list",
                                style={"marginLeft": "20px"}
                            )
                        ])
                    ])
                ],
                style={"display": "none"}  # Hidden by default
            )
        ])
    elif maneuver == "chandelle":
        return html.Div([
            # Row 1: Airspeed input
            dbc.Row([
                dbc.Col([
                    html.Label("Airspeed (KIAS)", className="input-label-sm"),
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

            # Row 2: AOB Slider
            dbc.Row([
                dbc.Col([
                    html.Label("Angle of Bank (°)", className="input-label-sm"),
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

            # Row 3: Ghost Trace Toggle
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Div([
                            html.Span("Ghost Trace", className="overlay-label"),
                            html.Span("?", id={"type": "ghost-help-trigger", "index": "chandelle"}, className="help-icon", n_clicks=0)
                        ], className="label-group"),
                        dbc.Switch(
                            id={"type": "chandelle-ghost", "index": 0},
                            value=True,
                            className="form-switch"
                        )
                    ], className="overlay-row")
                ])
            ])
        ])

    # No maneuver selected
    return None

# Callback to enforce mutual exclusivity on ACS Standard toggles
@app.callback(
    Output({"type": "steepturn-standard", "index": 0}, "value"),
    Input({"type": "steepturn-standard", "index": 0}, "value"),
    prevent_initial_call=True
)
def enforce_single_standard(current_value):
    """Only allow one ACS standard to be selected at a time."""
    if not current_value or len(current_value) <= 1:
        return current_value
    # If multiple selected, keep only the most recently added (last in list)
    return [current_value[-1]]

# Callback to show/hide ACS Standard options based on Ghost Trace toggle
@app.callback(
    Output("acs-standard-container", "style"),
    Input({"type": "steepturn-ghost", "index": 0}, "value"),
    prevent_initial_call=True
)
def toggle_acs_standard_visibility(ghost_value):
    """Show ACS Standard options only when Ghost Trace is enabled."""
    # Handle both boolean (from Switch) and list (from Checklist)
    if ghost_value is True or (isinstance(ghost_value, list) and "on" in ghost_value):
        return {"display": "block"}
    return {"display": "none"}


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
    State("prop-condition", "data"),
    State("maneuver-select", "value"),
    State("oat-input", "value"),
    State("unit-select", "data"),
    State("cg-slider", "value"),
    State("overlay-toggle", "data"),
    prevent_initial_call=True
)
def generate_pdf(n_clicks, fig_data, ac_name, engine_name, config, gear, occupants, pax_weight, fuel, total_weight,
                 power_fraction, altitude, pitch, oei_toggle, prop_condition, maneuver,
                 oat_c, speed_unit, cg_position, active_overlays):
    if ctx.triggered_id != "pdf-button":
        return dash.no_update

    # Track PDF export with configuration details
    log_feature('diagram_export_pdf', {
        'aircraft': ac_name,
        'engine': engine_name,
        'config': config,
        'altitude': altitude,
        'maneuver': maneuver
    })

    fig = go.Figure(fig_data)

    # Generate timestamp
    from datetime import datetime
    export_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    


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

    # Convert OAT to Fahrenheit for display
    oat_f = round(oat_c * 9/5 + 32) if oat_c is not None else "N/A"
    oat_display = f"{oat_c}°C / {oat_f}°F" if oat_c is not None else "N/A"

    # Calculate CG in inches from slider position and aircraft CG range
    cg_display = "N/A"
    if cg_position is not None and ac_name and ac_name in aircraft_data:
        ac = aircraft_data[ac_name]
        cg_range = ac.get("cg_range", [0, 100])
        cg_inches = cg_range[0] + cg_position * (cg_range[1] - cg_range[0])
        cg_display = f"{cg_inches:.1f} in"

    # Format active overlays
    overlay_names = {
        "ps": "Ps Contours",
        "radius": "Turn Radius",
        "g": "G-Lines",
        "aob": "AOB Shading",
        "negative_g": "Neg-G Envelope",
        "vmca": "Dynamic Vmc",
        "vyse": "Dynamic Vyse"
    }
    active_overlay_list = [overlay_names.get(o, o) for o in (active_overlays or [])]
    overlays_display = ", ".join(active_overlay_list) if active_overlay_list else "None"

    summary_lines = [
        f"Engine: {engine_name} | {config} | Gear: {gear}",
        f"Weight: {int(total_weight) if total_weight else 'N/A'} lbs | Occupants: {occupants} x {pax_weight or 180} lbs | Fuel: {fuel} gal | CG: {cg_display}",
        f"Altitude: {altitude or 0} ft | OAT: {oat_display} | Power: {int(power_fraction * 100)}%",
        f"Speed Unit: {speed_unit or 'KIAS'} | OEI: {oei_status}" + (f" ({prop_condition})" if oei_status == "YES" else ""),
        f"Overlays: {overlays_display}" + (f" | Maneuver: {maneuver}" if maneuver else ""),
        f"<i>Generated: {export_timestamp}</i>"
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

    # ✅ Footer for exports
    fig.add_annotation(
        text="© 2025 Nicholas Len, AEROEDGE. All rights reserved. | Not FAA-approved. For educational and reference use only.",
        xref="paper", yref="paper",
        x=0.5, y=-0.12,
        xanchor="center", yanchor="top",
        showarrow=False,
        font=dict(size=9, color="gray"),
        align="center"
    )

    # ✅ Clean layout margin (increased top margin for additional info lines)
    fig.update_layout(margin=dict(t=180, b=80))

    # ✅ Save PDF to temp and return
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pio.write_image(fig, tmp.name, format="pdf", width=1100, height=800)
        return send_file(tmp.name, filename="EMdiagram.pdf")


###----Generate PNG-----####

@app.callback(
    Output("png-download", "data"),
    Input("png-button", "n_clicks"),
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
    State("prop-condition", "data"),
    State("maneuver-select", "value"),
    State("oat-input", "value"),
    State("unit-select", "data"),
    State("cg-slider", "value"),
    State("overlay-toggle", "data"),
    prevent_initial_call=True
)
def generate_png(n_clicks, fig_data, ac_name, engine_name, config, gear, occupants, pax_weight, fuel, total_weight,
                 power_fraction, altitude, pitch, oei_toggle, prop_condition, maneuver,
                 oat_c, speed_unit, cg_position, active_overlays):
    if ctx.triggered_id != "png-button":
        return dash.no_update

    # Track PNG export with configuration details
    log_feature('diagram_export_png', {
        'aircraft': ac_name,
        'engine': engine_name,
        'config': config,
        'altitude': altitude,
        'maneuver': maneuver
    })

    fig = go.Figure(fig_data)

    # Generate timestamp
    from datetime import datetime
    export_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

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

    # Convert OAT to Fahrenheit for display
    oat_f = round(oat_c * 9/5 + 32) if oat_c is not None else "N/A"
    oat_display = f"{oat_c}°C / {oat_f}°F" if oat_c is not None else "N/A"

    # Calculate CG in inches from slider position and aircraft CG range
    cg_display = "N/A"
    if cg_position is not None and ac_name and ac_name in aircraft_data:
        ac = aircraft_data[ac_name]
        cg_range = ac.get("cg_range", [0, 100])
        cg_inches = cg_range[0] + cg_position * (cg_range[1] - cg_range[0])
        cg_display = f"{cg_inches:.1f} in"

    # Format active overlays
    overlay_names = {
        "ps": "Ps Contours",
        "radius": "Turn Radius",
        "g": "G-Lines",
        "aob": "AOB Shading",
        "negative_g": "Neg-G Envelope",
        "vmca": "Dynamic Vmc",
        "vyse": "Dynamic Vyse"
    }
    active_overlay_list = [overlay_names.get(o, o) for o in (active_overlays or [])]
    overlays_display = ", ".join(active_overlay_list) if active_overlay_list else "None"

    summary_lines = [
        f"Engine: {engine_name} | {config} | Gear: {gear}",
        f"Weight: {int(total_weight) if total_weight else 'N/A'} lbs | Occupants: {occupants} x {pax_weight or 180} lbs | Fuel: {fuel} gal | CG: {cg_display}",
        f"Altitude: {altitude or 0} ft | OAT: {oat_display} | Power: {int(power_fraction * 100)}%",
        f"Speed Unit: {speed_unit or 'KIAS'} | OEI: {oei_status}" + (f" ({prop_condition})" if oei_status == "YES" else ""),
        f"Overlays: {overlays_display}" + (f" | Maneuver: {maneuver}" if maneuver else ""),
        f"<i>Generated: {export_timestamp}</i>"
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

    # ✅ Footer for exports
    fig.add_annotation(
        text="© 2025 Nicholas Len, AEROEDGE. All rights reserved. | Not FAA-approved. For educational and reference use only.",
        xref="paper", yref="paper",
        x=0.5, y=-0.12,
        xanchor="center", yanchor="top",
        showarrow=False,
        font=dict(size=9, color="gray"),
        align="center"
    )

    # ✅ Clean layout margin (increased top margin for additional info lines)
    fig.update_layout(margin=dict(t=180, b=80))

    # ✅ Save PNG to temp and return
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        pio.write_image(fig, tmp.name, format="png", width=1200, height=900, scale=2)
        return send_file(tmp.name, filename="EMdiagram.png")


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

    # Track aircraft selection with details
    ac = aircraft_data[selected_name]
    log_feature('aircraft_select', {
        'aircraft': selected_name,
        'type': ac.get('type', 'unknown'),
        'engine_count': ac.get('engine_count', 1),
        'category': ac.get('category', 'unknown')
    })

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


    # Container children are left empty - the render callbacks will
    # populate them from the stored data (stored_g_limits, etc.)
    g_limit_fields = []
    stall_speed_fields = []
    engine_fields = []

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
                    "config": config_key,  # Use "config" for consistency with add/render callbacks
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
    # Basic info
    Output("aircraft-type", "value", allow_duplicate=True),
    Output("gear-type", "value", allow_duplicate=True),
    Output("engine-count", "value", allow_duplicate=True),
    # Aerodynamics
    Output("wing-area", "value", allow_duplicate=True),
    Output("aspect-ratio", "value", allow_duplicate=True),
    Output("cd0", "value", allow_duplicate=True),
    Output("oswald-efficiency", "value", allow_duplicate=True),
    Output("prop-static-factor", "value", allow_duplicate=True),
    Output("prop-vmax-kts", "value", allow_duplicate=True),
    # Weights
    Output("empty-weight", "value", allow_duplicate=True),
    Output("max-weight", "value", allow_duplicate=True),
    Output("seats", "value", allow_duplicate=True),
    Output("fuel-capacity-gal", "value", allow_duplicate=True),
    Output("fuel-weight-per-gal", "value", allow_duplicate=True),
    # Speeds
    Output("vne", "value", allow_duplicate=True),
    Output("vno", "value", allow_duplicate=True),
    Output("best-glide", "value", allow_duplicate=True),
    Output("best-glide-ratio", "value", allow_duplicate=True),
    Output("max-altitude", "value", allow_duplicate=True),
    # Arcs
    Output("arc-white-bottom", "value", allow_duplicate=True),
    Output("arc-white-top", "value", allow_duplicate=True),
    Output("arc-green-bottom", "value", allow_duplicate=True),
    Output("arc-green-top", "value", allow_duplicate=True),
    Output("arc-yellow-bottom", "value", allow_duplicate=True),
    Output("arc-yellow-top", "value", allow_duplicate=True),
    Output("arc-red", "value", allow_duplicate=True),
    # Flaps
    Output({"type": "vfe-input", "config": "takeoff"}, "value", allow_duplicate=True),
    Output({"type": "vfe-input", "config": "landing"}, "value", allow_duplicate=True),
    Output({"type": "clmax-input", "config": "clean"}, "value", allow_duplicate=True),
    Output({"type": "clmax-input", "config": "takeoff"}, "value", allow_duplicate=True),
    Output({"type": "clmax-input", "config": "landing"}, "value", allow_duplicate=True),
    # Stores
    Output("stored-engine-options", "data", allow_duplicate=True),
    Output("stored-g-limits", "data", allow_duplicate=True),
    Output("stored-stall-speeds", "data", allow_duplicate=True),
    Output("stored-oei-performance", "data", allow_duplicate=True),
    # Inputs
    Input("default-trainer", "n_clicks"),
    Input("default-single", "n_clicks"),
    Input("default-highperf", "n_clicks"),
    Input("default-multi", "n_clicks"),
    Input("default-aerobatic", "n_clicks"),
    Input("default-experimental", "n_clicks"),
    prevent_initial_call=True
)
def apply_default_performance(trainer, single, highperf, multi, aero, exp):
    triggered = ctx.triggered_id

    # Define comprehensive defaults for each category
    defaults = {
        "default-trainer": {
            # Basic Trainer: C150, C152, PA-28-140, DA20
            "aircraft_type": "single_engine",
            "gear_type": "fixed",
            "engine_count": 1,
            "wing_area": 160,
            "aspect_ratio": 6.8,
            "cd0": 0.028,
            "e": 0.78,
            "t_static": 2.5,
            "vmax": 125,
            "empty_weight": 1100,
            "max_weight": 1670,
            "seats": 2,
            "fuel_capacity": 26,
            "fuel_weight": 6.0,
            "vne": 140,
            "vno": 111,
            "best_glide": 60,
            "glide_ratio": 8.5,
            "ceiling": 14000,
            "arcs": {"white": [42, 85], "green": [48, 111], "yellow": [111, 140], "red": 140},
            "vfe": {"takeoff": 100, "landing": 85},
            "clmax": {"clean": 1.45, "takeoff": 1.7, "landing": 2.0},
            "engine": {"name": "Continental O-200-A", "hp": 100, "derate": 0.03},
            "g_limits": [
                {"category": "normal", "config": "clean", "positive": 3.8, "negative": -1.52},
                {"category": "normal", "config": "takeoff", "positive": 2.0, "negative": -1.0},
                {"category": "normal", "config": "landing", "positive": 2.0, "negative": -1.0},
            ],
            "stall_speeds": [
                {"config": "clean", "weight": 1670, "speed": 48},
                {"config": "takeoff", "weight": 1670, "speed": 44},
                {"config": "landing", "weight": 1670, "speed": 42},
            ],
        },
        "default-single": {
            # Standard Single: C172, PA-28-181, DA40, SR20
            "aircraft_type": "single_engine",
            "gear_type": "fixed",
            "engine_count": 1,
            "wing_area": 174,
            "aspect_ratio": 7.32,
            "cd0": 0.027,
            "e": 0.80,
            "t_static": 2.6,
            "vmax": 163,
            "empty_weight": 1660,
            "max_weight": 2550,
            "seats": 4,
            "fuel_capacity": 56,
            "fuel_weight": 6.0,
            "vne": 163,
            "vno": 129,
            "best_glide": 68,
            "glide_ratio": 9.0,
            "ceiling": 14000,
            "arcs": {"white": [41, 85], "green": [47, 129], "yellow": [129, 163], "red": 163},
            "vfe": {"takeoff": 110, "landing": 85},
            "clmax": {"clean": 1.5, "takeoff": 1.7, "landing": 1.9},
            "engine": {"name": "Lycoming IO-360-L2A", "hp": 180, "derate": 0.03},
            "g_limits": [
                {"category": "normal", "config": "clean", "positive": 3.8, "negative": -1.52},
                {"category": "normal", "config": "takeoff", "positive": 2.0, "negative": -1.0},
                {"category": "normal", "config": "landing", "positive": 2.0, "negative": -1.0},
            ],
            "stall_speeds": [
                {"config": "clean", "weight": 2550, "speed": 53},
                {"config": "clean", "weight": 2200, "speed": 49},
                {"config": "takeoff", "weight": 2550, "speed": 50},
                {"config": "landing", "weight": 2550, "speed": 47},
            ],
        },
        "default-highperf": {
            # High Performance: C182, Bonanza, Mooney, SR22
            "aircraft_type": "single_engine",
            "gear_type": "retractable",
            "engine_count": 1,
            "wing_area": 175,
            "aspect_ratio": 7.4,
            "cd0": 0.024,
            "e": 0.82,
            "t_static": 2.7,
            "vmax": 200,
            "empty_weight": 2100,
            "max_weight": 3400,
            "seats": 4,
            "fuel_capacity": 92,
            "fuel_weight": 6.0,
            "vne": 200,
            "vno": 165,
            "best_glide": 90,
            "glide_ratio": 10.5,
            "ceiling": 18500,
            "arcs": {"white": [50, 100], "green": [58, 165], "yellow": [165, 200], "red": 200},
            "vfe": {"takeoff": 120, "landing": 100},
            "clmax": {"clean": 1.4, "takeoff": 1.65, "landing": 1.95},
            "engine": {"name": "Continental IO-550-N", "hp": 310, "derate": 0.025},
            "g_limits": [
                {"category": "normal", "config": "clean", "positive": 3.8, "negative": -1.52},
                {"category": "normal", "config": "takeoff", "positive": 2.0, "negative": -1.0},
                {"category": "normal", "config": "landing", "positive": 2.0, "negative": -1.0},
            ],
            "stall_speeds": [
                {"config": "clean", "weight": 3400, "speed": 63},
                {"config": "clean", "weight": 2800, "speed": 57},
                {"config": "takeoff", "weight": 3400, "speed": 58},
                {"config": "landing", "weight": 3400, "speed": 53},
            ],
        },
        "default-multi": {
            # Light Twin: PA-44, DA42, Baron 58
            "aircraft_type": "multi_engine",
            "gear_type": "retractable",
            "engine_count": 2,
            "wing_area": 183,
            "aspect_ratio": 7.2,
            "cd0": 0.028,
            "e": 0.80,
            "t_static": 2.6,
            "vmax": 202,
            "empty_weight": 2570,
            "max_weight": 3800,
            "seats": 4,
            "fuel_capacity": 110,
            "fuel_weight": 6.0,
            "vne": 202,
            "vno": 169,
            "best_glide": 88,
            "glide_ratio": 9.5,
            "ceiling": 15000,
            "arcs": {"white": [55, 108], "green": [64, 169], "yellow": [169, 202], "red": 202},
            "vfe": {"takeoff": 125, "landing": 108},
            "clmax": {"clean": 1.35, "takeoff": 1.6, "landing": 1.95},
            "engine": {"name": "Lycoming IO-360-A1B6", "hp": 180, "derate": 0.03},
            "g_limits": [
                {"category": "normal", "config": "clean", "positive": 3.8, "negative": -1.52},
                {"category": "normal", "config": "takeoff", "positive": 2.0, "negative": -1.0},
                {"category": "normal", "config": "landing", "positive": 2.0, "negative": -1.0},
            ],
            "stall_speeds": [
                {"config": "clean", "weight": 3800, "speed": 68},
                {"config": "clean", "weight": 3200, "speed": 62},
                {"config": "takeoff", "weight": 3800, "speed": 63},
                {"config": "landing", "weight": 3800, "speed": 58},
            ],
            "oei": [
                {"config": "clean_up", "prop_condition": "feathered", "max_power_fraction": 0.5},
                {"config": "clean_up", "prop_condition": "windmilling", "max_power_fraction": 0.45},
            ],
        },
        "default-aerobatic": {
            # Aerobatic: Extra 300, Pitts, CAP 232, Decathlon
            "aircraft_type": "single_engine",
            "gear_type": "fixed",
            "engine_count": 1,
            "wing_area": 100,
            "aspect_ratio": 5.0,
            "cd0": 0.030,
            "e": 0.75,
            "t_static": 2.8,
            "vmax": 220,
            "empty_weight": 1100,
            "max_weight": 1650,
            "seats": 2,
            "fuel_capacity": 40,
            "fuel_weight": 6.0,
            "vne": 220,
            "vno": 163,
            "best_glide": 100,
            "glide_ratio": 8.0,
            "ceiling": 16000,
            "arcs": {"white": [54, 100], "green": [61, 163], "yellow": [163, 220], "red": 220},
            "vfe": {"takeoff": None, "landing": 100},
            "clmax": {"clean": 1.6, "takeoff": 1.8, "landing": 2.1},
            "engine": {"name": "Lycoming AEIO-540", "hp": 300, "derate": 0.025},
            "g_limits": [
                {"category": "aerobatic", "config": "clean", "positive": 6.0, "negative": -3.0},
                {"category": "aerobatic", "config": "takeoff", "positive": 6.0, "negative": -3.0},
                {"category": "aerobatic", "config": "landing", "positive": 6.0, "negative": -3.0},
            ],
            "stall_speeds": [
                {"config": "clean", "weight": 1650, "speed": 61},
                {"config": "clean", "weight": 1400, "speed": 56},
                {"config": "landing", "weight": 1650, "speed": 54},
            ],
        },
        "default-experimental": {
            # LSA/Experimental: RV-12, CTLS, SportStar
            "aircraft_type": "single_engine",
            "gear_type": "fixed",
            "engine_count": 1,
            "wing_area": 120,
            "aspect_ratio": 8.5,
            "cd0": 0.025,
            "e": 0.82,
            "t_static": 2.5,
            "vmax": 138,
            "empty_weight": 750,
            "max_weight": 1320,
            "seats": 2,
            "fuel_capacity": 24,
            "fuel_weight": 6.0,
            "vne": 138,
            "vno": 108,
            "best_glide": 70,
            "glide_ratio": 11.0,
            "ceiling": 12000,
            "arcs": {"white": [37, 80], "green": [45, 108], "yellow": [108, 138], "red": 138},
            "vfe": {"takeoff": 90, "landing": 80},
            "clmax": {"clean": 1.45, "takeoff": 1.75, "landing": 2.05},
            "engine": {"name": "Rotax 912 ULS", "hp": 100, "derate": 0.03},
            "g_limits": [
                {"category": "normal", "config": "clean", "positive": 4.0, "negative": -2.0},
                {"category": "normal", "config": "takeoff", "positive": 4.0, "negative": -2.0},
                {"category": "normal", "config": "landing", "positive": 4.0, "negative": -2.0},
            ],
            "stall_speeds": [
                {"config": "clean", "weight": 1320, "speed": 45},
                {"config": "takeoff", "weight": 1320, "speed": 41},
                {"config": "landing", "weight": 1320, "speed": 37},
            ],
        },
    }

    if triggered not in defaults:
        raise PreventUpdate

    d = defaults[triggered]
    arcs = d["arcs"]
    clmax = d["clmax"]
    vfe = d["vfe"]
    eng = d["engine"]

    # Build engine options
    engine_options = [{
        "name": eng["name"],
        "horsepower": eng["hp"],
        "power_curve_sea_level": eng["hp"],
        "power_curve_derate": eng["derate"]
    }]

    # OEI data for multi-engine
    oei_data = d.get("oei", [])

    return (
        # Basic info
        d["aircraft_type"],
        d["gear_type"],
        d["engine_count"],
        # Aerodynamics
        d["wing_area"],
        d["aspect_ratio"],
        d["cd0"],
        d["e"],
        d["t_static"],
        d["vmax"],
        # Weights
        d["empty_weight"],
        d["max_weight"],
        d["seats"],
        d["fuel_capacity"],
        d["fuel_weight"],
        # Speeds
        d["vne"],
        d["vno"],
        d["best_glide"],
        d["glide_ratio"],
        d["ceiling"],
        # Arcs
        arcs["white"][0],
        arcs["white"][1],
        arcs["green"][0],
        arcs["green"][1],
        arcs["yellow"][0],
        arcs["yellow"][1],
        arcs["red"],
        # Flaps
        vfe["takeoff"],
        vfe["landing"],
        clmax["clean"],
        clmax["takeoff"],
        clmax["landing"],
        # Stores
        engine_options,
        d["g_limits"],
        d["stall_speeds"],
        oei_data,
    )

# Hide multi-engine sections for single-engine aircraft
@app.callback(
    Output("multi-engine-sections", "style"),
    Input("aircraft-type", "value"),
    prevent_initial_call=True
)
def toggle_multi_engine_sections(aircraft_type):
    if aircraft_type == "multi_engine":
        return {"display": "block"}
    else:
        return {"display": "none"}

# Sync units toggle switch with hidden input
@app.callback(
    Output("units-toggle", "value"),
    Input("units-toggle-switch", "value"),
    prevent_initial_call=True
)
def sync_units_toggle(switch_value):
    return "MPH" if switch_value else "KIAS"

# Expand/Collapse all accordions
@app.callback(
    Output("edit-accordion", "active_item"),
    Input("expand-all-btn", "n_clicks"),
    Input("collapse-all-btn", "n_clicks"),
    prevent_initial_call=True
)
def expand_collapse_all(expand_clicks, collapse_clicks):
    triggered = ctx.triggered_id
    all_items = ["basic", "aero", "weight", "speeds", "flaps", "glimits", "stall", "engines"]
    if triggered == "expand-all-btn":
        return all_items
    else:
        return []

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
        Output("gear-type", "value", allow_duplicate=True),
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
        "fixed",  # gear-type
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
    def to_mph(val): return round(val * KTS_TO_MPH, 1) if val is not None else None
    def to_kias(val): return round(val / KTS_TO_MPH, 1) if val is not None else None
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


def _build_single_engine_limits(se_limits, best_glide, best_glide_ratio):
    """
    Build the single_engine_limits dict with proper nesting for multi-engine aircraft.

    Input se_limits format (list of dicts):
        {"limit_type": "Vmca", "flap_config": "clean", "gear_config": "up", "value": 56}

    Output format (matching JSON schema):
        {
            "Vmca": {"clean_up": 56, "takeoff_up": 56, ...},
            "Vyse": {...},
            "Vxse": {...},
            "best_glide": 106,
            "best_glide_ratio": 9.5
        }
    """
    result = {}

    # Group by limit_type with config keys
    for s in (se_limits or []):
        limit_type = s.get("limit_type")
        if not limit_type:
            continue

        flap = s.get("flap_config", "clean")
        gear = s.get("gear_config", "up")
        value = s.get("value")

        # Build config key like "clean_up", "takeoff_down", "landing_down"
        config_key = f"{flap}_{gear}"

        if limit_type not in result:
            result[limit_type] = {}

        result[limit_type][config_key] = value

    # Add best glide info
    if best_glide is not None:
        result["best_glide"] = best_glide
    if best_glide_ratio is not None:
        result["best_glide_ratio"] = best_glide_ratio

    return result


@app.callback(
    [
        Output("save-status", "children", allow_duplicate=True),
        Output("aircraft-data-store", "data", allow_duplicate=True),
        Output("last-saved-aircraft", "data", allow_duplicate=True),
        Output("download-aircraft", "data", allow_duplicate=True),
    ],
    Input("save-aircraft-button", "n_clicks"),
    State("aircraft-data-store", "data"),
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
    State("stored-oei-performance", "data"),
    prevent_initial_call=True
)
def save_aircraft_to_file(
    n_clicks,
    current_data,
    name, wing_area, ar, cd0, e,
    flaps, g_limits, stall_speeds, se_limits, engines,
    units, empty_weight, max_weight, seats, cg_fwd, cg_aft, fuel_capacity, fuel_weight,
    white_btm, white_top, green_btm, green_top, yellow_btm, yellow_top, red,
    t_static, v_max_kts, best_glide, best_glide_ratio, aircraft_type, engine_count, vne, vno,
    vfe_takeoff, vfe_landing,
    clmax_clean, clmax_takeoff, clmax_landing, max_altitude, gear_type, oei_performance
):
    if not name:
        return (
            "❌ Aircraft name is required.",
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )

    # Track aircraft save/creation
    log_feature('aircraft_save', {
        'aircraft': name,
        'type': aircraft_type,
        'engine_count': engine_count
    })

    try:
        def convert_speed(val):
            return round(val / KTS_TO_MPH, 1) if units == "MPH" and isinstance(val, (int, float)) else val

        # --- Convert stall + SE limits ---
        converted_stalls = [
            {
                "config": s["config"],
                "gear": s["gear"],
                "weight": s["weight"],
                "speed": convert_speed(s["speed"])
            } for s in (stall_speeds or [])
        ]

        converted_se_limits = [
            {
                "limit_type": s["limit_type"],
                "flap_config": s["flap_config"],
                "gear_config": s["gear_config"],
                "value": convert_speed(s["value"])
            } for s in (se_limits or [])
        ]

        # --- Engines with OEI Performance ---
        engine_dict = {}
        if engines:
            for eng in engines:
                eng_name = eng.get("name", "Unnamed Engine")
                eng_data = {
                    "horsepower": eng.get("horsepower"),
                    "power_curve": {
                        "sea_level_max": eng.get("power_curve_sea_level"),
                        "derate_per_1000ft": eng.get("power_curve_derate"),
                    },
                }

                # Build OEI performance structure for this engine
                # OEI data is stored flat with config (e.g. "clean_up") and prop_condition
                oei_struct = {}
                for oei in (oei_performance or []):
                    # Handle both "config" and "config_key" for compatibility
                    config_key = oei.get("config") or oei.get("config_key", "clean_up")
                    prop_cond = oei.get("prop_condition", "feathered").lower()

                    if config_key not in oei_struct:
                        oei_struct[config_key] = {}

                    oei_struct[config_key][prop_cond] = {
                        "max_power_fraction": oei.get("max_power_fraction"),
                    }

                if oei_struct:
                    eng_data["oei_performance"] = oei_struct

                engine_dict[eng_name] = eng_data

        # --- G limits ---
        g_structured = {}
        for g in (g_limits or []):
            cat = g.get("category")
            cfg = g.get("config")
            pos = g.get("positive")
            neg = g.get("negative")

            # Default negative G to 0 if not specified
            if neg is None:
                neg = 0

            if cat and cfg:
                g_structured.setdefault(cat, {})[cfg] = {
                    "positive": pos,
                    "negative": neg,
                }

        # --- Stall structured ---
        stall_structured = {}
        for s in converted_stalls:
            cfg = s["config"]
            if cfg not in stall_structured:
                stall_structured[cfg] = {"weights": [], "speeds": []}
            stall_structured[cfg]["weights"].append(s["weight"])
            stall_structured[cfg]["speeds"].append(s["speed"])

        # --- Flap names ---
        flap_names = [f["name"] for f in (flaps or []) if isinstance(f, dict) and f.get("name")]
        if not flap_names:
            flap_names = ["clean", "takeoff", "landing"]

        # --- Vfe dict (using the dedicated Vfe fields you added) ---
        arcs = {
            "white": [convert_speed(white_btm), convert_speed(white_top)],
            "green": [convert_speed(green_btm), convert_speed(green_top)],
            "yellow": [convert_speed(yellow_btm), convert_speed(yellow_top)],
            "red": convert_speed(red),
        }

        vfe_dict = {}
        if vfe_takeoff is not None:
            vfe_dict["takeoff"] = convert_speed(vfe_takeoff)
        if vfe_landing is not None:
            vfe_dict["landing"] = convert_speed(vfe_landing)

        # --- CLmax dict ---
        clmax_dict = {}
        if clmax_clean is not None:
            clmax_dict["clean"] = clmax_clean
        if clmax_takeoff is not None:
            clmax_dict["takeoff"] = clmax_takeoff
        if clmax_landing is not None:
            clmax_dict["landing"] = clmax_landing

        # --- Build aircraft dict ---
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
            "engine_options": engine_dict,
            "max_altitude": max_altitude,
            "Vne": convert_speed(vne),
            "Vno": convert_speed(vno),
            "Vfe": vfe_dict,
            "CL_max": clmax_dict,
            "arcs": arcs,
            "empty_weight": empty_weight,
            "max_weight": max_weight,
            "single_engine_limits": _build_single_engine_limits(
                converted_se_limits, best_glide, best_glide_ratio
            ),
            "seats": seats,
            "cg_range": [cg_fwd, cg_aft],
            "fuel_capacity_gal": fuel_capacity,
            "fuel_weight_per_gal": fuel_weight,
            "prop_thrust_decay": {
                "T_static_factor": t_static,
                "V_max_kts": v_max_kts,
            },
        }

        # --- Write to disk ---
        filename = name.replace(" ", "_") + ".json"
        filepath = os.path.join("aircraft_data", filename)

        if os.path.exists(filepath):
            # File already exists – do NOT overwrite, do NOT change store
            return (
                "❌ That aircraft already exists. Please enter a new name.",
                dash.no_update,
                dash.no_update,
                dash.no_update,
            )

        with open(filepath, "w") as f:
            json.dump(ac_dict, f, indent=2)

        # --- Update in-memory data store instead of reloading from folder ---
        current_data = current_data or {}
        current_data[name] = ac_dict

        return (
            f"✅ Saved as {filename}",
            current_data,                                        # aircraft-data-store
            name,                                                # last-saved-aircraft
            dcc.send_string(json.dumps(ac_dict, indent=2), filename),  # download-aircraft
        )

    except Exception as e:
        return (
            f"❌ Error saving: {str(e)}",
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )


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

        # Track aircraft upload
        log_feature('aircraft_upload', {
            'aircraft': name,
            'type': aircraft_json.get('type', 'unknown'),
            'engine_count': aircraft_json.get('engine_count', 1)
        })

        dprint(f"[UPLOAD] Loaded aircraft: {name}")
        return current_data, name, name

    except Exception as e:
        dprint(f"[UPLOAD ERROR]: {e}")
        raise PreventUpdate

@app.callback(
    Output("disclaimer-modal", "is_open"),
    Output("terms-policy-modal", "is_open"),
    Output("readme-modal", "is_open"),
    Input("open-disclaimer", "n_clicks"),
    Input("close-disclaimer", "n_clicks"),
    Input("open-terms-policy", "n_clicks"),
    Input("close-terms-policy", "n_clicks"),
    Input("open-readme", "n_clicks"),
    Input("close-readme", "n_clicks"),
    State("disclaimer-modal", "is_open"),
    State("terms-policy-modal", "is_open"),
    State("readme-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_modals(open_disc, close_disc, open_terms, close_terms, open_readme, close_readme, disc_open, terms_open, readme_open):
    if not ctx.triggered:
        raise PreventUpdate

    ctx_id = ctx.triggered_id

    if ctx_id == "open-disclaimer" and open_disc:
        return True, False, False
    elif ctx_id == "close-disclaimer" and close_disc:
        return False, terms_open, readme_open
    elif ctx_id == "open-terms-policy" and open_terms:
        return False, True, False
    elif ctx_id == "close-terms-policy" and close_terms:
        return disc_open, False, readme_open
    elif ctx_id == "open-readme" and open_readme:
        return False, False, True
    elif ctx_id == "close-readme" and close_readme:
        return disc_open, terms_open, False

    raise PreventUpdate




# =============================================================================
# MOBILE OVERLAY SYNC CALLBACK
# =============================================================================

@app.callback(
    Output("overlay-toggle", "data", allow_duplicate=True),
    Input("mobile-overlay-checklist", "value"),
    prevent_initial_call=True
)
def sync_mobile_overlay_to_store(checklist_value):
    """Sync mobile overlay checklist to the overlay-toggle store."""
    return checklist_value if checklist_value is not None else []


# =============================================================================
# SIDEBAR COLLAPSE CALLBACKS
# =============================================================================

# Desktop sidebar collapse - use Python callback for reliability
@app.callback(
    [Output("sidebar-collapsed", "data"),
     Output("sidebar-collapse-btn", "children"),
     Output("sidebar-container", "className")],
    Input("sidebar-collapse-btn", "n_clicks"),
    State("sidebar-collapsed", "data"),
    prevent_initial_call=True
)
def toggle_sidebar_collapse(n_clicks, is_collapsed):
    if n_clicks:
        new_state = not is_collapsed
        btn_text = "»" if new_state else "«"
        class_name = "resizable-sidebar collapsed" if new_state else "resizable-sidebar"
        return new_state, btn_text, class_name
    return is_collapsed, "«", "resizable-sidebar"

# Mobile settings toggle
@app.callback(
    [Output("mobile-settings-collapse", "is_open"),
     Output("mobile-settings-toggle", "children")],
    Input("mobile-settings-toggle", "n_clicks"),
    State("mobile-settings-collapse", "is_open"),
    prevent_initial_call=True
)
def toggle_mobile_settings(n_clicks, is_open):
    if n_clicks:
        new_state = not is_open
        return new_state, "▲" if new_state else "▼"
    return is_open, "▼"


# =============================================================================
# HELP SYSTEM CALLBACKS
# =============================================================================

# Help content for each feature
HELP_CONTENT = {
    "ps": {
        "title": "Ps Contours (Specific Excess Power)",
        "body": """
**Ps (Specific Excess Power)** represents the rate at which the aircraft can gain or lose energy per unit weight, expressed in feet per second.

**How to interpret:**
- **Positive Ps** (solid lines): The aircraft has excess power and can climb or accelerate
- **Zero Ps** (dashed line): The aircraft is at its performance limit - it can maintain speed and altitude but cannot climb or accelerate
- **Negative Ps** (inside the zero line): The aircraft is losing energy and must descend or decelerate

**Practical use:**
- Find the airspeed/turn rate combination where Ps = 0 to know your sustained turn capability
- Higher Ps values indicate better climb performance at that flight condition
- Use this to compare sustained vs instantaneous maneuvering capability
"""
    },
    "g": {
        "title": "Intermediate G Lines",
        "body": """
**G-Lines** show constant load factor (G) contours across the maneuvering envelope.

**What load factor means:**
- **1G**: Level, unaccelerated flight
- **2G**: The aircraft experiences twice its weight (common in 60° bank turns)
- **Higher G**: More aggressive maneuvering, higher structural and physiological loads

**How to interpret:**
- Each line represents a specific G loading
- Where a G-line intersects the stall boundary shows the minimum speed to achieve that G
- The lines help visualize how turn rate relates to load factor and airspeed

**Practical use:**
- Identify sustainable G levels for extended maneuvering
- Plan maneuvers that stay within structural and physiological limits
- Understand the relationship between bank angle, G, and turn performance
"""
    },
    "radius": {
        "title": "Turn Radius Lines",
        "body": """
**Turn Radius Lines** show constant-radius turn contours in feet.

**How to interpret:**
- Each curved line represents a specific turn radius
- Smaller radius = tighter turn (more aggressive maneuvering)
- Turn radius depends on both airspeed and turn rate

**Key relationships:**
- Higher speeds at the same turn rate = larger radius
- Higher turn rates at the same speed = smaller radius
- Minimum radius occurs at the intersection of stall boundary and structural limit

**Practical use:**
- Plan ground reference maneuvers with specific radius requirements
- Evaluate maneuvering capability in confined airspace
- Compare different speed/bank combinations that achieve the same radius
"""
    },
    "aob": {
        "title": "Angle of Bank Shading",
        "body": """
**Angle of Bank (AOB) Shading** shows the bank angle required to achieve each turn rate at various airspeeds.

**Color interpretation:**
- Lighter shades = shallow bank angles (30-45°)
- Darker shades = steep bank angles (60°+)
- The color gradient helps visualize how bank angle varies across the envelope

**Key relationships:**
- At a given turn rate, higher speeds require steeper bank angles
- At a given speed, higher turn rates require steeper bank angles
- Bank angle directly relates to load factor: G = 1/cos(bank)

**Practical use:**
- Quickly identify the bank angle needed for a desired turn rate
- Plan steep turns and chandelles at appropriate speeds
- Understand the transition from shallow to steep maneuvering
"""
    },
    "negative_g": {
        "title": "Negative G Envelope",
        "body": """
**Negative G Envelope** shows the aircraft's capability when flying at negative (pushed) load factors.

**What this represents:**
- The region where the aircraft is being "pushed" rather than "pulled"
- Occurs during inverted flight, pushovers, or outside maneuvers
- Limited by negative G structural limits and inverted stall characteristics

**Key assumptions:**
- The aircraft is being pushed to maintain level flight attitude
- Negative G stall speeds are typically higher than positive G
- Structural negative G limits are usually lower than positive limits

**Practical use:**
- Understand the full maneuvering envelope including unusual attitudes
- Plan recovery from unusual attitudes within structural limits
- Useful for aerobatic flight planning
"""
    },
    "dvmc": {
        "title": "Dynamic Vmc",
        "body": """
**Dynamic Vmc** shows how the minimum control speed with one engine inoperative varies with flight conditions.

**What affects DVmc:**
- **Weight**: Lighter weight = higher Vmc (less rudder authority relative to asymmetric thrust)
- **Density altitude**: Higher DA = lower Vmc (reduced engine power)
- **Bank angle**: 5° into good engine = lowest Vmc; deviations increase it
- **CG position**: Aft CG = higher Vmc (reduced rudder moment arm)
- **Prop condition**: Windmilling = highest Vmc; feathered = lowest

**How to interpret:**
- The DVmc line shows Vmc at various bank angles
- Points above the line are controllable; below may not be
- The published Vmc is a certification point at specific conditions

**Safety note:**
- DVmc shows where directional control is lost
- Always maintain above DVmc during OEI operations
- Real-world Vmc depends on many factors - this is a planning tool
"""
    },
    "dvyse": {
        "title": "Dynamic Vyse",
        "body": """
**Dynamic Vyse** shows how the best single-engine rate of climb speed varies with conditions.

**What affects DVyse:**
- **Weight**: Higher weight = higher Vyse
- **Density altitude**: Higher DA = higher Vyse
- **Configuration**: Gear/flaps extended = higher Vyse
- **Prop condition**: Affects drag and thus optimal speed

**How to interpret:**
- The DVyse marker shows the calculated best single-engine climb speed
- This is where you'll get maximum climb (or minimum sink) on one engine
- Published Vyse is based on standard conditions and max weight

**Practical use:**
- Adjust Vyse for actual conditions during OEI operations
- Lighter weight at altitude may require a different target speed
- Use in conjunction with DVmc to understand the OEI speed envelope
"""
    },
    "fpa": {
        "title": "Flight Path Angle",
        "body": """
**Flight Path Angle** adjusts the EM diagram for climbing or descending flight.

**What it represents:**
- **0°**: Level flight (default)
- **Positive angles**: Climbing - aircraft exchanges kinetic for potential energy
- **Negative angles**: Descending - aircraft gains kinetic energy from altitude

**Effect on the diagram:**
- Climbing reduces available excess power for maneuvering
- Descending increases available energy (but altitude is being spent)
- The diagram shifts to reflect changed energy state

**Practical use:**
- Analyze climb performance during maneuvering
- Plan maneuvers during approach or departure segments
- Understand how climb/descent affects turn performance
"""
    },
    "maneuver": {
        "title": "Maneuver Overlays & Ghost Trace",
        "body": """
**Maneuver Overlays** trace the energy state throughout specific flight maneuvers.

**Steep Turn:**
- Shows the trajectory through the EM diagram during a constant-altitude steep turn
- Traces from entry through established turn
- Helps verify the aircraft has sufficient Ps to maintain altitude

**Chandelle:**
- Shows the climbing turn trajectory
- Entry speed, bank angle, and climb combine to trace a path
- Useful for planning energy management through the maneuver

**Ghost Trace:**
The Ghost Trace toggle displays a visual path showing how the maneuver progresses through the EM diagram:
- Shows the trajectory from entry conditions through the maneuver
- Visualizes how airspeed and turn rate change during the maneuver
- Helps identify if you have enough Ps margin to maintain altitude/complete the maneuver

**ACS Standards (Steep Turns):**
- **Private**: 45° bank angle per ACS requirements
- **Commercial**: 50° bank angle per ACS requirements

**How to interpret:**
- The trace shows where in the envelope the maneuver takes you
- If the trace crosses negative Ps regions, altitude/speed will be lost
- Staying in positive Ps regions means the maneuver is sustainable

**Practical use:**
- Verify maneuver feasibility before attempting
- Optimize entry speeds and bank angles
- Understand energy trade-offs during complex maneuvers
"""
    },
    "ghost": {
        "title": "Ghost Trace",
        "body": """
**Ghost Trace** displays a visual path showing how a maneuver progresses through the EM diagram.

**What it shows:**
- The trajectory from entry conditions through the maneuver
- How airspeed and turn rate change during the maneuver
- Where the aircraft's energy state moves relative to the performance envelope

**For Steep Turns:**
- Shows the path from straight-and-level entry into the established turn
- Visualizes the speed/energy trade-off during roll-in
- Helps identify if you have enough Ps margin to maintain altitude

**For Chandelles:**
- Traces the climbing turn from entry through the 180° heading change
- Shows energy state as speed bleeds off during the climb
- Indicates if the maneuver will result in adequate final airspeed

**ACS Standards (Steep Turns):**
- **Private**: 45° bank angle requirement per ACS
- **Commercial**: 50° bank angle requirement per ACS

**Practical use:**
- Preview maneuver energy requirements before flying
- Optimize entry airspeed for maneuver completion
- Understand why certain entry conditions may not work
"""
    }
}


@app.callback(
    Output("overlay-toggle", "data"),
    Input("toggle-ps", "value"),
    Input("toggle-g", "value"),
    Input("toggle-radius", "value"),
    Input("toggle-aob", "value"),
    Input("toggle-negative-g", "value"),
    prevent_initial_call=True
)
def sync_overlay_switches(ps_on, g_on, radius_on, aob_on, neg_g_on):
    """Sync individual overlay switches to the overlay-toggle store."""
    selected = []
    if ps_on:
        selected.append("ps")
    if g_on:
        selected.append("g")
    if radius_on:
        selected.append("radius")
    if aob_on:
        selected.append("aob")
    if neg_g_on:
        selected.append("negative_g")
    return selected


@app.callback(
    Output("multi-engine-toggle-options", "data"),
    Input("toggle-vmca", "value"),
    Input("toggle-vyse", "value"),
    prevent_initial_call=True
)
def sync_me_switches(vmca_on, vyse_on):
    """Sync multi-engine switches to the multi-engine-toggle-options store."""
    selected = []
    if vmca_on:
        selected.append("vmca")
    if vyse_on:
        selected.append("dynamic_vyse")
    return selected


@app.callback(
    Output("help-modal", "is_open"),
    Output("help-modal-title", "children"),
    Output("help-modal-body", "children"),
    Input("help-ps", "n_clicks"),
    Input("help-g", "n_clicks"),
    Input("help-radius", "n_clicks"),
    Input("help-aob", "n_clicks"),
    Input("help-negative-g", "n_clicks"),
    Input("help-dvmc", "n_clicks"),
    Input("help-dvyse", "n_clicks"),
    Input("help-fpa", "n_clicks"),
    Input("help-maneuver", "n_clicks"),
    Input("help-ghost", "n_clicks"),
    Input("close-help-modal", "n_clicks"),
    State("help-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_help_modal(ps, g, radius, aob, neg_g, dvmc, dvyse, fpa, maneuver, ghost, close, is_open):
    """Handle help icon clicks and display appropriate content."""
    if not ctx.triggered:
        raise PreventUpdate

    triggered_id = ctx.triggered_id

    # Extra guard: ensure this is an actual click (n_clicks > 0)
    triggered_value = ctx.triggered[0]["value"] if ctx.triggered else None
    if triggered_value is None or triggered_value == 0:
        raise PreventUpdate

    # Close button
    if triggered_id == "close-help-modal":
        return False, "", ""

    # Map triggered ID to help topic
    topic_map = {
        "help-ps": "ps",
        "help-g": "g",
        "help-radius": "radius",
        "help-aob": "aob",
        "help-negative-g": "negative_g",
        "help-dvmc": "dvmc",
        "help-dvyse": "dvyse",
        "help-fpa": "fpa",
        "help-maneuver": "maneuver",
        "help-ghost": "ghost"
    }

    topic = topic_map.get(triggered_id)
    if topic and topic in HELP_CONTENT:
        content = HELP_CONTENT[topic]
        # Convert markdown to HTML using dcc.Markdown
        body = dcc.Markdown(content["body"], style={"lineHeight": "1.6"})
        return True, content["title"], body

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

    # Use 0.0.0.0 to allow access from other devices on the network
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8051
    app.run(debug=debug_mode, host="0.0.0.0", port=port)
