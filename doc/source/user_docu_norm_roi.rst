.. _image-norm-roi-user:

****************************
Normalized Spectrum from ROI
****************************

The `ImageNormRoi` device is used to calculate an inline normalized spectrum
from an image. In order to compute the spectrum, the operator has to define a
data region of interest (ROI) and a normalization ROI from the incoming image.
Both regions of interest are created with the same size (``roiSize``) and the
positions can be defined by ``dataRoiPosition`` and ``normRoiPosition``,
respectively.
The normalization ROI is then subtracted from the pixel values of the data
region of interest and the result is finally integrated along the Y direction
to retrieve the spectrum.


Input to the Device
===================

=======================  =======================================================
Property key             Description
=======================  =======================================================
roiSize                  | The size of the user-defined ROI, specified as
                         | [width_roi, height_roi].
dataRoiPosition          | The position of the user-defined data ROI of the
                         | image, specified as [x, y].
                         | Coordinates are counted from top-left corner!
normRoiPosition          | The position of the user-defined ROI to normalize
                         | the image, specified as [x, y].
=======================  =======================================================



Output of the Device
====================

=======================  =======================================================
Property key             Description
=======================  =======================================================
output                   | It will contain the calculated spectrum, in the
                         | ``data.spectrum`` key.
spectrumIntegral         | The sum of the spectrum values.
=======================  =======================================================
