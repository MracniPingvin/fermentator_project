from app import app
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import pandas as pd
from scripts.fermentor import Fermentor
from snippets import header
import datetime
import time

class Graph_page:
    def __init__(self, app):
        self.app = app
        #self.fermentor = Fermentor(serial_port_name='/dev/ttyACM0')
        self.fermentor = Fermentor()
        
        self.auto_scale = True
        self.update_shapes = False
        self.config = {
            'modeBarButtonsToRemove': ['toggleSpikelines', 'hoverCompareCartesian', 'lasso2d', 'hoverClosestCartesian', 'autoScale2d', 'resetScale2d'],
            'displaylogo': False,
            'displayModeBar': False}
        self.colors_temperature = ["red", "red", "red", "red"]
        self.colors_humidity = ["blue", "blue", "blue", "blue"]
        self.dashes = ["solid", "dash", "dot", "dashdot"]
        self.trace_names = ["back-top-left","front-bottom-left","front-top-right","back-bottom-right"]
        
        self.temperature_range_tolerance = 5
        self.temperature_ranges = None
        self.temperature_range_y_axis = [0, 110]
        self.temperature_columns = [x for x in self.fermentor.in_names["temperature"]]
        self.temperature_delta = 5
        self.humidity_range_tolerance = 5
        self.humidity_ranges = None
        self.humidity_range_y_axis = [0, 100]
        self.humidity_columns = [x for x in self.fermentor.in_names["humidity"]]
        self.humidity_delta = 5
        self.time_delta = datetime.timedelta(minutes=10, seconds=0)
        self.time_offset = self.time_delta/5
        
        self.init_ranges()
        data = self.init_data()

        figure_temperature, figure_humidity = self.init_graphs(data)
        self.layout = None
        self.init_layout(figure_temperature, figure_humidity)
        self.init_callbacks()

    def init_ranges(self):
        target_temp = self.fermentor.params["temperature"]["target"]["current"]
        hyst_temp = self.fermentor.params["temperature"]["hysteresis"]["current"]
        self.temperature_ranges = [target_temp - hyst_temp - self.temperature_range_tolerance,
                                   target_temp - hyst_temp,
                                   target_temp + hyst_temp,
                                   target_temp + hyst_temp + self.temperature_range_tolerance]
                                   
        target_humid = self.fermentor.params["humidity"]["target"]["current"]
        hyst_humid = self.fermentor.params["humidity"]["hysteresis"]["current"]
        self.humidity_ranges = [target_humid - hyst_humid - self.humidity_range_tolerance,
                                   target_humid - hyst_humid,
                                   target_humid + hyst_humid,
                                   target_humid + hyst_humid + self.humidity_range_tolerance]

    def filter_results(self, df):
        max_time = df["time"].max()
        cutoff_time = max_time - self.time_delta + self.time_offset
        return df[df["time"] > cutoff_time]

    def draw_acceptable_ranges(self, fig, ranges):
        # input: range in format [lower yellow, lower green, high green, high yellow]
        fig['layout']['shapes'] = tuple() # delete current rectangles
        fig.add_hrect(
            y0=-100, y1=ranges[0], line_width=0,
            fillcolor="red", opacity=0.2)
        fig.add_hrect(
            y0=ranges[0], y1=ranges[1], line_width=0,
            fillcolor="yellow", opacity=0.2)
        fig.add_hrect(
            y0=ranges[1], y1=ranges[2], line_width=0,
            fillcolor="green", opacity=0.2)
        fig.add_hrect(
            y0=ranges[2], y1=ranges[3], line_width=0,
            fillcolor="yellow", opacity=0.2)
        fig.add_hrect(
            y0=ranges[3], y1=200, line_width=0,
            fillcolor="red", opacity=0.2)
        # fig.add_hline(y=(ranges[2]-ranges[1])/2, line_width=3, line_color="red")
        return fig
        
    def init_graph(self, df, columns, ranges=None, dash=None, color=None, y_axis_range=None):
        fig = go.Figure()
        fig.update_layout(uirevision=True)
        if ranges:
            fig = self.draw_acceptable_ranges(fig, ranges)
        fig.update_xaxes(autorange=False)
        fig.update_layout(yaxis_range=y_axis_range, margin={'t': 10, 'b': 10}, height=400)
        fig = self.draw_lines(fig, df, columns, dash, color)
        return fig

    def draw_lines(self, fig, df, columns, dash=None, color=None):
        if self.time_delta < datetime.timedelta(minutes=11):
            mode = 'lines+markers'
        else:
            mode = 'lines'
        fig.data = [] # delete current lines
        for i in range(len(columns)):
            fig.add_trace(
                go.Scatter(x=df['time'],
                           y=df[columns[i]],
                           mode=mode,
                           opacity=0.3,
                           line=dict(dash=dash[i],
                                     color=color[i],),
                           name=self.trace_names[i]),

                )
        avg_df = df[columns].mean(axis=1)
        fig.add_trace(
                go.Scatter(x=df['time'],
                           y=avg_df,
                           mode=mode,
                           opacity=1,
                           line=dict(dash='solid',
                                     color=color[0],),
                           name="average"),
                )
        return fig

    def init_data(self):
        df = pd.DataFrame(self.fermentor.measurements.copy())
        if df.empty:
            df = pd.DataFrame([self.fermentor.create_empty_data_block()])
            df['time'] = datetime.datetime.now()
            df = self.filter_results(df)
        return df

    def init_graphs(self, data):
        figure_temperature = self.init_graph(data, self.temperature_columns,
                                              color=self.colors_temperature,
                                              dash=self.dashes,
                                              ranges=self.temperature_ranges,
                                              y_axis_range=self.temperature_range_y_axis)
        figure_humidity = self.init_graph(data, self.humidity_columns,
                                           color=self.colors_humidity,
                                           dash=self.dashes,
                                           ranges=self.humidity_ranges,
                                           y_axis_range=self.humidity_range_y_axis)
        return figure_temperature, figure_humidity
    
    def update_indicator_row(self, states):
        elements = []
        for i in states:
            if i:
                elements.append(html.Div(className="square-indicator-true"))
            else:
                elements.append(html.Div(className="square-indicator-false"))
        return elements
    
    def update_parameters(self, n_clicks, temperature_target, temperature_hysteresis, humidity_target, humidity_hysteresis):
        if n_clicks:
            try:
                temperature_target = float(temperature_target)
                temperature_hysteresis = float(temperature_hysteresis)
                humidity_target = float(humidity_target)
                humidity_hysteresis = float(humidity_hysteresis)
                if temperature_target + temperature_hysteresis > 95:
                    return "TOO HOT TO HANDLE!"
                if temperature_target - temperature_hysteresis < 0:
                    return "TOO COLD TO HANDLE"
                if humidity_target + humidity_hysteresis > 100:
                    return "TOO HUMID TO HANDLE!"
                if humidity_target - humidity_hysteresis < 0:
                    return "TOO DRY TO HANDLE"
            except:
                return "INVALID PARAMETERS!"
            self.fermentor.update_parameters(temperature_target, humidity_target, temperature_hysteresis, humidity_hysteresis)
            message = self.fermentor.get_parameter_string()
            self.fermentor.send_queue.put(message)
            self.init_ranges()
            self.update_shapes = True
            return "PARAMETERS UPDATED!"
        return ""
            
    def init_layout(self, figure_temperature, figure_humidity):
        self.layout = \
            dbc.Container([
                header.layout,
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            dcc.RadioItems(
                                id="time-radio",
                                options=[
                                    {'label': '1min', 'value': '1 min'},
                                    {'label': '10min', 'value': '5 min'},
                                    {'label': '30min', 'value': '30 min'},
                                    {'label': '1h', 'value': '1 h'},
                                    {'label': '12h', 'value': '12 h'},
                                    {'label': '1d', 'value': '1 d'},
                                    {'label': '7d', 'value': '7 d'},
                                    {'label': '14d', 'value': '14 d'},
                                    {'label': '1mo', 'value': '1 mo'},
                                    {'label': '3mo', 'value': '3 mo'},
                                    {'label': 'disable auto-scale', 'value': '0 disable'},
                                    ],
                                value='5 min',
                                labelStyle={'display': 'inline-block'}
                            ),
                            dcc.Graph(
                                id='temperature',
                                figure=figure_temperature,
                                config=self.config,
                                #animate=True
                            ),
                            dcc.Graph(
                                id='humidity',
                                figure=figure_humidity,
                                config=self.config,
                                #animate=True
                            ),
                            html.Div(id="time_select"),
                            ], className="graph-wrapper text-center",
                        ),
                        dcc.Interval(
                            id='interval-component',
                            interval=3*1000, # in milliseconds
                            n_intervals=0
                        ),
                    ], lg=9, md=12),
                    dbc.Col([
                        html.Div([
                            html.Div([
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Label("Target temperature:"),
                                        html.Br(),
                                        dcc.Input(id='input-temperature-target', type='number', value='80'),
                                    ], className="text-center"),
                                    dbc.Col([
                                        dbc.Label("Temperature hysteresis:"),
                                        html.Br(),
                                        dcc.Input(id='input-temperature-hysteresis', type='number', value='5'),
                                    ], className="text-center"),
                                ]),
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Label("Target humidity:"),
                                        html.Br(),
                                        dcc.Input(id='input-humidity-target', type='number', value='80'),
                                    ], className="text-center"),
                                    dbc.Col([
                                        dbc.Label("Humidity hysteresis:"),
                                        html.Br(),
                                        dcc.Input(id='input-humidity-hysteresis', type='number', value='5'),
                                    ], className="text-center")
                                ]),
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Button("Update parameters", id='input-update-parameters', color="dark",
                                                   className="button-custom"),
                                        html.Div(id="output-update-parameters")
                                    ], className="text-center")
                                ])
                            ], className="target-wrapper"),
                            html.Div([
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Button("Pause", id="button-pause", color="dark", className="button-custom")
                                    ], className="text-center"),
                                    dbc.Col([
                                        dbc.Button("Resume", id="button-resume", color="dark", className="button-custom")
                                    ], className="text-center"),
                                ]),
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Button("Start", id="button-start", color="dark", className="button-custom"),
                                        dcc.Input(
                                            id="input-start",
                                            type="number",
                                            value="50",
                                            placeholder="input number in minutes",
                                        )
                                    ], className="text-center"),
                                    dbc.Col([
                                        dbc.Button("Stop", id="button-stop", color="dark", className="button-custom")
                                    ], className="text-center"),
                                ]),
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Label("Time to finish:"),
                                        html.Br(),
                                        dbc.Label("", id="countdown-time"),
                                    ])
                                ], className="text-center"),
                            ], className="target-wrapper"),
                        ], className="graph-wrapper"),
                        html.Div([
                            dbc.Label("Heater"),
                            html.Br(),
                            html.Div([
                                html.Div(className="square-indicator-false") for x in self.fermentor.in_names["heater"]
                            ], id= "heater-indicator-row"),
                            dbc.Label("Fans"),
                            html.Br(),
                            html.Div([
                                html.Div(className="square-indicator-false") for x in self.fermentor.in_names["fan"]
                            ], id= "fans-indicator-row"),
                            dbc.Label("Humidifier"),
                            html.Br(),
                            html.Div([
                                html.Div(className="square-indicator-false") for x in self.fermentor.in_names["moisturizer"]
                            ], id= "humidifier-indicator-row"),
                        ], className="graph-wrapper"),
                    ], lg=3, md=12),
                    
                    
                ]),
                html.Div(id='none0', style = {'display':'none'}),
                html.Div(id='none1', style = {'display':'none'}),
                html.Div(id='none2', style = {'display':'none'}),
                html.Div(id='none3', style = {'display':'none'}),
                html.Div(id='none4', style = {'display':'none'}),
                html.Div(id='none5', style = {'display':'none'}),
                html.Div(id='none6', style = {'display':'none'}),
            ],fluid=True)

    def init_callbacks(self):
        @self.app.callback(
            Output("output-update-parameters", "children"),
            Input("input-update-parameters", "n_clicks"),
            State('input-temperature-target', "value"),
            State('input-temperature-hysteresis', "value"),
            State('input-humidity-target', "value"),
            State('input-humidity-hysteresis', "value"),
        )
        def update_parameters(n_clicks, temperature_target, temperature_hysteresis, humidity_target, humidity_hysteresis):
            return self.update_parameters(n_clicks, temperature_target, temperature_hysteresis, humidity_target, humidity_hysteresis)

        @app.callback(Output('temperature', 'figure'),
                      Output('humidity', 'figure'),
                      Output('temperature', 'config'),
                      Output('humidity', 'config'),
                      Output('countdown-time', 'children'),
                      Output('heater-indicator-row','children'),
                      Output('fans-indicator-row','children'),
                      Output('humidifier-indicator-row', 'children'),
                      Input('interval-component', 'n_intervals'),
                      Input('time-radio', 'value'),
                      State('temperature', 'figure'),
                      State('humidity', 'figure'),
                      )
        def update_graphs(n, time_radio, figure_temperature, figure_humidity):
            time_radio = time_radio.split()
            if time_radio[1] == "min":
                self.time_delta = datetime.timedelta(minutes=int(time_radio[0]))
            if time_radio[1] == "h":
                self.time_delta = datetime.timedelta(hours=int(time_radio[0]))
            if time_radio[1] == "d":
                self.time_delta = datetime.timedelta(days=int(time_radio[0]))
            if time_radio[1] == "mo":
                self.time_delta = datetime.timedelta(days=31 * int(time_radio[0]))
            if time_radio[1] == "disable":
                self.auto_scale = False
            else:
                self.auto_scale = True
                self.time_offset = self.time_delta / 5

            data = self.init_data()
            
            #refresh lines
            figure_temperature = go.Figure(figure_temperature)
            figure_humidity = go.Figure(figure_humidity)
            figure_temperature = self.draw_lines(figure_temperature,
                                                  data,
                                                  self.temperature_columns,
                                                  self.dashes,
                                                  self.colors_temperature)
            figure_humidity = self.draw_lines(figure_humidity,
                                              data,
                                              self.humidity_columns,
                                              self.dashes,
                                              self.colors_humidity)
            
            #handle all automatic scaling
            if self.auto_scale:
                self.config['displayModeBar']=False
                range_x_max = data["time"].max() + self.time_offset
                range_x_min = range_x_max - self.time_delta
                range_y_max_temperature = data[self.temperature_columns].max().max() + self.temperature_delta
                range_y_min_temperature = data[self.temperature_columns].min().min() - self.temperature_delta
                range_y_max_humidity = data[self.humidity_columns].max().max() + self.humidity_delta
                range_y_min_humidity = data[self.humidity_columns].min().min() - self.humidity_delta
                self.humidity_range_y_axis = [range_y_min_humidity, range_y_max_humidity]
                self.temperature_range_y_axis = [range_y_min_temperature, range_y_max_temperature]
                figure_humidity.update_xaxes(range=[range_x_min, range_x_max])
                figure_humidity.update_yaxes(range=self.humidity_range_y_axis)
                figure_temperature.update_xaxes(range=[range_x_min, range_x_max])
                figure_temperature.update_yaxes(range=self.temperature_range_y_axis)
            else:
                self.config['displayModeBar']=True
            
            #update range rectangles
            if self.update_shapes:
                figure_temperature = self.draw_acceptable_ranges(figure_temperature, self.temperature_ranges)
                figure_humidity = self.draw_acceptable_ranges(figure_humidity, self.humidity_ranges)
            
            #update countdown
            countdown_time = data[self.fermentor.in_names["time_left"][0]].iloc[-1]
            countdown_string = str(countdown_time)
            
            #update indicators
            heater_indicator_row = self.update_indicator_row(data[x].iloc[-1] for x in self.fermentor.in_names["heater"])
            fans_indicator_row = self.update_indicator_row(data[x].iloc[-1] for x in self.fermentor.in_names["fan"])
            humidifier_indicator_row = self.update_indicator_row(data[x].iloc[-1] for x in self.fermentor.in_names["moisturizer"])

            return figure_temperature, figure_humidity, self.config, self.config, countdown_string, heater_indicator_row, fans_indicator_row, humidifier_indicator_row

        @self.app.callback(
            Output("none0", "children"),
            Input("button-start", "n_clicks"),
            State("input-start", "value"),
            State('input-temperature-target', "value"),
            State('input-temperature-hysteresis', "value"),
            State('input-humidity-target', "value"),
            State('input-humidity-hysteresis', "value"),
        )
        def button_start(n_clicks, n_minutes, temperature_target, temperature_hysteresis, humidity_target, humidity_hysteresis):
            if n_clicks:
                try:
                    int_minutes = int(n_minutes)
                    if int_minutes < 0 or int_minutes > 200000:
                        return ""
                except:
                    return ""
                message = "start|time|" + str(n_minutes)
                self.fermentor.send_queue.put(message)
                return message
            return ""
            
        @self.app.callback(
            Output("none1", "children"),
            Input("button-stop", "n_clicks")
        )
        def button_stop(n_clicks):
            if n_clicks:
                message = "stop\n"
                self.fermentor.send_queue.put(message)
                return message
            return ""
            
        @self.app.callback(
            Output("none2", "children"),
            Input("button-pause", "n_clicks")
        )
        def button_pause(n_clicks):
            if n_clicks:
                message = "pause\n"
                self.fermentor.send_queue.put(message)
                return message
            return ""
            
        @self.app.callback(
            Output("none3", "children"),
            Input("button-resume", "n_clicks")
        )
        def button_resume(n_clicks):
            if n_clicks:
                message = "resume\n"
                self.fermentor.send_queue.put(message)
                print(message)
                return message
            return ""

graph_page = Graph_page(app)
layout = graph_page.layout
