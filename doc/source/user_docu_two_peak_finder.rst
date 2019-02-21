.. _image-two-peak-finder-user:

***************
Two Peak Finder
***************

The `TwoPeakFinder` device will integrate the input image in the vertical
direction, then find two peaks, one left and one right from the `zero_point`.


.. _image-two-peak-finder-settings:

Input to the Device
===================

=======================  =======================================================
Property key             Description
=======================  =======================================================
zeroPoint                | The device will try to find a peak left, and a peak
                         | right, from this point.
threshold                | TODO - currently unused.
roi                      | The user-defined region of interest (ROI), specified
                         | as [lowX, highX].
                         | [0, 0] will be interpreted as 'whole range'.
=======================  =======================================================


Commands
========

=======================  =======================================================
Slot key                 Description
=======================  =======================================================
reset                    | Reset error count.
=======================  =======================================================


Output of the Device
====================

=======================  =======================================================
Property key             Description
=======================  =======================================================
frameRate                | The rate of incoming and outgoing images. It is
                         | refreshed once per second.
errorCount               | Number of errors.
peak1Value               | Amplitude of the 1st peak.
peak1Position            | Position of the 1st peak.
peak1Fwhm                | FWHM of the 1st peak.
peak2Value               | Amplitude of the 2nd peak.
peak2Position            | Position of the 2nd peak.
peak2Fwhm                | FWHM of the 2nd peak.
=======================  =======================================================
