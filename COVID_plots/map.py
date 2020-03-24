import bokeh
import numpy as np
import geopandas as gp
from bokeh.io import curdoc
from bokeh.plotting import figure
from data_exploration import CovidPlot

helper = CovidPlot()

curdoc().theme = 'dark_minimal'

world = gp.read_file(gp.datasets.get_path('naturalearth_lowres'))

cdf = helper.confirmed_df - helper.deaths_df - helper.recovered_df

world_source = bokeh.models.sources.GeoJSONDataSource(
    geojson=world.to_json())

title = 'COVID-19 development' + helper.data_disclaimer
fig = figure(
    sizing_mode='scale_both',
    aspect_ratio=2,
    title=title
)

fig.patches(
    'xs', 'ys',
    source=world_source,
    line_color='black',
    line_width=0.25)


now = cdf.iloc[0, :].T.to_frame()
now['date'] = str(now.columns[0])
now.columns = ['confirmed', 'date']
now = now.reset_index()
# now.loc[now.confirmed == 0, 'confirmed'] = np.nan
now.confirmed = np.log2(now.confirmed) / 3
source = bokeh.models.sources.ColumnDataSource(now)

glyph = fig.circle(
    'Long', 'Lat',
    source=source,
    color='red',
    alpha=0.3,
    radius='confirmed')

data_source = glyph.data_source

# textglyph = fig.text(
#     x=0, y=0,
#     text='date',
#     source=source,
#     color='white')

# text_source = textglyph.data_source

i = 0


def callback():
    global i
    now = cdf.iloc[0, :].T.to_frame()
    now['date'] = str(now.columns[0])
    now.columns = ['confirmed', 'date']
    now = now.reset_index()
    # now.loc[now.confirmed == 0, 'confirmed'] = np.nan
    now.confirmed = np.log2(now.confirmed) / 3

    cds = dict(bokeh.models.sources.ColumnDataSource(now).data)
    data_source.data = cds
    # text_source.data = cds

    i += 1

    if i >= cdf.shape[0]:
        i = 0


curdoc().add_periodic_callback(callback, 300)
curdoc().add_root(fig)