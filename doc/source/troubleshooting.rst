***************
Troubleshooting
***************
Some typical errors have been identified up to now:

- In case the camera device is not instantiated or it is stopped
  the peak position and FWHM should be null, and no calculation of the
  pulse duration can be performed;

- In case the uncertainty arising from the fit procedure is relative large,
  likely the model used in the fit is not appropriate:

  -- try to use a different available model;

  -- try to optimize the fitting region;

  -- verify that the tails of the second harmonic beam are well within
     the fitting area;
  
- In case no available model describes correctly the data, 
  an optimization of the optical line setup could be attempted.
