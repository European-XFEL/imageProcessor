.. _image-pattern-picker-user:

********************
Image Pattern Picker
********************

The aim of this device is to filter input images according to their train IDs.

The image pattern picker has two nodes (``chan_1`` and ``chan_2``); each of
them contains an input channel that can be connected to an output channel to
receive an image stream (e.g. from a camera).

The input image has to be found in the ``data.image`` element. If its
``trainId`` fulfills a given condition (see next Section), it will be forwarded
to the output channel in the same node.


Input to the Device
===================

=======================  =======================================================
Property key             Description
=======================  =======================================================
nBunchPatterns           | Number of bunch patterns.
patternOffset            | The image will be forwarded to the output if its
                         | ``trainId`` satisfies the following relation:
                         | ``(trainId % nBunchPatterns) ==  patternOffset``.
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
output                   | The output channel. The forwarded images can be found
                         | in ``data.image``.
=======================  =======================================================