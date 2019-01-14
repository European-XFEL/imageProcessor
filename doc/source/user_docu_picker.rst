.. _image-picker-user:

************
Image Picker
************

This device has two input channels (``inputImage`` and ``inputTrainid``).

* ``inputImage`` expects an image stream (e.g. from a camera);
* ``inputTrainId`` is used to get the timestamps. Its data content is ignored,
  as only timestamp is relevant.

Images whose ``trainId`` equals ``inputTrainId + trainIdOffset`` are forwarded
to an output channel, while others are discarded.


Input to the Device
===================

=======================  =======================================================
Property key             Description
=======================  =======================================================
isDisabled               | When disabled, all images received in input are
                         | forwarded to output channel.
imgBufferSize            | Number of images to be kept waiting for a matching
                         | train ID.
trainIdOffset            | Train ID Offset.
                         | If positive: output image train ID is greater than
                         | input train ID (delay).
                         | If negative: output image train ID is lower than
                         | input train (advance).
trainIdBufferSize        | Number of train IDs to be kept waiting for an image
                         | with matching train ID.
inputImage               | The input channel for the image stream.
inputTrainId             | The input channel for train IDs.
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
