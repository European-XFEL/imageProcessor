.. _image-background-user:

****************************
Image Background Subtraction
****************************

The `ImageBackgroundSubtraction` device can subtract a background image
from the incoming one. Its settings are described in the
:ref:`image-background-settings` section.


.. _image-background-settings:

Input to the Device
===================

=======================  =======================================================
Property key             Description
=======================  =======================================================
disable                  | Disable background subtraction.
imageFilename            | The full filename to the background image.
                         | File format must be 'npy', 'raw' or TIFF.
=======================  =======================================================


Commands
========

=======================  =======================================================
Slot key                 Description
=======================  =======================================================
resetBackgroundImage     | Reset background image.
save                     | Save to file the current image.
load                     | Load a background image from file.
useAsBackgroundImage     | Use the current image as background image.
reset                    | Reset error count.
=======================  =======================================================


Output of the Device
====================

=======================  =======================================================
Property key             Description
=======================  =======================================================
frameRate                | The rate of incoming images. It is refreshed once per
                         | second.
errorCount               | Number of errors.
ppOutput                 | The output channel for GUI and pipelines.
                         | The background subtracted imaged can be found in
                         | ``data.image``.
daqOutput                | The output channel for DAQ - with reshaped image.
=======================  =======================================================
