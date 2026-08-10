import pytest
from dopyi.doorsmod import doorsmod

TSTMOD_B1 = "/xxx_SYS_TestsProject/TestDoorsmod@0.1"


def test_read_baseline():
    dsm = doorsmod(TSTMOD_B1)
    dsm.read(force=True)
    dsm.wcd.to_excel("test.xlsx", sheet_name="Module")
    # verify that dsm.wcd is not an empty dataframe
    assert not dsm.wcd.empty
