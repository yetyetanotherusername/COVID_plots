import bokeh
import numpy as np
import geopandas as gp
from bokeh.io import curdoc
from bokeh.themes import Theme
from bokeh.plotting import figure
from data_exploration import CovidPlot
from COVID_plots.themes.dark_minimal_adapted import json as jt

helper = CovidPlot()

curdoc().theme = Theme(json=jt)

world = gp.read_file(gp.datasets.get_path('naturalearth_lowres'))

helper.recovered_df = helper.recovered_df.reindex(
    columns=helper.confirmed_df.columns).fillna(0)

cdf = helper.confirmed_df - helper.deaths_df - helper.recovered_df

world_source = bokeh.models.sources.GeoJSONDataSource(
    geojson=world.to_json())

title = 'COVID-19 development' + helper.data_disclaimer
fig = figure(
    title=title
)

fig.patches(
    'xs', 'ys',
    source=world_source,
    line_color='black',
    line_width=0.25)


now = cdf.iloc[0, :].T.to_frame()
now['date'] = str(now.columns[0].strftime('%d %m %Y'))
now.columns = ['confirmed', 'date']
now = now.reset_index()
now.loc[now.confirmed == 0, 'confirmed'] = np.nan
mask = ~np.logical_or(
    np.isclose(now.Lat, 0),
    np.isclose(now.Long, 0)
)
now = now.loc[mask, :]
now.confirmed = now.confirmed / 5000
source = bokeh.models.sources.ColumnDataSource(now)
t_source = bokeh.models.sources.ColumnDataSource(now.iloc[[0]])

glyph = fig.circle(
    'Long', 'Lat',
    source=source,
    color='red',
    alpha=0.3,
    radius='confirmed',
    radius_dimension='min')

data_source = glyph.data_source

textglyph = fig.text(
    x=0, y=90,
    text='date',
    source=t_source,
    color='white',
    text_align='center',
    text_font_size='20pt')

text_source = textglyph.data_source

i = 0


def callback():
    global i
    now = cdf.iloc[i, :].T.to_frame()
    now['date'] = str(now.columns[0].strftime('%d-%m-%Y'))
    now.columns = ['confirmed', 'date']
    now = now.reset_index()
    now.loc[now.confirmed == 0, 'confirmed'] = np.nan
    mask = ~np.logical_or(
        np.isclose(now.Lat, 0),
        np.isclose(now.Long, 0)
    )
    now = now.loc[mask, :]
    now.confirmed = now.confirmed / 5000

    data_source.data = dict(bokeh.models.sources.ColumnDataSource(now).data)
    text_source.data = dict(bokeh.models.sources.ColumnDataSource(
        now.iloc[[0]]).data)

    i += 1

    if i >= cdf.shape[0]:
        i = 0


curdoc().add_periodic_callback(callback, 300)
curdoc().add_root(fig)
