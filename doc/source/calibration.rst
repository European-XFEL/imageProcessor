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
      :label: shift_eq
	
	      .. _fig-SH_profile:

.. figure:: _images/autocorrelator_setup.png
   :scale: 50 %
   :align: center

   Setup ([1]_) of an intensity autocorrelator. BS refers to the beam splitter.

				     
Combining equations :eq:`profile_eq` the dependence on the intersection
angle :math:`\phi` is removed, and the pulse duration can be obtained as

.. math::
   \tau_p = D_z \cdot \frac{1}{2} \cdot \frac{\Delta t}{\Delya Z_0}
   :label: tau_calib_eq

The ratio :math: K = ∆Z
is a calibration factor which allows the convertion of the SH
0
transverse profile (measured in pixel unit) in the pulse time profile (measured
in femtosecond unit). Its determination with sufficient accuracy is challenging.
To overcome this difficulty the following procedure is applied. One of the two
optical paths can be varied by pulling or pushing one mirror in the line in a
controllable way using a micrometer. A change ∆l of the micrometer head
position results in a pulse delay of ∆t = 2∆l/c and in the shift described by
eq. (6). Thus, shifting the SH distribution, as measured in the CCD camera, in
two extreme opposite positions of the sensitive area allows the measurements of
calibration factor with larger relative uncertainty as



Before instantiating the device no special action should be taken
by the user. In the initialization phase the device will check the
possible laser patterns allowed to the users, according to the groups they
belongs to, as well as whether they are authorized to access the relevant 
DOOCS server. In case some needed registration conditions are not fulfilled
the initialization of the device will fail, and the device will
transition into the ERROR state.
An example of the device configuration editor after successful initialization,
as running in an example topic, is presented in :numref:`Fig. %s <fig-editor>`:

.. _fig-editor:

.. figure:: _images/pplPattern_editor.png
   :scale: 60 %
   :align: center

   :numref:`Fig. %s <fig-editor>`: After successful initialization
   the users can visualize their credentials and the patterns
   to work with.

After initialization the users can cross-check their credentials:
   
- **Operator: User Name**: The username associated to the running server;

- **Operator: User Group**: The group of the user, relevant for ppl
  operations (exfl_cas, exfl_fxe, exfl_spb, exfl_sqs, exfl_scs, exfl_wp78);

- **Operator: Laser Pattern**: The laser pattern which can be modified
  by the users (according to their group). Every pattern corresponds to a
  specific bit in the 32-bits pattern associated to each electron bunch.
  One instrument user should have only one pattern, except LAS group which
  can instead modify all possible patterns. In case more patterns
  are available to the users, they can be selected in this drop-up menu.
  The patterns available in the system are the following:

  -- LP_LAS1: For LAS;

  -- LP_LAS2: For LAS;

  -- LP_SPB: For SPB instrument;

  -- LP_FXE: For FXE instrument;

  -- LP_SQS: For SQS instrument;

  -- LP_SCS: For SCS instrument;

  -- LP_SASE2: For future use in SASE 2;

  -- LP_15: For LAS and for testing by Control group.

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

The variable **Selected Pattern** allows to configure the ppl patterns
in a train. At the moment, up to two train configurations can be set,
named as *A* or *B*, which can be selected via its drop up menu.
Each train can be then configured with up to four
consequent sub-patterns, independently configurable, exposed as nodes
in the device configuration editor, 
:numref:`Fig. %s <fig-nodes>`. A train configuration can be repeated
*N* times in sequence configuring the variable
**Set Repetition Factor of Pattern**. Setting a null value for a selected
pattern, e.g. *B*, will result in not considering that pattern in the ppl
firing sequence. The currently user-selected configuration is shown
in the variable **User: Pattern Sequence**.
Let us have, as an example, the configuration *N[A]M[B]*. This will
translate in firing the ppl in sequence the configuration *A* for
*N* consequent trains, and soon after firing the configuration *B*
for the next *M* trains. At the end of the last train, the sequence 
will restart from the beginning. In order to make active (i.e. to save
it in DOOCS), the slot **Write Pattern Sequence to Doocs** should be called.

.. _fig-nodes:

.. figure:: _images/pplPattern_nodes.png
   :scale: 70 %
   :align: center

   :numref:`Fig. %s <fig-nodes>`: Up to four consequent sub-patterns
   can be configured in each train.


For each node (sub-pattern) the following variables can be set:

- **Nr. of Laser Pulses**: The number of laser pulses in a sequence;

- **Nr. of Empty Bunches between Pulses**: The number of empty
  XFEL bunches between the laser pulses. The pulse frequency and the
  interval between pulses in the specific sequence will change accordingly. 

  
After each selection is *entered* in the editor, the variable
**User: Ppl Pattern** will be updated. The total subpattern length (in unit of
XFEL bunches) and interval, including all empty bunches, will be also updated. 
This configuration will not be automatically transferred to the DOOCS server;
this will be done only
after pressing the slot (button) **Write Pattern to Doocs**.
The new pattern stored in DOOCS (**Doocs: Ppl SubPattern**)
will be then updated accordingly.
Note that the patterns saved in DOOCS are not regularly monitored. To retrieve
the current patterns the slot **Read Pattern from Doocs** should be called.
	
The variable **User: Complete Burst Duration** shows (for each selected train)
the duration of complete ppl, burst from first to last pulse.
