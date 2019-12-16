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
   D_z = \frac{\tau_p \cdot u}{sin(\phi/2)}
   :label: profile_eq
	   
.. math::
   \tau_p = D_z \cdot \frac{1}{2} \cdot \frac{\Delta t}{\Delta Z_0}
   :label: tau_eq
   
where :math:`u = c/n` and :math:`\phi` are the speed of light and the
intersection angle of input beams, respectively, in the crystal with
refractive index :math:`n`.
The transverse profile :math:`D_z` is determined from the data accumulated
with the CCD camera available in the system.
An example is presented in :numref:`Fig. %s <fig-SH_profile>`:

.. _fig-SH_profile:

.. figure:: _images/SH_profile.png
   :scale: 50 %
   :align: center

   The fundamental beams and the second harmonic beam
   are detected in the CCD camera located after the non-linear crystal.

The figure shows clearly the deposited energy from the signal of the generated
second harmonic beam (central and more intense peak) and of the two
fundamental beams (low intensity side signals). The transverse profile
:math:`D_z` is determined from a fit to the SH peak.

The angle :math:`\phi` cannot
be measured with sufficient precision for a reliable extraction of pulse
duration :math:`\tau_p`. The way used in the device to determine the pulse
duration from the measured transverse profile is presented the calibration
section.

.. [1] RP Photonics Encyclopedia, https://www.rp-photonics.com/autocorrelators.html
