.. _image-averager-user:

**************
Image Averager
**************

The `ImageAverager` device can perform a running average, or the standard one,
of the incoming images. Its settings are described in the
:ref:`image-averager-settings` section.


.. _image-averager-settings:

Input to the Device
===================

=======================  =======================================================
Property key             Description
=======================  =======================================================
nImages                  | The number of images to be averaged.
runningAverage           | If ``True``, a `simple moving average`_ is
                         | calculated, otherwise the standard average.
=======================  =======================================================

.. _simple moving average: https://en.wikipedia.org/wiki/Moving_average#Simple_moving_average

Commands
========

=======================  =======================================================
Slot key                 Description
=======================  =======================================================
resetAverage             | Resets all temporary variables used for averaging.
=======================  =======================================================


Output of the Device
====================

=======================  =======================================================
Property key             Description
=======================  =======================================================
inFrameRate              | The rate of incoming images. It is refreshed once per
                         | second.
outFrameRate             | The rate of averaged images written to the output
                         | channel. It is refreshed once per second.
ppOutput                 | The output channel for GUI and pipelines.
                         | The averaged imaged can be found in ``data.image``.
daqOutput                | The output channel for DAQ - with reshaped image.
=======================  =======================================================
