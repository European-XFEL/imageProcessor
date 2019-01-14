.. _image-to-spectrum-user:

*****************
Image to Spectrum
*****************

The `ImageToSpectrum` device is used to calculate an inline spectrum
from an image. In order to compute the spectrum, the operator has to define a
region of interest (ROI) from the incoming image.
After the selection of the ROI, the image is integrated along the Y direction
to retrieve the spectrum.

Input to the Device
===================

=======================  =======================================================
Property key             Description
=======================  =======================================================
roi                      | The user-defined region of interest, specified as
                         | [lowX, highX].
                         | [0, 0] will be interpreted as 'whole range'.
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