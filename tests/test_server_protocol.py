"""Integration tests of the socket protocol against a fake DOORS server.

These verify basic_run_dxl / run_dxl / is_server_on and the dxl class
communication layer without any DOORS installation.
"""

from dopyi.doorserver.server import (
    S_ECHO,
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


def test_basic_run_dxl_wrong_starter_returns_false():
    with FakeDoorsServer(lambda req: "!!WRONG_STARTER") as srv:
        assert basic_run_dxl(S_ECHO, srv.port, "#####") is False


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
