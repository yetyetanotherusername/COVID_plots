import io

import plotly.graph_objects as go
import polars as pl
import requests
from plotly.subplots import make_subplots
from scipy.stats import gmean

requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = "ALL:@SECLEVEL=1"


class OpenDataPlot:
    def __init__(self):
        self.load_open_data()

    def load_open_data(self):
        gv = "https://opendata.sozialversicherung.at/eimpfpass/"
        open_data_url = "https://covid19-dashboard.ages.at/data/"

        self.covid_numbers = self.url_to_df(open_data_url + "CovidFaelle_Timeline.csv")
        self.hospitalizations = self.url_to_df(open_data_url + "Hospitalisierung.csv")
        self.vaccination_timeseries = self.url_to_df(
            gv + "COVID19_vaccination_timeline_v202210.csv"
        )

    def url_to_df(self, url):
        return self.parse_csv(self.download_csv(url))

    def parse_csv(self, csv):
        return pl.read_csv(csv, separator=";")

    def download_csv(self, url):
        req = requests.get(url).content
        return io.StringIO(req.decode("utf-8"))

    def prepare_data(self):
        frame = self.covid_numbers.lazy()
        plot_frame = (
            frame.filter(pl.col("Bundesland") == "Österreich")
            .with_columns(
                pl.col("Time").str.strptime(pl.Datetime, format="%d.%m.%Y %H:%M:%S")
            )
            .select(["Time", "AnzahlFaelle", "AnzahlTotTaeglich"])
            .rename({"AnzahlTotTaeglich": "deaths", "AnzahlFaelle": "pos_cases"})
            .sort("Time")
        )

        tests = (
            self.hospitalizations.lazy()
            .filter(pl.col("Bundesland") == "Österreich")
            .with_columns(
                pl.col("Meldedatum").str.strptime(
                    pl.Datetime, format="%d.%m.%Y %H:%M:%S"
                )
            )
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
            .sort("Time")
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
            self.vaccination_timeseries.lazy()
            .filter(pl.col("state_name") == "Österreich")
            .with_columns(
                pl.col("date")
                .str.replace("[+|-][0-9]{2}:[0-9]{2}", "")
                .str.strptime(pl.Datetime, format="%Y-%m-%dT%H:%M:%S")
                .dt.round("1d")
            )
            .sort(["date", "vaccination"])
            .drop(["state_name", "state_id"])
            .collect()
            .pivot(
                values="vaccinations_administered_cumulative",
                index="date",
                columns="vaccination",
                aggregate_function="sum",
            )
            .lazy()
        )

        vac_frame = (
            vac_frame.with_columns(
                vac_frame.drop("date")
                .collect()
                .sum(axis=1)
                .alias("vaccinations_administered_cumulative")
            )
            .rename(
                {
                    "1": "first_doses",
                    "2": "second_doses",
                    "3": "third_doses",
                    "4+": "four_or_more_doses",
                }
            )
            .with_columns(
                pl.col("vaccinations_administered_cumulative")
                .diff()
                .alias("doses_per_day")
            )
        )

        plot_frame = (
            plot_frame.join(vac_frame, left_on="Time", right_on="date", how="outer")
            .rename({"Time": "idx"})
            .with_columns(
                [
                    pl.col("pos_cases").rolling_mean(7, center=True).alias("7d_mean"),
                    pl.col("deaths")
                    .rolling_mean(7, center=True)
                    .alias("7d_mean_deaths"),
                ]
            )
            .with_columns(
                [
                    (pl.col("7d_mean") / pl.col("7d_mean").shift()).alias("rel_change"),
                    (pl.col("7d_mean_deaths") / pl.col("7d_mean_deaths").shift()).alias(
                        "rel_change_deaths"
                    ),
                ]
            )
            .with_columns(
                [
                    pl.col("rel_change")
                    .rolling_apply(gmean, 7, center=True)
                    .alias("change_smoothed"),
                    pl.col("rel_change_deaths")
                    .rolling_apply(gmean, 7, center=True)
                    .alias("change_deaths_smoothed"),
                ]
            )
        )

        plot_frame = plot_frame.with_columns(
            pl.when(pl.col("tests") < 1)
            .then(None)
            .otherwise(pl.col("tests"))
            .interpolate()
            .keep_name()
        )

        plot_frame = plot_frame.with_columns(
            [
                (pl.col("rel_change") - 1) * 100,
                (pl.col("rel_change_deaths") - 1) * 100,
                (pl.col("change_smoothed") - 1) * 100,
                (pl.col("change_deaths_smoothed") - 1) * 100,
                pl.lit(0.0).alias("zero"),
                (pl.col("pos_cases") / pl.col("tests") * 100).alias(
                    "test_pos_percentage"
                ),
            ]
        )

        plot_frame = plot_frame.with_columns(
            pl.when(pl.col("test_pos_percentage").is_infinite())
            .then(None)
            .otherwise(pl.col("test_pos_percentage"))
            .keep_name()
        )

        plot_frame = plot_frame.with_columns(
            pl.col("test_pos_percentage")
            .rolling_mean(7, center=True)
            .alias("test_pos_percentage_smoothed")
        )

        self.plot_frame = plot_frame.collect()

    def vac_vs_infection_plot(self):
        low_opacity = 0.3

        fig = make_subplots(
            rows=5,
            cols=1,
            shared_xaxes=True,
            subplot_titles=[
                "Infection numbers relative change in %",
                "Daily view",
                "Tests",
                "Vaccinations",
                "Hospitalizations",
            ],
            specs=[
                [{"secondary_y": False}],
                [{"secondary_y": True}],
                [{"secondary_y": True}],
                [{"secondary_y": True}],
                [{"secondary_y": True}],
            ],
        )

        fig.update_layout(
            title_text="COVID-19 Austria open data plot", template="plotly_dark"
        )

        fig.add_traces(
            [
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("rel_change").to_series(),
                    opacity=low_opacity,
                    line=dict(width=1, color="white"),
                    name="Relative change",
                ),
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("rel_change_deaths").to_series(),
                    opacity=low_opacity,
                    line=dict(width=1, color="teal"),
                    name="Relative change of deaths",
                ),
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("change_smoothed").to_series(),
                    line=dict(width=1, color="white"),
                    name="Relative change smoothed",
                ),
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("change_deaths_smoothed").to_series(),
                    line=dict(width=1, color="teal"),
                    name="Relative change of deaths smoothed",
                ),
            ],
            rows=1,
            cols=1,
        )
        fig.add_hline(y=0, row=1, col=1, line=dict(width=1), opacity=0.7)
        fig.update_layout(yaxis1=dict(range=[-16, 16]))

        fig.add_traces(
            [
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("pos_cases").to_series(),
                    opacity=low_opacity,
                    line=dict(width=1, color="#ff7f0e"),
                    name="Positive cases",
                ),
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("7d_mean").to_series(),
                    line=dict(width=1, color="#ff7f0e"),
                    name="Positive cases smoothed",
                ),
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("deaths").to_series(),
                    opacity=low_opacity,
                    line=dict(width=1, color="#d62728"),
                    name="Deaths",
                ),
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("7d_mean_deaths").to_series(),
                    line=dict(width=1, color="#d62728"),
                    name="Deaths smoothed",
                ),
            ],
            secondary_ys=[False, False, True, True],
            rows=2,
            cols=1,
        )

        fig.add_traces(
            [
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("tests").to_series(),
                    line=dict(width=1, color="#1f77b4"),
                    name="Tests",
                    fill="tozeroy",
                ),
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("test_pos_percentage").to_series(),
                    opacity=low_opacity,
                    line=dict(width=1, color="#e377c2"),
                    name="Test positive percentage",
                ),
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select(
                        "test_pos_percentage_smoothed"
                    ).to_series(),
                    line=dict(width=1, color="#e377c2"),
                    name="Test positive percentage smoothed",
                ),
            ],
            secondary_ys=[False, True, True],
            rows=3,
            cols=1,
        )

        fig.add_traces(
            [
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("doses_per_day").to_series(),
                    line=dict(width=1, color="#1f77b4"),
                    name="Doses administered per day",
                    fill="tozeroy",
                ),
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("first_doses").to_series(),
                    line=dict(width=1, color="#ff7f0e"),
                    name="First doses administered",
                ),
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("second_doses").to_series(),
                    line=dict(width=1, color="#2ca02c"),
                    name="Second doses administered",
                ),
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("third_doses").to_series(),
                    line=dict(width=1, color="#d62728"),
                    name="Third doses administered",
                ),
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("four_or_more_doses").to_series(),
                    line=dict(width=1, color="#9467bd"),
                    name="Fourth or more doses administered",
                ),
            ],
            secondary_ys=[False, True, True, True, True, True],
            rows=4,
            cols=1,
        )

        fig.add_traces(
            [
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("hospitalizations").to_series(),
                    line=dict(width=1, color="#8c564b"),
                    name="Patients hospitalized",
                ),
                go.Scatter(
                    x=self.plot_frame.select("idx").to_series(),
                    y=self.plot_frame.select("ICU").to_series(),
                    line=dict(width=1, color="#17becf"),
                    name="Patients in intensive care",
                ),
            ],
            secondary_ys=[False, True],
            rows=5,
            cols=1,
        )

        fig.show()

    def run(self):
        self.prepare_data()
        self.vac_vs_infection_plot()


def main():
    plot = OpenDataPlot()
    plot.run()


if __name__ == "__main__":
    main()
