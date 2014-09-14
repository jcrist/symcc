"""Functions to get the correct symcc version to run tests."""

from __future__ import print_function

import os
import sys


def path_hack():
    """Hack sys.path to import correct (local) symcc."""
    this_file = os.path.abspath(__file__)
    symcc_dir = os.path.join(os.path.dirname(this_file), "..")
    symcc_dir = os.path.normpath(symcc_dir)
    sys.path.insert(0, symcc_dir)
    return symcc_dir
