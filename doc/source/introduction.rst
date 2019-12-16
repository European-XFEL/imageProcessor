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
:math:`\tau_p` and uniform transverse intensity profile, it is
found that the transverse profile :math:`D_z` of the second harmonic
depends on the pulse duration :math:`\tau_p` of the fundamental beams,

.. math::
   \Delta Z_0 = \frac{\Delta t \cdot u}{2 \cdot sin(\phi/2)}

.. math::
   \tau_p = D_z \cdot \frac{1}{2} \cdot \frac{\Delta t}{\Delta Z_0}
   
where :math:`u = c/n` and :math:`\phi` are the speed of light and the
intersection angle of input beams, respectively, in the crystal with
refractive index :math:`n`. The angle :math:`\phi` cannot
be measured with sufficient precision for a reliable extraction of pulse
duration :math:`\tau_p` .
The transverse profile :math:`D_z` is determined from the data accumulated
with the CCD camera available in the system.
An example is presented in Fig. 14. The left panel of the
figure shows clearly the deposited energy from the signal of the generated
second harmonic beam (central and more intense peak) and of the two
fundamental beams (low intensity side signals). The transverse profile
:math:`D_z` is determined from a fit to the SH peak.
The right panel of the figure presents the result of a

.. [1] RP Photonics Encyclopedia, https://www.rp-photonics.com/autocorrelators.html
