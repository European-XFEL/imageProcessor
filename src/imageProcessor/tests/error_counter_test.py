#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on October 10, 2013
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################
from pytest import approx

from ..common import ErrorCounter

WIN_SIZE = 30  # The window size


def test_error_counter():
    error_counter = ErrorCounter(window_size=WIN_SIZE)

    # Initial values
    assert error_counter.size == 0
    assert error_counter.fraction == approx(0.0, abs=0.01)
    assert not error_counter.warn

    # Append all successes to counter
    for _ in range(2 * WIN_SIZE):
        error_counter.append()
    assert error_counter.size == WIN_SIZE
    assert error_counter.fraction == approx(0.0, abs=0.01)
    assert not error_counter.warn

    # Append one failure (10%)
    coeff = 0.1
    for _ in range(int(coeff * WIN_SIZE)):
        error_counter.append(error=True)
    assert error_counter.fraction == approx(coeff, abs=0.01)
    assert not error_counter.warn

    # Append another 10% failures (20% in total)
    for _ in range(int(coeff * WIN_SIZE)):
        error_counter.append(error=True)
    assert error_counter.fraction == approx(coeff * 2, abs=0.01)
    assert error_counter.warn

    # Increase threshold to 0.25
    error_counter.threshold = 0.25
    assert not error_counter.warn

    # Clear and check again
    error_counter.clear()
    assert error_counter.size == 0
    assert error_counter.fraction == approx(0.0, abs=0.01)
    assert not error_counter.warn


def test_epsilon():
    error_counter = ErrorCounter(
        window_size=100, threshold=0.1, epsilon=0.01)

    # Append all successes to counter
    for _ in range(100):
        error_counter.append()
    assert not error_counter.warn

    # Append 10 failures - no warn yet
    for _ in range(10):
        error_counter.append(True)
    # fraction (0.10) < threshold + epsilon (0.11)
    assert not error_counter.warn

    # Append one more failure - enter warn
    error_counter.append(True)
    # Now fraction (0.11) == threshold + epsilon (0.11)
    assert error_counter.warn

    # Clear
    error_counter.clear()
    assert not error_counter.warn

    # Append 10 failures - enter warn
    for _ in range(10):
        error_counter.append(True)
    # fraction (1.00) >= threshold + epsilon (0.11)
    assert error_counter.warn

    # Append 90 successes - still warn
    for _ in range(90):
        error_counter.append()
    # fraction (0.10) >= threshold-epsilon (0.09)
    assert error_counter.warn

    # Append one more success - leave warn
    error_counter.append()
    # fraction (0.09) <= threshold-epsilon (0.09)
    assert not error_counter.warn


def test_error_squeezing():
    error_counter = ErrorCounter(window_size=WIN_SIZE)

    # Initial values
    assert error_counter.size == 0
    assert error_counter.fraction == approx(0.0, abs=0.01)
    assert not error_counter.warn

    # Append one failure (100%)
    error_counter.append(True)
    assert error_counter.fraction == approx(1.0, abs=0.01)
    assert error_counter.warn

    # Check error squeezing
    for _ in range(WIN_SIZE):
        error_counter.append(True)
    assert error_counter.size == WIN_SIZE
    assert error_counter.fraction == approx(1.0, abs=0.01)
    assert error_counter.warn
    for _ in range(WIN_SIZE):
        error_counter.append()
    assert error_counter.fraction == approx(0.0, abs=0.01)
    assert not error_counter.warn
