import yaml
import numpy as np
import pandas as pd
from utils.data import get_ts_hot_actuals, get_ts_hot_forecast, get_ts_cold_snap, get_ts_cold, get_forecast_snap
from utils.data import get_vwap
from utils.data import get_ts_db_sql, get_ts_db_sql_time_of_day
import plotly.express as px
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)

start_utc = pd.to_datetime(config['start']).tz_localize('Europe/Paris').tz_convert('UTC')
end_utc = pd.to_datetime(config['end']).tz_localize('Europe/Paris').tz_convert('UTC')

country_timezones = {
    "NL": "Europe/Amsterdam",  # Netherlands
    "DE": "Europe/Berlin",  # Netherlands
    "AT": "Europe/Berlin",  # Netherlands
    "BE": "Europe/Berlin",  # Netherlands
    "FR": "Europe/Paris",      # France
    "GB": "Europe/London",     # United Kingdom
}

st.set_page_config(layout='wide')
country = st.selectbox('Select Country:', ['NL', 'FR', 'BE', 'DE', 'GB', 'IE', 'AT'], index= 1)


start_date, end_date = st.date_input('Select a date range', value=[start_utc, end_utc])
start_date = pd.to_datetime(start_date)
end_date = pd.to_datetime(end_date)  +  pd.Timedelta(days=1)
start_utc = start_date.tz_localize('Europe/Paris').tz_convert('UTC')
end_utc = end_date.tz_localize('Europe/Paris').tz_convert('UTC')


# Place each widget in a column
forecast, threshold = st.columns(2)

with forecast:
    forecast_selection = st.selectbox('Select Forecast reference', config['solar_forecast'], index=5, key="forecast_reference_select") #16

with threshold:
    Threshold = st.number_input('Percentage of max production', value = 85)

price_list = ['epex_gb_day_ahead_auction_price_hourly', 'nordpool_gb_da_auction_prices', 'epex_gb_hh_day_ahead_auction_price_30_min', 'epex_gb_ida1_intraday_auction_price_30_min', 'epex_gb_ida2_intraday_auction_price_30_min',
            'XBID_Hour_Power', 'epex_fr_h_day_ahead_auction_price_hourly', 'Intraday_Hour_Power', 'gb_2H_Block_vwap_last_hour', 'gb_4H_Block_vwap_last_hour', 'rte_fr_imbalance_price_positive_settlement_30_min',
            'epex_at_h_day_ahead_auction_price_hourly', 'at_imbalance', 'gb_hh_intraday_last_hour', 'gb_imbalance']

entry_price_selction, exit_price_selection = st.columns(2)
with entry_price_selction:
    entry_price = st.selectbox('Select entry price', price_list, index=6)
with exit_price_selection:
    exit_price = st.selectbox('Select exit price', price_list, index=10)


selected_strategy = st.selectbox("Select Closure Strategy", options=list(config['Closure_strategy'].keys()))


st.write(f"Options for {selected_strategy} strategy:")
# Create a column layout to display the options side by side
cols = st.columns(4)
options = config['Closure_strategy'][selected_strategy]

# Dynamically create the input fields based on the selected strategy
for i, (option, value) in enumerate(options.items()):
    with cols[i % 4]:  # Adjust the number of columns if necessary
        # Create a number_input for each option
        # Using `key` to ensure each input is uniquely identified
        globals()[option] = st.number_input(f"{option}", value=value, key=option)


    
@st.cache_data
def get_forecast(start_utc, end_utc, forecast_selection, config):

    id_forecast = config['solar_forecast'][forecast_selection]

    if forecast_selection == 'fr_solar_actuals_rte':

        forecast = get_ts_hot_actuals(start_utc, end_utc, config, config['solar_forecast'][forecast_selection], id_forecast)
    elif forecast_selection[-3:] == 'rte':

        forecast = get_ts_hot_forecast(start_utc, end_utc, config, config['solar_forecast'][forecast_selection], id_forecast)
    elif forecast_selection == 'nl_solar_cloud_cover_actuals':
        file_name = config['solar_forecast'][forecast_selection]
        nl_actual = pd.read_parquet(file_name)
        col = ['validdate', 'total_cloud_cover:p']
        nl_actual= nl_actual[col]
        nl_actual.set_index('validdate', inplace= True)
        forecast = nl_actual.groupby('validdate')['total_cloud_cover:p'].mean()
        forecast = forecast.reset_index()
        forecast.set_index('validdate', inplace= True)
        id_forecast = 'total_cloud_cover:p'
    elif 'meteologica_france_pv_powergeneration_forecast' in forecast_selection:
        id_str = config['solar_forecast'][forecast_selection]
        resolution = 60
        forecast = get_ts_db_sql_time_of_day(start_utc, end_utc, id_str, 9, 1, resolution)
        forecast = forecast.rename({'value': id_forecast}, axis= 1)
    else:
        forecast = get_forecast_snap(start_utc,end_utc, id_forecast)
        
    forecast = forecast[id_forecast]

    if forecast_selection == "nl_solar_actuals":
        "Netander solar acutals are in kilowats need to convert to MWh"
        forecast = forecast/1000
        forecast = forecast.round(0)



    return forecast

@st.cache_data
def get_price_data(start_utc,  end_utc, config, country, price_name):

        ## get intraday transactions of clear skies days

    ## intraday vwaps
    if price_name == 'rte_fr_imbalance_price_positive_settlement_30_min':
        id_exit = config['timeseries']['prices'][price_name]
        price_data = get_ts_hot_actuals(start_utc, end_utc, config, id_exit, price_name)
        price_data = price_data.resample('1h').mean()
    elif price_name == 'at_imbalance':
        id_exit = config['timeseries']['prices'][price_name]
        price_data = get_ts_hot_actuals(start_utc, end_utc, config, id_exit, price_name)
        price_data = price_data.resample('1h').mean()
    elif price_name in ['epex_fr_h_day_ahead_auction_price_hourly', 'epex_gb_day_ahead_auction_price_hourly', 'nordpool_gb_da_auction_prices', 'epex_gb_hh_day_ahead_auction_price_30_min', 'epex_gb_ida1_intraday_auction_price_30_min', 'epex_gb_ida2_intraday_auction_price_30_min', 'epex_at_h_day_ahead_auction_price_hourly']:

        id= config['timeseries']['prices'][price_name]
        price_data = get_ts_hot_actuals(start_utc, end_utc, config, id, price_name)
        price_data = price_data.resample('1h').mean()
    elif price_name == "gb_2H_Block_vwap_last_hour":
        product = "2H Block vwap"
        duration = 60
        time_before_delivery = 60

        date_start = start_utc - pd.Timedelta(hours= 4)
        date_end = end_utc + pd.Timedelta(hours=4)
        price_data = get_vwap('GB', product, date_start, date_end, time_before_delivery, duration)
        price_data = price_data.rename(columns={"VWAP": price_name})
        price_data = price_data.resample('1h').ffill()
        price_data = price_data.rename(columns={"vwap": price_name})
        price_data = price_data[price_name]
    elif price_name == "gb_4H_Block_vwap_last_hour":
        product = "4H Block vwap"
        duration = 60
        time_before_delivery = 60

        date_start = start_utc - pd.Timedelta(hours= 4)
        date_end = end_utc + pd.Timedelta(hours=4)
        price_data = get_vwap('GB', product, date_start, date_end, time_before_delivery, duration)
        price_data = price_data.rename(columns={"VWAP": price_name})
        price_data = price_data.resample('1h').ffill()
        price_data = price_data.rename(columns={"vwap": price_name})
        price_data = price_data[price_name]
    elif price_name == "gb_hh_intraday_last_hour":
        product = "HH vwap"
        duration = 60
        country = price_name[:2].upper()
        lead_time = None
        date_start = start_utc - pd.Timedelta(hours= 2)
        price_data = get_vwap(country, product, date_start,  end_utc, lead_time, duration)
        price_data = price_data.sort_values(by = ['DeliveryEndUTC', 'TradeStartUTC'])
        price_data = price_data.drop_duplicates(subset = 'DeliveryEndUTC', keep = 'last')

        price_data = price_data.rename(columns={"VWAP": price_name})
        price_data = price_data[price_name]
        price_data = price_data.resample('1h').mean()
    elif price_name == 'gb_imbalance':
        id_exit = config['timeseries']['prices'][price_name]
        price_data = get_ts_hot_actuals(start_utc, end_utc, config, id_exit, price_name)
        price_data = price_data.resample('1h').mean()

    elif price_name == "XBID_Hour_Power":
        product = "XBID_Hour_Power"
        duration = config['intraday_trades']['vwap_duration']
        vwap_delivery_2h = config['intraday_trades']['vwap_h_delivery'][1] - 60 
        price_data = get_vwap(country, product, start_utc, end_utc, vwap_delivery_2h, duration)
        price_data = price_data.rename(columns={"VWAP": price_name, 'vwap volume': price_name + ' market volume'})
        price_data = price_data[[price_name, price_name + ' market volume']]
    elif price_name == "Intraday_Hour_Power":
        product = "Intraday_Hour_Power"
        duration = 60
        lead_time = 0
        price_data = get_vwap(country, product, start_utc, end_utc, lead_time, duration)
        price_data = price_data.rename(columns={"VWAP": price_name, 'vwap volume': price_name + ' market volume'})
        price_data = price_data[[price_name, price_name + ' market volume']]
    elif price_name == '2H Block vwap':
        product = "2H Block vwap"
        duration = 60
        time_before_delivery = 60
        date_start = start_utc - pd.Timedelta(hours= 4)
        date_end = end_utc + pd.Timedelta(hours=4)
        price_data = get_vwap(country, product, date_start, date_end, time_before_delivery, duration)
        price_data = price_data.resample('1h').ffill()
        price_data = price_data.rename(columns={"VWAP":price_name})
        price_data = price_data[price_name]       

    
    return price_data

@st.cache_data
def get_data(start_utc, end_utc, country, forecast_selection, entry_price, exit_price, config):

    start_time_utc_history = start_utc - pd.Timedelta(days= 365) ## get previous year solar dah
    data = pd.DataFrame(index = pd.date_range(start_time_utc_history, end_utc, freq= 'h'))

    forecast = get_forecast(start_time_utc_history, end_utc, forecast_selection, config)
    forecast = forecast.rename(forecast_selection)
    ## solar forecast
    cwe_solar = True
    if cwe_solar == True:
        forecast_i = pd.DataFrame(index = pd.date_range(start_time_utc_history, end_utc, freq= 'h'))
        cwe_solar_list = ['de_solar_dah_em', 'nl_solar_dah_em', 'fr_solar_dah_meteo', 'be_solar_dah_meteo', 'gb_solar_dah_meteo', 'at_solar_dah_em']
        
        if forecast_selection in cwe_solar_list:
            cwe_solar_list.remove(forecast_selection)
        
        for forecast_cwe_selection in cwe_solar_list:
            cwe_solar = get_forecast(start_time_utc_history, end_utc, forecast_cwe_selection, config)
            forecast_i = forecast_i.join(cwe_solar)
        forecast_cwe = forecast_i.sum(axis=1)
        forecast_cwe = forecast_cwe.rename('cwe_solar_dah')
        forecast = pd.DataFrame(forecast_cwe).join(forecast)


    if country != "DE":
        solar_a = get_ts_hot_actuals(start_time_utc_history, end_utc, config, config['timeseries'][country.lower() +'_solar_actuals'], 'solar_actuals')
    elif country == "DE":
        ## DE has four tso agregate the data for solar
        ids_de = config['timeseries'][country.lower() +'_solar_actuals']
        solar_de = pd.DataFrame(index = pd.date_range(start_time_utc_history, end_utc, freq= 'h'))
        for key, value in ids_de.items():
            solar_de_tsos = get_ts_hot_actuals(start_time_utc_history, end_utc, config, value, key)
            solar_de = solar_de.join(solar_de_tsos)
        solar_de['solar_actuals'] = solar_de.sum(axis= 1)
        solar_a = solar_de['solar_actuals']
        solar_a = pd.DataFrame(solar_a)
        solar_a.index.name = 'event_at_utc'


    if country == 'NL':
        solar_a = solar_a/1000 # convert from kwh to Mwh
    solar_a = solar_a.resample('1h').mean()


    entry_price_data = get_price_data(start_utc, end_utc, config, country, entry_price)
    exit_price_data = get_price_data(start_utc, end_utc, config, country, exit_price)
    data = data.join([forecast, solar_a, exit_price_data, entry_price_data])


    return data

def find_sky_clear(data, forecast_selection, Threshold):

    Threshold = Threshold/100
    solar_a = pd.DataFrame(data[forecast_selection])
    # solar_a = solar_a[solar_a.index.year <= 2023]
    solar_a.index = solar_a.index + pd.DateOffset(years=1) # move forward 1 year
    clear_sky = solar_a.groupby([solar_a.index.year, solar_a.index.month]).max()
    clear_sky = clear_sky.reset_index()
    clear_sky.columns = ['year', 'month', 'solar_skyclear']
    clear_sky['solar_growth_multiplier'] = np.nan
    clear_sky.loc[clear_sky['year'] == 2023, 'solar_growth_multiplier'] = 1.30
    clear_sky.loc[clear_sky['year'] == 2024, 'solar_growth_multiplier'] = 1.19
    clear_sky = clear_sky.dropna()
    clear_sky['solar_skyclear'] = clear_sky['solar_skyclear']*clear_sky['solar_growth_multiplier']


    solar_a['month'] = solar_a.index.month
    solar_a['year'] = solar_a.index.year

    data = pd.merge(solar_a.reset_index(), clear_sky, on=['year', 'month'], how='inner')

    sky_clear_days = data.loc[data[forecast_selection] >= data['solar_skyclear']*Threshold]
    sky_clear_days = sky_clear_days.rename({'index': 'event_at_utc'}, axis = 1 )
    sky_clear_days = sky_clear_days.sort_values(by='event_at_utc')
    sky_clear_days.set_index('event_at_utc', inplace= True)

    ### filter the full day for solar hours 10-16
    data = data.rename({'index': 'event_at_utc'}, axis = 1 )
    sky_clear_fullday = data.loc[data['event_at_utc'].dt.date.isin(sky_clear_days.index.date)]
    hour = sky_clear_fullday['event_at_utc'].dt.tz_convert('Europe/Amsterdam').dt.hour
    sky_clear_fullday = sky_clear_fullday.loc[(hour >= 9) & (hour <= 19) ]
    sky_clear_fullday.set_index('event_at_utc', inplace= True)
    sky_clear_days = sky_clear_fullday


    return sky_clear_days

def find_sky_clear_v3(data, forecast_selection, Threshold, end_utc):

    Threshold = Threshold/100
    CAPACITY_GROWTH = 1.18
    solar_a = data[[forecast_selection]]
    solar_a['month'] = solar_a.index.month
    solar_a['year'] = solar_a.index.year

    # Find the highest solar day of each month in the previous year
    max_production = solar_a.groupby(['year', 'month']).max().reset_index()
    max_production['year'] = max_production['year'] + 1
    max_production.columns = ['year', 'month', 'max_production']

    solar_a = solar_a.reset_index().merge(max_production, on=['year', 'month'], how='left')

    # Filter the days where the solar value is higher than the previous year's max times the threshold
    sky_clear = solar_a.loc[solar_a[forecast_selection] > solar_a['max_production']*Threshold*CAPACITY_GROWTH]
    sky_clear.set_index('index', inplace = True)
    ## get only date !!!

    # Filter the full day for solar hours 10-16
    sky_clear_fullday = solar_a.loc[solar_a['index'].dt.date.isin(sky_clear.index.date)]
    sky_clear_fullday.set_index('index', inplace = True)
    sky_clear_fullday.index = sky_clear_fullday.index.tz_convert('Europe/Paris')
    sky_clear_fullday = sky_clear_fullday.between_time('09:00', '19:00')
    sky_clear_fullday.index = sky_clear_fullday.index.tz_convert('UTC')

    # Filter the data up to the specified end_utc
    sky_clear_days = sky_clear_fullday[sky_clear_fullday.index <= end_utc]

    return sky_clear_days



def find_sky_clear_map(data, forecast_selection, Threshold):

    Threshold_inv = 100 - Threshold

    ### sky clear days # remove night hours
    mask = (data.index.hour >= 8) & (data.index.hour <= 18)
    data = data.loc[mask]

    daily_averages = data.groupby([data.index.month, data.index.date]).mean()
    min_daily_average = daily_averages[forecast_selection].groupby(level=0).idxmin()
    dates_list = [date for month, date in min_daily_average]

    # To get the actual minimum values for each month:
    # data = pd.DataFrame(data)
    data['date'] = data.index.date
    sky_clear_days = data.loc[data['date'].isin(dates_list)]
    sky_clear_days = sky_clear_days[[forecast_selection]]

    sky_clear_days = data.loc[data['nl_solar_cloud_cover_actuals'] < Threshold_inv, forecast_selection]
    sky_clear_days = pd.DataFrame(sky_clear_days)
    
    return sky_clear_days

def gen_signal_pnl(sky_clear_days, Volume, entry_price, exit_price, data):

    ### Filter sklear clear days
    price_data = data[exit_price]
    entry_price_data = data[entry_price]
    tz_country = country_timezones[country]
    sky_clear_days.index = sky_clear_days.index.tz_convert(tz_country)
    sky_clear_days = sky_clear_days.join(price_data)
    entry_price_data.index = entry_price_data.index.tz_convert(tz_country)
    sky_clear_days = sky_clear_days.join(entry_price_data)

    ### create a chart for analyssy
    ### solar transaction
    ### create volumes 
    sky_clear_days.index = sky_clear_days.index.tz_convert('Europe/Paris')
    sky_clear_days = sky_clear_days.between_time('10:00', '17:00')
    sky_clear_days.index = sky_clear_days.index.tz_convert('UTC')
    sky_clear_days['signal'] = -1
    
    bid_1 = -0.1
    bidding_condition = sky_clear_days['epex_fr_h_day_ahead_auction_price_hourly'] < bid_1 
    sky_clear_days.loc[bidding_condition, 'signal'] = 0

    ### create scenarios 
    sky_clear_days['spread'] = sky_clear_days[exit_price] - sky_clear_days[entry_price]
    sky_clear_days['Profit'] = sky_clear_days['spread']*sky_clear_days['signal']*Volume
    sky_clear_days['cumpnl'] = sky_clear_days['Profit'].cumsum()
    ## sky clear alone

    return sky_clear_days

data = get_data(start_utc, end_utc, country, forecast_selection, entry_price, exit_price, config)


if forecast_selection == 'nl_solar_cloud_cover_actuals': 
    sky_clear_days = find_sky_clear_map(data, forecast_selection, Threshold)
else:
    # sky_clear_days = find_sky_clear(data, forecast_selection, Threshold)
    sky_clear_days = find_sky_clear_v3(data, forecast_selection, Threshold, end_utc)
    sky_clear_days = sky_clear_days.join(data['cwe_solar_dah'])
    sky_clear_days['max_cwe_solar_dah_per_month'] = sky_clear_days.groupby(sky_clear_days.index.month)['cwe_solar_dah'].transform('max')
    CWE_MAX_PROD = st.number_input('CWE Max Solar filter perc - CWE Solar Forecast must be higher to activate signal', min_value= 1, max_value= 100, value= 70)
    CWE_MAX_PROD = CWE_MAX_PROD/100

    cond = (sky_clear_days['cwe_solar_dah'] >= sky_clear_days['max_cwe_solar_dah_per_month']*CWE_MAX_PROD) & (sky_clear_days.index.month >=7)
    sky_clear_days = sky_clear_days.loc[~cond]
    # sky_clear_days = sky_clear_days.loc[sky_clear_days['cwe_solar_dah'] >= sky_clear_days['max_cwe_solar_dah_per_month']*CWE_MAX_PROD]
sky_clear_days_results = gen_signal_pnl(sky_clear_days, Volume, entry_price, exit_price, data)
sky_clear_days_results = sky_clear_days_results.join(data['solar_actuals'])
sky_clear_days_results['volume'] = Volume


# fig = px.line(sky_clear_days_results, x = sky_clear_days_results.index, y ='cumpnl')
# fig.update_traces(line_color='green')

fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.02, subplot_titles=('Cumulative PnL', 'Volume'))
# Add the cumulative PnL line chart to the first subplot
fig.add_trace(
    go.Scatter(x=sky_clear_days_results.index, y=sky_clear_days_results['cumpnl'], name='Cumulative PnL', line_color='green'),
    row=1, col=1
)
fig.add_trace(
    go.Bar(x=sky_clear_days_results.index, y=sky_clear_days_results['volume'], name='Volume'),
    row=2, col=1
)

if any(' market volume' in element for element in list(data.columns)):
    if 'imbal' not in exit_price:
        market_vol_name = exit_price + ' market volume'
        sky_clear_days_results = sky_clear_days_results.join(data[market_vol_name])
        sky_clear_days_results['market_vol_perc'] = 100*sky_clear_days_results['volume']/sky_clear_days_results[market_vol_name]
        # fig.update_layout({'yaxis2': {'title': market_vol_name, 'overlaying': 'y', 'side': 'right'}})
        fig.add_trace(go.Bar(x=sky_clear_days_results.index, y=sky_clear_days_results['market_vol_perc'], yaxis='y2', name='market_vol_perc'),row=2, col=1)

fig.add_trace(
    go.Scatter(x=sky_clear_days_results.index, y=sky_clear_days_results[forecast_selection], name= forecast_selection, line_color='yellow'),
    row=3, col=1
)
fig.add_trace(
    go.Scatter(x=sky_clear_days_results.index, y=sky_clear_days_results['solar_actuals'], name= 'solar_actuals', line_color='orange'),
    row=3, col=1
)
fig.add_trace(
    go.Scatter(x=sky_clear_days_results.index, y=sky_clear_days_results['cwe_solar_dah'], name= 'cwe_solar_dah', line_color='red'),
    row=3, col=1
)
fig.update_layout(height=1000, title_text="Cumulative PnL and Volume")
fig.update_layout(
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=-0.5,
        xanchor="center",
        x=0.5
    )
)
# fig_fund = px.line(sky_clear_days_results, x = sky_clear_days_results.index, y = forecast_selection)
# fig_fund.update_traces(line_color='yellow')

st.plotly_chart(fig, use_container_width= True)
# st.plotly_chart(fig_fund, use_container_width= True)
sky_clear_days_results.index = sky_clear_days_results.index.tz_convert('Europe/London')
st.dataframe(sky_clear_days_results, use_container_width= True)
sky_clear_days_results['Profit_mwh'] = sky_clear_days_results['Profit']/sky_clear_days_results['volume']
hourly_profit = pd.DataFrame(sky_clear_days_results.groupby(sky_clear_days_results.index.hour)['Profit'].sum())
hourly_profit = pd.DataFrame(sky_clear_days_results.groupby(sky_clear_days_results.index.hour)['Profit_mwh'].mean())
day_hour = pd.DataFrame(sky_clear_days_results.groupby([sky_clear_days_results.index.hour, sky_clear_days_results.index.day_name()])['Profit_mwh'].sum())
day_hour.unstack(0).to_csv('report/weekday_hour.csv')
st.dataframe(hourly_profit, use_container_width= True)
## sky clear a combination (DE,NL) (BE, NL) (DE, NL,FR,BE)