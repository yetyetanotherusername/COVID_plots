import os
import pandas as pd
import matplotlib.pyplot as plt
from cycler import cycler
import geopandas as gp
import shapely
import pandas_bokeh
from bokeh.io import curdoc
import bokeh
from bokeh.palettes import Category20_20 as palette1
from bokeh.palettes import Colorblind8 as palette2
import itertools

# set matplotlib options
plt.style.use('dark_background')
plt.rcParams['axes.prop_cycle'] = cycler(
    color=[u'#1f77b4', u'#ff7f0e', u'#2ca02c', u'#d62728', u'#9467bd',
           u'#8c564b', u'#e377c2', u'#7f7f7f', u'#bcbd22', u'#17becf'])
plt.rcParams['figure.figsize'] = (10.0, 5.0)


class CovidPlot(object):
    def __init__(self):
        self.data_path = os.path.join(
            os.path.abspath(os.pardir),
            'COVID-19',
            'csse_covid_19_data',
            'csse_covid_19_time_series'
        )

        self.confirmed_filepath = os.path.join(
            self.data_path, 'time_series_19-covid-Confirmed.csv'
        )

        self.deaths_filepath = os.path.join(
            self.data_path, 'time_series_19-covid-Deaths.csv'
        )

        self.recovered_filepath = os.path.join(
            self.data_path, 'time_series_19-covid-Recovered.csv'
        )

        self.confirmed_raw = pd.read_csv(self.confirmed_filepath)
        self.confirmed_df = self.confirmed_raw.set_index(
            ['Country/Region', 'Province/State', 'Lat', 'Long']).sort_index().T
        self.confirmed_df.index = pd.to_datetime(self.confirmed_df.index)

        self.deaths_raw = pd.read_csv(self.deaths_filepath)
        self.deaths_df = self.deaths_raw.set_index(
            ['Country/Region', 'Province/State', 'Lat', 'Long']).sort_index().T
        self.deaths_df.index = pd.to_datetime(self.deaths_df.index)

        self.recovered_raw = pd.read_csv(self.recovered_filepath)
        self.recovered_df = self.recovered_raw.set_index(
            ['Country/Region', 'Province/State', 'Lat', 'Long']).sort_index().T
        self.recovered_df.index = pd.to_datetime(self.recovered_df.index)

        self.data_disclaimer = ' (data source: Johns Hopkins CSSE)'

        if not os.path.isdir(os.path.join(os.getcwd(), 'figures')):
            os.mkdir(os.path.join(os.getcwd(), 'figures'))

    def calc_totals(self, countries=None):
        total_df = pd.DataFrame()

        if countries is not None and type(countries) == list:
            confirmed_df = self.confirmed_df.loc[
                :, (countries, slice(None), slice(None), slice(None))
            ]

            deaths_df = self.deaths_df.loc[
                :, (countries, slice(None), slice(None), slice(None))
            ]

            recovered_df = self.recovered_df.loc[
                :, (countries, slice(None), slice(None), slice(None))
            ]

        elif countries is not None:
            raise TypeError('countries argument accepts type list, '
                            f'got {type(countries)} instead')

        else:
            confirmed_df = self.confirmed_df
            deaths_df = self.deaths_df
            recovered_df = self.recovered_df

        total_df['confirmed'] = confirmed_df.sum(axis=1)
        total_df['deaths'] = deaths_df.sum(axis=1)
        total_df['recovered'] = recovered_df.sum(axis=1)

        return total_df

    def countries_to_string(self, countries):
        if countries is None:
            c_string = 'Global'
        else:
            c_string = "".join(countries)

        return c_string

    def simple_plot(self, countries=['Germany', 'Austria', 'Italy']):
        if type(countries) != list:
            raise TypeError('countries argument accepts type list, '
                            f'got {type(countries)} instead')

        confirmed = self.confirmed_df.loc[
            :, (countries,
                slice(None), slice(None), slice(None))
        ]

        confirmed.columns = (
            confirmed.columns.droplevel(3).droplevel(2).droplevel(1)
        )

        pandas_bokeh.output_file(
            os.path.join('figures', 'simple_plot.html'))
        curdoc().theme = 'dark_minimal'
        confirmed.plot_bokeh.line(
            figsize=(1500, 750),
            title="simple plot",
            plot_data_points=True,
            plot_data_points_size=5,
            marker="circle")

    def not_so_simple_plot(self, countries=['Germany', 'Austria', 'Italy']):
        if type(countries) != list:
            raise TypeError('countries argument accepts type list, '
                            f'got {type(countries)} instead')

        confirmed = self.confirmed_df.loc[
            :, (countries,
                slice(None), slice(None), slice(None))
        ]

        confirmed.columns = (
            confirmed.columns.droplevel(3).droplevel(2).droplevel(1)
        )

        concat_list = []
        for label in list(set(confirmed.columns)):
            series = confirmed[label]
            if type(series) == pd.DataFrame:
                series = series.sum(axis=1)
                series.name = label
            series = series[series >= 100]
            series = series + 100 - series[0]
            series = series.reset_index(drop=True)
            concat_list.append(series)

        transformed = pd.concat(concat_list, axis=1)

        reference = pd.DataFrame()
        reference['helper'] = transformed.index
        reference['double every other day'] = (
            100 * (2 ** (1 / 2)) ** reference['helper']
        )
        reference['double every third day'] = (
            100 * (2 ** (1 / 3)) ** reference['helper']
        )
        reference['double every week'] = (
            100 * (2 ** (1 / 7)) ** reference['helper']
        )
        reference['double every month'] = (
            100 * (2 ** (1 / 30)) ** reference['helper']
        )

        reference = reference.drop('helper', axis=1)

        bokeh.plotting.output_file(
            os.path.join('figures', 'shifted.html'))
        curdoc().theme = 'dark_minimal'

        transformed['index'] = transformed.index
        source = bokeh.models.sources.ColumnDataSource(transformed)

        figure = bokeh.plotting.figure(
            title='COVID-19 cases per country' + self.data_disclaimer,
            plot_width=1500,
            plot_height=750,
            y_axis_type='log',
            x_axis_label='Days since more than 100 cases',
            y_axis_label='Accumulated positive cases')

        column_list = list(transformed.columns)
        column_list.remove('index')

        colors = itertools.cycle(palette1)

        for column, color in zip(column_list, colors):
            glyph = figure.line(
                x='index',
                y=column,
                source=source,
                color=color,
                legend_label=column,
                alpha=0.6,
                name=column
            )

            figure.circle(
                x='index',
                y=column,
                source=source,
                color=color,
                radius=0.05,
                alpha=0.6,
                legend_label=column,
                name=column
            )

            fstring = '{' + f'{column}' + '}'
            hover_tool = bokeh.models.HoverTool(
                tooltips=[(f'{column}', f'day: $index, value: @{fstring}')],
                mode='vline',
                renderers=[glyph],
                line_policy='nearest')
            figure.tools.append(hover_tool)

        reference['index'] = reference.index
        source = bokeh.models.sources.ColumnDataSource(reference)

        column_list = list(reference.columns)
        column_list.remove('index')

        colors = itertools.cycle(palette2)

        for column, color in zip(column_list, colors):
            figure.line(
                x='index',
                y=column,
                source=source,
                color=color,
                legend_label=column,
                line_dash='dashed',
                name=column
            )

        figure.legend.location = 'top_left'
        figure.legend.click_policy = "hide"
        figure.toolbar.active_scroll = figure.select_one(
            bokeh.models.tools.WheelZoomTool)

        bokeh.plotting.show(figure)

    def totals_plot(self, countries=None):
        total_df = self.calc_totals(countries)

        total_df['currently_sick'] = (
            total_df.confirmed - total_df.deaths - total_df.recovered
        )

        total_df = total_df.drop('confirmed', axis=1)
        c_string = self.countries_to_string(countries)

        pandas_bokeh.output_file(
            os.path.join('figures', 'totals.html'))
        curdoc().theme = 'dark_minimal'
        total_df.plot_bokeh.area(
            figsize=(1500, 750),
            title=f'Total COVID-19 numbers, {c_string}' + self.data_disclaimer,
            ylabel='Number of individuals affected (stacked)',
            stacked=True
        )

    def rate_plot(self, countries=None):
        total_df = self.calc_totals(countries)

        plot_df = pd.DataFrame()

        plot_df['confirmed'] = total_df.confirmed.diff()
        plot_df['deaths'] = total_df.deaths.diff().clip(lower=0)
        plot_df['recovered'] = total_df.recovered.diff().clip(lower=0)

        c_string = self.countries_to_string(countries)

        pandas_bokeh.output_file(
            os.path.join('figures', 'totals.html'))
        curdoc().theme = 'dark_minimal'
        plot_df.plot_bokeh.area(
            figsize=(1500, 750),
            title=f'{c_string} daily COVID-19 cases' + self.data_disclaimer,
            ylabel='Number of newly affected individuals per day'
        )

    def map_plot(self):

        world = gp.read_file(gp.datasets.get_path('naturalearth_lowres'))

        cdf = self.confirmed_df - self.deaths_df - self.recovered_df

        def animate(idx):
            now = cdf.iloc[idx, :].T.to_frame()
            now.columns = ['confirmed']
            now = now.reset_index()

            geometry = [
                shapely.geometry.Point(xy) for xy in zip(now.Long, now.Lat)
            ]

            now = now.drop(['Lat', 'Long'], axis=1)
            crs = {'init': 'epsg:4326'}
            pgdf = gp.GeoDataFrame(
                now, crs=crs, geometry=geometry)

            base = world.plot()

            pgdf.plot(
                ax=base, color='r',
                markersize=pgdf['confirmed'] / 20,
                alpha=0.3
            )

            plt.title('COVID-19 development' + self.data_disclaimer)
            plt.text(0, -50, cdf.iloc[idx, :].name.date())

            if len(str(idx)) > 2:
                lex_sort_num = str(idx)
            elif len(str(idx)) > 1:
                lex_sort_num = f'0{str(idx)}'
            else:
                lex_sort_num = f'00{str(idx)}'

            plt.savefig(
                os.path.join(
                    'figures', f'animated_map{lex_sort_num}.png'), dpi=300)

            plt.close()

        for iidx in range(0, cdf.shape[0]):
            animate(iidx)

    def run(self):
        # self.simple_plot()
        self.not_so_simple_plot()
        self.totals_plot()
        self.rate_plot()
        # self.map_plot()
        # plt.show()


def main():
    plot = CovidPlot()
    plot.run()


if __name__ == '__main__':
    main()
