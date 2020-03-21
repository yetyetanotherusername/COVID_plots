import os
import pandas as pd
import matplotlib.pyplot as plt
from cycler import cycler
import geopandas as gp
import shapely

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

        confirmed.plot()
        plt.grid()
        plt.savefig(os.path.join('figures', 'simple_plot.png'), dpi=300)

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
        ax = transformed.plot(logy=True, marker='o', markersize=2, alpha=0.7)
        reference.plot(ax=ax, style='--', colormap='winter', alpha=0.7)
        plt.grid()
        plt.title('COVID-19 cases per country' + self.data_disclaimer)
        plt.xlabel('Days since more than 100 cases')
        plt.ylabel('Accumulated positive cases')
        plt.savefig(os.path.join('figures', 'shifted.png'), dpi=300)

    def totals_plot(self, countries=None):
        total_df = self.calc_totals(countries)

        total_df['currently_sick'] = (
            total_df.confirmed - total_df.deaths - total_df.recovered
        )

        total_df = total_df.drop('confirmed', axis=1)

        total_df.plot.area(alpha=0.6)
        plt.grid()
        c_string = self.countries_to_string(countries)
        plt.title(f'Total COVID-19 numbers, {c_string}' + self.data_disclaimer)
        plt.ylabel('Number of individuals affected (stacked)')
        plt.savefig(os.path.join('figures', 'totals.png'), dpi=300)

    def rate_plot(self, countries=None):
        total_df = self.calc_totals(countries)

        plot_df = pd.DataFrame()

        plot_df['confirmed'] = total_df.confirmed.diff()
        plot_df['deaths'] = total_df.deaths.diff().clip(lower=0)
        plot_df['recovered'] = total_df.recovered.diff().clip(lower=0)

        plot_df.plot.area(stacked=False)
        plt.grid()
        c_string = self.countries_to_string(countries)
        plt.title(f'{c_string} daily COVID-19 cases' + self.data_disclaimer)
        plt.ylabel('Number of newly affected individuals per day')
        plt.savefig(os.path.join('figures', 'rates.png'), dpi=300)

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
