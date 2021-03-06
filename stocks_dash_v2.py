import numpy as np
from yahoo_fin import stock_info as si
from plotly.subplots import make_subplots
import stock_options
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.express as px
import pandas as pd
import dash_table
import plotly.graph_objs as go

from dash.dependencies import Input, Output, State

import datetime

import json
from yahoo_fin import options

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

class stock_custom():
    def __init__(self):
        self.ticker = ''
        self.current_price = 0
        self.stats = [{'Attribute':'', 'Value':0}]
        self.historical =0
        self.risk_free_rate = 0
        self.prices_today = []
        self.todays_times = []
        self.option_dates = []
        self.observed_options = {}
        
    def update(self,new_ticker, rate):
        old_ticker = self.ticker
        self.risk_free_rate = rate/100
        self.ticker = new_ticker.upper()
        if (self.ticker!='') & (new_ticker!=old_ticker):
#            self.current_price = si.get_live_price(self.ticker)
            self.todays_times = [datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")[11:]]
            self.prices_today = [si.get_live_price(self.ticker)]
            self.historical = si.get_data(self.ticker)
            self.option_dates = options.get_expiration_dates(new_ticker)
            self.observed_options = {}
            try:
                self.stats = si.get_stats(self.ticker).to_dict('records')
            except ValueError:
                self.stats = [{'Attribute':'none available', 'Value':'none available'}]
            
    def update_price(self):
        if self.ticker!='':
            self.todays_times.append(datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")[11:])
            self.prices_today.append(si.get_live_price(self.ticker))
    
    def update_options_list(self, option_type, strike, date):
        empty = {'Last Trade Date': '', 
                 'Strike':'',
                 'Last Price': '',
                 'Bid': '',
                 'Ask':'',
                 'Change':'',
                 '% Change':'',
                 'Volume':'',
                 'Open Interest':'',
                 'Implied Volatility': ''}  
        contract_name = stock_options.option_naming(self.ticker, strike, date, option_type)
        orig_date = date
        if contract_name not in self.observed_options:
            #breakdown date string        
            month_int = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November','December']
            month_today = month_int.index(date[0:date.index(' ')])+1
            date = date[date.index(' ')+1:]
            day_today = int(date[0:date.index(',')])
            year_today = int(date[-4:])
            strike_date_datetime = datetime.date(year_today, month_today, day_today)
            tod = datetime.date(year = datetime.datetime.today().year, month = datetime.datetime.today().month, day = datetime.datetime.today().day)
            years_to_maturity = (strike_date_datetime-tod).days/365
            
            #get implied volatility
            if option_type.lower()=='call':
                df = options.get_calls(self.ticker, orig_date)
            else:
                df = options.get_puts(self.ticker, orig_date)
            iv = float(df.loc[df['Strike']==strike]['Implied Volatility'].to_list()[0][0:-1])/100
    
            #calculate greeks        
            grks = stock_options.option_greeks(self.prices_today[-1], 
                                              strike, years_to_maturity, 
                                              iv,
                                              self.risk_free_rate)[option_type.lower()]
            
            #calculate prices
            price = round(stock_options.option_price(self.prices_today[-1], 
                                              strike, years_to_maturity, 
                                              iv,
                                              self.risk_free_rate)[option_type.lower()],2)
            
            opt = {'Expir Date': orig_date,
                   'Strike Price': '${}'.format(strike)}
            
            opt['Value'] = '${}'.format(price)
            opt['Type'] = option_type
            opt.update(grks)
            self.observed_options[contract_name] = opt
        return self.observed_options
        
    
    def add_observed_option(self, option_type, strike, date, greeks):
        new_opt = {'type': option_type,
                    'strike':strike,
                    'date': date, 
                    'greeks': greeks}
        if new_opt not in self.observed_options:
            self.observed_options.append(new_opt)
            
    def remove_observed_option(self, option_type, strike, date, greeks):
        new_opt = {'type': option_type,
                    'strike':strike,
                    'date': date, 
                    'greeks': greeks}
        if new_opt in self.observed_options:
            self.observed_options.remove(new_opt)
                    
    
    
"""
option_price(stock_price, strike_price, years_to_maturity,  IV, rate)
option_breakdown(string)
option_greeks(stock_price, strike_price, years_to_maturity, volatility, rate)
bulk_calc(all_dates,all_strikes, current_price, rate, IV_list)
    

intrinsic value: max(0, (current_price - strike_price)*(-1)**(option_type == 'put'))
time value: option_price - intrinsic value
"""
     
examined_stock = stock_custom()

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)


app.layout = html.Div(children = [
    html.H3("Ticker Name and Risk Free Interest Rate"),
    
    html.Div(children = [
        dcc.Input(id = 'ticker-input', value = '', type = 'text'),
        dcc.Input(id = 'rate-input', value = .69, type = 'number'),
        html.Button(id = 'update-ticker-info', n_clicks = 0, children = 'Start Tracking Live Price'),
        html.Button(id = 'fill-ticker-table-info', n_clicks = 0, children = 'Fill Table'),
        ],
        className = 'row'),
    
    html.Div(id='ticker-output', className = 'row'),
    
    html.Div(children = [
        html.Div(children = [
            dash_table.DataTable(id = 'stockoverview-table', 
                             columns = [{'name': 'Attribute', 'id': 'Attribute'}, {'name': 'Value', 'id': 'Value'}], 
                             data = [{'Attribute':'', 'Value':0}],
                             page_action='none',
#                             style_table={'height': '300px', 'width': '500px','overflowY': 'auto'},
                             fixed_rows={'headers': True}) ], 
            className = 'six columns'),
        html.Div(children = [
            dcc.Graph(id='live-price-graph',
#                  style = {'width': 800}
                  )], 
            className = 'six columns')
        
        ], className = 'row'),#style = {'display': 'inline-block'}, 
    
    dcc.Interval(
            id='interval-component',
            interval=1*1000, # in milliseconds
            n_intervals=0
        ),
    html.Div(children = [
        dcc.Input(id = 'prev-date-select', value = datetime.datetime.today().strftime("%d/%m/%Y %H:%M:%S")[0:10], type = 'text'),
        html.Button(id = 'display-candle', n_clicks = 0, children = 'Update'),
        ], className = 'row'),
    
    html.Br(),
    
    html.Div(children = [
        dcc.Graph(id = 'historical-candlestick-graph')],className = 'row' 
        ),
    
    html.H4('Options Details'),
    
    html.Div(children = [
        html.Div(children = [dcc.Dropdown(id = 'contract-dates', 
                                          options = [{'label':'','value':''}], 
#                                          value = '',
                                          placeholder = 'Select Strike Date'),], className = 'two columns'), #'height': '400px', 
        html.Div(children = [html.Button(id = 'show-options-info', n_clicks = 0, children = 'Display Options Info')], className = 'two columns'),
        ],
        className = 'row'),
    
    html.Div(children = [
        html.Div(children = [
            html.H5('Call Options'),
            dash_table.DataTable(id = 'options-calls-table',
                            columns = [{'name':'Contract Name', 'id':'Contract Name'}, 
                                       {'name':'Last Trade Date', 'id':'Last Trade Date'}, 
                                       {'name':'Strike', 'id':'Strike'}, 
                                       {'name':'Last Price', 'id':'Last Price'},
                                       {'name':'Bid','id':'Bid'},
                                       {'name':'Ask','id':'Ask'}, 
                                       {'name':'Change','id':'Change'}, 
                                       {'name':'% Change','id':'% Change'}, 
                                       {'name':'Volume','id':'Volume'}, 
                                       {'name':'Open Interest','id':'Open Interest'},
                                       {'name':'Implied Volatility','id':'Implied Volatility'}],
                            data = [{'Contract Name':'', 
                                     'Last Trade Date': '', 
                                     'Strike':'',
                                     'Last Price': '',
                                     'Bid': '',
                                     'Ask':'',
                                     'Change':'',
                                     '% Change':'',
                                     'Volume':'',
                                     'Open Interest':'',
                                     'Implied Volatility': ''}],
                            style_table={'overflowY': 'auto'},#'height': '400px', 
                            fixed_rows={'headers': True}),
            ], className = 'six columns'),
        html.Div(children = [
            html.H5('Put Options'),
            dash_table.DataTable(id = 'options-puts-table',
                            columns = [{'name':'Contract Name', 'id':'Contract Name'}, 
                                       {'name':'Last Trade Date', 'id':'Last Trade Date'}, 
                                       {'name':'Strike', 'id':'Strike'}, 
                                       {'name':'Last Price', 'id':'Last Price'},
                                       {'name':'Bid','id':'Bid'},
                                       {'name':'Ask','id':'Ask'}, 
                                       {'name':'Change','id':'Change'}, 
                                       {'name':'% Change','id':'% Change'}, 
                                       {'name':'Volume','id':'Volume'}, 
                                       {'name':'Open Interest','id':'Open Interest'},
                                       {'name':'Implied Volatility','id':'Implied Volatility'}],
                            data = [{'Contract Name':'', 
                                     'Last Trade Date': '', 
                                     'Strike':'',
                                     'Last Price': '',
                                     'Bid': '',
                                     'Ask':'',
                                     'Change':'',
                                     '% Change':'',
                                     'Volume':'',
                                     'Open Interest':'',
                                     'Implied Volatility': ''}],
                            style_table={'overflowY': 'auto'},#'height': '400px', 
                            fixed_rows={'headers': True}),
            ], className = 'six columns'),
        ], className = 'row'),
    
    html.Br(),
    
    html.Div(children = [
        html.H3("Options Greeks"),
        html.Div(children = [
            html.Div(children = [dcc.Dropdown(id = 'analysis1-contract-type-selection', style = {'width': 250}, options = [{'label':'Call','value':'Call'}, {'label':'Put','value':'Put'}], placeholder = 'Select Option Type' ),],
                     className = 'two columns'),
            html.Div(children = [dcc.Dropdown(id = 'analysis1-contract-date-selection', style = {'width': 250}, options = [{'label':'','value':''},], placeholder = 'Select Strike Date' ),],
                     className = 'two columns'),
            html.Div(children = [html.Button(id = 'analysis1-fill-options-prices-button', n_clicks = 0, children = 'Fill Strike Prices')], 
                     className = 'two columns'),
            html.Div(children = [dcc.Dropdown(id = 'analysis1-contract-strike-selection', style = {'width': 250}, options = [{'label':'','value':''}], placeholder = 'Select Strike Price', ),],
                     className = 'two columns'),
            html.Div(children = [html.Button(id = 'analysis1-display-options-greeks-button', n_clicks = 0, children = 'Calc Options Info')], 
                     className = 'two columns'),
            ],className = 'row', ),
        
        ],
        ),
    
    html.Br(),
    
    html.Div(children = [
        html.Div(children = [dash_table.DataTable(id = 'options-greeks-table',
                            columns = [{'name': 'Contract Name', 'id': 'Contract Name'},
                                       {'name': 'Expir Date', 'id': 'Expir Date'},
                                       {'name': 'Strike Price', 'id': 'Strike Price'},
                                       {'name':'Value', 'id': 'Value'},
                                       {'name':'Type', 'id': 'Type'},
                                       {'name':'delta', 'id':'delta'}, 
                                       {'name':'gamma', 'id':'gamma'}, 
                                       {'name':'theta', 'id':'theta'}, 
                                       {'name':'vega', 'id':'vega'},
                                       {'name':'rho', 'id':'rho'}],
                            data = [{'Contract Name': '',
                                     'Expir Date': '',
                                     'Strike Price': '',
                                     'Value': '',
                                     'Type': '',
                                     'delta':'', 
                                     'gamma': '', 
                                     'theta':'',
                                     'vega':'',
                                     'rho': '',}],
                            fixed_rows={'headers': True}),], className = 'six columns'),
        ],
        className = 'row'),
    html.Br(),
    #up to 3 lines, one for overall profit, others are profits from up to two contracts
    html.Div(children = [
        html.Div(children = [dcc.Dropdown(id = 'options-to-display-dropdown',placeholder = 'Select Options To Plot', 
                     multi = True, clearable = True)], className = 'three columns'),
        html.Button(id = 'plot-options-possibilities-button', n_clicks = 0, children = 'Plot Projections'),
        dcc.Graph(id = 'options-plot-overlay' )
        ],
        className = 'row')


])


#
#-----------------------------------------------------------------------------------
#
#function: display option profitability graph
#
#initiation: press 'plot options possiblities' button option(s) selected
#
#-----------------------------------------------------------------------------------
@app.callback(Output(component_id = 'options-plot-overlay', component_property = 'figure'),
              Input(component_id = 'plot-options-possibilities-button', component_property = 'n_clicks'),
              State(component_id = 'options-to-display-dropdown', component_property = 'value'))

def display_options_profitabilities_plot(clicks, values):
    fig = make_subplots(rows=1, cols=2, x_title = 'Stock Price($)',y_title = 'Profit($)',
                    subplot_titles = ['Contract(s) Profit/Loss($)', 'Overall Profit/Loss($)'])
    if (values is None) | (values==[]):
        fig.add_scatter(x = [-.05,1], y = [0, 0], mode = 'lines', marker = dict(color = 'Grey'),
                        row = 1, col = 1, showlegend=False)
        fig.add_scatter(x = [0,0], y = [-.05, 1], mode = 'lines', marker = dict(color = 'Grey'), 
                        row = 1, col = 1, showlegend=False)
        fig.add_scatter(x = [-.05,1], y = [0, 0], mode = 'lines', marker = dict(color = 'Grey'), 
                        row = 1, col = 2, showlegend=False)
        fig.add_scatter(x = [0,0], y = [-.05, 1], mode = 'lines', marker = dict(color = 'Grey'), 
                        row = 1, col = 2, showlegend=False)
        return fig
    else:
        #plot individual options
        total_option_cost = 0
        
        xlist = []
        ylist = []
        typelist = []
        pricelist = []
        strikepricelist = []
        for v in values:
            dat = examined_stock.observed_options[v]
            
            option_price = float(dat['Value'][1:])
            pricelist.append(option_price)
            total_option_cost+=option_price
            option_type = dat['Type']
            typelist.append(option_type)
            
            option_strike_price = float(dat['Strike Price'][1:])
            strikepricelist.append(option_strike_price)
            
            xval = [0, max(0,option_strike_price - option_price), option_strike_price, 
                    option_strike_price + option_price, option_strike_price * 1.5]
            xlist.append(xval)
        xvals_for_profits = np.sort(np.unique(np.array(xlist).flatten()))
        for p,s,t in zip(pricelist, strikepricelist,typelist):
            if t.lower()=='call':
                ylist.append([max(-p, x - s - p) for x in xvals_for_profits])
            else:
                ylist.append([max(-p, s - x - p) for x in xvals_for_profits])
                
        for ind in range(len(xlist)):
            fig.add_scatter(x =xvals_for_profits ,y=ylist[ind], mode="lines + markers",
                            marker=dict(size=5, color="LightSeaGreen"),name = values[ind],row=1, col=1)
            
        #calculate min/maxes to for axis and to extend any necessary arrays
        minX = np.min(np.array(xlist).flatten())
        maxX = np.max(np.array(xlist).flatten())

        #calculate profits
        profits = sum([np.array(i) for i in ylist])
        
        minY = np.min(np.array(profits).flatten())
        maxY = np.max(np.array(profits).flatten())
        
        #plot profit
        fig.add_scatter(x = xvals_for_profits, y = profits, mode="lines + markers",
                        marker=dict(size=5, color="MediumPurple"),name="P/L", row=1, col=2)
 
        #plot axis
        fig.add_scatter(x = [minX-.1,maxX+.1], y = [0, 0], mode = 'lines', marker = dict(color = 'Black'),
                        row = 1, col = 1, showlegend=False)
        fig.add_scatter(x = [minX-.1,minX-.1], y = [minY-.1, maxY+.1], mode = 'lines', marker = dict(color = 'Black'), 
                        row = 1, col = 1, showlegend=False)
        fig.add_scatter(x = [minX-.1,maxX+.1], y = [0, 0], mode = 'lines', marker = dict(color = 'Black'), 
                        row = 1, col = 2, showlegend=False)
        fig.add_scatter(x = [minX-.1,minX-.1], y = [minY-.1, maxY+.1], mode = 'lines', marker = dict(color = 'Black'), 
                        row = 1, col = 2, showlegend=False)
        
        return fig
    

#
#-----------------------------------------------------------------------------------
#
#function: display option greeks in table and option price
#
#initiation: press 'show options greeks' button AFTER price and option type selected
#
#-----------------------------------------------------------------------------------

@app.callback(
    [Output(component_id = 'options-to-display-dropdown', component_property = 'options'),
    Output(component_id = 'options-greeks-table', component_property = 'data')],
    Input(component_id = 'analysis1-display-options-greeks-button', component_property = 'n_clicks'),
    [State(component_id = 'analysis1-contract-strike-selection', component_property = 'value'),
     State(component_id = 'analysis1-contract-type-selection', component_property = 'value'), 
     State(component_id = 'analysis1-contract-date-selection', component_property = 'value')])

def display_option_greeks_table(clicks, strike,  option_type,date):
    orig_date = date
    try:
        date_len = len(date)
    except TypeError:
        date_len = 0
    if date is None:
        return [{'label': '', 'value': ''}],[{'Contract Name': '','Expir Date': '','Strike Price': '','Value': '',
                 'Type': '', 'delta':'','gamma': '', 'theta':'',
                 'vega':'','rho': '',}]
    else:
        dat = examined_stock.update_options_list(option_type, strike, date)
        names = [i for i in dat]
        info = [dat[i] for i in dat]
        
        opt = []
        for i in range(len(names)):
            tmp = {'Contract Name': names[i]}
            tmp.update(info[i])
            opt.append(tmp)

        return [{'label': i, 'value': i} for i in names],opt

#-----------------------------------------------------------------------------------
#
#function: fill options dropdown with list of strike prices for available options
#
#initiation: press 'fill strike prices' button AFTER price and option type selected
#
#-----------------------------------------------------------------------------------

@app.callback(
    Output(component_id = 'analysis1-contract-strike-selection', component_property = 'options'),
    Input(component_id = 'analysis1-fill-options-prices-button', component_property = 'n_clicks'),
    [State(component_id = 'analysis1-contract-date-selection', component_property = 'value'),
     State(component_id = 'analysis1-contract-type-selection', component_property = 'value')])

def update_options_strike_dropdown(clicks, date, option_type):
    if examined_stock.ticker!='':
        strike_prices = options.get_options_chain(examined_stock.ticker,date)[option_type.lower()+'s'].Strike.to_numpy()
    
        return [{'label':float(i), 'value':float(i)} for i in strike_prices]
    else:
        return [{'label':'', 'value':''}]


#-----------------------------------------------------------------------------------
#
#function: fill call and put tables 
#
#initiation: press 'show options info' button AFTER expiration date has been selected
#
#-----------------------------------------------------------------------------------

@app.callback(
    [Output(component_id = 'options-calls-table', component_property = 'data'),
     Output(component_id = 'options-puts-table', component_property = 'data')],
    Input(component_id = 'show-options-info', component_property = 'n_clicks'),
    State(component_id = 'contract-dates', component_property = 'value'))
def display_calls_table(clicks, date):
    if date is None:
        return[{'Contract Name':'', 'Last Trade Date': '', 'Strike':'',
                'Last Price': '','Bid': '','Ask':'','Change':'',
                '% Change':'','Volume':'','Open Interest':'',
                'Implied Volatility': ''}], [{'Contract Name':'', 
                                     'Last Trade Date': '', 
                                     'Strike':'',
                                     'Last Price': '',
                                     'Bid': '',
                                     'Ask':'',
                                     'Change':'',
                                     '% Change':'',
                                     'Volume':'',
                                     'Open Interest':'',
                                     'Implied Volatility': ''}]
    else:        
        return options.get_options_chain(examined_stock.ticker,date)['calls'].to_dict('records'), options.get_options_chain(examined_stock.ticker,date)['puts'].to_dict('records')


#-----------------------------------------------------------------------------------
#
#function: display candlestick historical graph, will show at most 10 years prior
#
#initiation: press 'display candlestick' button AFTER ticker ahs been selected
#   use 'previous date' selection to limit further limit display
#-----------------------------------------------------------------------------------

@app.callback(
    Output(component_id = 'historical-candlestick-graph', component_property = 'figure'),
    [Input(component_id = 'display-candle', component_property = 'n_clicks')],
    [State(component_id = 'prev-date-select', component_property = 'value')])

def update_candlestick(click, date):
    df = examined_stock.historical
    yrsbefore = datetime.datetime.today() - datetime.timedelta(days = 365*10)
    
    if len(np.shape(df))>0:
        dates = [i for i in df.to_dict()['open']]
        earliest = dates[0].to_pydatetime()
        latest = max(yrsbefore, earliest)
        if latest ==earliest:
            fig = go.Figure(data=[go.Candlestick(x= dates, 
                                                 open = df['open'],
                                                 high = df['high'],
                                                 low = df['low'],
                                                 close = df['close'])], 
                            layout= {'title': 'Historical Candlestick'})
        else:
            latest = datetime.datetime(year = latest.year, month = latest.month, day = latest.day)
            while latest not in dates:
                latest = latest + datetime.timedelta(days = 1)
            ind = dates.index(latest)
            fig = go.Figure(data=[go.Candlestick(x= dates[ind:], 
                                             open = df['open'][ind:],
                                             high = df['high'][ind:],
                                             low = df['low'][ind:],
                                             close = df['close'][ind:])], 
                        layout= {'title': 'Historical Candlestick'})
    else:
        fig = go.Figure(data=[go.Candlestick(x= [0], 
                                             open =[0],
                                             high = [0],
                                             low = [0],
                                             close = [0])], 
                        layout= {'title': 'Input ticker then click update'})
    return fig

#-----------------------------------------------------------------------------------
#
#function: begin tracking live price; tracks every 1 second, displays at most 600 seconds
#
#initiation: n/a
#
#-----------------------------------------------------------------------------------

@app.callback(
    Output(component_id = 'live-price-graph', component_property = 'figure'),
    [Input(component_id = 'interval-component', component_property = 'n_intervals')])

def update_live_price(interval):
    #updated every 1 second;
    #do we only want to look at previous... 60*10= 600 seconds?
    examined_stock.update_price()
    p = examined_stock.prices_today
    t = examined_stock.todays_times
    if len(p)>600:
        p = p[-600:]
        t = t[-600:]
    fig = go.Figure(data=[go.Scatter(x= t, y=p)], 
                    layout= {'title': 'Today\'s Price'}
            )

    return fig
            
#-----------------------------------------------------------------------------------
#
#function: display ticker selected; will internally update stock tracked to be the ticker 
#
#initiation: press 'update ticker info' button
#
#-----------------------------------------------------------------------------------

@app.callback(
    [Output(component_id = 'contract-dates', component_property = 'options'),
     Output(component_id = 'analysis1-contract-date-selection', component_property = 'options'),
    Output(component_id='ticker-output', component_property='children')] ,
    [Input(component_id ='update-ticker-info', component_property = 'n_clicks'),],
    [State(component_id='ticker-input', component_property='value'),
     State(component_id='rate-input', component_property='value'),]
)
def update_output_div(n_clicks, i1, i2):
    if i1!='':
        output = i1.upper()+' with interest rate {}%'.format(i2)
    else:
        output = 'Select Ticker'
    examined_stock.update(i1, i2)
    dates = [{'label': i, 'value': i} for i in examined_stock.option_dates]
    return dates,dates,output


#-----------------------------------------------------------------------------------
#
#function: fill stock info tables 
#
#initiation: press 'show ticker info' button AFTER selecting stock ticker and updating internal system
#
#-----------------------------------------------------------------------------------

@app.callback( Output(component_id = 'stockoverview-table', component_property = 'data'),
              Input(component_id = 'fill-ticker-table-info', component_property = 'n_clicks'),
              State(component_id = 'ticker-input', component_property = 'value'))
def update_general_info_table(tick, col):
    return examined_stock.stats
                

if __name__ == '__main__':
    app.run_server(debug=True)
    