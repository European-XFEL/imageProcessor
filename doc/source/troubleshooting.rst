***************
Troubleshooting
***************
Some typical errors have been identified up to now:

- In case the camera device is not instantiated or it is stopped
  the peak position and FWHM should be null, and no calculation of the
  pulse duration can be performed;

- In case no calibration constant is provided, either inserted by the user (if
  previously known) or by following the calibration procedure described in the
  text, the pulse duration is not calculated;

- In case the calibration constant is inserted by the user, and the results
  appear to be very different from what expected, the value used might describe
  no more the current optical setup of the autocorrelator device.
  A new calibration measurement could be performed;

- In case the uncertainty arising from the fit procedure is relative large,
  likely the model used in the fit is not appropriate:

  -- try to use a different available model;

  -- try to optimize the fitting region;

  -- verify that the tails of the second harmonic beam are well within the fitting area;
  
- In case no available model describes correctly the data, 
  an optimization of the optical line setup could be attempted.
