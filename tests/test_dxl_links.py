"""DOORS-free tests of dxl.get_links error handling.

They reproduce the failure seen in the field: a link whose module
cannot be resolved used to halt the DXL execution and crash Python
with "'bool' object has no attribute 'strip'".
"""

import pytest

from dopyi.doorserver.server import DoorsDxlExecutionError
from dopyi.dxl import AbsnoNotFoundError, dxl

from tests.fake_doorserver import FakeDoorsServer

S_UNRESOLVED = "<unresolved module>"


def test_get_links_absno_not_found_raises():
    reply = "@<Error:#1:Absolute number not found"
    with FakeDoorsServer(lambda req: reply) as srv:
        d = dxl(port=srv.port)
        with pytest.raises(AbsnoNotFoundError):
            d.get_links(10)


def test_get_links_halted_dxl_raises_execution_error():
    # DXL halted: DOORS sends back garbage without the starter
    with FakeDoorsServer(lambda req: "-R-E- DXL: null Module") as srv:
        d = dxl(port=srv.port)
        with pytest.raises(DoorsDxlExecutionError):
            d.get_links(1063)


def test_get_links_keeps_unresolved_module_marker():
    reply = ("@<KEY:in<#>/links/satisfies<#>" + S_UNRESOLVED + "<#>12<#>"
             "KEY:out<#>/links/satisfies<#>/Project/Target<#>7<#>")
    with FakeDoorsServer(lambda req: reply) as srv:
        d = dxl(port=srv.port)
        d_links = d.get_links(10)
    assert d_links["in"][0]["mod"] == S_UNRESOLVED
    assert d_links["in"][0]["absno"] == "12"
    assert d_links["out"][0]["mod"] == "/Project/Target"
