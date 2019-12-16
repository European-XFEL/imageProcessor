************
Introduction
************

The autoCorrelator bound device is designed to provide an online
determination of the pulse duration using a single-shot auto
correlator [1]_.

The measurement of the time profile of pulses is based on the following
principle graphically displayed in :numref:`Fig. %s <fig-principle>`.
The input beam is sent to a beam-splitter; the two identical originated
beams propagate along two distinct optical paths until they intersect
in a non-linear crystal. Here, due to the high-intensity of the beams,
a second harmonic beam (SH) is created and its integrated energy is
measured by a CCD camera located after the crystal.
.. _fig-principle:

.. figure:: _images/principle.png
   :scale: 50 %
   :align: center

   The diagram describes geometrically the
   intersection of two identical beams in a
   crystal and the generation of the second
   harmonic beam.

The pulse duration of laser pulses can be determined upon measuring
the transverse distribution of the energy deposited in the CCD camera.
From geometrical considerations in :numref:`Fig. %s <fig-principle>`,
assuming for the incoming beams a rectangular time profile
:math:`\tau\p` and uniform transverse intensity profile, it is
found that the transverse profile :math: D_z of the second harmonic
depends on the pulse duration :math: \tau\p of the fundamental beams,

.. [1] RP Photonics Encyclopedia, https://www.rp-photonics.com/autocorrelators.html
