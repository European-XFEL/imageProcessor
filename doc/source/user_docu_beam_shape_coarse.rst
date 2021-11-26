.. _image-beam-shape-user:

*****************
Beam Shape Coarse
*****************

The `BeamShapeCoarse` device integrates the incoming images in Y and X
directions, then finds the position of the peak and the beam size on such
integrals.

Position and size of the beam are calculated with the `peakParametersEval`
function from the :ref:`image processing <imageprocessing>` package, thus the
evaluated values make sense only if the peak has a single maximum. Also noise
(ripple) may affect the result.


Commands
========

=======================  =======================================================
Slot key                 Description
=======================  =======================================================
resetError               | Resets the error state.
=======================  =======================================================


Output of the Device
====================

=======================  =======================================================
Property key             Description
=======================  =======================================================
x0                       | X coordinate of the maximum intensity pixel.
y0                       | Y coordinate of the maximum intensity pixel.
fwhmX                    | Full Width at Half Maximum for X projection, A.K.A.
                         | beam width.
fwhmY                    | Full Width at Half Maximum for Y projection, A.K.A.
                         | beam height.
frameRate                | Rate of processed images. It is refreshed once per
                         | second.
=======================  =======================================================
