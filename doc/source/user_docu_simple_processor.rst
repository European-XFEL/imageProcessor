.. _simple-image-processor-user:

**********************
Simple Image Processor
**********************

The Simple Image Processor device can be connected to the output channel of a
device producing images (usually a camera, or an image processor device).

Incoming data will be sought for images in the ``data.image`` key.

The Simple Image Processor device can provide for each incoming image:

* the maximum pixel value;
* gaussian fit parameters for the x and y integrals.

The settings of the Simple Image Processor are described in the next section.


Input to the Device
===================

=======================  =======================================================
Property key             Description
=======================  =======================================================
pixelSize                | The pixel size, to be used for converting the fit's
                         | standard deviation to FWHM.
imageThreshold           | The threshold for doing processing. Only images
                         | having maximum pixel value above this threshold
                         | will be processed.
subtractImagePedestal    | Set to `True`, to subtract the image pedestal (i.e.
                         | image = image - image.min()) before centre-of-mass
                         | and Gaussian fit.
thresholdType            | Defines whether an absolute or relative thresholding
                         | is used in the calculations.
pixelThreshold           | If thresholdType is set to 'absolute', pixels below
                         | this threshold will be set to 0 in the processing of
                         | images. If it is set to 'relative', pixels below
                         | this fraction of the maximum pixel value will be set
                         | to zero. If it is set to None, no thresholding will
                         | occur.
=======================  =======================================================


Commands
========

=======================  =======================================================
Slot key                 Description
=======================  =======================================================
reset                    | Resets the processor output values.
=======================  =======================================================

Output of the Device
====================

General properties
------------------

=======================  =======================================================
Property key             Description
=======================  =======================================================
frameRate                | The actual frame rate.
imageSizeX               | The image width.
imageSizeY               | The image height.
offsetX                  | The image offset in X direction, i.e. the X position
                         | of its top-left corner.
offsetY                  | The image offset in Y direction, i.e. the Y position
                         | of its top-left corner.
binningX                 | The image binning in X direction.
binningY                 | The image binning in Y direction.
=======================  =======================================================


Gaussian Fit
------------

=======================  =======================================================
Property key             Description
=======================  =======================================================
success                  | Success boolean whether the image processing was
                         | successful or not.
maxPxValue               | Maximum pixel value.
amplitudeX, amplitudeY   | Amplitude from Gaussian fit.
positionX, positionY     | Beam position from Gaussian fit.
sigmaX, sigmaY           | Standard deviation from Gaussian fit.
fwhmX, fwhmY             | FWHM obtained from standard deviation.
errSigmaX, errSigmaY     | Uncertainty on position from Gaussian fit.
=======================  =======================================================


Expert Contact
==============

* Dennis Goeries <dennis.goeries@xfel.eu>
* Andrea Parenti <andrea.parenti@xfel.eu>