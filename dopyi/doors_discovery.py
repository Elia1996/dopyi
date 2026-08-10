"""Discovery of the locally installed IBM Rational DOORS client.

This module finds the ``doors.exe`` executable to be used by the local
DOORS server (:mod:`dopyi.doorserver.server`). The search order used by
:func:`resolve_doors_exe` is:

1. ``DOPYI_DOORS_EXE`` environment variable (explicit override)
2. Choice previously saved in ``~/DoorsLocalDatabase/doors_exe.json``
3. ``%DOORSHOME%\\bin\\doors.exe`` (DOORSHOME is the canonical DOORS
   environment variable, see the DXL reference manual)
4. Windows registry: ``Software\\Telelogic\\DOORS`` keys (the section
   documented in the DXL reference manual) and the standard uninstall
   keys with "DOORS" in their display name
5. Standard filesystem locations, e.g.
   ``C:\\Program Files\\IBM\\Rational\\DOORS\\<version>\\bin\\doors.exe``
   and the older ``C:\\Program Files\\Telelogic\\DOORS_<version>``

If more than one installation is found the user is asked to pick one
(GUI list), or the highest version is taken in non-interactive mode.
The choice is persisted and re-validated at every startup.

All discovery functions are pure and receive injectable dependencies
(environment mapping, registry value iterator, search roots) so they
are fully unit-testable on machines without DOORS installed.
"""

import json
import os
import re
import sys
from dataclasses import dataclass
from glob import glob
from pathlib import Path

S_ENV_EXE = "DOPYI_DOORS_EXE"
S_ENV_DOORSHOME = "DOORSHOME"
S_EXE_NAME = "doors.exe"

# File where the resolved/chosen executable is persisted
F_SAVED_CHOICE = os.path.join(os.path.expanduser("~"),
                              "DoorsLocalDatabase", "doors_exe.json")

RE_VERSION = re.compile(r"(\d+(?:\.\d+)+)")


class DoorsNotFoundError(Exception):
    """Raised when no DOORS installation can be found."""

    def __init__(self, message=None):
        if message is None:
            message = (
                "No IBM Rational DOORS installation found. Searched: "
                f"{S_ENV_EXE} environment variable, saved configuration, "
                f"%{S_ENV_DOORSHOME}%, Windows registry and standard "
                "install locations. If DOORS is installed in a custom "
                f"path, set the {S_ENV_EXE} environment variable to the "
                "full path of doors.exe."
            )
        super().__init__(message)


@dataclass(frozen=True)
class DoorsInstall:
    """A discovered DOORS installation."""
    exe: str        # full path of doors.exe
    version: str    # e.g. "9.7", "" if unknown
    source: str     # where it was found: doorshome/registry/filesystem

    @property
    def version_tuple(self):
        """Version as a tuple of ints, () if unknown (sorts lowest)."""
        if not self.version:
            return ()
        return tuple(int(x) for x in self.version.split("."))

    def label(self):
        s_ver = self.version if self.version else "unknown version"
        return f"DOORS {s_ver} - {self.exe}"


def parse_version(s_path):
    """Extract a dotted version (e.g. "9.7") from a path/string.

    Returns the last dotted-number group found, "" if none: the last
    group is used because install paths like
    "...\\Rational\\DOORS\\9.7\\bin" have the version as the deepest
    component.
    """
    l_found = RE_VERSION.findall(str(s_path))
    return l_found[-1] if l_found else ""


def validate_install(s_path):
    """Return the full doors.exe path for a candidate path, or None.

    The candidate may be the executable itself, an install root
    (containing bin/doors.exe) or the bin directory.
    """
    if not s_path:
        return None
    p = Path(str(s_path).strip().strip('"'))
    try:
        if p.name.lower() == S_EXE_NAME and p.is_file():
            return str(p)
        if p.is_dir():
            for sub in (Path("bin") / S_EXE_NAME, Path(S_EXE_NAME)):
                exe = p / sub
                if exe.is_file():
                    return str(exe)
    except OSError:
        return None
    return None


def candidates_from_doorshome(env=None):
    """Candidates from the DOORSHOME environment variable."""
    if env is None:
        env = os.environ
    exe = validate_install(env.get(S_ENV_DOORSHOME))
    if exe is None:
        return []
    return [DoorsInstall(exe, parse_version(exe), "doorshome")]


def iter_registry_values():
    """Yield path-like string values from DOORS-related registry keys.

    Scanned keys:
    - HKCU/HKLM ``Software\\Telelogic\\DOORS`` (and WOW6432Node): the
      section where DOORS stores its configuration per version
    - Uninstall keys with "DOORS" in DisplayName: InstallLocation and
      DisplayIcon values

    Silently yields nothing on non-Windows platforms or on access
    errors: discovery must never crash.
    """
    if sys.platform != "win32":
        return
    import winreg

    def iter_subkeys(root, path):
        try:
            with winreg.OpenKey(root, path) as key:
                n = winreg.QueryInfoKey(key)[0]
                for i in range(n):
                    yield path + "\\" + winreg.EnumKey(key, i)
        except OSError:
            return

    def iter_values(root, path):
        try:
            with winreg.OpenKey(root, path) as key:
                n = winreg.QueryInfoKey(key)[1]
                for i in range(n):
                    name, value, typ = winreg.EnumValue(key, i)
                    if typ == winreg.REG_SZ and value:
                        yield name, value
        except OSError:
            return

    l_doors_roots = [
        (winreg.HKEY_CURRENT_USER, r"Software\Telelogic\DOORS"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Telelogic\DOORS"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Telelogic\DOORS"),
    ]
    for root, base in l_doors_roots:
        for verkey in iter_subkeys(root, base):
            for subkey in [verkey, verkey + r"\Config"]:
                for _, value in iter_values(root, subkey):
                    yield value

    l_uninstall_roots = [
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER,
         r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for root, base in l_uninstall_roots:
        for appkey in iter_subkeys(root, base):
            d_vals = dict(iter_values(root, appkey))
            if "doors" not in d_vals.get("DisplayName", "").lower():
                continue
            for name in ("InstallLocation", "DisplayIcon"):
                if d_vals.get(name):
                    # DisplayIcon may be "path,0"
                    yield d_vals[name].split(",")[0]


def candidates_from_registry(registry_values=None):
    """Candidates from the Windows registry.

    registry_values: iterable of path-like strings, injectable for
    tests; defaults to the real registry scan.
    """
    if registry_values is None:
        registry_values = iter_registry_values()
    l_out = []
    for value in registry_values:
        exe = validate_install(value)
        if exe is not None:
            l_out.append(DoorsInstall(exe, parse_version(exe), "registry"))
    return l_out


def default_search_roots(env=None):
    """Standard install locations of the modern and legacy DOORS."""
    if env is None:
        env = os.environ
    l_pf = []
    for var in ("ProgramFiles", "ProgramFiles(x86)"):
        if env.get(var):
            l_pf.append(env[var])
    if not l_pf:
        l_pf = [r"C:\Program Files", r"C:\Program Files (x86)"]
    l_roots = []
    for pf in l_pf:
        l_roots.append(os.path.join(pf, "IBM", "Rational", "DOORS"))
        l_roots.append(pf)  # for Telelogic\DOORS_9.x style dirs
    return l_roots


def candidates_from_filesystem(search_roots=None, env=None):
    """Candidates found by globbing the standard install locations."""
    if search_roots is None:
        search_roots = default_search_roots(env)
    l_patterns = []
    for root in search_roots:
        l_patterns.append(os.path.join(root, "*", "bin", S_EXE_NAME))
        l_patterns.append(os.path.join(root, "Telelogic", "DOORS*",
                                       "bin", S_EXE_NAME))
    l_out = []
    for pattern in l_patterns:
        for exe in glob(pattern):
            exe = validate_install(exe)
            if exe is not None:
                l_out.append(DoorsInstall(exe, parse_version(exe),
                                          "filesystem"))
    return l_out


def find_candidates(env=None, registry_values=None, search_roots=None):
    """Find all DOORS installations, deduplicated, highest version first.

    All parameters are injectable for tests; by default the real
    environment, registry and filesystem are used.
    """
    l_all = (candidates_from_doorshome(env)
             + candidates_from_registry(registry_values)
             + candidates_from_filesystem(search_roots, env))
    d_unique = {}
    for cand in l_all:
        key = os.path.normcase(os.path.normpath(cand.exe))
        if key not in d_unique:
            d_unique[key] = cand
    return sorted(d_unique.values(),
                  key=lambda c: c.version_tuple, reverse=True)


def load_saved_choice(f_saved=F_SAVED_CHOICE):
    """Return the saved doors.exe path if still valid, else None."""
    try:
        with open(f_saved, "r") as fp:
            d = json.load(fp)
        return validate_install(d.get("doors_exe"))
    except (OSError, ValueError):
        return None


def save_choice(s_exe, f_saved=F_SAVED_CHOICE):
    """Persist the chosen doors.exe path; failures are not fatal."""
    try:
        os.makedirs(os.path.dirname(f_saved), exist_ok=True)
        with open(f_saved, "w") as fp:
            json.dump({"doors_exe": s_exe}, fp)
    except OSError:
        pass


def ask_user_gui(l_candidates):
    """Ask the user to pick an installation with a small GUI list.

    Returns the chosen DoorsInstall; raises DoorsNotFoundError if the
    user cancels.
    """
    import FreeSimpleGUI as sg
    l_labels = [c.label() for c in l_candidates]
    layout = [
        [sg.Text("More than one DOORS installation was found.\n"
                 "Please select the one to use:")],
        [sg.Listbox(l_labels, default_values=[l_labels[0]],
                    size=(80, min(len(l_labels), 8)), key="-SEL-")],
        [sg.Button("OK"), sg.Button("Cancel")],
        [sg.Push(), sg.Text("Made by Elia R. with ❤",
                            font=("Helvetica", 8, "italic"),
                            text_color="gray")],
    ]
    window = sg.Window("Select DOORS installation", layout)
    try:
        while True:
            event, values = window.read()
            if event in (sg.WIN_CLOSED, "Cancel"):
                raise DoorsNotFoundError(
                    "DOORS installation selection cancelled by the user.")
            if event == "OK" and values["-SEL-"]:
                return l_candidates[l_labels.index(values["-SEL-"][0])]
    finally:
        window.close()


def resolve_doors_exe(interactive=True, ask_fn=None, env=None,
                      f_saved=F_SAVED_CHOICE, registry_values=None,
                      search_roots=None):
    """Return the full path of the doors.exe to use.

    Parameters
    ----------
    interactive: bool
        if True and more than one installation is found, ask the user
        (with ask_fn, default a GUI list); if False take the highest
        version.
    ask_fn: callable(list[DoorsInstall]) -> DoorsInstall
        selection function used in interactive mode, injectable for
        tests. Defaults to :func:`ask_user_gui`.

    Raises DoorsNotFoundError when nothing is found, or when the
    DOPYI_DOORS_EXE override points to a non-existing file.
    """
    if env is None:
        env = os.environ

    # 1. explicit override: must be valid, never silently ignored
    if env.get(S_ENV_EXE):
        exe = validate_install(env[S_ENV_EXE])
        if exe is None:
            raise DoorsNotFoundError(
                f"The {S_ENV_EXE} environment variable is set to "
                f"\"{env[S_ENV_EXE]}\" but no doors.exe was found there.")
        return exe

    # 2. previously saved (and still existing) choice
    exe = load_saved_choice(f_saved)
    if exe is not None:
        return exe

    # 3-5. discovery
    l_candidates = find_candidates(env, registry_values, search_roots)
    if not l_candidates:
        raise DoorsNotFoundError()
    if len(l_candidates) == 1:
        chosen = l_candidates[0]
    elif interactive:
        if ask_fn is None:
            ask_fn = ask_user_gui
        chosen = ask_fn(l_candidates)
    else:
        chosen = l_candidates[0]  # highest version
    save_choice(chosen.exe, f_saved)
    return chosen.exe
