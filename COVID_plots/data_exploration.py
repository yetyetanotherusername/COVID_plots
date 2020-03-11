import os
import pandas as pd
import matplotlib.pyplot as plt
from cycler import cycler

plt.style.use('dark_background')
plt.rcParams['axes.prop_cycle'] = cycler(
    color=[u'#1f77b4', u'#ff7f0e', u'#2ca02c', u'#d62728', u'#9467bd',
           u'#8c564b', u'#e377c2', u'#7f7f7f', u'#bcbd22', u'#17becf'])


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

    def simple_plot(self):
        confirmed = self.confirmed_df.loc[
            :, (['Germany', 'Austria', 'Italy'],
                slice(None), slice(None), slice(None))]
        confirmed.plot(logy=True)
        plt.grid()

    def run(self):
        self.simple_plot()
        plt.show()


def main():
    plot = CovidPlot()
    plot.run()


if __name__ == '__main__':
    main()
