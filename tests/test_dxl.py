from dopyi.dxl import dxl
from icecream import ic
import pytest

pytestmark = pytest.mark.doors

MOD_PREFIX = "/Copy 2 of Example_Project/"

SYS1_MOD = MOD_PREFIX + "10_System/05_Stakeholder/SoW_Example"
SYS2_MOD = MOD_PREFIX + "10_System/05_SystemRequirements/SRS_Example"
TSTMOD = "/xxx_SYS_TestsProject/TestDoorsmod"
TSTMOD_B1 = "/xxx_SYS_TestsProject/TestDoorsmod@0.1"

dxlobj = dxl()



def test_get_baselines():
    dxlobj.open(TSTMOD)
    ic(dxlobj.get_baselines())


def test_get_last_baseline():
    dxlobj.open(TSTMOD)
    ic(dxlobj.get_last_baseline())

def test_get_inoutlinks():
    dxlobj.open(TSTMOD)
    ic(dxlobj.get_links(4))

def test_open_baseline():
    dxlobj.open(TSTMOD_B1)
    ic(dxlobj.get_links(4))