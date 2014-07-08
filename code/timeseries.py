"""This file contains code for use with "Think Stats",
by Allen B. Downey, available from greenteapress.com

Copyright 2014 Allen B. Downey
License: GNU GPLv3 http://www.gnu.org/licenses/gpl.html
"""

from __future__ import print_function

import pandas
import datetime
import numpy as np
import statsmodels.formula.api as smf
import statsmodels.tsa.stattools as smtsa
import itertools

import matplotlib.pyplot as pyplot

import thinkplot
import thinkstats2
import regression

from pandas.tools.plotting import autocorrelation_plot


def ReadData():
    """Reads data about cannabis transactions.

    http://zmjones.com/static/data/mj-clean.csv

    returns: DataFrame
    """
    transactions = pandas.read_csv('mj-clean.csv', parse_dates=[5])
    return transactions


def tmean(series):
    """Computes a trimmed mean.

    series: Series 

    returns: float
    """
    t = series.values
    n = len(t)
    if n <= 3:
        return t.mean()
    trim = max(1, n/10)
    return np.mean(sorted(t)[trim:n-trim])


def GroupByDay(transactions, func=np.mean):
    """Groups transactions by day and compute the daily mean ppg.

    transactions: DataFrame of transactions

    returns: DataFrame of daily prices
    """
    groups = transactions[['date', 'ppg']].groupby('date')
    daily = groups.aggregate(func)

    daily['date'] = daily.index
    start = daily.date[0]
    one_year = np.timedelta64(1, 'Y')
    daily['years'] = (daily.date - start) / one_year

    return daily


def GroupByQualityAndDay(transactions):
    """Divides transactions by quality and computes mean daily price.

    transaction: DataFrame of transactions
    
    returns: map from quality to time series of ppg
    """
    groups = transactions.groupby('quality')
    dailies = {}
    for name, group in groups:
        dailies[name] = GroupByDay(group)        

    return dailies


def PlotDailies(dailies):
    """Makes a plot with daily prices for different qualities.

    dailies: map from name to DataFrame
    """
    thinkplot.PrePlot(rows=3)
    for i, (name, daily) in enumerate(dailies.items()):
        thinkplot.SubPlot(i+1)
        title = 'price per gram ($)' if i==0 else ''
        thinkplot.Config(ylim=[0, 20], title=title)
        thinkplot.Scatter(daily.ppg, s=10, label=name)
        if i == 2: 
            pyplot.xticks(rotation=30)
        else:
            thinkplot.Config(xticks=[])

    thinkplot.Save(root='timeseries1')


def RunLinearModel(daily):
    """Runs a linear model of prices versus years.

    daily: DataFrame of daily prices

    returns: model, results
    """
    model = smf.ols('ppg ~ years', data=daily)
    results = model.fit()
    return model, results


def RunQuadraticModel(daily):
    """Runs a linear model of prices versus years.

    daily: DataFrame of daily prices

    returns: model, results
    """
    daily['years2'] = daily.years**2
    model = smf.ols('ppg ~ years + years2', data=daily)
    results = model.fit()
    return model, results


def PlotFittedValues(model, results, label=''):
    """Plots original data and fitted values.

    model: StatsModel model object
    results: StatsModel results object
    """
    years = model.exog[:,1]
    values = model.endog
    thinkplot.Scatter(years, values, s=15, label=label)
    thinkplot.Plot(years, results.fittedvalues, label='model')


def PlotResiduals(model, results):
    """Plots the residuals of a model.

    model: StatsModel model object
    results: StatsModel results object    
    """
    years = model.exog[:,1]
    thinkplot.Plot(years, results.resid, linewidth=0.5, alpha=0.5)


def PlotResidualPercentiles(model, results, index=1, num_bins=20):
    """Plots percentiles of the residuals.

    model: StatsModel model object
    results: StatsModel results object
    index: which exogenous variable to use
    num_bins: how many bins to divide the x-axis into
    """
    exog = model.exog[:,index]
    resid = results.resid.values
    df = pandas.DataFrame(dict(exog=exog, resid=resid))

    bins = np.linspace(np.min(exog), np.max(exog), num_bins)
    indices = np.digitize(exog, bins)
    groups = df.groupby(indices)

    means = [group.exog.mean() for _, group in groups][1:-1]
    cdfs = [thinkstats2.Cdf(group.resid) for _, group in groups][1:-1]

    thinkplot.PrePlot(3)
    for percent in [75, 50, 25]:
        percentiles = [cdf.Percentile(percent) for cdf in cdfs]
        label = '%dth' % percent
        thinkplot.Plot(means, percentiles, label=label)


def SimulateResults(daily, iters=101, func=RunLinearModel):
    """Run simulations based on resampling residuals.

    daily: DataFrame of daily prices
    iters: number of simulations
    func: function that fits a model to the data

    returns: list of result objects
    """
    model, results = func(daily)
    fake = daily.copy()
    
    result_seq = []
    for i in range(iters):
        fake.ppg = results.fittedvalues + thinkstats2.Resample(results.resid)
        _, fake_results = func(fake)
        result_seq.append(fake_results)

    return result_seq


def GeneratePredictions(result_seq, years, add_resid=False):
    """Generates an array of predicted values from a list of model results.

    When add_resid is False, predictions represent sampling error only.

    When add_resid is True, they also include residual error (which is
    more relevant to prediction).
    
    result_seq: list of model results
    years: sequence of times (in years) to make predictions for
    add_resid: boolean, whether to add in resampled residuals

    returns: array with one row per model result, one column per timestep
    """
    n = len(years)
    inter = np.ones(n)
    predict_df = pandas.DataFrame(dict(Intercept=inter, 
                                       years=years, years2=years**2))
    
    size = len(result_seq), n
    array = np.zeros(size)

    for i, fake_results in enumerate(result_seq):
        predict = fake_results.predict(predict_df)
        if add_resid:
            predict += np.random.choice(fake_results.resid.values, n, 
                                        replace=True)
        array[i,] = predict

    array = np.sort(array, axis=0)
    return array


def GenerateSimplePrediction(results, years):
    """Generates a simple prediction.

    results: results object
    years: sequence of times (in years) to make predictions for

    returns: sequence of predicted values
    """
    n = len(years)
    inter = np.ones(n)
    d = dict(Intercept=inter, years=years, years2=years**2)
    predict_df = pandas.DataFrame(d)
    predict = results.predict(predict_df)
    return predict


def PercentileRow(array, p):
    """Selects the row from a sorted array that maps to percentile p.

    p: float 0--100

    returns: NumPy array (one row)
    """
    rows, cols = array.shape
    index = int(rows * p / 100)
    return array[index,]


def PlotPredictions(daily, years, iters=101, percent=90, func=RunLinearModel):
    """Plots actual data and predictions.

    daily: DataFrame of daily prices
    years: sequence of times (in years) to make predictions for
    iters: number of simulations
    percent: what percentile range to show
    func: function that fits a model to the data
    """
    thinkplot.Scatter(daily.years, daily.ppg, alpha=0.1)

    result_seq = SimulateResults(daily, iters=iters, func=func)
    p = (100 - percent) / 2

    predictions = GeneratePredictions(result_seq, years, add_resid=True)
    low = PercentileRow(predictions, p)
    high = PercentileRow(predictions, 100-p)
    thinkplot.FillBetween(years, low, high, alpha=0.3, color='gray')

    predictions = GeneratePredictions(result_seq, years, add_resid=False)
    low = PercentileRow(predictions, p)
    high = PercentileRow(predictions, 100-p)
    thinkplot.FillBetween(years, low, high, alpha=0.5, color='gray')


def PlotWindows():
    """Makes a plot showing the shapes of windows for rolling means.

    """
    import scipy.signal as sig
    gaussian = sig.get_window(('gaussian', 7.5), 30)
    gaussian_mean = gaussian.mean()
    gaussian /= gaussian.mean()
    thinkplot.Plot(gaussian)

    boxcar = sig.get_window('boxcar', 30)
    boxcar_mean = boxcar.mean()
    boxcar /= boxcar.mean()
    thinkplot.Plot(boxcar)

    triangle = sig.get_window('triangle', 30)
    triangle_mean = triangle.mean()
    triangle /= triangle.mean()
    thinkplot.Plot(triangle)


def Correlate(dailies):
    """Compute the correlation matrix between prices for difference qualities.

    dailies: map from quality to time series of ppg

    returns: correlation matrix
    """
    df = pandas.DataFrame()
    for name, daily in dailies.items():
        df[name] = daily.ppg

    return df.corr()
        

def CorrelateResid(dailies):
    """Compute the correlation matrix between residuals.

    dailies: map from quality to time series of ppg

    returns: correlation matrix
    """
    df = pandas.DataFrame()
    for name, daily in dailies.items():
        model, results = RunLinearModel(daily)
        df[name] = results.resid

    return df.corr()


def TestCorrelateResid(dailies, iters=101):
    """Tests observed correlations.

    dailies: map from quality to time series of ppg
    iters: number of simulations
    """

    t = []
    names = ['high', 'medium', 'low']
    for name in names:
        daily = dailies[name]
        t.append(SimulateResults(daily, iters=iters))

    corr = CorrelateResid(dailies)

    arrays = []
    for result_seq in zip(*t):
        df = pandas.DataFrame()
        for name, results in zip(names, result_seq):
            df[name] = results.resid

        opp_sign = corr * df.corr() < 0
        arrays.append((opp_sign.astype(int)))

    print(np.sum(arrays))


def RunModels(dailies):
    """Runs linear regression for each group in dailies.

    dailies: map from group name to DataFrame
    """
    rows = []
    for name, daily in dailies.items():
        model, results = RunLinearModel(daily)
        intercept, slope = results.params
        p1, p2 = results.pvalues
        r2 = results.rsquared
        s = r'%0.3f (%0.2g) & %0.3f (%0.2g) & %0.3f \\'
        row = s % (intercept, p1, slope, p2, r2)
        rows.append(row)

    # print results in a LaTeX table
    print(r'\begin{tabular}{|c|c|c|}')
    print(r'\hline')
    print(r'intercept & slope & $R^2$ \\ \hline')
    for row in rows:
        print(row)
    print(r'\hline')
    print(r'\end{tabular}')


def FillMissing(daily, span=30):
    """Fills missing values with an exponentially weighted moving average.

    Resulting DataFrame has new columns 'ewma' and 'resid'.

    daily: DataFrame of daily prices
    span: window size (sort of) passed to ewma

    returns: new DataFrame of daily prices
    """
    dates = pandas.date_range(daily.index.min(), daily.index.max())
    reindexed = daily.reindex(dates)

    ewma = pandas.ewma(reindexed.ppg, span=span)

    resid = (reindexed.ppg - ewma).dropna()
    fake_data = ewma + thinkstats2.Resample(resid, len(reindexed))
    reindexed.ppg.fillna(fake_data, inplace=True)

    reindexed['ewma'] = ewma
    reindexed['resid'] = reindexed.ppg - ewma
    return reindexed


def AddWeeklySeasonality(daily):
    """Adds a weekly pattern.

    daily: DataFrame of daily prices

    returns: new DataFrame of daily prices
    """
    frisat = (daily.index.dayofweek==4) | (daily.index.dayofweek==5)
    fake = daily.copy()
    fake.ppg[frisat] += np.random.uniform(2, 4, frisat.sum())
    return fake


def PrintSerialCorrelations(dailies):
    """
    """
    filled = {}
    for name, daily in dailies.items():
        filled[name] = FillMissing(daily, span=30)

    rows = []
    for lag in [1, 7, 30, 365]:
        row = [str(lag)]
        for name, daily in filled.items():            
            corr = SerialCorrelation(daily.resid, lag)
            row.append('%.2g' % corr)
        rows.append(row)

    print(r'\begin{tabular}{|c|c|c|c|}')
    print(r'\hline')
    print(r'lag & high & medium & low \\ \hline')
    for row in rows:
        print(' & '.join(row) + r' \\')
    print(r'\hline')
    print(r'\end{tabular}')

    daily = filled['high']
    acf = smtsa.acf(daily.resid, nlags=365, unbiased=True)
    print('%0.3f, %0.3f, %0.3f, %0.3f, %0.3f' % 
          (acf[0], acf[1], acf[7], acf[30], acf[365]))


def SerialCorrelation(series, lag=1):
    """Computes the serial correlation of a series.

    series: Series
    lag: integer number of intervals to shift

    returns: float correlation
    """
    xs = series[lag:]
    ys = series.shift(lag)[lag:]
    corr = thinkstats2.Corr(xs, ys)
    return corr


def SimulateAutocorrelation(daily, iters=1001, nlags=40):
    # run simulations
    t = []
    for i in range(iters):
        filled = FillMissing(daily, span=30)
        resid = thinkstats2.Resample(filled.resid)
        acf = smtsa.acf(resid, nlags=nlags, unbiased=True)[1:]
        t.append(np.abs(acf))

    # put the results in an array and sort the columns
    size = iters, len(acf)
    array = np.zeros(size)
    for i, acf in enumerate(t):
        array[i,] = acf
    array = np.sort(array, axis=0)

    # find the bounds that cover 95% of the distribution
    high = PercentileRow(array, 97.5)
    low = -high
    lags = range(1, nlags+1)
    thinkplot.FillBetween(lags, low, high, alpha=0.2, color='gray')


def PlotAutoCorrelation(dailies, nlags=40, add_weekly=False):
    """
    """
    thinkplot.PrePlot(3)
    daily = dailies['high']
    SimulateAutocorrelation(daily)

    for name, daily in dailies.items():

        if add_weekly:
            daily = AddWeeklySeasonality(daily)

        filled = FillMissing(daily, span=30)

        acf = smtsa.acf(filled.resid, nlags=nlags, unbiased=True)
        lags = np.arange(len(acf))
        thinkplot.Plot(lags[1:], acf[1:], label=name)


def MakeAcfPlot(dailies):
    axis = [0, 41, -0.2, 0.2]

    thinkplot.PrePlot(cols=2)
    PlotAutoCorrelation(dailies, add_weekly=False)
    thinkplot.Config(axis=axis, 
                     loc='lower right',
                     ylabel='correlation',
                     xlabel='lag (day)')

    thinkplot.SubPlot(2)
    PlotAutoCorrelation(dailies, add_weekly=True)
    thinkplot.Save(root='timeseries9',
                   axis=axis,
                   loc='lower right',
                   xlabel='lag (days)')


def PlotRollingMean(daily, name):
    """Plots rolling mean and EWMA.

    daily: DataFrame of daily prices
    """
    dates = pandas.date_range(daily.index.min(), daily.index.max())
    reindexed = daily.reindex(dates)

    thinkplot.PrePlot(cols=2)
    thinkplot.Scatter(reindexed.ppg, s=15, alpha=0.1, label=name)
    roll_mean = pandas.rolling_mean(reindexed.ppg, 30)
    thinkplot.Plot(roll_mean, label='rolling mean')
    pyplot.xticks(rotation=30)
    thinkplot.Config(ylabel='price per gram ($)')

    thinkplot.SubPlot(2)
    thinkplot.Scatter(reindexed.ppg, s=15, alpha=0.1, label=name)
    ewma = pandas.ewma(reindexed.ppg, span=30)
    thinkplot.Plot(ewma, label='EWMA')
    pyplot.xticks(rotation=30)
    thinkplot.Save(root='timeseries10')


def PlotFilled(daily, name):
    """Plots the EWMA and filled data.

    daily: DataFrame of daily prices
    """
    filled = FillMissing(daily, span=30)
    thinkplot.Scatter(filled.ppg, s=15, alpha=0.3, label=name)
    thinkplot.Plot(filled.ewma, label='EWMA', alpha=0.4)
    pyplot.xticks(rotation=30)
    thinkplot.Save(root='timeseries8',
                   ylabel='price per gram ($)')
    

def PlotLinearModel(daily, name):
    """
    """
    model, results = RunLinearModel(daily)
    PlotFittedValues(model, results, label=name)
    thinkplot.Save(root='timeseries2',
                   title='fitted values',
                   xlabel='years',
                   xlim=[-0.1, 3.8],
                   ylabel='price per gram ($)')

    PlotResidualPercentiles(model, results)
    thinkplot.Save(root='timeseries3',
                   title='residuals',
                   xlabel='years',
                   ylabel='price per gram ($)')
    
    years = np.linspace(0, 5, 101)
    predict = GenerateSimplePrediction(results, years)
    thinkplot.Plot(years, predict)
    thinkplot.Show()


def main(name):
    thinkstats2.RandomSeed(18)
    transactions = ReadData()

    dailies = GroupByQualityAndDay(transactions)
    #PlotDailies(dailies)
    #RunModels(dailies)
    #PrintSerialCorrelations(dailies)
    #MakeAcfPlot(dailies)

    name = 'high'
    daily = dailies[name]

    #PlotLinearModel(daily, name)
    #PlotRollingMean(daily, name)
    #PlotFilled(daily, name)

    years = np.linspace(0, 5, 101)
    PlotPredictions(daily, years)
    xlim = years[0]-0.1, years[-1]+0.1
    thinkplot.Save(root='timeseries4',
                   title='predictions',
                   xlabel='years',
                   xlim=xlim,
                   ylabel='price per gram ($)')

    return
    # TODO: move the quadratic model to chap12ex_soln
    print(name)
    model, results = RunQuadraticModel(daily)
    regression.SummarizeResults(results)
    PlotFittedValues(model, results, label=name)
    thinkplot.Save(root='timeseries5',
                   title='fitted values',
                   xlabel='years',
                   xlim=[-0.1, 3.8],
                   ylabel='price per gram ($)')

    PlotResidualPercentiles(model, results)
    thinkplot.Save(root='timeseries6',
                   title='residuals',
                   xlabel='years',
                   ylabel='price per gram ($)')

    years = np.linspace(0, 5, 101)
    PlotPredictions(daily, years, func=RunQuadraticModel)
    thinkplot.Save(root='timeseries7',
                   title='predictions',
                   xlabel='years',
                   xlim=[years[0]-0.1, years[-1]+0.1],
                   ylabel='price per gram ($)')





if __name__ == '__main__':
    import sys
    main(*sys.argv)