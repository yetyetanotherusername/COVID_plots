import io

import bokeh
import numpy as np
import pandas as pd
import requests
from bokeh import plotting
from bokeh.io import curdoc
from bokeh.models import BasicTickFormatter, LinearAxis, Range1d, Title
from bokeh.themes import Theme
from scipy.stats import gmean

from COVID_plots.plots.data_exploration import CovidPlot
from COVID_plots.themes.dark_minimal_adapted import json as jt

requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = "ALL:@SECLEVEL=1"

curdoc().theme = Theme(json=jt)


class OpenDataPlot:
    def __init__(self):
        self.load_open_data()

    def load_open_data(self):
        base_url = "https://info.gesundheitsministerium.gv.at/data/"
        open_data_url = "https://covid19-dashboard.ages.at/data/"

        self.vaccination_age_groups = self.url_to_df(
            base_url + "COVID19_vaccination_doses_agegroups.csv"
        )

        self.vaccination_timeseries = self.url_to_df(
            base_url + "COVID19_vaccination_doses_timeline.csv"
        )

        self.covid_numbers = self.url_to_df(open_data_url + "CovidFaelle_Timeline.csv")

        self.hospitalizations = self.url_to_df(open_data_url + "Hospitalisierung.csv")

    def url_to_df(self, url):
        return self.parse_csv(self.download_csv(url))

    def parse_csv(self, csv):
        return pd.read_csv(csv, delimiter=";")

    def download_csv(self, url):
        req = requests.get(url).content
        return io.StringIO(req.decode("utf-8"))

    def prepare_data(self):
        frame = self.covid_numbers
        frame.Time = pd.to_datetime(frame.Time, format="%d.%m.%Y %H:%M:%S")
        frame = frame.set_index(["Bundesland", "Time"]).sort_index()

        plot_frame = (
            frame.loc[("Österreich", slice(None)), "AnzahlFaelle"]
            .to_frame("pos_cases")
            .droplevel(0)
        )

        plot_frame["deaths"] = frame.loc[
            ("Österreich", slice(None)), "AnzahlTotTaeglich"
        ].droplevel(0)

        plot_frame.loc["2022-04-21":"2022-04-23", "deaths"] = plot_frame.loc[
            "2022-04-20 00:00:00", "deaths"
        ]
        plot_frame.at["2022-05-23 00:00:00", "deaths"] = plot_frame.at[
            "2022-05-22 00:00:00", "deaths"
        ]

        hframe = self.hospitalizations
        hframe.Meldedatum = pd.to_datetime(
            hframe.Meldedatum, format="%d.%m.%Y %H:%M:%S"
        )
        hframe = hframe.set_index(["Bundesland", "Meldedatum"]).sort_index()

        plot_frame["tests"] = (
            hframe.loc[("Österreich", slice(None)), "TestGesamt"]
            .droplevel(0)
            .diff()
            .fillna(0)
        )

        plot_frame["hospitalizations"] = hframe.loc[
            ("Österreich", slice(None)), "NormalBettenBelCovid19"
        ].droplevel(0)

        plot_frame["ICU"] = hframe.loc[
            ("Österreich", slice(None)), "IntensivBettenBelCovid19"
        ].droplevel(0)

        vac_frame = (
            self.vaccination_timeseries.set_index(["state_name", "date", "dose_number"])
            .sort_index()
            .loc[("Österreich", slice(None))]
            .doses_administered_cumulative.groupby(["date", "dose_number"])
            .sum()
            .to_frame()
            .unstack("dose_number")
        )
        vac_frame.columns = vac_frame.columns.droplevel(0)
        vac_frame.columns = ["first_doses", "second_doses", "third_doses"]

        vac_frame["doses_administered_cumulative"] = vac_frame.sum(axis=1)

        vac_frame[
            "doses_per_day"
        ] = vac_frame.doses_administered_cumulative.diff().fillna(0)

        plot_frame.index = pd.to_datetime(plot_frame.index, utc=True).normalize()
        vac_frame.index = pd.to_datetime(vac_frame.index, utc=True).normalize()

        plot_frame = pd.concat([plot_frame, vac_frame], axis=1)
        plot_frame.index.name = "idx"

        plot_frame["7d_mean"] = plot_frame.pos_cases.rolling(7, center=True).mean()
        plot_frame["7d_mean_deaths"] = plot_frame.deaths.rolling(7, center=True).mean()

        plot_frame["rel_change"] = plot_frame["7d_mean"] / plot_frame["7d_mean"].shift()

        plot_frame["change_smoothed"] = plot_frame.rel_change.rolling(
            7, center=True
        ).apply(gmean)

        plot_frame.rel_change = (plot_frame.rel_change - 1) * 100
        plot_frame.change_smoothed = (plot_frame.change_smoothed - 1) * 100

        plot_frame["zero"] = 0.0

        plot_frame["test_pos_percentage"] = (
            plot_frame.pos_cases / plot_frame.tests * 100
        ).replace([np.inf, -np.inf], np.nan)

        plot_frame[
            "test_pos_percentage_smoothed"
        ] = plot_frame.test_pos_percentage.rolling(7, center=True).mean()

        plot_frame.tests = plot_frame.tests / 10**5

        plot_frame.doses_per_day = plot_frame.doses_per_day / 10**4
        plot_frame.doses_administered_cumulative = (
            plot_frame.doses_administered_cumulative / 10**6
        )
        plot_frame.first_doses = plot_frame.first_doses / 10**6
        plot_frame.second_doses = plot_frame.second_doses / 10**6
        plot_frame.third_doses = plot_frame.third_doses / 10**6

        self.plot_frame = plot_frame

    def calc_axis_min_max(self, column_name):
        edge_margin = 0.1

        plot_frame = self.plot_frame
        col_max = plot_frame[column_name].max()
        col_min = plot_frame[column_name].min()
        diff = col_max - col_min

        ax_min = col_min - diff * edge_margin
        ax_max = col_max + diff * edge_margin

        return ax_min, ax_max

    def vac_vs_infection_plot(self):
        source = bokeh.models.sources.ColumnDataSource(self.plot_frame)

        aspect = 10
        low_alpha = 0.3

        fig0 = bokeh.plotting.figure(
            x_axis_type="datetime",
            y_axis_label="Relative\nchange-%",
            aspect_ratio=aspect,
        )

        fig0.xaxis.visible = False
        fig0.y_range = Range1d(-15, 20)

        fig0.add_layout(Title(text="Relative growth"), "above")

        date = self.plot_frame.index[-1].date().strftime("%d-%m-%Y")

        fig0.add_layout(
            Title(
                text=(f"COVID-19 report Austria (last update {date})"),
                text_font_size="16pt",
            ),
            "above",
        )

        glyph1 = fig0.line(
            x="idx",
            y="rel_change",
            source=source,
            color="white",
            # legend_label='pos_cases',
            # line_dash=[3, 6],
            alpha=low_alpha,
            # name=column
        )

        glyph1 = fig0.line(
            x="idx",
            y="change_smoothed",
            source=source,
            color="white",
            # legend_label='pos_cases',
            # line_dash=[3, 6],
            alpha=1,
            # name=column
        )

        glyph1 = fig0.line(
            x="idx",
            y="zero",
            source=source,
            color="white",
            # legend_label='pos_cases',
            # line_dash=[3, 6],
            alpha=1,
            # name=column
        )

        fig1 = bokeh.plotting.figure(
            title="Daily view",
            x_axis_type="datetime",
            y_axis_label="Positive cases\nper day",
            aspect_ratio=aspect,
            x_range=fig0.x_range,
        )

        fig1_min, fig1_max = self.calc_axis_min_max("7d_mean")
        fig1.y_range = Range1d(fig1_min, fig1_max)

        fig1.add_layout(
            LinearAxis(y_range_name="y2", axis_label="Deaths per day"), "right"
        )

        fig1_sec_min, fig1_sec_max = self.calc_axis_min_max("7d_mean_deaths")
        fig1.extra_y_ranges = {"y2": Range1d(fig1_sec_min, fig1_sec_max)}

        fig1.xaxis.visible = False

        glyph1 = fig1.line(
            x="idx",
            y="pos_cases",
            source=source,
            color="orange",
            # legend_label='pos_cases',
            # line_dash=[3, 6],
            alpha=low_alpha,
            # name=column
        )

        glyph2 = fig1.line(
            x="idx",
            y="7d_mean",
            source=source,
            color="orange",
            legend_label="New cases smoothed",
            # line_dash=[3, 6],
            alpha=1,
            # name=column
        )

        glyph3 = fig1.line(
            x="idx",
            y="deaths",
            source=source,
            color="red",
            # legend_label='deaths',
            # line_dash=[3, 6],
            alpha=low_alpha,
            # name=column
            y_range_name="y2",
        )

        glyph = fig1.line(
            x="idx",
            y="7d_mean_deaths",
            source=source,
            color="red",
            legend_label="New deaths smoothed (right)",
            # line_dash=[3, 6],
            alpha=1,
            # name=column
            y_range_name="y2",
        )

        fig2 = bokeh.plotting.figure(
            title="Testing",
            x_axis_type="datetime",
            x_range=fig0.x_range,
            aspect_ratio=aspect,
            y_axis_label="100k tests per day",
        )
        fig2.yaxis.formatter = BasicTickFormatter(use_scientific=False)
        fig2.xaxis.visible = False

        fig2_min, fig2_max = self.calc_axis_min_max("tests")
        fig2.y_range = Range1d(fig2_min, fig2_max)

        fig2.add_layout(
            LinearAxis(y_range_name="y2", axis_label="Positive tests %"), "right"
        )

        fig2_sec_min, fig2_sec_max = self.calc_axis_min_max(
            "test_pos_percentage_smoothed"
        )

        fig2.extra_y_ranges = {"y2": Range1d(fig2_sec_min, fig2_sec_max)}

        glyph = fig2.varea(
            x="idx",
            y1="zero",
            y2="tests",
            source=source,
            # color='grey',
            legend_label="Tests",
            # line_dash=[3, 6],
            alpha=low_alpha,
            # name=column
        )

        glyph = fig2.line(
            x="idx",
            y="test_pos_percentage",
            source=source,
            color="violet",
            # line_dash=[3, 6],
            alpha=low_alpha,
            # name=column,
            y_range_name="y2",
        )

        glyph = fig2.line(
            x="idx",
            y="test_pos_percentage_smoothed",
            source=source,
            color="violet",
            legend_label="Positive tests % smoothed (right)",
            # line_dash=[3, 6],
            alpha=1,
            # name=column,
            y_range_name="y2",
        )

        fig3 = bokeh.plotting.figure(
            title="Vaccinations",
            x_axis_type="datetime",
            x_range=fig0.x_range,
            aspect_ratio=aspect,
            y_axis_label="Tenthousand doses\nper day",
        )

        fig3_min, fig3_max = self.calc_axis_min_max("doses_per_day")
        fig3.y_range = Range1d(fig3_min, fig3_max)

        fig3.add_layout(
            LinearAxis(y_range_name="y2", axis_label="Million doses\nadministered"),
            "right",
        )

        fig3_sec_min, fig3_sec_max = self.calc_axis_min_max(
            "doses_administered_cumulative"
        )

        fig3.extra_y_ranges = {"y2": Range1d(fig3_sec_min, fig3_sec_max)}
        fig3.yaxis.formatter = BasicTickFormatter(use_scientific=False)
        fig3.xaxis.visible = False

        glyph = fig3.varea(
            x="idx",
            y1="zero",
            y2="doses_per_day",
            source=source,
            # color='gray',
            legend_label="Doses per day",
            # line_dash=[3, 6],
            alpha=low_alpha,
            # name=column
        )

        glyph = fig3.line(
            x="idx",
            y="doses_administered_cumulative",
            source=source,
            color="green",
            legend_label="Accumulated doses (right)",
            # line_dash=[3, 6],
            alpha=1,
            # name=column
            y_range_name="y2",
        )

        glyph = fig3.line(
            x="idx",
            y="first_doses",
            source=source,
            color="red",
            legend_label="First doses (right)",
            # line_dash=[3, 6],
            alpha=1,
            # name=column
            y_range_name="y2",
        )

        glyph = fig3.line(
            x="idx",
            y="second_doses",
            source=source,
            color="orange",
            legend_label="Second doses (right)",
            # line_dash=[3, 6],
            alpha=1,
            # name=column
            y_range_name="y2",
        )

        glyph = fig3.line(
            x="idx",
            y="third_doses",
            source=source,
            color="cyan",
            legend_label="Third doses (right)",
            # line_dash=[3, 6],
            alpha=1,
            # name=column
            y_range_name="y2",
        )

        fig4 = plotting.figure(
            title="Hospitalization",
            x_axis_type="datetime",
            x_range=fig0.x_range,
            aspect_ratio=aspect,
            y_axis_label="Patients hospitalized",
        )

        fig4_min, fig4_max = self.calc_axis_min_max("hospitalizations")
        fig4.y_range = Range1d(fig4_min, fig4_max)

        fig4.add_layout(
            LinearAxis(y_range_name="y2", axis_label="Patients in ICU"), "right"
        )

        fig4_sec_min, fig4_sec_max = self.calc_axis_min_max("ICU")

        fig4.extra_y_ranges = {"y2": Range1d(fig4_sec_min, fig4_sec_max)}
        fig4.yaxis.formatter = BasicTickFormatter(use_scientific=False)

        glyph = fig4.line(
            x="idx",
            y="hospitalizations",
            source=source,
            color="brown",
            legend_label="Hospitalizations",
            # line_dash=[3, 6],
            alpha=1,
            # name=column
        )

        glyph = fig4.line(
            x="idx",
            y="ICU",
            source=source,
            color="aquamarine",
            legend_label="ICU patients (right)",
            # line_dash=[3, 6],
            alpha=1,
            # name=column
            y_range_name="y2",
        )

        plot = bokeh.layouts.gridplot(
            [[fig0], [fig1], [fig2], [fig3], [fig4]], sizing_mode="scale_width"
        )

        plotting.show(plot)

    def run(self):
        self.prepare_data()
        self.vac_vs_infection_plot()


def main():
    plot = OpenDataPlot()
    plot.run()


if __name__ == "__main__":
    main()
