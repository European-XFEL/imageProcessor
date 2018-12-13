.. _image-masking-user:

*************
Image Masking
*************

The `ImageApplyMask` device applies a mask to the incoming image, and writes
the masked image to an output channel.


Input to the Device
===================

=======================  =======================================================
Property key             Description
=======================  =======================================================
disable                  | No mask will be applied, if set to ``True``.
maskType                 | The mask type: rectangular or arbitrary (loaded
                         | from file).
x1x2y1y2                 | The rectangular selected region: x1, x2, y1, y2.
maskFilename             | The full path to the mask file. File format must be
                         | `npy`, `raw` or `TIFF`.
                         | Pixel value will be set to 0, where mask is <= 0.
=======================  =======================================================


Commands
========

=======================  =======================================================
Slot key                 Description
=======================  =======================================================
resetMask                | Discard the loaded mask.
loadMask                 | Load the mask from a file.
=======================  =======================================================


Output of the Device
====================

=======================  =======================================================
Property key             Description
=======================  =======================================================
frameRate                | The rate of incoming images. It is refreshed once per
                         | second.
output                   | The output channel for GUI and pipelines. The masked
                         | image can be found in ``data.image``.
=======================  =======================================================
