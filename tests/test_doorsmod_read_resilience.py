"""DOORS-free test: a broken object must not abort the module read.

If get_links (or the attribute read) of a single object raises a
DoorsDxlExecutionError, __doorsread must skip that object, keep
reading the others and report the skipped absnos at the end.
"""

import pytest

from dopyi.doorserver.server import DoorsDxlExecutionError
from dopyi.doorsmod import L_DEFAULT_ATTR_RO, doorsmod
from dopyi.dxl import dxl

L_MOD_ATTRS = ["Absolute Number", "Object Text", "MyAttr"]


class FakeConn:
    def __init__(self):
        self.messages = []

    def send(self, msg):
        self.messages.append(msg)


@pytest.fixture
def dsm(monkeypatch, tmp_path):
    """A doorsmod instance detached from DOORS (no __init__)."""

    def fake_get_links(sf, absno):
        if absno == 2:
            raise DoorsDxlExecutionError("-R-E- DXL: null Module",
                                         "objGetInOutLink(m, 2, ...)")
        return {"in": [], "out": [], "ext": []}

    monkeypatch.setattr(doorsmod, "open", lambda sf, name, mode="r": True)
    monkeypatch.setattr(doorsmod, "mod",
                        property(lambda sf: None, lambda sf, v: None))
    monkeypatch.setattr(doorsmod, "mod_absnos",
                        property(lambda sf: [1, 2, 3]))
    monkeypatch.setattr(doorsmod, "attr_names",
                        property(lambda sf: list(L_MOD_ATTRS)))
    monkeypatch.setattr(doorsmod, "get_obj_attr_values",
                        lambda sf, absno, attrs: ["v"] * len(attrs))
    monkeypatch.setattr(doorsmod, "get_links", fake_get_links)
    monkeypatch.setattr(
        doorsmod, "get_attr_def",
        lambda sf, attr: {"type": "Text", "basetype": "Text",
                          "l_enum": [], "multi": False, "default": ""})

    dsm = doorsmod.__new__(doorsmod)
    dsm._doorsmod__name = "/Fake/Module"
    dsm._p_data = str(tmp_path / "data.pkl")
    dsm._p_attrdef = str(tmp_path / "attrdef.pkl")
    return dsm


def test_doorsread_skips_broken_object_and_reports_it(dsm):
    conn = FakeConn()

    ret = dsm._doorsmod__doorsread(conn)

    assert ret is True
    # object 1 and 3 read normally
    assert dsm.wcd.loc[1, "MyAttr"] == "v"
    assert dsm.wcd.loc[3, "MyAttr"] == "v"
    # object 2 skipped, left empty
    assert dsm.wcd.loc[2, "MyAttr"] == ""
    # the user is told about the skipped object
    l_warn = [m for m in conn.messages
              if isinstance(m, str) and "skipped" in m]
    assert l_warn, "a warning about skipped objects must be sent"
    assert "2" in l_warn[0]
