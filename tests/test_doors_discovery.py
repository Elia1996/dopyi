"""Unit tests for dopyi.doors_discovery.

These run on any machine: environment, registry and filesystem are
injected, no DOORS installation is needed.
"""

import json

import pytest

from dopyi.doors_discovery import (
    DoorsInstall,
    DoorsNotFoundError,
    candidates_from_doorshome,
    candidates_from_filesystem,
    candidates_from_registry,
    find_candidates,
    load_saved_choice,
    parse_version,
    resolve_doors_exe,
    save_choice,
    validate_install,
)


def make_install(tmp_path, version, vendor="IBM"):
    """Create a fake DOORS install tree and return the exe path."""
    if vendor == "IBM":
        p_bin = tmp_path / "IBM" / "Rational" / "DOORS" / version / "bin"
    else:
        p_bin = tmp_path / "Telelogic" / f"DOORS_{version}" / "bin"
    p_bin.mkdir(parents=True)
    exe = p_bin / "doors.exe"
    exe.write_bytes(b"fake exe")
    return exe


##########################################################################
# parse_version / validate_install


def test_parse_version_from_modern_path():
    s = r"C:\Program Files\IBM\Rational\DOORS\9.7\bin\doors.exe"
    assert parse_version(s) == "9.7"


def test_parse_version_from_legacy_path():
    assert parse_version(r"C:\Program Files\Telelogic\DOORS_9.1\bin") == "9.1"


def test_parse_version_missing():
    assert parse_version(r"C:\somewhere\doors\bin") == ""


def test_validate_install_accepts_exe_root_and_bin(tmp_path):
    exe = make_install(tmp_path, "9.7")
    root = exe.parent.parent
    assert validate_install(str(exe)) == str(exe)
    assert validate_install(str(root)) == str(exe)
    assert validate_install(str(exe.parent)) == str(exe)


def test_validate_install_rejects_missing_and_empty(tmp_path):
    assert validate_install(str(tmp_path / "nothing")) is None
    assert validate_install("") is None
    assert validate_install(None) is None


##########################################################################
# single-source candidate functions


def test_candidates_from_doorshome(tmp_path):
    exe = make_install(tmp_path, "9.6")
    root = exe.parent.parent
    l_cand = candidates_from_doorshome({"DOORSHOME": str(root)})
    assert [c.exe for c in l_cand] == [str(exe)]
    assert l_cand[0].version == "9.6"
    assert l_cand[0].source == "doorshome"


def test_candidates_from_doorshome_unset():
    assert candidates_from_doorshome({}) == []


def test_candidates_from_registry_injected(tmp_path):
    exe = make_install(tmp_path, "9.7")
    values = [str(exe.parent.parent),        # install root
              str(tmp_path / "not-there"),   # invalid
              str(exe)]                      # duplicate, kept as candidate
    l_cand = candidates_from_registry(values)
    assert all(c.exe == str(exe) for c in l_cand)
    assert len(l_cand) == 2  # dedup happens in find_candidates


def test_candidates_from_filesystem(tmp_path):
    exe97 = make_install(tmp_path, "9.7")
    exe91 = make_install(tmp_path, "9.1", vendor="Telelogic")
    roots = [str(tmp_path / "IBM" / "Rational" / "DOORS"), str(tmp_path)]
    l_cand = candidates_from_filesystem(search_roots=roots)
    assert {c.exe for c in l_cand} == {str(exe97), str(exe91)}


##########################################################################
# find_candidates: merge, dedupe, sort


def test_find_candidates_dedupes_and_sorts(tmp_path):
    exe910 = make_install(tmp_path, "9.10")
    exe97 = make_install(tmp_path, "9.7")
    l_cand = find_candidates(
        env={"DOORSHOME": str(exe97.parent.parent)},
        registry_values=[str(exe910.parent.parent), str(exe97)],
        search_roots=[str(tmp_path / "IBM" / "Rational" / "DOORS")],
    )
    # 9.10 sorts above 9.7 (numeric, not lexicographic)
    assert [c.exe for c in l_cand] == [str(exe910), str(exe97)]
    # the duplicate of 9.7 (doorshome + registry + filesystem) is one entry
    assert len(l_cand) == 2


##########################################################################
# saved choice persistence


def test_save_and_load_choice(tmp_path):
    exe = make_install(tmp_path, "9.7")
    f_saved = tmp_path / "choice.json"
    save_choice(str(exe), str(f_saved))
    assert json.loads(f_saved.read_text())["doors_exe"] == str(exe)
    assert load_saved_choice(str(f_saved)) == str(exe)


def test_load_choice_stale_or_missing(tmp_path):
    f_saved = tmp_path / "choice.json"
    assert load_saved_choice(str(f_saved)) is None
    f_saved.write_text(json.dumps({"doors_exe": str(tmp_path / "gone")}))
    assert load_saved_choice(str(f_saved)) is None
    f_saved.write_text("not a json")
    assert load_saved_choice(str(f_saved)) is None


##########################################################################
# resolve_doors_exe


def _resolve(tmp_path, **kw):
    kw.setdefault("env", {})
    kw.setdefault("registry_values", [])
    kw.setdefault("search_roots", [str(tmp_path / "IBM" / "Rational"
                                       / "DOORS")])
    kw.setdefault("f_saved", str(tmp_path / "choice.json"))
    return resolve_doors_exe(**kw)


def test_resolve_env_override_wins(tmp_path):
    exe = make_install(tmp_path, "9.7")
    other = make_install(tmp_path, "9.6")
    assert _resolve(tmp_path, env={"DOPYI_DOORS_EXE": str(exe)}) == str(exe)
    assert other.exists()  # not chosen even if discoverable


def test_resolve_env_override_invalid_raises(tmp_path):
    with pytest.raises(DoorsNotFoundError):
        _resolve(tmp_path,
                 env={"DOPYI_DOORS_EXE": str(tmp_path / "missing.exe")})


def test_resolve_uses_saved_choice(tmp_path):
    exe = make_install(tmp_path, "9.6")
    f_saved = tmp_path / "choice.json"
    save_choice(str(exe), str(f_saved))
    assert _resolve(tmp_path, f_saved=str(f_saved)) == str(exe)


def test_resolve_single_candidate_and_persists(tmp_path):
    exe = make_install(tmp_path, "9.7")
    f_saved = tmp_path / "choice.json"
    assert _resolve(tmp_path, f_saved=str(f_saved)) == str(exe)
    assert load_saved_choice(str(f_saved)) == str(exe)


def test_resolve_multiple_non_interactive_picks_highest(tmp_path):
    exe910 = make_install(tmp_path, "9.10")
    make_install(tmp_path, "9.7")
    assert _resolve(tmp_path, interactive=False) == str(exe910)


def test_resolve_multiple_interactive_uses_ask_fn(tmp_path):
    make_install(tmp_path, "9.10")
    exe97 = make_install(tmp_path, "9.7")

    def pick_97(l_candidates):
        assert len(l_candidates) == 2
        return [c for c in l_candidates if c.version == "9.7"][0]

    assert _resolve(tmp_path, interactive=True, ask_fn=pick_97) == str(exe97)


def test_resolve_nothing_found_raises(tmp_path):
    with pytest.raises(DoorsNotFoundError):
        _resolve(tmp_path)


def test_version_tuple_unknown_sorts_lowest(tmp_path):
    known = DoorsInstall("a", "9.7", "x")
    unknown = DoorsInstall("b", "", "x")
    assert sorted([known, unknown], key=lambda c: c.version_tuple,
                  reverse=True)[0] is known
