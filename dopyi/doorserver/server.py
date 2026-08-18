"""A module used to run DXL command in DOORS using a Local Server.

    The communication between Python and the local server is done
    through Socket connection.

    Features:
        - Auto Management of Local DOORS server process
        - Multi Local DOORS server management
        - DOORS password management

    Attributes:
        run_dxl(s_cmd: string, n_port: int, s_starter: string)
            return the _return value of a DXL command <s_cmd> using the
            port <n_port> for the socket connection to the server. The
            returning value is considered valid if it starts with
            <s_starter> string.
            Example:
                    s_cmd =
                    "Item i_mod = item \"<module_path_name
                    m = module(i_mod)
                    Object o = gotoObject(10, m)
                    _return \"#####\" o."Object ID" "***" o."ASIL" "
                    n_port = 5094
                    s_starter = "#####"

                    The function will return a string like:
                    "#####LH_MOD_10***A" where "#####"

            This function auto manage the server run, if it is the first
            time you connect to DOORS using this function it ask you to
            write your username and password and it will store it locally.
            If you change the DOORS password the function recognize the
            change and ask the new password auutomatically.

            Using different port you can run multiple server in parallel.

        show_prompt(show=True)
            used to set if the Local DOORS Servers are hide or not.
            If show = True you will see the DOORS prompt with the
            DXL command log.

        close_all()
            Close all opened Local DOORS sever.
        
    Author: Elia Ribaldone
"""

import sys
from os.path import exists
import os
import socket
import signal
import subprocess
from easygui import multpasswordbox
from time import sleep

from dopyi.doorserver import S_DOORSERVER
from dopyi.doorserver import S_DOORSERVER_LIB
from dopyi.doorserver import S_DOORSERVER_NEW
from dopyi.doorserver import S_DOORSKEY
from dopyi.doors_discovery import resolve_doors_exe

D_PORTS = {}
D_PROC = {}

B_SHOW_PROMPT = True
B_DXL_REWRITE = False


class DoorsDxlExecutionError(Exception):
    """Raised when DOORS replies with a corrupted/missing answer,
    typically because the DXL execution halted with an error."""

    def __init__(self, reply, cmd=None):
        self.reply = reply
        self.cmd = cmd
        s_cmd = (cmd or "").strip()
        if len(s_cmd) > 300:
            s_cmd = s_cmd[:300] + " [...]"
        super().__init__(
            "DOORS did not return a valid answer (the DXL execution "
            "probably halted, check the DOORS console).\n"
            f"  Reply received: {reply!r}\n"
            f"  DXL command sent:\n{s_cmd}")


class DoorsLoginAbortedError(Exception):
    """Raised when the user cancels the DOORS login dialog."""

# f_user = os.path.join(os.path.expanduser('~'),"Documents","user.txt")

# s_BATCHSERVER = os.path.join("..", "..", "batchserver.dxl")

#####################################
# DOORS Connection and script run
#####################################


def getDOORS_UserPassw(f_user_passw, ask=False):
    """ Manage DOORS username and password with a single dialog.

    Parameters
    -----------------------------------
    f_user_passw: string
        the filename of the file used to store the username
        and password of the user.
    ask: bool
        used to force the user/passw ask to user even
        if it is already present in the f_user_passw.

    Raises
    -----------------------------------
    DoorsLoginAbortedError
        if the user cancels the dialog.

    The username is stripped (leading/trailing spaces are never
    valid in DOORS usernames), the password is kept verbatim.
    """
    if not exists(f_user_passw) or ask:
        if ask:
            s_msg = ("DOORS login failed, please check your "
                     "credentials.\n(usernames with spaces are "
                     "supported)")
        else:
            s_msg = "Insert your DOORS credentials:"
        # multpasswordbox masks only the last field
        l_ret = multpasswordbox(s_msg, "DOORS login",
                                ["Username", "Password"])
        if l_ret is None:
            raise DoorsLoginAbortedError(
                "DOORS login cancelled by the user")
        user = l_ret[0].strip()
        passw = l_ret[1]
        with open(f_user_passw, "w") as fp:
            fp.write(user + "\n")
            fp.write(passw + "\n")
    else:
        with open(f_user_passw, "r") as fp:
            user = fp.readline().strip()
            passw = fp.readline().rstrip("\n")

    return [user, passw]


S_ECHO = """
return_ "#####HELLO"
"""


def is_server_on(proc, n_port):
    """ Return True if the given process is a running server.

    Parameters
    -----------------------------------
    proc: Popen
        Popen object of the process you has tried to open,
        this process has to be a Local DOORS database with
        socket connection through port n_port
    n_port: int
        the number of the Socket port of the Local DOORS
        database opened in the proc process.

    """
    for i in range(0, 12):
        sleep(1)
        if proc.poll():
            return False
        try:
            ret = basic_run_dxl(S_ECHO, n_port, "#####")
        except:
            ret = "no"
        if ret == "HELLO":
            return True
    return False


def show_prompt(show=True):
    """ Set if the prompt is shown.

    Parameters
    -----------------------------------
    show: bool
        if True the terminal of the Local DOORS server
        is shown and it will print the log of the DXl
        command you run.

    The function set the B_SHOW_PROMPT constants and
    kill all already running Server if the B_SHOW_PROMPT
    value change, in this way they are reopened with
    the new show setting.
    """
    global B_SHOW_PROMPT, B_DXL_REWRITE
    old_show = B_SHOW_PROMPT
    B_SHOW_PROMPT = show
    if B_SHOW_PROMPT != old_show:
        B_DXL_REWRITE = True
        for n_port, proc in D_PROC.items():
            proc.kill()
            run(n_port)
        B_DXL_REWRITE = False


def close_all():
    """ Close all opened Local DOORS sever.
    """
    for n_port, proc in D_PROC.items():
        proc.kill()


def run(n_port=5094, doors_exe=None):
    """ Run a Local DOORS server with the specified Socket port.

    Parameters:
    ----------------------------------
    n_port: int
        the number of the socket port used for the
        local server. from 1024 to 65535
    doors_exe: str
        full path of the doors.exe to use; if None it is
        discovered automatically (DOPYI_DOORS_EXE env var,
        saved choice, DOORSHOME, registry, standard install
        paths - see dopyi.doors_discovery)

    The function steps are:
    -   create the dxl script in localdatabase dir coping the doorserver.dxl
            and substituting the port, this is done if the file is not already
            created in the current session
    -   check if the server is openend or not
    -   if the server is not opened run it
    -   The password is managed using a support file called userpassw.txt
            in the localdatabase dir, if the password is not stored or
            it is wrong the function use a login dialog to ask the
            correct username and password.
    """
    global D_PROC, D_PORTS, B_SHOW_PROMPT

    if n_port not in D_PORTS.keys() or B_DXL_REWRITE:
        fp = open(S_DOORSERVER, "r")
        data = fp.read()
        fp.close()
        # Modify port number
        data = data.replace("CONNECTION_PORT", str(n_port))
        # Point the include to the packaged lib_doorserver.dxl
        data = data.replace("#include <lib_doorserver.dxl>",
                            "#include <" + S_DOORSERVER_LIB + ">")
        if B_SHOW_PROMPT:
            data = data.replace("""//PRINT_LINE""", "print")
        new_doorserver = S_DOORSERVER_NEW + str(n_port) + ".dxl"
        D_PORTS[n_port] = new_doorserver
        fp = open(new_doorserver, "w")
        fp.write(data)
        fp.close()
    else:
        new_doorserver = D_PORTS[n_port]

    try:
        # If the server is active this command works without error
        ret = basic_run_dxl(S_ECHO, n_port, "#####")
        # print("The server is already active" + str(ret))
    except:
        # open the server
        if doors_exe is None:
            doors_exe = resolve_doors_exe()

        bl_reask = False
        while True:
            [user, passw] = getDOORS_UserPassw(S_DOORSKEY, bl_reask)

            # Argument list (no shell string): usernames with spaces
            # and passwords with quotes/backslashes are passed as-is.
            cmd = [doors_exe, "-u", user, "-pass", passw,
                   "-b", new_doorserver]
            pro = subprocess.Popen(cmd)
            D_PROC[n_port] = pro

            if is_server_on(pro, n_port):
                break
            bl_reask = True
    return True


def basic_run_dxl(s_cmd, n_port, s_starter):
    """ Connect to the local server and run a DXL code.

    Parameters:
    --------------------------------
    s_cmd : str
        the DXl code to execute in DOORS, the command
        must has the "_return" command at the end with
        the string you want to return.
    n_port : int
        the number of the socket port used for the
        local server. from 1024 to 65535
    s_starter : string
        the starting string of the returning value, it
        is used to check if the returning value is
        corrupted.

    Like run_dxl but this function get an error if
    the local DOORS server isn't active.
    """
    # Open soket
    sok = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sok.connect(("127.0.0.1", n_port))

    # Send dxl program
    sok.send(s_cmd.encode())

    # Receive data from doors
    rcv = sok.recv(134217728)
    ret_byte_data = b""  # rcv

    while rcv != b'':
        ret_byte_data += rcv
        rcv = sok.recv(134217728)

    # Close socket
    sok.close()

    # Analyze receiving data and converting in dict
    stringa = ret_byte_data.decode("utf-8")
    # ic(stringa)
    stringa = stringa.replace("b'", "").replace("'", "")

    if stringa[0:len(s_starter)] != s_starter:
        raise DoorsDxlExecutionError(stringa, s_cmd)
    return stringa[len(s_starter):].strip()


def run_dxl(s_cmd, n_port, s_starter):
    """Run a DXL code in DOORS and get the return value.

    Parameters:
    --------------------------------
    s_cmd : str
        the DXl code to execute in DOORS, the command
        must has the "_return" command at the end with
        the string you want to return.
    n_port : int
        the number of the socket port used for the
        local server. from 1024 to 65535
    s_starter : string
        the starting string of the returning value, it
        is used to check if the returning value is
        corrupted.

    This function communicate to DOORS through a local
    server written in DXL, the template used is
    dopy/doorserver/doorserver.dxl, this script is
    customize according to the correct socket port and
    written in the S_DOORSERVER directory, then it is
    runned in DOORS. The server wait for socket communication
    from Ptyhon, receive DXL commands, execute it in DOORS
    and get back the returning value.
    The server use dopy/doorserver/lib_doorserver.dxl
    library, so inside s_cmd you can use the DXL functions
    you find in that library.
    """
    try:
        return basic_run_dxl(s_cmd, n_port, s_starter)
    except OSError:
        # Socket error: the local DOORS server is not running yet.
        # DoorsDxlExecutionError is NOT caught here on purpose: the
        # command reached DOORS and failed, re-running it could
        # execute a write command twice.
        run(n_port)
        return basic_run_dxl(s_cmd, n_port, s_starter)
