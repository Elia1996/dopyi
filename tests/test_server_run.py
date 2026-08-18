"""DOORS-free tests of the server login flow (run + credentials).

They verify that doors.exe is started with a proper argument list
(usernames with spaces, passwords with quotes/backslashes) and that
the credential dialog handles stripping and cancellation.
"""

import pytest

import dopyi.doorserver.server as server


class DummyProc:
    """Mimics a Popen of a process that is still running."""

    def poll(self):
        return None

    def kill(self):
        pass


@pytest.fixture
def popen_calls(monkeypatch, tmp_path):
    """Patch everything around run() so no DOORS is needed.

    Returns a dict where the Popen arguments are recorded.
    """
    calls = {}

    def raise_conn_refused(*args, **kwargs):
        raise ConnectionRefusedError()

    def fake_popen(args, *a, **k):
        calls["args"] = args
        return DummyProc()

    monkeypatch.setattr(server, "basic_run_dxl", raise_conn_refused)
    monkeypatch.setattr(server, "resolve_doors_exe",
                        lambda: r"C:\Program Files\IBM\Rational\DOORS"
                                r"\9.7\bin\doors.exe")
    monkeypatch.setattr(server, "is_server_on", lambda proc, port: True)
    monkeypatch.setattr(server.subprocess, "Popen", fake_popen)
    # port already "prepared" so run() does not write the dxl file
    monkeypatch.setitem(server.D_PORTS, 5099, str(tmp_path / "srv.dxl"))
    return calls


def test_run_passes_spaced_username_as_single_argument(
        popen_calls, monkeypatch):
    monkeypatch.setattr(
        server, "getDOORS_UserPassw",
        lambda f, ask=False: ["Mario Rossi", 'p"a\\ss word'])

    server.run(5099)

    args = popen_calls["args"]
    assert isinstance(args, list), \
        "doors.exe must be started with an argument list, not a string"
    assert args[args.index("-u") + 1] == "Mario Rossi"
    assert args[args.index("-pass") + 1] == 'p"a\\ss word'


def test_run_writes_lib_include_in_generated_dxl_not_in_template(
        popen_calls, monkeypatch, tmp_path):
    # The absolute path of lib_doorserver.dxl must be injected in the
    # per-port generated file, NOT by rewriting the packaged template
    # (which dirties the git tree and breaks read-only installs).
    monkeypatch.setattr(
        server, "getDOORS_UserPassw",
        lambda f, ask=False: ["user", "passw"])
    monkeypatch.setattr(server, "S_DOORSERVER_NEW",
                        str(tmp_path / "doorserver_"))
    monkeypatch.delitem(server.D_PORTS, 5099, raising=False)

    server.run(5099)

    with open(server.D_PORTS[5099]) as fp:
        s_generated = fp.read()
    assert "#include <" + server.S_DOORSERVER_LIB + ">" in s_generated

    with open(server.S_DOORSERVER) as fp:
        s_template = fp.read()
    assert "#include <lib_doorserver.dxl>" in s_template, \
        "the packaged template must stay generic"


def test_get_user_passw_cancel_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "multpasswordbox", lambda *a, **k: None)
    with pytest.raises(server.DoorsLoginAbortedError):
        server.getDOORS_UserPassw(str(tmp_path / "up.txt"), ask=True)


def test_get_user_passw_roundtrip_strips_user_keeps_passw(
        monkeypatch, tmp_path):
    f_creds = str(tmp_path / "up.txt")
    monkeypatch.setattr(server, "multpasswordbox",
                        lambda *a, **k: ["  Mario Rossi  ", " s3cret "])
    assert server.getDOORS_UserPassw(f_creds) == ["Mario Rossi", " s3cret "]

    # Second call must read from the file without showing the dialog
    monkeypatch.setattr(
        server, "multpasswordbox",
        lambda *a, **k: pytest.fail("dialog must not be shown"))
    assert server.getDOORS_UserPassw(f_creds) == ["Mario Rossi", " s3cret "]
