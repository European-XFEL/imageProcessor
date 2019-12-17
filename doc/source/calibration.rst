***********
Calibration
***********

To overcome the difficulty in measuring the incident angle :math:`\phi`
of the primary beams, the following methode is applied.

By shifting the mirror stage in the optical delay line,
:numref:`Fig. %s <fig-delay_line>`, a delay :math:`\Delta t` is added
between the two input pulses, resulting in a shift :math:`\Delta Z_0`
of the center of SH transverse distribution

.. math::
      \Delta Z_0 = \frac{\Delta t \cdot u}{2 \cdot sin(\phi/2)}  
	
.. _fig-delay_line:

.. figure:: _images/autocorrelator_setup.png
   :scale: 50 %
   :align: center

   Setup of an intensity autocorrelator. BS refers to the beam splitter.

				     
Combining equations on transverse profile :math:`D_z` with shift
:math:`\Delta Z_0` the dependence on the intersection
angle :math:`\phi` is removed, and the pulse duration can be obtained as

.. math::
   \tau_p = D_z \cdot \frac{1}{2} \cdot \frac{\Delta t}{\Delta Z_0}

The ratio :math:`K = \frac{\Delta t}{\Delta Z}` is a calibration factor
which allows the convertion of the SH transverse profile (measured in
pixel unit) in the pulse time profile (measured in femtosecond unit).

Its determination with sufficient accuracy is challenging.
To overcome this difficulty the following procedure is applied. One of the two
optical paths can be varied by pulling or pushing one mirror in the line in a
controllable way using a micrometer. A change :math:`\Delta l` of the
micrometer head position results in a pulse delay of
:math:`\Delta t = 2\Delta l / c` and in the shift
:math:`\Delta Z_0`.
Thus, shifting the SH distribution, as measured in the CCD camera, in
two extreme opposite positions (1 & 2) of the sensitive area allows
the measurements
of calibration factor with a lower relative uncertainty as shown in the steps
here below:

.. math::
   \Delta t = 2\Delta l / c

.. math::
   \Delta t_1 - \Delta t_2 = 2(\Delta l_1 - \Delta l_2) / c

Considering the above espression of :math:`\tau_p`,

.. math::
   \Delta t_1 - \Delta t_2 = 2\cdot \tau_p/D_z (\Delta Z_1 - \Delta Z_2)

.. math::
   (\Delta l_1 - \Delta l_2)/c = \tau_p/D_z (\Delta Z_1 - \Delta Z_2)

resulting in 

.. math::
   \tau_p = D_z \cdot \frac{1}{2} \cdot (\frac{2}{c} \cdot \frac{\Delta_1 - \Delta_2}{(\Delta Z_1 - \Delta Z_2)}


.. _fig-editor:

.. figure:: _images/device_editor.png
   :scale: 60 %
   :align: center

   :numref:`Fig. %s <fig-editor>`: After successful initialization
   the users can visualize their credentials and the patterns
   to work with.

After initialization the users can cross-check their credentials:
   
The status of electron bunches in the XFEL machine is periodically
retrieved. The interval to wait before polling for an update from DOOCS
can be tuned by changing the value of the parameter
**Charge Update Interval** (its default value is 2s).
Each instrument will have visualized only the sequence of bunches emitting
X-rays in their corresponding SASE tunnel. In case of LAS or Control
user, at moment only SASE1 is displayed; in the next releases the possibility
to choose at run time which tunnel to monitor will be given.
The base frequency for the bunches (**XFEL Bunch Base Frequency**)
is regularly updated by DOOCS.

