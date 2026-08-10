"""Create Doors local dir for data
Author: Elia Ribaldone, ribaldoneelia@gmail.com
"""
__all__ = ["dxl", "doorsmod", "doorserver", "std"]

from importlib.metadata import version, PackageNotFoundError
import os

P_DATA_SAVE = os.path.join(os.path.expanduser('~'), "DoorsLocalDatabase")
if not os.path.exists(P_DATA_SAVE):
    os.makedirs(P_DATA_SAVE)

try:
    __version__ = version("dopyi")
except PackageNotFoundError:
    __version__ = "unknown"