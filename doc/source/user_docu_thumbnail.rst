.. _image-thumbnail-user:

***************
Image Thumbnail
***************

The `ImageThumbnail` device is meant to reduce the input image for preview
purposes. expects an image in input.

It lets the user specify the size of a canvas where the output thumbnail image
must fit. It outputs the image downscaled to fit in the specivied canvas.
Downscaled image is obtained by means of the `thumbnail` function from the
:rtd:`image-processing` package.


.. _image-averager-settings:

Input to the Device
===================

=======================  =======================================================
Property key             Description
=======================  =======================================================
thumbCanvas              | Shape of the canvas where thumbanail must fit [X, Y]
resample                 | If ``True`` binned pixel are averaged. Set to `False`
                         | to spare CPU load, set to `True` to avoid aliasing.
=======================  =======================================================


Output of the Device
====================

=======================  =======================================================
Property key             Description
=======================  =======================================================
frameRate                | The rate of incoming and outgoing images. It is
                         | refreshed once per second.
ppOutput                 | The output channel for GUI and pipelines.
                         | Thumbnail image can be found in ``data.image``.
daqOutput                | The output channel for DAQ - with reshaped image.
=======================  =======================================================
