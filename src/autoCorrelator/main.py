#!/usr/bin/env python

__author__="andrea.parenti@xfel.eu"
__date__ ="February, 2014, 02:13 PM"
__copyright__="Copyright (c) 2010-2013 European XFEL GmbH Hamburg. All rights reserved."

from karabo.configurator import Configurator
from karathon import Hash
from AutoCorrelator import PythonDevice

if __name__ == "__main__":
    device = Configurator(PythonDevice).create("AutoCorrelator", Hash("Logger.priority", "DEBUG", "deviceId", "AutoCorrelatorMain_0"))
    device.run()
