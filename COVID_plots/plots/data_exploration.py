import os
import itertools
import pandas as pd
import numpy as np

import bokeh
import pandas_bokeh
from bokeh.io import curdoc
from bokeh.themes import Theme
from bokeh.models import DatetimeTickFormatter
from bokeh.palettes import Category20_20 as palette1
from bokeh.palettes import Colorblind8 as palette2
from COVID_plots.themes.dark_minimal_adapted import json as jt

curdoc().theme = Theme(json=jt)


class CovidPlot(object):
    def parse_csv(self, path):
        raw = pd.read_csv(path)
        df = raw.set_index(
            ['Country/Region', 'Province/State', 'Lat', 'Long']
        ).sort_index().T
        df.index = pd.to_datetime(df.index)
        return df

    def parse_US_csv(self, path):
        raw = pd.read_csv(path)
        df = raw.rename(
            columns={
                'Country_Region': 'Country/Region',
                'Province_State': 'Province/State',
                'Long_': 'Long'
            }
        ).set_index(
            ['Country/Region', 'Province/State', 'Lat', 'Long']
        ).drop(
            ['UID', 'iso2', 'iso3', 'code3', 'FIPS', 'Admin2', 'Combined_Key',
             'Population'],
            axis=1, errors='ignore'
        ).sort_index().T
        df.index = pd.to_datetime(df.index)
        return df

    def __init__(self):
        self.data_path = os.path.join(
            os.path.abspath(os.pardir),
            'COVID-19',
            'csse_covid_19_data',
            'csse_covid_19_time_series'
        )

        self.confirmed_filepath = os.path.join(
            self.data_path, 'time_series_covid19_confirmed_global.csv'
        )

        self.deaths_filepath = os.path.join(
            self.data_path, 'time_series_covid19_deaths_global.csv'
        )

        self.recovered_filepath = os.path.join(
            self.data_path, 'time_series_covid19_recovered_global.csv'
        )

        self.confirmed_US_filepath = os.path.join(
            self.data_path, 'time_series_covid19_confirmed_US.csv'
        )

        self.deaths_US_filepath = os.path.join(
            self.data_path, 'time_series_covid19_deaths_US.csv'
        )

        self.confirmed_df = self.parse_csv(self.confirmed_filepath)
        self.deaths_df = self.parse_csv(self.deaths_filepath)
        self.recovered_df = self.parse_csv(self.recovered_filepath)

        confirmed_US = self.parse_US_csv(self.confirmed_US_filepath)
        deaths_US = self.parse_US_csv(self.deaths_US_filepath)

        self.confirmed_df = self.confirmed_df.drop(
            columns='US').join(confirmed_US)
        self.deaths_df = self.deaths_df.drop(
            columns='US').join(deaths_US)

        self.population_data = pd.read_csv(
            os.path.join('COVID_plots', 'data', 'population_numbers.csv'),
            names=['Country', 'Population']
        ).set_index('Country', drop=True).T.sort_index(axis=1).set_index(
            'index', drop=True)
        self.population_data.index = pd.to_datetime(self.population_data.index)

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
        curdoc().theme = Theme(json=jt)
        confirmed.plot_bokeh.line(
            figsize=(1500, 750),
            title="simple plot",
            plot_data_points=True,
            plot_data_points_size=5,
            marker="circle",
            sizing_mode='scale_both')

    def relative_plot(self, countries=['Germany', 'Austria', 'Italy']):
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

            concat_list.append(series)

        confirmed = pd.concat(concat_list, axis=1).sort_index(axis=1)

        population_data = self.population_data.astype(int).reindex(
            confirmed.index).fillna(method='ffill')

        confirmed = confirmed / population_data * 1000000

        confirmed = confirmed['2020-02-25':]

        bokeh.plotting.output_file(
            os.path.join('figures', 'relative_plot.html'))

        confirmed['idx'] = confirmed.index.to_pydatetime()
        source = bokeh.models.sources.ColumnDataSource(confirmed)

        figure = bokeh.plotting.figure(
            title='COVID-19 cases per country' + self.data_disclaimer,
            x_axis_type='datetime',
            x_axis_label='Date',
            y_axis_type='log',
            y_axis_label='Confirmed cases per million inhabitants',
        )

        column_list = list(confirmed.columns)
        column_list.remove('idx')

        colors = itertools.cycle(palette1)

        for column, color in zip(column_list, colors):
            glyph = figure.line(
                x='idx',
                y=column,
                source=source,
                color=color,
                legend_label=column,
                alpha=0.6,
                name=column
            )

            figure.circle(
                x='idx',
                y=column,
                source=source,
                color=color,
                size=5,
                alpha=0.6,
                legend_label=column,
                name=column
            )

            fstring = '{' + f'{column}' + '}'
            dstring = '{%d-%m-%Y}'
            hover_tool = bokeh.models.HoverTool(
                tooltips=[(f'{column}',
                           f'Date: @idx{dstring}, Confirmed: @{fstring}')],
                formatters={'@idx': 'datetime'},
                mode='vline',
                renderers=[glyph],
                line_policy='nearest')

            figure.tools.append(hover_tool)

        figure.xaxis.formatter = DatetimeTickFormatter(
            days='%d-%m-%Y',
            hours='%H:%M'
        )

        bokeh.plotting.show(figure)

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
            series = series[series >= 1000]
            # series = series[0:35]
            series = series.reset_index(drop=True)
            concat_list.append(series)

        transformed = pd.concat(concat_list, axis=1).sort_index(axis=1)

        reference = pd.DataFrame()
        reference['helper'] = np.arange(
            0, transformed.index.tolist()[-1], 1 / 24)
        reference.index = reference.helper

        reference['double every other day'] = (
            1000 * (2 ** (1 / 2)) ** reference['helper']
        )
        reference['double every third day'] = (
            1000 * (2 ** (1 / 3)) ** reference['helper']
        )
        reference['double every week'] = (
            1000 * (2 ** (1 / 7)) ** reference['helper']
        )

        reference['double every other_week'] = (
            1000 * (2 ** (1 / 14)) ** reference['helper']
        )

        reference['double every month'] = (
            1000 * (2 ** (1 / 30)) ** reference['helper']
        )

        reference = reference.drop('helper', axis=1)

        max_crop = transformed.max().max()
        reference.loc[
            reference['double every other day'] > max_crop,
            'double every other day'] = float('nan')
        reference.loc[
            reference['double every third day'] > max_crop,
            'double every third day'] = float('nan')

        bokeh.plotting.output_file(
            os.path.join('figures', 'shifted.html'))

        transformed['idx'] = transformed.index
        source = bokeh.models.sources.ColumnDataSource(transformed)

        figure = bokeh.plotting.figure(
            title='COVID-19 cases per country' + self.data_disclaimer,
            y_axis_type='log',
            x_axis_label='Days since more than 1000 cases',
            y_axis_label='Accumulated positive cases'
        )

        column_list = list(transformed.columns)
        column_list.remove('idx')

        colors = itertools.cycle(palette1)

        for column, color in zip(column_list, colors):
            glyph = figure.line(
                x='idx',
                y=column,
                source=source,
                color=color,
                legend_label=column,
                alpha=0.6,
                name=column
            )

            figure.circle(
                x='idx',
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
                tooltips=[(f'{column}',
                           f'Day: @idx, Confirmed: @{fstring}')],
                mode='vline',
                renderers=[glyph],
                line_policy='nearest')

            figure.tools.append(hover_tool)

        reference['idx'] = reference.index
        source = bokeh.models.sources.ColumnDataSource(reference)

        column_list = list(reference.columns)
        column_list.remove('idx')

        colors = itertools.cycle(palette2)

        for column, color in zip(column_list, colors):
            figure.line(
                x='idx',
                y=column,
                source=source,
                color=color,
                legend_label=column,
                line_dash='dashed',
                name=column
            )

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
        curdoc().theme = Theme(json=jt)
        total_df.plot_bokeh.area(
            figsize=(1500, 750),
            title=f'Total COVID-19 numbers, {c_string}' + self.data_disclaimer,
            ylabel='Number of individuals affected (stacked)',
            stacked=True,
            sizing_mode='scale_both'
        )

    def rate_plot(self, countries=None):
        total_df = self.calc_totals(countries)

        plot_df = pd.DataFrame()

        plot_df['confirmed'] = total_df.confirmed.diff()
        plot_df['deaths'] = total_df.deaths.diff().clip(lower=0)
        plot_df['recovered'] = total_df.recovered.diff().clip(lower=0)

        c_string = self.countries_to_string(countries)

        pandas_bokeh.output_file(
            os.path.join('figures', 'rate.html'))
        curdoc().theme = Theme(json=jt)
        plot_df.plot_bokeh.area(
            figsize=(1500, 750),
            title=f'{c_string} daily COVID-19 cases' + self.data_disclaimer,
            ylabel='Number of newly affected individuals per day',
            sizing_mode='scale_both'
        )

    def run(self):
        countries = [
            'Germany',
            'Austria',
            'Italy',
            'US',
            'United Kingdom',
            'Spain',
            'Norway',
            'Sweden',
            'Finland',
            'China'
        ]
        # self.simple_plot(countries)
        self.relative_plot(countries)
        self.not_so_simple_plot(countries)
        self.totals_plot()
        self.rate_plot()


def main():
    plot = CovidPlot()
    plot.run()


if __name__ == '__main__':
    main()
