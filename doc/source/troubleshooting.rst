***************
Troubleshooting
***************
Some typical errors have been identified up to now:

- Device initialization failing with device state
  *"Could not instantiate base class"*.
  This is due either to the user not belonging to the allowed xfel groups
  or not be allowed to access the relevant DOOCS server. After agreement
  with LAS group permissions can be required to ITDM or DOOCS, accordingly;


- Start of the server failed because the user not able to log into
  exflcon146. This problem can be fixed by asking ITDM for the proper
  authorization to login to that machine.


- In case the configured ppl pattern appears to be not applied, one of
  the following scenarios could have likely happened:

  -- The slot *Write Pattern Sequence to Doocs* was pressed instead of *Write Patterns to Doocs*;


  -- The pattern was configured for a train pattern, e.g. *B*, which has a null repetition factor (thus not being applied);

     
  -- Everything was done correctly, but the flag **Is Custom Pattern Enabled**
  is false. In this case the machine is running in the so called *Legacy mode* which does not follow the user setting;

- The number of wanted empty bunches cannot be set. This is typically
  due to the resulting pulse frequency not being compliant with what
  allowed by the laser. Look at the **Frequency Lookup Table** for the
  possible values to be used.
  

