import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

from app import app
from snippets import header

layout = \
dbc.Container([
    header.layout,
    dbc.Row([
        dbc.Col([
            html.Div([
                dcc.Link('Go to graph', href='/graph', className='landing-text'),
            ], className="landing-wrapper graph-wrapper"),
        ], className="text-center"),
        dbc.Col([
            html.Div([
                dcc.Link('Go to camera', href='/camera', className='landing-text'),
            ], className="graph-wrapper landing-wrapper"),
        ], className="text-center")
    ])
], fluid=True)
