import pytest
import numpy as np
from icecream import ic
import pandas as pd
from dopyi.doorsmod import doorsmod

pytestmark = pytest.mark.doors

l_attr = ["Py Function", "Satisfied SRS", "Setup ID", "Tested By",
          "Automated", "Setup1 Result", "Setup1 Result", "Setup2 Result",
          "Exec. Time Estimation [h]", "# Dut to be Tested"]

MODNAME = "/xxx_SYS_TestsProject/TestDoorsmod2"


@pytest.fixture
def dsm():
    return doorsmod("/xxx_SYS_TestsProject/TestDoorsmod2")


@pytest.mark.del_module
def test_del_module(dsm: doorsmod):
    dsm.del_mod(True)


@pytest.mark.check_reload
def test_reload(dsm: doorsmod):
    dsm.read(force=True)
    del dsm
    dsm = doorsmod(MODNAME)
    dsm.read()
    for i, row in dsm.wcd.iterrows():
        ic(i, row)


@pytest.mark.new_objects
def test_change_value(dsm: doorsmod):
    dsm.check_mod(True, "Module to test Doorsmod class", "DOPYI_")
    dsm.read(force=True)
    # Add a new column to dsm.wcd dataframe named "Py Function"
    dsm.check_create_attr(l_attr)
    # Create 10 row in dsm.wcd dataframe with empty values
    for i in range(10):
        if i not in dsm.wcd.index:
            dsm.wcd.append(pd.Series(), ignore_index=True)
        dsm.wcd.loc[i] = np.nan
    dsm.write()


@pytest.mark.new_view
def test_new_view(dsm: doorsmod):
    dsm = doorsmod("/xxx_SYS_TestsProject/TestDoorsmod2")
    dsm.new_view("Standard All", l_attr)


@pytest.mark.change_values
def test_change_values(dsm: doorsmod):
    dsm.read(force=True)
    # Select a random column from dsm.wcd dataframe
    col = np.random.choice(l_attr)
    # Select a random row from dsm.wcd dataframe
    row = np.random.choice(dsm.wcd.index)
    # Write a random string to dsm.wcd dataframe
    ic(row, col)
    dsm.wcd.loc[row, col] = "".join(np.random.choice(["A", "B", "C", "E"], 10))
    dsm.wcd.to_excel("test.xlsx")
    dsm.write()


@pytest.mark.add_rows
def test_add_rows(dsm: doorsmod):
    dsm.read(force=True)
    for i in range(3):
        dsm.wcd.append(pd.Series(), ignore_index=True)
        ind = i
        col = np.random.choice(l_attr)
        dsm.wcd.loc[ind, col] = "".join(np.random.choice(["A", "B", "C", "E"], 10))
    dsm.write()


@pytest.mark.to_excel
def test_to_excel(dsm: doorsmod):
    if not dsm.read(force=True):
        raise AssertionError("Failed to read data")
    writer = pd.ExcelWriter("test.xlsx", engine='xlsxwriter')
    dsm.wcd.to_excel(writer, sheet_name="Module")
    dsm.wc_attrdef.to_excel(writer, sheet_name="AttrDef", index=False)
    writer.save()


@pytest.mark.from_excel
def test_from_excel(dsm: doorsmod):
    if not dsm.read(force=True):
        raise AssertionError("Failed to read data")
    dsm.wcd = pd.read_excel("test.xlsx", sheet_name="Module")
    dsm.wc_attrdef = pd.read_excel("test.xlsx", sheet_name="AttrDef")
    dsm.write()


@pytest.mark.get_last_baseline
def test_get_last_baseline(dsm: doorsmod):
    ic(dsm.get_last_baseline())


@pytest.mark.dxl_create_links
def test_dxl_create_links(dsm: doorsmod):
    try:
        dsm.open(dsm.name, "w")
        dsm.create_links("/xxx_SYS_TestsProject/TestDoorsmod@EL_1.0",
                         2, [8, 9], "/xxx_SYS_TestsProject/satisfy")
    except:
        pass
    finally:
        dsm.close()


@pytest.mark.dxl_delete_links
def test_dxl_delete_links(dsm: doorsmod):
    try:
        dsm.open(dsm.name, "w")
        dsm.delete_links("/xxx_SYS_TestsProject/TestDoorsmod@0.1",
                         2, [8, 9], "/xxx_SYS_TestsProject/satisfy")
    except Exception as e:
        pass
    finally:
        dsm.close()


@pytest.mark.dxl_delete_all_obj_links
def test_delete_all__obj_links(dsm: doorsmod):
    try:
        dsm.open(dsm.name, "w")
        dsm.delete_all_obj_links(2)
    except Exception as e:
        pass
    finally:
        dsm.close()


@pytest.mark.dxl_create_link_by_attr
def test_create_links_by_attr(dsm: doorsmod):
    dsm = doorsmod("/xxx_SYS_TestsProject/Example_SQT")
    dsm.read(force=True)
    s_target = "/xxx_SYS_TestsProject/TestDoorsmod"
    s_link_mod = "/xxx_SYS_TestsProject/satisfy"
    s_log = "linklog.txt"
    dsm.create_links_by_attr("Satisfied SRS", [s_target], [s_link_mod], s_log)
