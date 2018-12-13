.. _image-masking-user:

*********
Image ROI
*********

The `ImageApplyROI` device applies a ROI to the incoming image, and writes
the sub-image to an output channel.


Input to the Device
===================

=======================  =======================================================
Property key             Description
=======================  =======================================================
disable                  | No ROI will be applied, if set to ``True``.
roi                      | The user-defined region of interest (ROI),
                         | specified as [lowX, highX, lowY, highY].
=======================  =======================================================


Output of the Device
====================

=======================  =======================================================
Property key             Description
=======================  =======================================================
frameRate                | The rate of incoming images. It is refreshed once per
                         | second.
output                   | The output channel for GUI and pipelines. The ROI-ed
                         | image can be found in ``data.image``.
=======================  =======================================================
