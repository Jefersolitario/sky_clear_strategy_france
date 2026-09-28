import yaml
import pandas as pd
from utils.utility import plot_order_book
from utils.data import get_transactions, get_ts_hot_actuals
import plotly.express as px
import streamlit as st

def Order_book_backtest_run(start_dt, end_dt, signal, entry_price, Order_Book, frequency, strategy, params):

    Order_Book = Order_Book.sort_values(by= ['DeliveryStartUTC', 'Ts', 'type_order', 'Level'])
    Order_Book['Lead_time'] = Order_Book['DeliveryStartUTC'] - Order_Book[ 'Ts']
    Order_Book = Order_Book.loc[Order_Book['Lead_time'] <= pd.Timedelta(hours=params['lead_time'])]

    backtest_period = pd.date_range(start_dt, end_dt, freq= frequency)
    backtest_results = pd.DataFrame()
    orders = pd.DataFrame()

    # self.training_data = self.training_data.loc[self.training_data.index > self.historical_data] # Optional should be in params


    for i, period in enumerate(backtest_period):
        # train_embargo = period - pd.Timedelta(self.embargo) ## optional should be in params
        Xi = Order_Book[Order_Book['DeliveryStartUTC'] == period]
        
        if len(Xi) == 0:
            continue 
        backtest_results_i, orders_xi = clear_order_passive(Xi, entry_price, params)

        print(backtest_results_i)
        backtest_results = pd.concat([backtest_results, backtest_results_i])
        orders = pd.concat([orders, orders_xi])


    backtest_results._metadata = params
    backtest_results["run_Timestamp"] = pd.Timestamp.utcnow()
    cols = ['DeliveryStartUTC', 'Ts', 'Level', 'Price', 'Qty', 'type_order', 'volume_closed_evol']

    return backtest_results[cols], orders


def clear_order_passive_best_bid(Xi, entry_price, params):
    '''
    Simulating ICEBERG order EPEX
    Order Params:
        Price: Price of the Order
        Volume(Qty): Total volume to close
        delta v: increment volume of the Iceberg Order
        delta p: decrement price of hte Iceberg Order
        order type : -1 Sell Order, 1 Buy Order 

    '''
    
    Xi_offer = Xi.loc[(Xi['type_order'] == -1) & (Xi['Level'] == params['level'])] ## get 1 level on the orderbook
    Xi_bid = Xi.loc[Xi['type_order'] == 1] ## get 1 level on the orderbook

    Volume = params['Volume']
    d_v = params['delta_volume']
    t0 = params['lead_time']
    d_p = 1
    Pt0 = Xi_bid['Price'].iloc[0] # first bid initial 
    tt0 = Xi_bid['Ts'].iloc[0] # first bid initial time of update


    Open_vol = Volume
    orders_xi = pd.DataFrame(Xi_bid.iloc[0]).T
    orders_xi['Qty'] = d_v
    orders_xi['type_order'] = 1
    trades_xi = pd.DataFrame()

    while Open_vol !=0:
        
        Order_book_tn = Xi_offer.loc[(Xi_offer['Price'] <= Pt0)]## wrong need to do cumsum
        if len(Order_book_tn) == 0:
            print('No Orders closed placing a market order for stop loss')
            ## Place a market order to force close or go to imbal
            break

        Order_book_tn['cum_vol'] = Order_book_tn['Qty'].cumsum()

        if Order_book_tn['cum_vol'].iloc[-1] >= d_v:

            Order_book_tn = Order_book_tn.loc[(Order_book_tn['cum_vol'] >= d_v)] # find the first cumvol that clear the trade
        else:
            ## partial fill occours
            Order_book_tn = Order_book_tn

        clear_trade_final_time = Order_book_tn['Ts'].iloc[0]
        trades = Order_book_tn.loc[Order_book_tn['Ts'] <= clear_trade_final_time] ## CHANGE VOL TO CALCULATE EXACTLY THE D_V MW
        trades_xi = pd.concat([trades_xi, trades])
        
        
        Open_vol -= d_v
        Order_book_tn = Order_book_tn.loc[Order_book_tn['Ts'] > clear_trade_final_time]
        ## Place new Order automatically after the first delta of the iceberg order is cleared
        Pt0 -= d_p
        new_order = trades.iloc[-1]
        new_order['Qty'] = d_v
        new_order['type_order'] = 1
        orders_xi = orders_xi._append(new_order)
        ###
    trades_xi.loc[trades_xi['Qty'] > d_v, 'Qty'] = d_v
    trades_xi['volume_closed_evol'] = trades_xi['Qty'].cumsum()
        ## Add forced closure

    return trades_xi, orders_xi


def clear_order_passive(Xi, entry_price, params):
    '''
    Simulating ICEBERG order EPEX
    Order Params:
        Price: Price of the Order
        Volume(Qty): Total volume to close
        delta v: increment volume of the Iceberg Order
        delta p: decrement price of hte Iceberg Order
        order type : -1 Sell Order, 1 Buy Order 

    '''
    
    Xi_offer = Xi.loc[(Xi['type_order'] == -1) & (Xi['Level'] == params['level'])] ## get 1 level on the orderbook
    Xi_bid = Xi.loc[Xi['type_order'] == 1] ## get 1 level on the orderbook

    Volume = params['Volume']
    d_v = params['delta_volume']
    t0 = params['lead_time']
    d_p = params['delta_premium']
    Pt0 = entry_price.loc[entry_price.index == Xi.iloc[0]['DeliveryStartUTC']].values[0][0] -  d_p# spot + premium
    tt0 = Xi_bid['Ts'].iloc[0] # first bid initial time of update


    Open_vol = Volume
    orders_xi = pd.DataFrame(Xi_bid.iloc[0]).T
    orders_xi['Qty'] = d_v
    orders_xi['type_order'] = 1
    trades_xi = pd.DataFrame()

    while Open_vol !=0:
        
        Order_book_tn = Xi_offer.loc[(Xi_offer['Price'] <= Pt0)]## wrong need to do cumsum
        if len(Order_book_tn) == 0:
            print('No Orders closed placing a market order for stop loss')
            ## Place a market order to force close or go to imbal
            break

        Order_book_tn['cum_vol'] = Order_book_tn['Qty'].cumsum()

        if Order_book_tn['cum_vol'].iloc[-1] >= d_v:

            Order_book_tn = Order_book_tn.loc[(Order_book_tn['cum_vol'] >= d_v)] # find the first cumvol that clear the trade
        else:
            ## partial fill occours
            Order_book_tn = Order_book_tn

        clear_trade_final_time = Order_book_tn['Ts'].iloc[0]
        trades = Order_book_tn.loc[Order_book_tn['Ts'] <= clear_trade_final_time] ## CHANGE VOL TO CALCULATE EXACTLY THE D_V MW
        trades_xi = pd.concat([trades_xi, trades])
        
        
        Open_vol -= d_v
        Order_book_tn = Order_book_tn.loc[Order_book_tn['Ts'] > clear_trade_final_time]
        ## Place new Order automatically after the first delta of the iceberg order is cleared
        Pt0 -= d_p
        new_order = trades.iloc[-1]
        new_order['Qty'] = d_v
        new_order['type_order'] = 1
        orders_xi = orders_xi._append(new_order)
        ###
    trades_xi.loc[trades_xi['Qty'] > d_v, 'Qty'] = d_v
    trades_xi['volume_closed_evol'] = trades_xi['Qty'].cumsum()
        ## Add forced closure

    return trades_xi, orders_xi


def prepare_order_book(orderbook_path, start_utc, end_utc, TIME_ZONE):
    orderbook = pd.read_parquet(orderbook_path)
    orderbook = orderbook.rename({'DeliveryStartTs': 'DeliveryStartUTC'}, axis=1)
    orderbook['DeliveryStartUTC'] = orderbook['DeliveryStartUTC'].dt.tz_convert(TIME_ZONE)
    return orderbook

def get_public_trades(start_utc, end_utc, TIME_ZONE):
    public_trades = get_transactions(start_utc, end_utc, 'NL', ['XBID_Hour_Power'])
    public_trades['DeliveryStartUTC'] = public_trades['DeliveryStartUTC'].dt.tz_convert(TIME_ZONE)
    public_trades['ExecutionTimeUTC'] = public_trades['ExecutionTimeUTC'].dt.tz_convert(TIME_ZONE)
    return public_trades

def get_spot_prices(start_utc, config, id, TIME_ZONE):
    spot = get_ts_hot_actuals(start_utc, start_utc, config, id, 'spot')
    spot.index = spot.index.tz_convert(TIME_ZONE)
    return spot

def get_data(start_utc, end_utc, TIME_ZONE, config):
    
    orderbook = prepare_order_book('data/order_booksnap_skyclear.parquet', start_utc, end_utc, TIME_ZONE)
    public_trades = get_public_trades(start_utc, end_utc, TIME_ZONE)
    spot = get_spot_prices(start_utc, config, config['timeseries']['prices']['epex_nl_h_day_ahead_auction_price_hourly'], TIME_ZONE)

    return orderbook, public_trades, spot

def plot_results(backtest_results_select, orders_xi_select, orderbook_select, public_trades_select, spot_selection, params):
    fig_trades = px.scatter(backtest_results_select, x='Ts', y='Price', color_discrete_sequence=['white'])
    fig_trades.update_traces(line=dict(width=10))

    fig_orders = px.line(orders_xi_select, x='Ts', y='Price', color_discrete_sequence=['blue'])
    trace_orders = fig_orders.data[0]


    fig_trades_vol = px.area(backtest_results_select, x='Ts', y='volume_closed_evol', color_discrete_sequence=['Green'])

    fig, fig_vol = plot_order_book(orderbook_select, public_trades_select, spot_selection, params['lead_time'], params['level'])
    trace_orders = fig_orders.data[0]
    fig.add_trace(trace_orders)
    trace_trades = fig_trades.data[0]
    fig.add_trace(trace_trades)

    trace_trades_vol = fig_trades_vol.data[0]
    fig_vol.add_trace(trace_trades_vol)

    return fig, fig_vol


def main():

    st.set_page_config(layout='wide')
    st.title('Order Book Analysis')

    # Load configuration
    with open('config.yaml', 'r') as file:
        config = yaml.safe_load(file)
    
    TIME_ZONE = 'Europe/Amsterdam'
    strategy = 'passive_best_bid'
    strategy = st.selectbox('Select Product:', list(config['Closure_strategy'].keys()), index=0)
    params = config['Closure_strategy'][strategy]

    # User input for date range
    # start_utc = st.date_input("Start date", pd.to_datetime('2024-03-02')).tz_localize('Europe/Paris').tz_convert('UTC')
    # end_utc = st.date_input("End date", pd.to_datetime('2024-03-02')).tz_localize('Europe/Paris').tz_convert('UTC')
    start_utc = pd.to_datetime('2024-03-02 09:00').tz_localize('Europe/Paris').tz_convert('UTC')
    end_utc = pd.to_datetime('2024-03-02 17:00').tz_localize('Europe/Paris').tz_convert('UTC')


    orderbook, public_trades, spot = get_data(start_utc, end_utc, TIME_ZONE, config)
    # Select product and lead time
    products = orderbook['DeliveryStartUTC'].unique()
    products = pd.to_datetime(products).tz_convert(TIME_ZONE)
    product = st.selectbox('Select Product:', products, index=5)
    delivery = list(range(1, 36))
    params['lead_time'] = st.selectbox('Start Trading:', delivery, index=2)
    params['Volume'] = st.number_input('Volume :', params['Volume'])

    # Filter data based on user selection
    orderbook_select = orderbook.loc[orderbook['DeliveryStartUTC'] == product]
    orderbook_select['Lead_time'] = orderbook_select['DeliveryStartUTC'] - orderbook_select[ 'Ts']
    orderbook_select = orderbook_select.loc[orderbook_select['Lead_time'] <= pd.Timedelta(hours=params['lead_time'] )]
    orderbook_select['Ts'] = orderbook_select['Ts'].dt.tz_convert(TIME_ZONE)
    public_trades_select = public_trades.loc[public_trades['DeliveryStartUTC'] == product]
    public_trades_select['lead_time'] = public_trades_select['DeliveryStartUTC'] - public_trades_select['ExecutionTimeUTC']
    public_trades_select = public_trades_select.loc[public_trades_select['lead_time'] <= pd.Timedelta(hours=params['lead_time'] )]
    spot_selection = spot.loc[spot.index == product]
    spot_selection.index = spot_selection.index.tz_convert(TIME_ZONE)
    entry_price = spot

    backtest_results, orders_xi = Order_book_backtest_run(start_utc, end_utc, 'sky_clear_days', entry_price, orderbook_select, '60min', strategy, params)
    backtest_results['Ts'] = backtest_results['Ts'].dt.tz_convert(TIME_ZONE)
    orders_xi['Ts'] = pd.to_datetime(orders_xi['Ts']).dt.tz_convert(TIME_ZONE)

    # Plot results
    fig, fig_vol = plot_results(backtest_results, orders_xi, orderbook_select, public_trades_select, spot_selection, params)
    st.plotly_chart(fig, use_container_width=True)
    st.plotly_chart(fig_vol, use_container_width=True)


main()
