import io
from datetime import datetime

import bokeh
import polars as pl
import requests
from bokeh import plotting
from bokeh.io import curdoc
from bokeh.models import BasicTickFormatter, LinearAxis, Range1d, Title
from bokeh.themes import Theme
from COVID_plots.themes.dark_minimal_adapted import json as jt
from scipy.stats import gmean

requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = "ALL:@SECLEVEL=1"

curdoc().theme = Theme(json=jt)


class OpenDataPlot:
    def __init__(self):
        self.load_open_data()

    def load_open_data(self):
        base_url = "https://info.gesundheitsministerium.gv.at/data/"
        open_data_url = "https://covid19-dashboard.ages.at/data/"

        self.vaccination_timeseries = self.url_to_df(
            base_url + "COVID19_vaccination_doses_timeline_v202206.csv"
        )

        self.covid_numbers = self.url_to_df(open_data_url + "CovidFaelle_Timeline.csv")

        self.hospitalizations = self.url_to_df(open_data_url + "Hospitalisierung.csv")

    def url_to_df(self, url):
        return self.parse_csv(self.download_csv(url))

    def parse_csv(self, csv):
        return pl.read_csv(csv, sep=";")

    def download_csv(self, url):
        req = requests.get(url).content
        return io.StringIO(req.decode("utf-8"))

    def prepare_data(self):
        frame = self.covid_numbers
        frame = frame.with_column(
            pl.col("Time").str.strptime(pl.Datetime, fmt="%d.%m.%Y %H:%M:%S")
        ).sort(["Bundesland", "Time"])

        plot_frame = (
            frame.filter(pl.col("Bundesland") == "Österreich")
            .select(["Time", "AnzahlFaelle", "AnzahlTotTaeglich"])
            .rename({"AnzahlTotTaeglich": "deaths", "AnzahlFaelle": "pos_cases"})
        )

        plot_frame = plot_frame.with_columns(
            [
                pl.when(
                    pl.col("Time").is_between(
                        datetime(2022, 4, 21),
                        datetime(2022, 4, 23),
                        include_bounds=True,
                    )
                )
                .then(
                    plot_frame.filter(
                        pl.col("Time") == datetime(2022, 4, 20)
                    ).get_column("deaths")
                )
                .otherwise(pl.col("deaths"))
                .alias("deaths"),
                pl.when(pl.col("Time") == datetime(2022, 5, 23))
                .then(
                    plot_frame.filter(
                        pl.col("Time") == datetime(2022, 5, 22)
                    ).get_column("deaths")
                )
                .otherwise(pl.col("deaths"))
                .alias("deaths"),
            ]
        )

        hframe = self.hospitalizations
        hframe = hframe.with_column(
            pl.col("Meldedatum").str.strptime(pl.Datetime, fmt="%d.%m.%Y %H:%M:%S")
        ).sort(["Bundesland", "Meldedatum"])

        tests = (
            hframe.filter(pl.col("Bundesland") == "Österreich")
            .select(
                [
                    "Meldedatum",
                    "TestGesamt",
                    "NormalBettenBelCovid19",
                    "IntensivBettenBelCovid19",
                ]
            )
            .rename(
                {
                    "Meldedatum": "Time",
                    "TestGesamt": "tests",
                    "NormalBettenBelCovid19": "hospitalizations",
                    "IntensivBettenBelCovid19": "ICU",
                }
            )
        )

        plot_frame = plot_frame.join(
            other=tests, left_on="Time", right_on="Time", how="outer"
        ).with_columns(
            [
                pl.col("tests").diff(),
                pl.col("hospitalizations"),
                pl.col("ICU"),
            ]
        )

        vac_frame = (
            self.vaccination_timeseries.with_columns(
                pl.col("date")
                .str.strptime(pl.Datetime, fmt="%Y-%m-%dT%H:%M:%S%z")
                .dt.truncate("1d")
            )
            .filter(pl.col("state_name") == "Österreich")
            .sort(["date", "dose_number"])
            .drop(["state_name", "state_id"])
            .pivot(
                values="doses_administered_cumulative",
                index="date",
                columns="dose_number",
                aggregate_fn="sum",
            )
        )

        vac_frame = vac_frame.with_column(
            vac_frame.drop("date").sum(axis=1).alias("doses_administered_cumulative")
        ).rename(
            {
                "1": "first_doses",
                "2": "second_doses",
                "3": "third_doses",
                "4": "fourth_doses",
                "5+": "five+_doses",
            }
        )

        vac_frame = vac_frame.with_column(
            pl.col("doses_administered_cumulative").diff().alias("doses_per_day")
        )

        plot_frame = plot_frame.join(
            vac_frame, left_on="Time", right_on="date", how="outer"
        ).rename({"Time": "idx"})

        plot_frame = pl.concat(
            [plot_frame.select(pl.col("idx")), plot_frame.drop("idx")],
            how="horizontal",
        )

        plot_frame = plot_frame.with_columns(
            [
                pl.col("pos_cases").rolling_mean(7, center=True).alias("7d_mean"),
                pl.col("deaths").rolling_mean(7, center=True).alias("7d_mean_deaths"),
            ]
        )

        plot_frame = plot_frame.with_column(
            (pl.col("7d_mean") / pl.col("7d_mean").shift()).alias("rel_change")
        ).with_column(
            pl.col("rel_change")
            .rolling_apply(gmean, 7, center=True)
            .alias("change_smoothed")
        )

        plot_frame = plot_frame.with_columns(
            [
                (pl.col("rel_change") - 1) * 100,
                (pl.col("change_smoothed") - 1) * 100,
                pl.lit(0.0).alias("zero"),
                (pl.col("pos_cases") / pl.col("tests") * 100).alias(
                    "test_pos_percentage"
                ),
            ]
        )

        plot_frame = plot_frame.with_column(
            pl.when(pl.col("test_pos_percentage").is_infinite())
            .then(pl.lit(float("nan")))
            .otherwise(pl.col("test_pos_percentage"))
            .keep_name()
        )

        plot_frame = plot_frame.with_columns(
            [
                pl.col("test_pos_percentage")
                .rolling_mean(7, center=True)
                .alias("test_pos_percentage_smoothed"),
                pl.col("tests") / 10**6,
                pl.col("doses_per_day") / 10**4,
                pl.col("doses_administered_cumulative") / 10**6,
                pl.col("doses_per_day") / 10**5,
                pl.col("first_doses") / 10**6,
                pl.col("second_doses") / 10**6,
                pl.col("third_doses") / 10**6,
                pl.col("fourth_doses") / 10**6,
                pl.col("five+_doses") / 10**6,
            ]
        )

        self.plot_frame = plot_frame.to_pandas().set_index("idx")

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
            y_axis_label="Million tests per day",
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

        glyph = fig3.line(
            x="idx",
            y="fourth_doses",
            source=source,
            color="white",
            legend_label="Fourth doses (right)",
            # line_dash=[3, 6],
            alpha=1,
            # name=column
            y_range_name="y2",
        )

        glyph = fig3.line(
            x="idx",
            y="five+_doses",
            source=source,
            color="orange",
            legend_label="Fifth or higher doses (right)",
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
