import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
from app import app
from pages import graph, landing

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])


@app.callback(Output('page-content', 'children'),
              Input('url', 'pathname'))
def display_page(pathname):
    if pathname == '/graph':
        return graph.layout
    else:
        return landing.layout

if __name__ == '__main__':
    app.run_server(debug=True, use_reloader=False)
    #app.run_server(host= '0.0.0.0',debug=False, use_reloader=False)
