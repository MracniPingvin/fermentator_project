import dash
import dash_bootstrap_components as dbc
from data.private import VALID_USERNAME_PASSWORD_PAIRS
import dash_auth

external_stylesheets = [dbc.themes.LUX]
app = dash.Dash(__name__,
                external_stylesheets=external_stylesheets,
                suppress_callback_exceptions=True)
auth = dash_auth.BasicAuth(
    app,
    VALID_USERNAME_PASSWORD_PAIRS
)
server = app.server

