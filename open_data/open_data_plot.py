import bokeh
from bokeh.io import curdoc
from bokeh.themes import Theme
from bokeh.models import DatetimeTickFormatter
from bokeh.palettes import Category20_20 as palette1
from bokeh.palettes import Colorblind8 as palette2
from COVID_plots.themes.dark_minimal_adapted import json as jt
import io
import pandas as pd
import pandas_bokeh
import requests


requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = 'ALL:@SECLEVEL=1'

curdoc().theme = Theme(json=jt)


class OpenDataPlot(object):
    def __init__(self):

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

    def vac_vs_infection_plot(self):
        frame = self.covid_numbers.set_index(['Name', 'Datum']).sort_index()

        plot_frame = frame.loc[
            ('Österreich', slice(None)),
            'Todesfaelle'
        ].to_frame('pos_cases').droplevel(0).diff()

        vac_frame = self.vaccination_timeseries.set_index(
            ['state_name', 'date']
        ).sort_index().loc[
            ('Österreich', slice(None))
        ].doses_administered_cumulative.groupby('date').sum()

        plot_frame.index = pd.to_datetime(plot_frame.index, utc=True).normalize()
        vac_frame.index = pd.to_datetime(vac_frame.index, utc=True).normalize()

        plot_frame = pd.concat([plot_frame, vac_frame], axis=1)
        plot_frame.index.name = 'idx'

        # plot_frame = (plot_frame - plot_frame.min()) / (plot_frame.max() - plot_frame.min())

        plot_frame['7d_mean'] = plot_frame.pos_cases.rolling(7, center=True).mean()
        source = bokeh.models.sources.ColumnDataSource(plot_frame)

        fig1 = bokeh.plotting.figure(
            title='COVID-19 cases Austria vs vaccinations',
            x_axis_type='datetime',
            y_axis_label='Positive tests per day\nper million inhabitants',
            aspect_ratio=7
        )

        fig1.xaxis.visible = False

        glyph = fig1.line(
            x='idx',
            y='pos_cases',
            source=source,
            color='orange',
            # legend_label=column,
            # line_dash=[3, 6],
            alpha=0.2,
            # name=column
        )

        glyph = fig1.line(
            x='idx',
            y='7d_mean',
            source=source,
            color='orange',
            # legend_label=column,
            # line_dash=[3, 6],
            alpha=1,
            # name=column
        )

        fig2 = bokeh.plotting.figure(
            x_axis_type='datetime',
            x_range=fig1.x_range,
            aspect_ratio=7
        )

        glyph = fig2.line(
            x='idx',
            y='doses_administered_cumulative',
            source=source,
            color='green',
            # legend_label=column,
            # line_dash=[3, 6],
            alpha=1,
            # name=column
        )


        plot = bokeh.layouts.gridplot([[fig1], [fig2]], sizing_mode='scale_width')

        bokeh.plotting.show(plot)

    def run(self):
        self.vac_vs_infection_plot()


def main():
    plot = OpenDataPlot()
    plot.run()


if __name__ == '__main__':
    main()
