__author__="Sergey Esenov <serguei.essenov at xfel.eu>"
__date__ ="$Jul 17, 2013 2:46:38 PM$"
__copyright__="Copyright (c) 2010-2013 European XFEL GmbH Hamburg. All rights reserved."

from karabo.configurator import Configurator
from karathon import Hash
from ImageProcessor import PythonDevice

if __name__ == "__main__":
    device = Configurator(PythonDevice).create("ImageProcessor", Hash("Logger.priority", "DEBUG", "deviceId", "ImageProcessorMain_0"))
    device.run()
