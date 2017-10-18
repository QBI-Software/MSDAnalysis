from msdapp.msd.filterMSD import FilterMSD
from os.path import join, exists, dirname

from msdapp.msd.filterMSD import FilterMSD
import time
from glob import glob
from multiprocessing import Manager, Process
from multiprocessing.managers import SyncManager
import signal
from threading import Thread
from os import access, R_OK, walk, mkdir
from os.path import join, expanduser, dirname, exists, split
import logging
import matplotlib.pyplot as plt
import pandas as pd
import wx
from configobj import ConfigObj
from tabulate import tabulate

from msdapp.msd.batchCompareMSD import CompareMSD
from msdapp.msd.batchHistogramStats import HistoStats
from msdapp.msd.filterMSD import FilterMSD
from msdapp.msd.histogramLogD import HistogramLogD
from msdapp.msd.msdStats import MSDStats
from noname import AppConfiguration, StatsDialog


class MSDController():
    def __init__(self, configfile):
        self.processes = [
            {'caption': '1. Filter Data', 'href': 'filter',
             'description': 'Filter log10 diffusion coefficient (log10D) and corresponding MSD data between min and max range',
             'files': 'DATA_FILENAME, MSD_FILENAME',
             'filesout': 'FILTERED_FILENAME, FILTERED_MSD'},
            {'caption': '2. Generate Histograms', 'href': 'histogram',
             'description': 'Generate relative frequency histograms of Log10 D data for individual cells and all cells',
             'files': 'FILTERED_FILENAME',
             'filesout': 'HISTOGRAM_FILENAME'},
            {'caption': '3. Histogram Stats', 'href': 'stats',
             'description': 'Compiles histogram data from all cell directories (batch) into one file in output directory with statistics',
             'files': 'HISTOGRAM_FILENAME',
             'filesout': 'ALLSTATS_FILENAME'},
            {'caption': '4. Compile MSD', 'href': 'compare',
             'description': 'Compiles MSD data from all cell directories (batch) into one file in output directory with statistics',
             'files': 'FILTERED_MSD',
             'filesout': 'AVGMSD_FILENAME'}
        ]
        self.configfile = configfile
        self.loaded = self.loadConfig()
        self.timer = wx.Timer()

    def loadConfig(self, config=None):
        rtn = False
        try:
            if self.configfile is not None and access(self.configfile, R_OK):
                print("Loading config file:", self.configfile)
                config = ConfigObj(self.configfile, encoding='ISO-8859-1')
            else:
                print("Loading config object:", config.filename)

            self.datafile = config['DATA_FILENAME']  # AllROI-D.txt
            self.msdfile = config['MSD_FILENAME']  # AllROI-MSD.txt
            self.filteredfname = config['FILTERED_FILENAME']
            self.filtered_msd = config['FILTERED_MSD']
            self.histofile = config['HISTOGRAM_FILENAME']
            self.diffcolumn = config['DIFF_COLUMN']
            self.logcolumn = config['LOG_COLUMN']
            self.msdpoints = config['MSD_POINTS']
            self.minlimit = config['MINLIMIT']
            self.maxlimit = config['MAXLIMIT']
            self.timeint = config['TIME_INTERVAL']
            self.binwidth = config['BINWIDTH']
            self.threshold = config['THRESHOLD']
            self.allstats = config['ALLSTATS_FILENAME']
            self.msdcompare = config['AVGMSD_FILENAME']
            self.group1 = config['GROUP1']
            self.group2 = config['GROUP2']
            self.config = config
            rtn = True

        except:
            raise IOError
        return rtn

    def processFilter(self, datafile, q):
        """
        Activate filter process - multithreaded
        :param datafile:
        :param q:
        :return:
        """
        try:
            datafile_msd = datafile.replace(self.datafile, self.msdfile)
            outputdir = join(dirname(datafile), 'processed')  # subdir as inputfiles
            if not exists(outputdir):
                mkdir(outputdir)
            fmsd = FilterMSD(self.configfile, datafile, datafile_msd, outputdir, self.minlimit, self.maxlimit)
            q[datafile] = fmsd.runFilter()
        except KeyboardInterrupt:
            print("Keyboard interrupt in process: ", datafile)
        finally:
            print("cleaning up thread", datafile)

    def processHistogram(self, datafile, q):
        outputdir = dirname(datafile)  # same dir as inputfile Filtered*
        fd = HistogramLogD(self.minlimit, self.maxlimit, self.binwidth, datafile, self.configfile)
        q[datafile] = fd.generateHistogram(outputdir)

    def ShowFeedBack(self, show):
        # self.result.Show(not show)
        if show:
            self.timer.Start(250)
        else:
            self.timer.Stop()

    # initializer for SyncManager
    def mgr_init(self):
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        print("initialized manager")

    def RunFilter(self, filenames, progresswidget=None,row=None):
        """

        :param event:
        :param filenames:
        :return:
        """
        type = 'filter'

        self.ShowFeedBack(True)
        # find datafile - assume same directory for msd file
        # result = [y for x in walk(self.inputdir) for y in glob(join(x[0], self.datafile))]

        if len(filenames) > 0:
            total_tasks = len(filenames)
            tasks = []
            # mm = Manager()
            # q = mm.dict()
            # now using SyncManager vs a Manager
            mm = SyncManager()
            # explicitly starting the manager, and telling it to ignore the interrupt signal
            mm.start(self.mgr_init)

            try:
                q = mm.dict()
                for i in range(total_tasks):
                    self.count = 1
                    p = Process(target=self.processFilter, args=(filenames[i], q))
                    p.start()
                    tasks.append(p)

                try:
                    for p in tasks:
                        # self.gauge_filter.SetFocus()
                        while p.is_alive():
                            time.sleep(1)
                            self.count = self.count + 1
                            progresswidget.SetValue(self.count, row=row, col=1)
                        p.join()
                except KeyboardInterrupt:
                    print("Keyboard interrupt in main")
                    progresswidget.SetValue("Interrupt", row=row, col=2)

                headers = ['Data', 'MSD', 'Total', 'Filtered', 'Total_MSD', 'Filtered_MSD']
                results = pd.DataFrame.from_dict(q, orient='index')
                results.columns = headers
                return results
            finally:
                # to be safe -- explicitly shutting down the manager
                mm.shutdown()


        else:
            raise ValueError("Cannot find any datafiles: %s" % self.datafile)

        self.ShowFeedBack(False, type)

    def RunHistogram(self, event):
        type = 'histo'
        self.ShowFeedBack(True, type)
        # find datafile - assume same directory for msd file
        result = [y for x in walk(self.inputdir) for y in glob(join(x[0], self.filteredfname))]
        if len(result) > 0:
            total_tasks = len(result)
            tasks = []
            mm = Manager()
            q = mm.dict()
            for i in range(total_tasks):
                self.count = 1
                self.StatusBar.SetStatusText(
                    "Running %s script: %s (%d of %d)" % (type.title(), result[i], i, total_tasks))
                p = Process(target=self.processHistogram, args=(result[i], q))

                tasks.append(p)
                p.start()

            for p in tasks:
                self.gauge_histo.SetFocus()
                while p.is_alive():
                    time.sleep(1)
                    self.count = self.count + 1
                    self.gauge_histo.SetValue(self.count)
                p.join()

            headers = ['Figure', 'Histogram data']
            results = pd.DataFrame.from_dict(q, orient='index')
            results.columns = headers
            for i, row in results.iterrows():
                self.resultbox.AppendText("HISTOGRAM: %s\n\t%s\n\t%s\n" % (
                    i, row['Figure'], row['Histogram data']))
            self.result_histo.SetLabel("Complete")

        else:
            self.Warn("Cannot find any datafiles: %s" % self.filteredfname)

        self.ShowFeedBack(False, type)

    def RunStats(self, event, expt=None):
        type = 'stats'
        if expt is None:
            expt = ''
        self.ShowFeedBack(True, type)
        # loop through directory structure and locate prefixes with expt name
        try:
            for prefix in self.prefixes:
                print("Group:", prefix)
                self.statusbar.SetStatusText("Running %s script: %s (%s)" % (type.title(), expt, prefix))
                self.gauge_stats.SetFocus()
                fmsd = HistoStats(self.inputdir, self.outputdir, prefix, expt, self.configfile)
                fmsd.compile()
                compiledfile = fmsd.runStats()
                # Split to Mobile/immobile fractions - output
                ratiofile = fmsd.splitMobile()
                self.resultbox.AppendText(
                    "HISTOGRAM BATCH: %s: %s\n\t%s\n\t%s\n" % (expt, prefix, compiledfile, ratiofile))
                self.result_stats.SetLabel("Complete - Close plot to continue")
                # Set the figure
                fig = plt.figure(figsize=(10, 5))
                axes1 = plt.subplot(121)
                fmsd.showPlots(axes1)

                axes2 = plt.subplot(122)
                fmsd.showAvgPlot(axes2)

                figtype = 'png'  # png, pdf, ps, eps and svg.
                figname = fmsd.compiledfile.replace('csv', figtype)
                plt.savefig(figname, facecolor='w', edgecolor='w', format=figtype)
                plt.show()
        except ValueError as e:
            self.Warn("Batch Histogram error: %s" % e.message)

        self.ShowFeedBack(False, type)

    def RunMSD(self, event, expt=None):
        type = 'msd'
        if expt is None:
            expt = ''
        self.ShowFeedBack(True, type)
        # loop through directory
        for prefix in self.prefixes:
            self.statusbar.SetStatusText("Running %s script: %s (%s)" % (type.title(), expt, prefix))
            self.gauge_msd.SetFocus()
            fmsd = CompareMSD(self.inputdir, self.outputdir, prefix, expt, self.configfile)
            compiledfile = fmsd.compile()
            self.resultbox.AppendText("MSD BATCH: %s: %s\n\t%s\n\t%s\n" % (expt, prefix, compiledfile, areasfile))
            self.result_msd.SetLabel("Complete")
            # Set the figure
            fig = plt.figure(figsize=(10, 5))
            axes1 = plt.subplot(121)
            areasfile = fmsd.showPlotsWithAreas(axes1)

            axes2 = plt.subplot(122)
            fmsd.showAvgPlot(axes2)

            figtype = 'png'  # png, pdf, ps, eps and svg.
            figname = fmsd.compiledfile.replace('csv', figtype)
            plt.savefig(figname, facecolor='w', edgecolor='w', format=figtype)
            plt.show()

        self.ShowFeedBack(False, type)
