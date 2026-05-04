#############################################################################
# Author: carinanc
# Created on May 26, 2021, 03:08 PM
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################
from enum import Enum

import numpy as np

DEFAULT_ROI = (0, 0, 0, 0)
DTYPE = np.float64


class Origin(Enum):
    NONE = 'NONE'
    IMAGE_CENTER = 'IMAGE CENTER'
    CENTROID = 'CENTROID'

    @classmethod
    def as_list(cls):
        return [origin.value for origin in list(cls)]

    @classmethod
    def index(cls, index):
        return cls.as_list()[index]
