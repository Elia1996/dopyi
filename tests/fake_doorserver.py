"""A fake local DOORS server for tests.

Replicates the socket protocol used by dopyi.doorserver.server:
the client connects, sends the DXL program in one message and then
reads the response until the server closes the connection. A valid
response must start with the agreed starter string (e.g. "#####").

This makes dxl/run_dxl code paths testable on machines without a
DOORS installation.
"""

import socket
import threading


class FakeDoorsServer:
    """Context manager serving fake DXL responses on an ephemeral port.

    Usage::

        with FakeDoorsServer(lambda req: "#####HELLO") as srv:
            basic_run_dxl(cmd, srv.port, "#####")

    The received requests are recorded in ``self.requests``.
    """

    def __init__(self, handler=None, host="127.0.0.1"):
        self.host = host
        self.handler = handler or (lambda s_request: "#####HELLO")
        self.requests = []
        self.port = None
        self._sock = None
        self._thread = None
        self._stop = threading.Event()

    def __enter__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind((self.host, 0))
        self.port = self._sock.getsockname()[1]
        self._sock.listen(5)
        self._sock.settimeout(0.2)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self

    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with conn:
                try:
                    data = conn.recv(1 << 20)
                except OSError:
                    continue
                s_request = data.decode("utf-8", "replace")
                self.requests.append(s_request)
                s_response = self.handler(s_request)
                if s_response is not None:
                    try:
                        conn.sendall(s_response.encode())
                    except OSError:
                        pass
            # closing the connection ends the client's recv loop

    def __exit__(self, exc_type, exc_value, traceback):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self._sock is not None:
            self._sock.close()
        return False
