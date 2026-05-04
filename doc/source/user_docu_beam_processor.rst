
***************
Beam Processor
***************

The Beam Processor device can provide for each incoming images (2D):

* Energy, computed as the integral of the pixel values.
* X and Y coordinates of the centre-of-mass position.
* Major and minor beam widths (one standard deviation).
* Major and minor scaled beam widths (one standard deviation).
* Rotation angle of the beam ellipse, in degrees.
* Maximum image pixel value and the corresponding X and Y coordinates.


Input to the Device
===================

.. _beam-processor-general-settings:

General Settings
----------------

The following properties affect all the algorithms ran in the device.

+--------------------------------+--------------------------------------------------+
| Parameter                      | Description                                      |
+================================+==================================================+
| axisScale                      | Display-only scaling factor for the              |
|                                | plotted major/minor axes;                        |
|                                | it does not modify core measurement values.      |
+--------------------------------+--------------------------------------------------+
| inhomogeneousBackgroundSamples | Number of pixels sampled from top and bottom     |
|                                | of the image.                                    |
+--------------------------------+--------------------------------------------------+
| energyScale                    | Output normalization factor for the reported     |
|                                | energy magnitude to improve numerical            |
|                                | readability (display scaling only).              |
+--------------------------------+--------------------------------------------------+
| width                          | Beam width in terms of FWHM.                     |
+--------------------------------+--------------------------------------------------+
| pixelScale                     | Constant pixel-to-physical calibration factor    |
|                                | applied to the image coordinates and downstream  |
|                                | computed quantities (e.g.,                       |
|                                | :math:`2 \text{mm·px}^{-1}`)                     |
+--------------------------------+--------------------------------------------------+
| pixelTranslate                 | Translation for both x- and y-axis.              |
+--------------------------------+--------------------------------------------------+
| beamWidthScale                 | A multiplier applied after beam-width detection. |  
+--------------------------------+--------------------------------------------------+
| pixelTranslate                 | Translation for both x- and y-axis.              |
+--------------------------------+--------------------------------------------------+
| origin                         | Index of the closest position to the beam's      |
|                                | centroid, which represents its centre of mass    |
|                                | based on pixel intensity.                        |
+--------------------------------+--------------------------------------------------+
    
.. _image-processor-enabling-features:

Enabling Features
-----------------

The Gaussian fit can be performed using either a standard Gaussian distribution or a super-Gaussian distribution.

+--------------------------------+--------------------------+
| Property key                   | Description              |
+================================+==========================+
| isSuperGaussian                | Use super Gaussian.      |
+--------------------------------+--------------------------+

A super-Gaussian is a mathematical function that resembles a Gaussian but decays more rapidly,
resulting in a sharper peak and heavier tails. It is often used in fields like optics and statistics
to model intensity distributions or probability distributions that require a different shape than a standard Gaussian.

Output Parameters
====================

General Properties
------------------

+--------------------------------+--------------------------------------------------+
| Parameter                      | Description                                      |
+================================+==================================================+
| Energy                         | Integral of pixel values.                        |
+--------------------------------+--------------------------------------------------+
| x0                             | X position of the centre-of-mass.                |
+--------------------------------+--------------------------------------------------+
| y0                             | Y position of the centre-of-mass.                |
+--------------------------------+--------------------------------------------------+
| a                              | Major-axis beam width.                           |
+--------------------------------+--------------------------------------------------+
| b                              | Minor-axis beam width.                           |
+--------------------------------+--------------------------------------------------+
| majorAxisScaled                | Major-axis beam width (a), scaled.               |
+--------------------------------+--------------------------------------------------+
| minorAxisScaled                | Minor-axis beam width (b), scaled.               |
+--------------------------------+--------------------------------------------------+
| theta                          | Beam-ellipse rotation angle in degrees.          |
+--------------------------------+--------------------------------------------------+
| peak                           | The maximum image pixel value.                   |
+--------------------------------+--------------------------------------------------+
| peakX                          | X position of the maximum pixel value.           |
+--------------------------------+--------------------------------------------------+
| peakY                          | Y position of the maximum pixel value.           |
+--------------------------------+--------------------------------------------------+

Gaussian-Specific Properties
----------------------------

Summary of the Gaussian fit parameters for the following 1D distributions:
major and minor axes in the x and y directions.

+--------+--------------------------------------------------------------------------+
| Name   | Description                                                              |
+========+==========================================================================+
| pos    | Position of the centre of the Gaussian distribution.                     |
+--------+--------------------------------------------------------------------------+
| width  | Full width at half maximum (FWHM)*                                       |
+--------+--------------------------------------------------------------------------+
| r2     | Coefficient of determination (:math:`\text{R}^{2}`) of the Gaussian fit. |
+--------+--------------------------------------------------------------------------+

\* Computed as :math:`2\sqrt{2\ln 2}\,\sigma`, where :math:`\sigma` is the standard
deviation of the Gaussian and the order :math:`n` corresponds to either
a Gaussian (:math:`n = 2`) or a super-Gaussian distribution.


Initial Calculations for Improving the Accuracy of the Detected Beam
====================================================================

1. Using a filtered image to minimize artifacts in the image, a Gaussian filter is applied.

   The ``gaussian_filter`` function smooths a 2D image by convolution with a
   Gaussian kernel, which is a small, bell-shaped pattern of weights that gives
   more importance to pixels near the centre and less to those farther away.
   During the convolution process, the kernel is slid across the image and each
   pixel is replaced by a weighted average of its neighboring pixels, gently
   reducing noise and small fluctuations while preserving the overall structure
   of the image.
   To keep the computation efficient and avoid unnecessary
   computational cost, especially for large images, the convolution is performed
   using a fast method based on Fourier transforms. The result is a blurred image
   with the same size as the original, which can optionally be scaled so that its
   maximum value is equal to one.

2. Guessing initial beam parameters.

   To help with the detection, we guess the initial centroid and width:

   * For the centroid, we use weights on the image (``gaussian_filter``) that represents the centre of mass.
   * For the width, ``initial_widths finds`` the width from the thresholded intensity (which was developed by LAS).
   
   This function estimates an initial width of a bright spot (e.g. a beam or peak) in a 2D image.
   The width is based on how far the signal extends from the centre above half of the maximum intensity,
   which is conceptually related to a full width at half maximum (FWHM).

3. Subtracting the background:

   * Creating a mask from the previously detected beam. The ``rectangle_mask`` method generates a boolean mask representing a rotated rectangular region within an image.
     The rectangle is defined by its centre position (centroid), its width along two axes (widths),
     and an optional rotation angle. The method computes the rectangle's corner coordinates,
     draws the rotated rectangle onto an image canvas, and converts the result into a boolean array
     that can be used to select or exclude pixels within that region.
      
   * Removing the pedestal of the resulting image, which is calculated from the background mask.


4. Iterating to find the best beam position.

   * A loop refines the beam parameters using the previously calculated values.
     Iteration continues while the parameters still change.
     Consider stopping earlier once the parameters have already converged to avoid unnecessary iterations.


Beam Parameter Extraction via Spatial Moments
=============================================

This section summarizes how to compute beam parameters (centroid,
orientation, widths) directly from intensity moments, following the ISO 11146. No Gaussian-specific fitting is required; the same workflow applies
to any measured transverse intensity distribution. See `ISO 11146-1:2021 <https://www.iso.org/standard/77769.html>`_ for details.


Inputs
------

- :math:`I(x_i, y_j)`: measured intensity at pixel :math:`(i, j)`
- :math:`x_i`, :math:`y_j`: coordinates of each pixel in the transverse plane
- Optional: background estimate to subtract if the camera has an offset signal

Zeroth and First Moments
------------------------

The zeroth moment is the total power:

.. math::

   P = \sum_{i,j} I_{ij}

The first moments define the centroid (intensity-weighted center):

.. math::

   \bar x = \frac{1}{P} \sum_{i,j} x_i\,I_{ij} \\
   \bar y = \frac{1}{P} \sum_{i,j} y_j\,I_{ij}

Second Central Moments
----------------------

Compute the centered second moments (variances and covariance):

.. math::

   S_{xx} = \frac{1}{P}\sum_{i,j} (x_i-\bar x)^2\,I_{ij} \\ 
   S_{yy} = \frac{1}{P}\sum_{i,j} (y_j-\bar y)^2\,I_{ij} \\ 
   S_{xy} = \frac{1}{P}\sum_{i,j} (x_i-\bar x)(y_j-\bar y)\,I_{ij}

- :math:`S_{xx}` and :math:`S_{yy}` give the beam spread along the lab x and y axes.
- :math:`S_{xy}` is the covariance; it encodes whether the intensity “cloud” is tilted
  relative to the lab axes. A nonzero value indicates a rotated ellipse.

Covariance Matrix and Principal Axes
-------------------------------------

Form the covariance matrix:

.. math::

   \mathbf{S} =
   \left[\begin{matrix}
   S_{xx} & S_{xy} \\
   S_{xy} & S_{yy}
   \end{matrix}\right]

Diagonalizing :math:`\mathbf{S}` yields eigenvectors (principal axes) and
eigenvalues :math:`\lambda_1`, :math:`\lambda_2` (variances along those axes).

The azimuthal angle :math:`\varphi` of the long principal axis is

.. math::

   \varphi = \frac{1}{2} \arctan\left( \frac{2S_{xy}}{S_{xx}-S_{yy}} \right)

Use an ``atan2`` variant to handle all quadrants robustly. When :math:`S_{xx} = S_{yy}`,
the ellipse is at :math:`\varphi = 45^\circ`.

Beam Widths (D :math:`4\sigma`)
-------------------------------

ISO 11146 defines the beam diameter as four times the square root of the eigenvalues
(:math:`4\sigma`):

.. math::

   D_{4\sigma,k} = 4 \sqrt{\lambda_k}, \qquad k=1,2

The beam radius along axis k is :math:`D_{4\sigma,k}/2`.

The eigenvalues are computed solving the characteristic equation: 

.. math::
  \lambda^2 - tr(A) \lambda + det(A) = 0

