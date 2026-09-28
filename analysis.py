import pandas as pd
import plotly.express as px

forecast = pd.read_parquet('data/forecast_dah.parquet')
forecast.index = forecast.index.tz_convert('Europe/Paris')
forecast_name = 'meteologica_france_pv_powergeneration_forecast_meteologica_total_total_hourly_perc50_-1_11_55'
summary = forecast.groupby([forecast.index.year, forecast.index.month])[forecast_name].max()

### France installed capacity
## 2022 : 15.84 GW 2023 : 19 GW
solar_change = (19/15.84)
summary_table = summary.unstack(0)
summary_table['ratio_20232022'] = summary_table[2023]/summary_table[2022]
summary_table['ratio_20242023'] = summary_table[2024]/summary_table[2023]
summary_table.mean()