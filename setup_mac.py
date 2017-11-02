"""
Usage:
    python3 setup.py py2app

    [ref: http://doc.qt.io/qt-4.8/deployment-mac.html]
"""
from setuptools import setup
from plistlib import Plist

# Add info to MacOSX plist
# plist = Plist.fromFile('Info.plist')
plist = dict(CFBundleDisplayName='QBI MSD Analysis',
             NSHumanReadableCopyright='Copyright (c) 2017 Queensland Brain Institute',
             CFBundleTypeIconFile='resources/chart128.ico',
             CFBundleVersion='1.0')

APP = ['appgui.py']
DATA_FILES = ['resources/', 'noname.py']
OPTIONS = {'argv_emulation': True,
           'plist': plist,
           'iconfile': 'resources/chart128.ico',
           'includes': ['numpy.core._methods','numpy.lib.format', 'matplotlib.backends.backend_tkagg'],
           'excludes': ['PyQt5', 'PyQt4'],
           'packages': ['tkinter','seaborn', 'scipy', 'matplotlib'],
           }

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
