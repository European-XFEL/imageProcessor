#############################################################################
# Author: carinanc
# Created on May 26, 2021, 03:08 PM
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################
import operator
from dataclasses import dataclass, field
from functools import cached_property

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage, signal
from scipy.optimize import curve_fit
from scipy.spatial import distance

from .const import Origin


class Beam:

    MAX_ITERATION = 10
    WEIGHTED_CENTROID = True
    WIDTH_DIFFERENCE = 0.01

    INTERPOLATION_SCALE = 2
    INTERPOLATION_ORDER = 3

    PEAK_SIZE = 5

    @classmethod
    def detect(cls, image, background_scale=1):
        instance = cls(image, background_scale)
        instance.evaluate()
        return instance

    def __init__(self, image, background_scale=1):
        self.image = image
        self.background_scale = background_scale

        interpolated = ndimage.zoom(
            image, 1 / self.INTERPOLATION_SCALE, order=self.INTERPOLATION_ORDER
        )
        self._filtered_image = gaussian_filter(interpolated)

        # Initial values
        self.centroid = (np.nan, np.nan)
        self.widths = (np.nan, np.nan)
        self.energy = 0
        self.angle = 0  # radians

        # Other values
        self.count = 0
        self._deltas = []
        self._is_processed = False

    def evaluate(self):
        image = self._filtered_image
        weight = gaussian_filter(image**10, normalized=True)
        weighted = image * (weight / weight.sum())

        mean = np.mean(weighted)
        std = np.std(weighted)
        max_ = np.max(weighted)

        if max_ < mean + 6 * std:
            raise RuntimeError("Beam not found.")

        self.centroid = calc_centroid(weighted)
        self.widths = initial_widths(self._filtered_image, *self.centroid)

        while self.count < self.MAX_ITERATION:
            results = self._evaluate()

            if results is None:
                raise RuntimeError("Beam not found.")

            if not all([width > 0 for width in results["widths"]]):
                if _divergent(self._deltas):
                    raise RuntimeError("Beam not found.")
                break

            # Calculate delta from widths
            delta = np.sum(
                abs(np.divide(self.widths, results["widths"]) - 1)) / 2
            if delta < self.WIDTH_DIFFERENCE:
                break
            self._deltas.append(delta)

            # Bookkeep
            self.energy = results["energy"]
            self.centroid = results["centroid"]
            self.widths = results["widths"]
            self.angle = results["angle"]
            self.count += 1
        else:
            if _divergent(self._deltas):
                raise RuntimeError("Beam not found.")

        # Finalize
        self.centroid = np.multiply(self.centroid, self.INTERPOLATION_SCALE)
        self.widths = np.multiply(self.widths, self.INTERPOLATION_SCALE)
        self._is_processed = True

    def _evaluate(self):
        # 0. Prepare
        image = self._filtered_image

        # 1. Get mask
        mask = rectangle_mask(image.shape, self.centroid,
                              self.widths, angle=self.angle)

        # 2. Overlay the mask onto the image
        masked = np.ma.array(image, mask=mask)

        # 3. Subtract background offset
        widths = np.multiply(self.widths, self.background_scale)
        bg_mask = rectangle_mask(
            image.shape, self.centroid, widths, angle=self.angle)
        bg_mask = (
            ~bg_mask if np.count_nonzero(
                bg_mask) > 400 else corner_mask(*image.shape)
        )
        bg_offset = np.ma.array(image, mask=bg_mask).mean()
        masked = masked - bg_offset

        # 4. Calculate beam parameters from moments
        energy, centroid, variances = calc_moments(masked, *self.centroid)

        # Energy is 1 when the image contains only zeros
        # (fallback to avoid division by zero)
        if energy == 1:
            return

        major_axis, minor_axis = calc_beam_widths(*variances)
        angle = calc_rotation_angle(*variances)

        if major_axis < minor_axis:
            major_axis, minor_axis = minor_axis, major_axis
            angle += np.pi / 2

        return {
            "energy": energy,
            "centroid": centroid,
            "widths": (major_axis, minor_axis),
            "angle": angle,
        }

    def maximum(self):
        mask = rectangle_mask(
            self.image.shape, self.centroid, self.widths, angle=self.angle
        )
        image = np.ma.masked_array(self.image, mask=mask)
        neighbors = (self.PEAK_SIZE - 1) // 2

        height, width = image.shape
        x, y = np.unravel_index(np.argmax(image, axis=None), image.shape)[::-1]
        pixels = image[
            max(y - neighbors, 0): min(y + neighbors + 1, height),
            max(x - neighbors, 0): min(x + neighbors + 1, width),
        ]
        return pixels.mean(), (x, y)


@dataclass
class Ellipse:
    # Input
    image: np.ndarray = field(default_factory=lambda: np.array([]))

    centroid: tuple = (np.nan, np.nan)
    widths: tuple = (np.nan, np.nan)
    angle: float = np.nan

    _is_processed = False

    @classmethod
    def from_beam(cls, beam, scale=1):
        return cls(
            image=beam.image,
            centroid=beam.centroid,
            widths=tuple([w * scale for w in beam.widths]),
            angle=beam.angle,
        )

    def __post_init__(self):
        # Cast input to tuple
        self.centroid = tuple(self.centroid)
        self.widths = tuple(self.widths)

        # Check if everything is processed
        self._is_processed = (
            self.centroid != (np.nan, np.nan)
            and self.widths != (np.nan, np.nan)
            and self.angle != np.nan
        )

    @cached_property
    def _major_axis(self):
        if not self._is_processed:
            return np.array([]), np.array([])

        return self._values_along_axis(compare=operator.ge)

    @property
    def major_axis(self):
        if not self._is_processed:
            return np.array([]), np.array([])

        x, y = self._major_axis
        return (
            self._distance(x, y, ref=operator.le(*self.widths)),
            self.masked_image[y, x].astype(float),
        )

    @cached_property
    def _minor_axis(self):
        if not self._is_processed:
            return np.array([]), np.array([])

        return self._values_along_axis(compare=operator.le)

    @property
    def minor_axis(self):
        if not self._is_processed:
            return np.array([]), np.array([])

        x, y = self._minor_axis
        return (
            self._distance(x, y, ref=operator.ge(*self.widths)),
            self.masked_image[y, x].astype(float),
        )

    @property
    def x_axis(self):
        y0 = int(self.centroid[1])
        x_axis = self._get_range(np.s_[y0, :])
        y_axis = self.masked_image[y0, x_axis]
        return x_axis, y_axis

    @property
    def y_axis(self):
        x0 = int(self.centroid[0])
        y_axis = self._get_range(np.s_[:, x0])
        x_axis = self.masked_image[y_axis, x0]
        return y_axis, x_axis

    def _get_range(self, slice_):
        sliced = self._masked_image[slice_]
        start, stop = np.ma.notmasked_edges(sliced)
        return np.arange(start, stop)

    def _values_along_axis(self, *, compare):
        xc, yc = self.centroid
        dx, dy = self.widths
        v, h = self._masked_image.shape

        if compare(dx, dy):
            p0 = [max(xc - dx / 2, 0), yc]
            p1 = [min(xc + dx / 2, h - 1), yc]
        else:
            p0 = [xc, max(yc - dy / 2, 0)]
            p1 = [xc, min(yc + dy / 2, v - 1)]

        r0 = rotate_points(points=p0, origin=(xc, yc), angle=self.angle)
        r1 = rotate_points(points=p1, origin=(xc, yc), angle=self.angle)
        x, y = values_along_line(*r0, *r1)

        # Drop values out of bounds
        valid_x = np.logical_and(x >= 0, x < h)
        valid_y = np.logical_and(y >= 0, y < v)
        indices = np.logical_and(valid_x, valid_y)
        return x[indices], y[indices]

    def _distance(self, x, y, *, ref):
        if (x.size, y.size) == (0, 0):
            return np.array([])

        axis = [x, y][ref]

        dist = np.sqrt((x[-1] - x[0]) ** 2 + (y[-1] - y[0]) ** 2) / axis.size
        origin = distance.cdist([self.centroid], np.array([x, y]).T).argmin()
        return (np.arange(axis.size) - origin) * dist + self.centroid[ref]

    @cached_property
    def ellipse_mask(self):
        return ellipse_mask(
            self.image.shape, self.centroid, self.widths, angle=self.angle
        )

    @property
    def _masked_image(self):
        masked = np.ma.array(self.image, mask=self.ellipse_mask)
        offset = np.ma.array(self.image, mask=~self.ellipse_mask).mean()
        return masked - offset

    @cached_property
    def masked_image(self):
        return self._masked_image.filled(0)


def calc_centroid(image):
    total = image.sum()
    n_y, n_x = image.shape

    y_c = (image.sum(axis=1) * np.arange(n_y)).sum() / total
    x_c = (image.sum(axis=0) * np.arange(n_x)).sum() / total

    return x_c, y_c


def initial_widths(image, x_cent, y_cent):
    n_y, n_x = image.shape
    i_max = image[int(y_cent), int(x_cent)]

    w = np.zeros(4)
    w[0] = np.count_nonzero(
                image[int(y_cent): n_y, int(x_cent)] > (i_max * 0.5))
    w[1] = np.count_nonzero(image[0: int(y_cent), int(x_cent)] > (i_max * 0.5))
    w[2] = np.count_nonzero(image[int(y_cent), 0: int(x_cent)] > (i_max * 0.5))
    w[3] = np.count_nonzero(
                image[int(y_cent), int(x_cent): n_x] > (i_max * 0.5))

    w = np.amax(w) * 2
    return w, w


def _divergent(deltas, diff=0.3):
    # Calculate if changes are still significant
    return (
        np.mean(deltas[-3:]) > diff
        or np.subtract(*deltas[:-3:-1]) / deltas[-1] > 0.2
    )


# -----------------------------------------------------------------------------
# Moments


def calc_moments(im, m10=None, m01=None):
    # Prepare variables
    n_y, n_x = im.shape
    x = np.arange(n_x)
    y = np.arange(n_y)

    im_x = im.sum(axis=0)
    im_y = im.sum(axis=1)

    # Calculate zeroth- moment
    # Compute sum of all pixels (zeroth moment);
    # use 1 if result is 0 to avoid division by zero
    m00 = im_x.sum() or 1

    if m01 is None:
        m01 = (im_y * y).sum() / m00  # centroid along x
    if m10 is None:
        m10 = (im_x * x).sum() / m00  # centroid along y

    # Calculate second-order moments
    y_c = y - m01  # centered y
    m02 = (im_y * y_c**2).sum() / m00

    x_c = x - m10  # centered y
    m20 = (im_x * x_c**2).sum() / m00

    m11 = (im * x_c[None, :] * y_c[:, None]).sum() / m00

    return m00, (m10, m01), (m20, m02, m11)


def calc_rotation_angle(xx, yy, xy):
    if xx == yy:
        phi = np.sign(xy) * np.pi / 4
    else:
        phi = 0.5 * np.arctan(2 * xy / (xx - yy))

    return phi


def calc_beam_widths(xx, yy, xy):
    xx = abs(xx)
    yy = abs(yy)
    xy = abs(xy)

    if xx == yy:
        gamma = 0
        details = 2 * np.abs(xy)
    else:
        gamma = np.sign(xx - yy)
        details = gamma * np.sqrt((xx - yy) ** 2 + 4 * xy**2)

    dx = 2 * np.sqrt(2 * abs(xx + yy + details))
    dy = 2 * np.sqrt(2 * abs(xx + yy - details))

    return dx, dy


def calc_ellipticity(a, b):
    if a < b:
        a, b = b, a

    return b / a


# -----------------------------------------------------------------------------
# Masking


def ellipse_mask(shape, centroid, widths, angle=0):
    widths = tuple(int(w) for w in widths)

    overlay = Image.new("L", widths, color=0)
    draw = ImageDraw.Draw(overlay)
    draw.ellipse((0, 0, *widths), fill=1)

    rotated = overlay.rotate(-np.rad2deg(angle), expand=True)
    center = np.divide(rotated.size, 2)

    canvas = Image.new("L", shape[::-1], color=0)
    canvas.paste(rotated, tuple([int(a - b)
                 for a, b in zip(centroid, center)]))

    return ~np.array(canvas, dtype=bool)


def rectangle_mask(shape, centroid, widths, angle=0):
    a, b = np.divide(widths, 2)
    cos, sin = np.cos(angle), np.sin(angle)

    a_x, a_y = a * cos, a * sin
    b_x, b_y = -b * sin, b * cos

    coords = np.array([[a_x + b_x, a_y + b_y], [a_x - b_x, a_y - b_y]])
    coords = np.concatenate((coords, -coords), axis=0) + centroid

    canvas = Image.new("L", shape[::-1], color=1)
    ImageDraw.Draw(canvas).polygon([tuple(coord) for coord in coords], fill=0)
    return np.array(canvas, dtype=bool)


def corner_mask(n_y, n_x, pixels=10):
    # Create border mask
    mask = np.zeros((n_y, n_x), dtype=bool)

    # Calculate border width and height
    h = min(n_y, pixels)
    w = min(n_x, pixels)

    mask[:h, :w] = True
    mask[:h, -w:] = True
    mask[-h:, :w] = True
    mask[-h:, -w:] = True

    return mask


# -----------------------------------------------------------------------------
# Gaussian


def kernel_size(width):
    size = width // 10
    return int(max(size, 1))


def gaussian_kernel(size=5, sigma=None):
    if sigma is None:
        sigma = size / 10

    ax = np.linspace(-(size - 1) / 2.0, (size - 1) / 2.0, size)
    gauss = np.exp(-0.5 * np.square(ax) / np.square(sigma))
    kernel = np.outer(gauss, gauss)
    return kernel / np.sum(kernel)


def gaussian_filter(image, size=None, normalized=False):
    if size is None:
        size = kernel_size(min(image.shape))
    kernel = gaussian_kernel(size)
    filtered = signal.fftconvolve(image, kernel, mode="same")

    if normalized:
        filtered /= np.amax(filtered)

    return filtered


def fit_gaussian(x, y, super_gaussian=False):
    pos, width, r2 = np.nan, np.nan, np.nan
    p0 = None

    if not x.size:
        return pos, width, p0, r2

    # Fitting params
    try:
        p0 = list(initial_p0(x, y))
    except ValueError as e:
        print("Initial fit parameters not found:", e)
        return pos, width, p0, r2

    min_bounds = [0, -np.inf, -np.inf]
    max_bounds = [np.inf, np.inf, np.inf]

    if super_gaussian:
        p0 += [2]
        min_bounds += [1]
        max_bounds += [5]

    try:
        p0, _ = curve_fit(
            gaussian,
            x,
            y,
            p0=p0,
            bounds=(min_bounds, max_bounds),
            sigma=1 / (y ** 2),
            maxfev=100,
        )

        fit = gaussian(x, *p0)
        if np.isnan(fit.sum()):
            raise RuntimeError("Empty fit.")

        pos = p0[1]
        width = fwhm(p0[2], p0[-1] if super_gaussian else 2)
        r2 = r_squared(expected=fit, actual=y)
    except (TypeError, RuntimeError, ValueError) as e:
        print("Fit did not converge:", e)
        p0 = None

    return pos, width, p0, r2


def initial_p0(x, y):
    y_max = np.max(y)
    y = y / y_max
    y[y < 0.1] = 0
    y = y ** 4

    x0 = np.average(x, weights=y)
    sx = np.sqrt(np.average((x - x0) ** 2, weights=y)) * 4
    return y_max, x0, sx


def gaussian(x, height, x0, sigma, n=2):
    gauss = height * np.exp(-0.5 * np.abs((x - x0) / sigma) ** n)
    return gauss


def fwhm(sigma, n):
    return 2.0 * sigma * (2.0 * np.log(2.0)) ** (1 / n)


def r_squared(*, expected, actual):
    tss = np.sum((actual - np.mean(actual)) ** 2)
    rss = np.sum((actual - expected) ** 2)
    return 1 - rss / tss


# -----------------------------------------------------------------------------
# Others


def rotate_points(points, origin, angle):
    x_norm, y_norm = np.subtract(points, origin)
    sin, cos = np.sin(angle), np.cos(angle)

    x_rot = x_norm * cos - y_norm * sin
    y_rot = x_norm * sin + y_norm * cos

    return np.add((x_rot, y_rot), origin)


def values_along_line(x0, y0, x1, y1):
    x_diff = x1 - x0
    y_diff = y1 - y0

    if abs(x_diff) < abs(y_diff):
        return values_along_line(y0, x0, y1, x1)[::-1]

    if x0 > x1:
        return values_along_line(x1, y1, x0, y0)

    x = np.arange(int(x0), int(x1), dtype=float)
    y = x * y_diff / x_diff + (x1 * y0 - x0 * y1) / x_diff

    return x.astype(int), np.floor(y).astype(int)


def to_degrees(angle, normalized=True, reflected=False):
    if normalized:
        start, end = -np.pi, np.pi
        angle = np.mod(angle - start, end - start) + start
    angle = np.rad2deg(angle)
    if reflected:
        angle = 180 - (angle + 180) % 180
    return angle


def get_origin(beam, origin_type=Origin.NONE):
    if origin_type == Origin.IMAGE_CENTER:
        n_y, n_x = beam.image.shape
        return (n_x / 2, n_y / 2)
    elif origin_type == Origin.CENTROID:
        return beam.centroid
    else:
        return (0, 0)


def elongate(x):
    interval = np.diff(x)[0]
    tail_size = int(x.size / 4)

    left = (np.arange(tail_size) - tail_size) * interval + x[0]
    right = (np.arange(tail_size) + 1) * interval + x[-1]
    return np.concatenate((left, x, right))


def butterworth_filter(data, cutoff, order=2, btype="low"):
    cutoff = 1 / cutoff * 0.5

    b, a = signal.butter(order, cutoff, btype=btype, analog=False)
    y = signal.filtfilt(b, a, data)
    return y
