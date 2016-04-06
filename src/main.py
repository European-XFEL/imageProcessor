#!/usr/bin/env python

__author__="andrea.parenti@xfel.eu"
__date__ ="April, 2016, 04:19 PM"
__copyright__="Copyright (c) 2010-2013 European XFEL GmbH Hamburg. All rights reserved."

from karabo.configurator import Configurator
from SimpleImageProcessor import *

if __name__ == "__main__":
    device = Configurator(PythonDevice).create("SimpleImageProcessor", Hash("Logger.priority", "DEBUG", "deviceId", "SimpleImageProcessorMain_0"))
    device.run()
