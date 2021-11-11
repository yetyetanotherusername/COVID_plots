import bokeh
from bokeh.io import curdoc
from bokeh.themes import Theme
from bokeh.palettes import Category20_20 as palette1
from bokeh.models import DatetimeTickFormatter, LinearAxis, Range1d
from bokeh.palettes import Colorblind8 as palette2
from COVID_plots.themes.dark_minimal_adapted import json as jt
import io
import pandas as pd
import pandas_bokeh
import requests

from COVID_plots.plots.data_exploration import CovidPlot


requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = 'ALL:@SECLEVEL=1'

curdoc().theme = Theme(json=jt)


class OpenDataPlot(object):
    def __init__(self):

        self.load_open_data()
        self.parse_historic_data()

    def load_open_data(self):
        base_url = 'https://info.gesundheitsministerium.gv.at/data/'

        self.vaccination_age_groups = self.url_to_df(
            base_url + 'COVID19_vaccination_doses_agegroups.csv'
        )

        self.vaccination_timeseries = self.url_to_df(
            base_url + 'COVID19_vaccination_doses_timeline.csv'
        )

        self.covid_numbers = self.url_to_df(
            base_url + 'timeline-faelle-bundeslaender.csv'
        )

    def parse_historic_data(self):
        helper = CovidPlot()

        historic_cases = helper.confirmed_df['Austria'].T.reset_index(
            drop=True).T.iloc[:, 0]
        historic_deaths = helper.deaths_df['Austria'].T.reset_index(
            drop=True).T.iloc[:, 0]

        historic_data = pd.concat([historic_cases, historic_deaths], axis=1)
        historic_data.columns = ['historic_cases', 'historic_deaths']

        historic_data.index = historic_data.index.normalize().tz_localize(
            'UTC')

        self.historic_data = historic_data.diff()

    def url_to_df(self, url):
        return self.parse_csv(
            self.download_csv(
                url
            )
        )

    def parse_csv(self, csv):
        return pd.read_csv(
            csv,
            delimiter=';'
        )

    def download_csv(self, url):
        req = requests.get(url).content
        return io.StringIO(req.decode('utf-8'))

    def prepare_data(self):
        frame = self.covid_numbers.set_index(['Name', 'Datum']).sort_index()

        plot_frame = frame.loc[
            ('Österreich', slice(None)),
            'BestaetigteFaelleBundeslaender'
        ].to_frame('pos_cases').droplevel(0).diff()

        plot_frame['deaths'] = frame.loc[
            ('Österreich', slice(None)),
            'Todesfaelle'
        ].droplevel(0).diff()

        vac_frame = self.vaccination_timeseries.set_index(
            ['state_name', 'date']
        ).sort_index().loc[
            ('Österreich', slice(None))
        ].doses_administered_cumulative.groupby('date').sum().to_frame()

        vac_frame['doses_per_day'] = vac_frame.doses_administered_cumulative.diff()

        plot_frame.index = pd.to_datetime(plot_frame.index, utc=True).normalize()
        vac_frame.index = pd.to_datetime(vac_frame.index, utc=True).normalize()

        plot_frame = pd.concat([plot_frame, vac_frame, self.historic_data], axis=1)
        plot_frame.index.name = 'idx'

        plot_frame.pos_cases = plot_frame.pos_cases.fillna(
            plot_frame.historic_cases)
        plot_frame.deaths = plot_frame.deaths.fillna(
            plot_frame.historic_deaths)

        plot_frame = plot_frame.drop(
            ['historic_cases', 'historic_deaths'],
            axis=1
        )

        plot_frame['7d_mean'] = plot_frame.pos_cases.rolling(7, center=True).mean()
        plot_frame['7d_mean_deaths'] = plot_frame.deaths.rolling(7, center=True).mean()

        print(plot_frame)

        self.plot_frame = plot_frame

    def vac_vs_infection_plot(self):
        source = bokeh.models.sources.ColumnDataSource(self.plot_frame)

        fig1 = bokeh.plotting.figure(
            title='COVID-19 cases Austria vs vaccinations',
            x_axis_type='datetime',
            y_axis_label='Positive tests per day',
            aspect_ratio=7
        )

        fig1.add_layout(
            LinearAxis(
                y_range_name="y2",
                axis_label='Deaths per day'),
            'right'
        )
        fig1.extra_y_ranges = {
            "y2": Range1d(-10, self.plot_frame.deaths.max())
        }

        fig1.xaxis.visible = False

        glyph1 = fig1.line(
            x='idx',
            y='pos_cases',
            source=source,
            color='orange',
            # legend_label='pos_cases',
            # line_dash=[3, 6],
            alpha=0.3,
            # name=column
        )

        glyph2 = fig1.line(
            x='idx',
            y='7d_mean',
            source=source,
            color='orange',
            legend_label='New cases smoothed',
            # line_dash=[3, 6],
            alpha=1,
            # name=column
        )

        glyph3 = fig1.line(
            x='idx',
            y='deaths',
            source=source,
            color='red',
            # legend_label='deaths',
            # line_dash=[3, 6],
            alpha=0.3,
            # name=column
            y_range_name='y2'
        )

        glyph = fig1.line(
            x='idx',
            y='7d_mean_deaths',
            source=source,
            color='red',
            legend_label='New deaths smoothed (right)',
            # line_dash=[3, 6],
            alpha=1,
            # name=column
            y_range_name='y2'
        )

        fig2 = bokeh.plotting.figure(
            x_axis_type='datetime',
            x_range=fig1.x_range,
            aspect_ratio=7
        )

        fig2.xaxis.visible = False

        glyph = fig2.line(
            x='idx',
            y='pos_cases',
            source=source,
            color='orange',
            # legend_label=column,
            # line_dash=[3, 6],
            alpha=0.3,
            # name=column
        )

        glyph = fig2.line(
            x='idx',
            y='7d_mean',
            source=source,
            color='orange',
            # legend_label=column,
            # line_dash=[3, 6],
            alpha=1,
            # name=column
        )

        fig3 = bokeh.plotting.figure(
            x_axis_type='datetime',
            x_range=fig1.x_range,
            aspect_ratio=7
        )

        fig3.add_layout(LinearAxis(y_range_name="y2"), 'right')
        fig3.extra_y_ranges = {
            "y2": Range1d(0, self.plot_frame.doses_per_day.max())
        }

        glyph = fig3.line(
            x='idx',
            y='doses_per_day',
            source=source,
            color='green',
            # legend_label=column,
            # line_dash=[3, 6],
            alpha=1,
            # name=column
            y_range_name='y2'
        )

        glyph = fig3.line(
            x='idx',
            y='doses_administered_cumulative',
            source=source,
            color='green',
            # legend_label=column,
            # line_dash=[3, 6],
            alpha=1,
            # name=column
        )


        plot = bokeh.layouts.gridplot([[fig1], [fig2], [fig3]], sizing_mode='scale_width')

        bokeh.plotting.show(plot)

    def run(self):
        self.prepare_data()
        self.vac_vs_infection_plot()


def main():
    plot = OpenDataPlot()
    plot.run()


if __name__ == '__main__':
    main()
