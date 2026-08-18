"""Integration tests of the socket protocol against a fake DOORS server.

These verify basic_run_dxl / run_dxl / is_server_on and the dxl class
communication layer without any DOORS installation.
"""

import pytest

from dopyi.doorserver.server import (
    S_ECHO,
    DoorsDxlExecutionError,
    basic_run_dxl,
    is_server_on,
    run_dxl,
)
from dopyi.dxl import dxl

from tests.fake_doorserver import FakeDoorsServer


def test_basic_run_dxl_returns_payload_and_sends_request():
    with FakeDoorsServer(lambda req: "#####HELLO") as srv:
        assert basic_run_dxl(S_ECHO, srv.port, "#####") == "HELLO"
        assert srv.requests and "return_" in srv.requests[0]


def test_basic_run_dxl_wrong_starter_raises():
    # A reply without the starter means the DXL execution halted:
    # it must raise (with the reply and the command in the message),
    # not return a False sentinel that crashes later with
    # "'bool' object has no attribute 'strip'".
    with FakeDoorsServer(lambda req: "!!WRONG_STARTER") as srv:
        with pytest.raises(DoorsDxlExecutionError) as exc:
            basic_run_dxl(S_ECHO, srv.port, "#####")
    assert "!!WRONG_STARTER" in str(exc.value)
    assert "return_" in str(exc.value)


def test_run_dxl_does_not_rerun_command_on_dxl_error():
    # The server is alive but the DXL failed: run_dxl must NOT catch the
    # error and re-execute the command (dangerous for write commands).
    with FakeDoorsServer(lambda req: "no starter here") as srv:
        with pytest.raises(DoorsDxlExecutionError):
            run_dxl("print 1", srv.port, "@<")
        assert len(srv.requests) == 1


def test_basic_run_dxl_strips_payload():
    with FakeDoorsServer(lambda req: "#####  some value  \n") as srv:
        assert basic_run_dxl(S_ECHO, srv.port, "#####") == "some value"


def test_run_dxl_uses_already_running_server():
    # With a live server, run_dxl must answer without trying to start
    # DOORS (which would fail on a machine without it)
    with FakeDoorsServer(lambda req: "@<result data") as srv:
        assert run_dxl("print 1", srv.port, "@<") == "result data"


def test_dxl_object_communicates_through_socket():
    with FakeDoorsServer(lambda req: "@<hello from fake doors") as srv:
        d = dxl(port=srv.port)
        assert d.run_dxl("print 1") == "hello from fake doors"


def test_is_server_on_with_live_server():
    class DummyProc:
        """Mimics a Popen of a process that is still running."""

        def poll(self):
            return None

    with FakeDoorsServer() as srv:  # default handler answers #####HELLO
        assert is_server_on(DummyProc(), srv.port) is True
