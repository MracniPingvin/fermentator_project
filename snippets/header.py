import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc

layout = \
    dbc.Row([

        dbc.Col(
            html.H1(children="BLACK GARLIC FERMENTER",
                    className="header-title text-center"),
        ),
        dbc.Col(
            dcc.Link(html.H2(children="Graph",
                             className="header-button text-center"),
                     href='/graph',
                     className='header-button'),
            width=1
        ),
        dbc.Col(
            dcc.Link(html.H2(children="Camera",
                             className="header-button text-center"),
                    href='/camera',
                    className='header-button'),
            width=1),
        dbc.Col(
            className="col-xs-6 pull-right col-xs-pull-1",
            width=1
        ),
        ],
        align="center",
        className="header-row"
    )