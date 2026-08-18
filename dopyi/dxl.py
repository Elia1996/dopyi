# -*- coding: utf-8 -*-
"""Dxl commands as Python function.

    This module contain all needed dxl basic code
    used to send messages to the DOORS server and get data.

    The main class is **dxl**, a dxl object correspond to a
    server connection with a specific port and specific 
    returning string character.

Author: Elia Ribaldone, ribaldoneelia@gmail.com
Starting Date: 10/10/2022
"""

from enum import Enum
from dopyi.doorserver import server
from dopyi.doorserver.server import run_dxl
from datetime import datetime
from icecream import ic
import pandas as pd

# ic.configureOutput(prefix='dxl| ')
# ic.enable()

S_STD_STARTER = "@<"
# S_STD_DIV = ">\n@#<"
S_STD_DIV = "<#>"
N_PORT = 5095

S_BS_SUFFIX = "suffix"
S_BS_MAJOR = "major"
S_BS_MINOR = "minor"
S_BS_ANNOTATION = "annotation"
S_BS_DATE = "date"
S_BS_CREATOR = "user"
S_BS_ID = "id"
S_INFO_PREFIX = "prefix"
S_INFO_LAST_MODIFIED = "last_modified_on"
S_INFO_URL = "module_url"

# Error Handling Class #########################################


class DoorsokDxlError(Exception):
    # Exception class for the function in this module
    pass


class CommunicationOrDxlError(DoorsokDxlError):
    """Raised when something in the communication goes wrong
    """
    msg = "Error in soket communication or in dxl function."

    def __init__(self, s_msg="", message=msg):
        self.message = message + s_msg
        super().__init__(self.message)


class ModuleNotExist(DoorsokDxlError):
    """Raised when a module don't exist
    """
    msg = "The module you want to open don't exist: "

    def __init__(self, s_mod, message=msg):
        self.message = message + s_mod
        super().__init__(self.message)


class AbsnoNotFoundError(DoorsokDxlError):
    """Raised when the requested absolute number does not exist
    in the current module.
    """


#########################################################################
# Data handling function #######################################
""" In this section are collected all function used to transform row
data from server to list/str/bool/int etc.
"""


def coarse_to_list(s_ret, s_div=S_STD_DIV):
    """Transform a receiving data s_ret in a list

    If the s_ret is like:
        "Status After Customer Feedback" + s_div + "Areas" + s_div + "prova"
    For example if s_div is "****"
    "Status After Customer Feedback****Areas****prova"
    The function return:
    ["Status After Customer Feedback", "Areas", "prova"]

    Args:
        s_ret (str): a string with multiple word divided by s_div
        s_div (str, optional): the divisor of the strings.
            Defaults to S_STD_DIV.

    Returns:
        lit: the splitted string using s_div and removing empty elements
    """
    lista = s_ret.split(s_div)
    n = len(s_div)
    if s_ret[-n:] == s_div:
        lista = [ll for ll in lista[0:-1]]
    else:
        lista = [ll for ll in lista]
    return lista


def coarse_to_dic(s_ret, d_struct, s_div=S_STD_DIV):
    """Transform the receiving data in a dict using the d_struct structure

    Example:
        d_struct could be like:
            {"in":["linkmod", "mod", "abnso"],
            "out":["linkmod", "mod", "abnso"]}
        or like:
            {"name": 1, -> only one element
            "l_enum": "list",-> one or zero element(l_enum can be not present)
            "multi": "bool",
            "d_data":["linkmod", "mod", "abnso"]
        Using the previous two structure the returning value could be:
            {"in":[{"linkmod": "link/module/fullname",
            "mod": "source/module/fullname",
            "absno": n_absno_of_source},
            {"linkmod": "link/module/fullname2",
            "mod": "source/module/fullname2",
            "absno": n_absno_of_source2}],
        "out": [{"linkmod": "link/module/fullname",
            "mod": "target/module/fullname",
            "absno": n_absno_of_target}]}
    or
        {"name":"Domain feedback",
         "l_enum": ["Accepted", ...],
         "multi": False}

    Args:
        s_ret (_type_): _description_
        d_struct (_type_): _description_
        s_div (_type_, optional): _description_. Defaults to S_STD_DIV.

    Raises:
        CommunicationOrDxlError: If the d_struct don't fit with s_ret data

    Returns:
        dict: The s_ret data converted to dict.
    """
    # Transform data to list
    l_ret = coarse_to_list(s_ret, s_div)
    if not l_ret:
        return False

    l_ret.reverse()

    d_ret = {}

    i = 0

    V_K = "KEY:"
    N_VK = len(V_K)
    s_set_key = l_ret.pop()[N_VK:]

    if s_set_key not in d_struct.keys():
        return False

    while True:
        option = d_struct[s_set_key]

        if type(option) == list:
            if len(l_ret) < len(option):
                msg = "Dict transmitted in wrong way: " + s_ret
                raise CommunicationOrDxlError(msg)
            # Create the dict key
            if s_set_key not in d_ret:
                d_ret[s_set_key] = []
            d_ret[s_set_key].append({})

            # cycle on the data of a key
            for key in option:
                d_ret[s_set_key][-1][key] = l_ret.pop()

            if len(l_ret) < 1:
                break

        elif type(option) == int:
            # The option is the number of element to save as list

            # Create the dict key
            if s_set_key not in d_ret:
                d_ret[s_set_key] = []
            # Verify the remaing elements
            if len(l_ret) < option:
                msg = "Dict transmitted in wrong way: " + s_ret
                raise CommunicationOrDxlError(msg)
            # Save the elements
            if option == 1:
                d_ret[s_set_key] = l_ret.pop()
            else:
                for i in range(i, option):
                    d_ret[s_set_key].append(l_ret.pop())

        elif type(option) == str:
            # The option is the type of the data

            # Check data and save
            if option == "bool":
                d_ret[s_set_key] = coarse_to_bool(l_ret.pop())
            if option == "list":
                # Create the dict key
                if s_set_key not in d_ret:
                    d_ret[s_set_key] = []

                while len(l_ret) > 1:
                    if len(l_ret[-1]) > 4 and l_ret[-1][0:4] == "KEY:":
                        break
                    d_ret[s_set_key].append(l_ret.pop())
            if option == "date":
                # create a datetime object of the data
                # ic("CIAOOOO")
                if len(l_ret) >= 1:
                    s_date = l_ret.pop()
                    # ic(s_date)
                    date = datetime.strptime(s_date, "%d/%m/%y")
                    d_ret[s_set_key] = datetime(date.year, date.month,
                                                date.day, 23, 59, 59)
        else:
            msg = "Dict option are wrong" + s_ret
            raise CommunicationOrDxlError(msg)

        if len(l_ret) == 0:
            break
        s_set_key = l_ret.pop()[N_VK:]

        if s_set_key not in d_struct.keys():
            return False
    return d_ret


def coarse_to_bool(s_ret):
    """ Transform input to bool, if the element is equal to
    "True" it return true, if "False" return False, otherwise
    raise error
    """
    if not s_ret:
        return False
    if s_ret.strip() == "True":
        return True
    if s_ret.strip() == "False":
        return False
    raise CommunicationOrDxlError()


def coarse_to_int(s_ret):
    """ Transform input to int, if the element is equal to
    "True" it return true, if "False" return False, if it is
    an int return the int
    """
    if type(s_ret) == bool:
        return s_ret
    if s_ret.strip() == "True":
        return True
    if s_ret.strip() == "False":
        return False
    try:
        return int(s_ret)
    except ValueError:
        if not s_ret:
            return False
    raise CommunicationOrDxlError()


def coarse_handle_errors(s_ret, d_err):
    """ Handle the errors using d_err dictionary:
    if a certain error "#1" has to raise an exception "except"
    d_err will be like: {"#1": except()}
    The errors in s_ret has to be in the format "Error:#1:<err>"
    the <err> will be passed to the exception funtion.
    if you want that an error return False you has to get a d_err
    like: {"#1":False}
    """
    s_ret = s_ret.strip()
    if s_ret[0:6] == "Error:":
        s_err = s_ret[6:8]
        s_msg = s_ret[9:]
        if s_err in d_err.keys():
            if d_err[s_err] is False:
                return False
            if d_err[s_err] is True:
                return True
            else:
                raise d_err[s_err](s_msg)
        else:
            raise CommunicationOrDxlError()
    return True


def bs_to_string(major: int, minor: int, suffix: str = ""):
    """Return the string of a DOORS version

    Args:
        major (int): major version
        minor (int): minor version
        suffix (int): suffix version

    Returns:
        str: the string of the version
    """
    if suffix == "":
        return f"{major}.{minor}"
    return f"{suffix}_{major}.{minor}"

def bs_to_dict(s_baseline: str):
    """Return the dict of a DOORS version

    Args:
        s_baseline (str): string of the version

    Returns:
        dict: the dict of the version
    """
    l_bs = s_baseline.split("_")
    if len(l_bs) == 1:
        suffix = ""
    else:
        suffix = "_".join(l_bs[0:-1])
    l_bs = l_bs[-1].split(".")
    if len(l_bs) != 2:
        raise ValueError(f"Baseline string {s_baseline} is not valid.")
    major = int(l_bs[0])
    minor = int(l_bs[1])
    return {S_BS_SUFFIX: suffix, S_BS_MAJOR: major, S_BS_MINOR: minor}


def mod_bs_split(s_mod: str):
    """Return the module name and the baseline name which are divided by @

    Args:
        s_mod (str): the module name
    
    Returns:
        tuple: the module name and the baseline name
    """
    l_mod = s_mod.split("@")
    if len(l_mod) == 1:
        return l_mod[0], ""
    return l_mod[0], l_mod[1]



#########################################################################
# Class for connection #######################################


class typename(Enum):
    string = "String"
    text = "Text"
    integer = "Integer"
    date = "Date"
    username = "Username"
    real = "Real"
    enum = "Enumeration"

    @classmethod
    @property
    def l_val(cls):
        return [eval(f"typename.{i}.value") for i in cls.__members__]


class dxl():
    """Manage DOORS module in python with automatic connection.

    This class is the first real interface between dxl and python.
    The class enable to automatically connect through socket to a
    dxl server (generated by sysengpy.interfaces.doorserver.server)
    and sent customized dxl command.

    This is the list of property working on the current module:

        -   attr_names  TESTED
        -   mod_info
        -   mod_absnos  TESTED
        -   mod: set/get the current module  TESTED

    Methods for DOORS system info/modificaiton:

        -   type_exists  TESTED
        -   modules_in_folder(sf, folder, lev=None)  TESTED
        -   folders_in_folder(sf, folder)  TESTED
        -   module_exist(sf, mod)

    Methods to manage modules:

        -   open(sf, fullname, mode="r")  TESTED
        -   close(sf)  TESTED
        -   save(sf, fullname)
        -   new_mod(sf, fullname, description, prefix)  TESTED

    Methods to work inside a module:

        -   Module info (read mode):

            -   get_attr_def(sf, s_attr)
            -   mod_exists(mod)

        -   Module modification (write mode):

            -   def_enum_type(sf, name, values)
            -   def_type(sf, name, basetype)
            -   del_type(sf, name)
            -   def_attr(sf, attr, typename, basename=None,\
                         l_enum=None, multi=False, default="")
            -   def_view(sf, viewname, attrs)

        -   Object info (read mode):

            -   get_absno_by_attr(sf, s_attr, s_to_search)
            -   get_last_modified(sf, data)
            -   get_links(sf, absno)
            -   get_obj_attr_values(sf, absno, attrs)  TESTED
            -   get_attr_values(sf, attr)

        -   Object modification (write mode):

            -   new_obj(sf, where=None, below_after=None, absno=None)
                    TESTED
            -   del_obj(sf, absno)  TODO
            -   new_ext_link(sf, absno, name, url, s_descr="") TODO
            -   new_linkset(sf, linkmodname) TODO
            -   new_link(sf, absno, dest_fullname, dest_absno) TODO
            -   set_obj_attr_values(sf, absno, data, mode=ATTR_REPLACE):

    """
    typename = typename

    def __init__(self,
                 modname=None,
                 port=N_PORT,
                 div=S_STD_DIV,
                 starter=S_STD_STARTER):
        """Init the dxlserver class

        Args:
            port (int, optional): port number for socket connection with
                DOORS server. Defaults to N_PORT.
            div (str, optional): divider of returning lists.
                Defaults to S_STD_DIV.
            starter (str, optional): Starting string of the received
                data from DOORS. Defaults to S_STD_STARTER.
        """
        if type(port) is not int:
            raise TypeError(f"Port parameter must be an integer, value"
                            f" {port} is of type {type(port)}.")

        self.port = port
        self.div = div
        self.starter = starter
        self.__mod = None  # the current module
        if modname is not None:
            self.mod = modname

    def run_dxl(self, cmd):
        return run_dxl(cmd, self.port, self.starter)

    def __enter__(sf):
        sf.open(sf.mod, "w")

    def __exit__(sf, exc_type, exc_value, traceback):
        sf.close()

    #########################################################################
    # Global function       ########################################

    S_DXL_MODULES_IN_FOLDER = """
    s = scanModulesInFolder(\"S_FOLDER\", N_LEVEL, \"S_LIST_DIV\")
    return_ \"S_STARTER\" s
    """

    def modules_in_folder(sf, folder: str, lev=None):
        """Return the list of modules in a DOORS folder.

        This function return the list of all available module in
        a doors directory on the first level.

        Args:
            s_folder (str): DOORS folder fullpath
            n_lev (int, optional): Not implemented, leave it None.

        Returns:
            list: list of DOORS fullpath module name.
        """
        s = sf.S_DXL_MODULES_IN_FOLDER.replace("S_FOLDER", folder)
        s = s.replace("S_STARTER", sf.starter)
        s = s.replace("S_LIST_DIV", sf.div)
        if lev is not None and type(lev) is int:
            s = s.replace("N_LEVEL", str(lev))
        else:
            s = s.replace("N_LEVEL", "-1")

        s_ret = sf.run_dxl(s)

        return coarse_to_list(s_ret, sf.div)

    S_DXL_FOLDERS_IN_FOLDER = """
    s = scanFoldersInFolder(\"S_FOLDER\")
    return_ \"S_STARTER\" s
    """

    def folders_in_folder(sf, folder: str):
        """This function return the list of all folder/subfolder of a folder

        Args:
            s_folder (str): DOORS folder

        Returns:
            dict: dict of dict with the folder structure inside
        """
        s = sf.S_DXL_FOLDERS_IN_FOLDER.replace("S_FOLDER", folder)
        s = s.replace("S_STARTER", sf.starter)

        s_ret = sf.run_dxl(s)

        return eval(s_ret)

    #########################################################################
    # Checking functions          ###########################################

    S_DXL_MODULE_EXIST = """
    if ( ! exists module \"S_MOD\" )
        return_ \"S_STARTER\" "False"
    else
        return_ \"S_STARTER\" "True"
    """

    def mod_exists(sf, mod):
        """States if the module s_mod exists in DOORS

        No check on s_mod is done, be carefull.

        Args:
            mod (str): the full path name of the DOORS module

        Returns:
            bool: True if module exists.
        """
        mod, bsline = mod_bs_split(mod)
        # f_run_dxl is the function which run dxl on the server
        s = sf.S_DXL_MODULE_EXIST.replace("S_MOD", mod)
        s = s.replace("S_STARTER", sf.starter)
        s_ret = sf.run_dxl(s)
        b_exist = coarse_to_bool(s_ret)
        if not b_exist:
            return False
        if bsline == "":
            return True
        sf.open(mod)
        b_exist = sf.baseline_exists(bsline)
        return b_exist

    S_DXL_GET_MOD_FROM_URL = """
    s = get_modname_from_url(\"S_URL\")
    return_ \"S_STARTER\" s
    """

    def get_mod_from_url(sf, url: str):
        """Return the module name from the url

        Args:
            url (str): the url of the module

        Returns:
            str: the module name
        """
        s = sf.S_DXL_GET_MOD_FROM_URL.replace("S_URL", url)
        s = s.replace("S_STARTER", sf.starter)

        s_ret = sf.run_dxl(s)
        if s_ret == "Error:Invalid URL":
            return False
        return s_ret

    ###########################################################################
    # Module Setting functions          #######################################

    S_DXL_OPEN_MODULE = """
    s = openModule(\"S_MOD\", N_MODE)
    return_ \"S_STARTER\" s
    """

    D_DXL_OPEN_MODULE_ERR = {"#1": ModuleNotExist,
                             "#2": ModuleNotExist,
                             "#3": False,
                             "#4": False,
                             "#5": False}

    def open(sf, fullname: str, mode="r"):
        """Open a module in read or write mode.

        Remember that this function set the module as the current one
        but not in the "m" Module variable, always set the module with
        :func:`~dxl.dxl.mod` before use it (like sf.mod = "/path/modname")

        Args:
            fullname (str): The module fullname path, you can also specify
                the baseline name using @ like 
                "/path/modname@<suffix>_<major>.<minor>".
            mode (str, optional):
                -   "r" for read
                -   "w" for write, the module is taken in exclusive mode.
                Defaults to "r".

        Raises:
            CommunicationOrDxlError: If there has been some DXl/comunication
            err.

        Returns:
            bool: True if the module has been opened, False otherwise
        """
        n_mode = "0" if mode == "r" else "1"

        s = sf.S_DXL_OPEN_MODULE.replace("S_MOD", fullname)
        s = s.replace("N_MODE", n_mode)
        s = s.replace("S_STARTER", sf.starter)
        # Run dxl code in server
        s_ret = sf.run_dxl(s).strip()

        if not coarse_handle_errors(s_ret, sf.D_DXL_OPEN_MODULE_ERR):
            return False
        if s_ret[0:7] != "Opened":
            raise False
        # Return a int corresponding to the module number
        # False if the module can't be write/read
        return True

    @property
    def mod(sf):
        return sf.__mod

    @mod.setter
    def mod(sf, fullname: str):
        """Set the n_mod module as current module

        When you open multiple module it is useful don't close it
        but maintain all open and switch between them using this function.

        Args:
            fullname (str): The module fullname path

        Returns:
            bool: True if the module is succesfull setted
        """
        sf.__mod = fullname
        return sf.open(fullname, "r")

    """ Close a module n the skip list, it has not necessary the current
    module in m var.
    Arguments: S_STARTER, N_MOD
    """
    S_DXL_CLOSE_MODULE = """
    s = closeModule(\"S_MOD\")
    return_ \"S_STARTER\" s
    """
    D_DXL_CLOSE_MODULE = {"#1": ModuleNotExist}

    def close(sf, modname: str = None):
        """Close the module setted with :func:`~dxl.dxl.set` function.
        Args:
            ds (dxlserver): dxlserver object with data for DOORS connection.
        """
        if modname is None:
            modname = sf.mod
        s = sf.S_DXL_CLOSE_MODULE.replace("S_MOD", modname)
        s = s.replace("S_STARTER", sf.starter)

        # Run dxl code in server
        s_ret = sf.run_dxl(s).strip()

        if not coarse_handle_errors(s_ret, sf.D_DXL_CLOSE_MODULE):
            return False
        if s_ret[0:7] != "Deleted":
            raise CommunicationOrDxlError()
        return True

    """ Save a module n the skip list if it is in edit mode, it has not
    necessary the current module in m var.
    Arguments: S_STARTER, N_MOD
    """
    S_DXL_SAVE_MODULE = """
    s = saveModule(\"S_MOD\")
    return_ \"S_STARTER\" s
    """

    D_DXL_SAVE_MODULE = {"#1": ModuleNotExist,
                         "#2": False,
                         "#3": False}

    def save(sf, modname: str = None):
        """Save a module currently open in write mode

        Args:
            modname (str): modname of the module to save

        Raises:
            CommunicationOrDxlError: raised if some communication error exists

        Returns:
            bool: True if the module is closed
        """
        if modname is None:
            modname = sf.mod
        s = sf.S_DXL_SAVE_MODULE.replace("S_MOD", modname)
        s = s.replace("S_STARTER", sf.starter)

        # Run dxl code in server
        s_ret = sf.run_dxl(s).strip()

        if not coarse_handle_errors(s_ret, sf.D_DXL_CLOSE_MODULE):
            return False
        if s_ret[0:7] != "Saved":
            return False
        return True

    ##########################################################################
    # Functions get Meta informations          ###############################

    S_DXL_GET_ABSNO_BY_ATTR = """
    s = getAbsnoByAttr(m, \"S_ATTRIBUTE\", \"S_TO_SEARCH\")
    return_ \"S_STARTER\" s
    """

    def get_absno_by_attr(sf, s_attr: str, s_to_search: str):
        """Get the absolute number of the object which match.

        Before call this function you have to open a module with "open_module"
        or set an already opened module using *set* property.

        The function cycle on the whole module and when it is found
        an object with attribute s_attr matching s_to_search its
        absolute number is returned

        Args:
            s_attr (str): The attribue name in which search.
            s_to_search (str): The string to search in s_attr

        Raises:
            CommunicationOrDxlError: returned if the returning data from DOORS
                is wrong

        Returns:
            int: the absolute number of the matching object
        """
        s = sf.S_DXL_GET_ABSNO_BY_ATTR.replace("S_ATTRIBUTE", s_attr)
        s = s.replace("S_TO_SEARCH", s_to_search.replace("\"", "\\\""))
        s = s.replace("S_STARTER", sf.starter)

        # Run dxl code in server
        s_ret = sf.run_dxl(s).strip()

        if s_ret == "False":
            return False
        if not s_ret.isdigit():
            msg = "Returned data \"%s\" is not an integer." % s_ret
            raise CommunicationOrDxlError(msg)

        return int(s_ret)

    """ This function return the definition of an attribute in the module
    inside a dictionary like:
    name-> name of the type
    basetype -> the type of type
        {"name": "Domain feedback", "basetype": "Enumeration",
                "l_enum": ["Accepted", ..., "Change Responsible"],
                "multi": True}
    """
    S_DXL_GET_ATTR_DEF = """
    s = objGetAttrDef(m, \"S_ATTRIBUTE\", \"S_LIST_DIV\")
    return_ \"S_STARTER\" s
    """

    def get_attr_def(sf, s_attr: str):
        """Return the definition of a DOORS attribute

        Args:
            s_attr (str): The attribute name of which get information about the
                type.

        Returns:
            dict: the deifinition of s_attr in dict format.
                The dict contains "name" key which is the name of the type used
                , "basetype" which is the basic type used to create the type,
                if basetype is an Enumeration there is also "l_enum" key
                which contain the list of possible values and finally "multi"
                key which is true if the enumerate is multiple choice.

        Example:
            Returned dictionary look like::
            {"type": "Domain feedback", "basetype": "Enumeration",
            "l_enum": ["Accepted", ..., "Change Responsible"],
            "multi": True}
        """
        s = sf.S_DXL_GET_ATTR_DEF.replace("S_ATTRIBUTE", s_attr)
        s = s.replace("S_STARTER", sf.starter).replace("S_LIST_DIV", sf.div)

        # Run dxl code in server
        s_ret = sf.run_dxl(s).strip()

        if s_ret == "False":
            return False

        d_struct = {'type': 1, 'basetype': 1, 'l_enum': 'list',
                    'multi': 'bool', 'defval': 1}

        d_ret = coarse_to_dic(s_ret, d_struct, sf.div)

        if d_ret.get("l_enum"):
            d_ret["l_enum"] = d_ret["l_enum"] + [""]

        return d_ret

    S_DXL_GET_LINKSET = """
    s = getLinkSet(\"S_FOLDER\", \"S_LIST_DIV\")
    return_ \"S_STARTER\" s
    """

    @property
    def linksets(sf) -> dict:
        """Return the linkset of the current module

        Returns:
            list: list of all linkset for the module

        Example:
            {"inlink": [{"source": "linkmod", "linkmod": "linkmod", "target": "linkmod"}],
            "outlink": [{"source": "linkmod", "linkmod": "linkmod", "target": "linkmod"}]}
        """
        sf.mod = sf.mod
        modname_noversion = sf.mod.split("@")[0]
        s = sf.S_DXL_GET_LINKSET.replace(
            "S_FOLDER",
            "/".join(sf.mod.split("@")[0].split("/")[:-1])
        )
        s = s.replace("S_LIST_DIV", sf.div)
        s = s.replace("S_STARTER", sf.starter)

        # Run dxl code in server
        s_ret = sf.run_dxl(s).strip()

        lset = coarse_to_list(s_ret, sf.div)
        d_set_mod = {"inlink": [], "outlink": []}
        # lset is the concatenation of source, linkmod, target for each linkset
        for i in range(0, len(lset), 3):
            source = lset[i]
            linkmod = lset[i+1]
            target = lset[i+2]
            if source == modname_noversion:
                d_set_mod["outlink"].append({target: linkmod})
            if target == modname_noversion:
                d_set_mod["inlink"].append({source: linkmod})
        return d_set_mod

    """ This function return the list of attribute of a module
    Arguments: S_STARTER, S_LIST_DIV
    """
    S_DXL_GET_ATTRIBUTE_LIST = """
    s = modGetAttributeList( m, FROM, \"S_LIST_DIV\")
    return_ \"S_STARTER\" s
    """

    @property
    def attr_names(sf):
        """Return the list of attributes of the setted module.

        Returns:
            list: list of all attributes of the setted module.
        """
        def get_attr_names(sf, n_from: int = 0):
            s = sf.S_DXL_GET_ATTRIBUTE_LIST.replace("S_LIST_DIV", sf.div)
            s = s.replace("S_STARTER", sf.starter)
            s = s.replace("FROM", str(n_from))

            # Run dxl code in server
            s_ret = sf.run_dxl(s).strip()
            return coarse_to_list(s_ret, sf.div)

        l_ret = get_attr_names(sf, 0)
        while l_ret[-1] == "KEY:more":
            l_ret = l_ret[:-1]
            l_ret += get_attr_names(sf, len(l_ret))

        # Error management to implement

        return l_ret

    S_DXL_GET_MODIFIED_OBJ = """
    s = modGetModifiedObject( m, \"D_LAST_LOAD\", \"S_LIST_DIV\")
    return_ \"S_STARTER\" s
    """

    def get_last_modified(sf, data: datetime):
        """Return the list of absno of object modified after a date.

        This function cycle over the entire module and check for each
        objec if it last modification data is greater then the "data"
        passed. If the modification data is greater the absno is saved,
        at the end the complete list of object modified after "data" is
        returned.

        Args:
            data (datetime): datatime object with the data.

        Returns:
            list: list of absolute number of modified objects.
        """
        data = data.strftime("%d/%m/%y")
        s = sf.S_DXL_GET_MODIFIED_OBJ.replace("S_LIST_DIV", sf.div)
        s = s.replace("D_LAST_LOAD", data)
        s = s.replace("S_STARTER", sf.starter)

        # Run dxl code in server
        s_ret = sf.run_dxl(s).strip()

        # Error management to implement
        return coarse_to_list(s_ret, sf.div)

    S_DXL_GET_MODULE_INFO = """
    s = modGetInfo( m, \"S_LIST_DIV\")
    return_ \"S_STARTER\" s
    """
    D_GET_MODULE_INFO_STRUCT = {
        S_INFO_PREFIX: 1,
        S_INFO_LAST_MODIFIED: "date",
        S_INFO_URL: 1,
    }

    @property
    def mod_info(sf):
        """ This function return information about the module.

        Returns:
            dict: like {"prefix":"CUST_REQ_",
                        "last_modified_on":<datatime obj>}
        """
        sf.mod = sf.mod
        s = sf.S_DXL_GET_MODULE_INFO.replace("S_LIST_DIV", sf.div)
        s = s.replace("S_STARTER", sf.starter)

        # Run dxl code in server
        s_ret = sf.run_dxl(s).strip()

        # Error management to implement
        return coarse_to_dic(s_ret, sf.D_GET_MODULE_INFO_STRUCT, sf.div)

    ##########################################################################
    # Functions Read Data           ##########################################

    S_DXL_GET_ATTRIBUTES = """
    string l_attr[] = { L_ATTR }
    s = getAttributes(m, N_ABSNO, l_attr, \"S_LIST_DIV\")
    return_ \"S_STARTER\" s
    """

    def get_obj_attr_values(sf, absno, attrs: list):
        """Read the attributes data of a DOORS object for current module.

        Args:
            absno (int/str): the absolute number of an existing doors object
            attr (list): the list of attribute of which return the value

        Returns:
            list: list of attribute value in the same order of attr
        """

        if len(attrs) > 20:
            # Divide the attrs list in many list of max 20 elements
            # and call the function for each list
            l_ret = []
            for i in range(0, len(attrs), 20):
                # trunc the i+20 element if the list is shorter
                ll = min(i+20, len(attrs))
                l_ret += sf.get_obj_attr_values(absno, attrs[i:ll])
            return l_ret

        def jjoin(l_data):
            return "\"" + "\", \"".join(l_data) + "\""
        s = sf.S_DXL_GET_ATTRIBUTES.replace("L_ATTR", jjoin(attrs))
        s = s.replace("N_ABSNO", str(absno))
        s = s.replace("S_STARTER", sf.starter)
        s = s.replace("S_LIST_DIV", sf.div)

        # Run dxl code in server
        s_ret = sf.run_dxl(s).strip()

        # Error management to implement
        return coarse_to_list(s_ret, sf.div)

    S_DXL_GET_ATTR_VALUES_LIST = """
    s = modGetAttributeColValues( m, \"S_ATTRIBUTE\", \"S_LIST_DIV\")
    return_ \"S_STARTER\" s
    """

    def get_attr_values(sf, attr: str):
        """Get the column list of attr value in the setted DOORS module.

        The returned list has one element per DOORS object each is the
        value of the attribute *attr* in the DOROS module.

        Args:
            attr (str): attribute name of which get value.

        Returns:
            list: list with the value of the attribute *attr* for each
                object.
        """
        s = sf.S_DXL_GET_ATTR_VALUES_LIST.replace("S_ATTRIBUTE", attr)
        s = s.replace("S_LIST_DIV", sf.div)
        s = s.replace("S_STARTER", sf.starter)

        # Run dxl code in server
        s_ret = sf.run_dxl(s).strip()

        # Error management to implement
        return coarse_to_list(s_ret, sf.div)

    S_DXL_GET_OBJ_URL = """
    s = get_obj_url(m, N_ABSNO)
    return_ \"S_STARTER\" s
    """

    def get_obj_url(sf, absno):
        """Return the URL of the object *absno* in the setted Module.

        Args:
            absno (int/str): the absolute number of the desired object.

        Returns:
            str: the URL of the object.
        """
        sf.mod = sf.mod
        s = sf.S_DXL_GET_OBJ_URL.replace("N_ABSNO", str(absno))
        s = s.replace("S_STARTER", sf.starter)

        # Run dxl code in server
        s_ret = sf.run_dxl(s)

        # Error management to implement
        return s_ret

    S_DXL_GET_OBJ_LINKS = """
    s = objGetInOutLink( m, ABSNO, \"S_LIST_DIV\")
    return_ \"S_STARTER\" s
    """
    S_L_LINKMOD_KEY = "linkmod"
    S_L_MOD_KEY = "mod"
    S_L_ABSNO_KEY = "absno"
    D_STRUCT = {"in": [S_L_LINKMOD_KEY, S_L_MOD_KEY, S_L_ABSNO_KEY],
                "out": [S_L_LINKMOD_KEY, S_L_MOD_KEY, S_L_ABSNO_KEY],
                "ext": ["name", "descr", "url"]}

    def get_links(sf, absno):
        """Get the link information of the object *absno* in the setted Module.

        Args:
            absno (int/str): the absolute number of the desired object.

        Returns:
            dict: this dict contain all information to define a link,
                it is divided in *in* (input) and *out* (output) links,
                then there is a list of dict in which for each link is
                specified:
                    -   *linkmod* : it is the link module used for linking
                    -   *mod*: the source(for outlink)/target(for inlink)
                            module.
                    -   *absno*: the source(for outlink)/target(for inlink)
                            absolute number of the object.

        Example:
            This is a typicakl returning dict::

                {"in":[{"linkmod": "link/module/fullname",
                    "mod": "source/module/fullname",
                    "absno": n_absno_of_source},
                    {"linkmod": "link/module/fullname2",
                    "mod": "source/module/fullname2",
                    "absno": n_absno_of_source2}],
                "out": [{"linkmod": "link/module/fullname",
                    "mod": "target/module/fullname",
                    "absno": n_absno_of_target}],
                "ext": [{"name": "name_of_link",
                    "descr": "description_of_link",
                    "url": "url_of_link"}]}
        """
        s = sf.S_DXL_GET_OBJ_LINKS.replace("ABSNO", str(absno))
        s = s.replace("S_LIST_DIV", sf.div)
        s = s.replace("S_STARTER", sf.starter)

        # Run dxl code in server (raises DoorsDxlExecutionError if
        # the DXL execution halted)
        s_ret = sf.run_dxl(s)

        coarse_handle_errors(s_ret, {"#1": AbsnoNotFoundError})
        return coarse_to_dic(s_ret, sf.D_STRUCT, sf.div)

    S_DXL_GET_ABSNO = """
    s = getAbsnoList(m)
    return_ \"S_STARTER\" s
    """

    @property
    def mod_absnos(sf):
        """Return the list of all absolute number of selected DOORS module.s

        Returns:
            list: list of absno in int.
        """
        s = sf.S_DXL_GET_ABSNO.replace("S_STARTER", sf.starter)
        # Run dxl code in server
        s_ret = sf.run_dxl(s)
        # Error management to implement
        return eval(s_ret)

    S_DXL_TYPE_EXISTS = """
    s = typeExists(m, \"S_TYPE\")
    return_ \"S_STARTER\" s
    """

    def type_exists(sf, s_type):
        """Return True is the type s_type exists in DOORS.

        Args:
            s_type (str): name of the type

        Returns:
            bool: True if the type s_type exists in DOORS.
        """
        s = sf.S_DXL_TYPE_EXISTS.replace("S_STARTER", sf.starter)
        if type(s_type) == sf.typename:
            s_type = s_type.value
        s = s.replace("S_TYPE", s_type)
        # Run dxl code in server
        s_ret = sf.run_dxl(s)
        # Error management to be implemented
        return eval(s_ret)

    ##########################################################################
    # Functions to create/delete Modules/object/attributes/type  #############

    S_DEL_LINKS = """
    int l_target_absno[] = {L_TARGET_ABSNO}
    s = deleteLinks(m, S_ABSNO, \"S_M_TRGT\", l_target_absno, \"S_LINK\")
    return_ \"S_STARTER\" s
    """

    def delete_links(sf, target_mod: str, source_absno: int,
                     l_target_absno: list, link_mod: str):
        """Delete the link *link* between the object *source_absno* and
        *target_absno* in the module *target_mod*.

        Args:
            target_mod (str): the target module fullname.
            source_absno (int): the source object absolute number.
            l_target_absno (int): the target object absolute number.
            link_mod (str): the link module fullname.

        Returns:
            bool: True if the link is deleted correctly.
        """
        l_target_absno = [str(n) for n in l_target_absno]
        s = sf.S_DEL_LINKS.replace("S_STARTER", sf.starter)
        s = s.replace("S_ABSNO", str(source_absno))
        s = s.replace("S_M_TRGT", target_mod)
        s = s.replace("L_TARGET_ABSNO", ", ".join(l_target_absno))
        s = s.replace("S_LINK", link_mod)
        # Run dxl code in server
        s_ret = sf.run_dxl(s)
        # Error management to be implemented
        return coarse_to_bool(s_ret)

    S_DELETE_ALL_OBJ_LINKS = """
    s = deleteAllObjLinks(m, S_ABSNO)
    return_ \"S_STARTER\" s
    """

    def delete_all_obj_links(sf, absno: int):
        """Delete all the links between the object *absno* in the module
        *m*.

        Args:
            absno (int): the object absolute number.
        """
        s = sf.S_DELETE_ALL_OBJ_LINKS.replace("S_STARTER", sf.starter)
        s = s.replace("S_ABSNO", str(absno))
        # Run dxl code in server
        s_ret = sf.run_dxl(s)
        # Error management to be implemented
        return coarse_to_bool(s_ret)

    S_CREATE_LINKS = """
    int l_target_absno[] = {L_TARGET_ABSNO}
    s = createLinks(m, S_ABSNO, \"S_M_TRGT\", l_target_absno, \"S_LINK\")
    return_ \"S_STARTER\" s
    """

    def create_links(sf, target_mod: str, source_absno: int,
                     l_target_absno: list, link_mod: str):
        """Create the link *link* between the object *source_absno* and
        *target_absno* in the module *target_mod*.

        Args:
            target_mod (str): the target module fullname.
            source_absno (int): the source object absolute number.
            l_target_absno (int): the target object absolute number.
            link_mod (str): the link module fullname.

        Returns:
            bool: True if the link is created correctly.
        """
        s = sf.S_CREATE_LINKS.replace("S_STARTER", sf.starter)
        l_target_absno = [str(n) for n in l_target_absno]
        s = s.replace("S_ABSNO", str(source_absno))
        s = s.replace("S_M_TRGT", target_mod)
        s = s.replace("L_TARGET_ABSNO", ", ".join(l_target_absno))
        s = s.replace("S_LINK", link_mod)
        # Run dxl code in server
        s_ret = sf.run_dxl(s)
        # Error management to be implemented
        return coarse_to_bool(s_ret)


    S_DXL_GET_BASELINES = """
    s = getBaselines(m, \"S_LIST_DIV\")
    return_ \"S_STARTER\" s
    """

    def get_baselines(sf) -> list:
        """Get the list of baselines of the module *s_mod*.

        Args:
            s_mod (str): the module fullname.

        Returns:
            list: list of baseline name.
        """
        s = sf.S_DXL_GET_BASELINES.replace("S_STARTER", sf.starter)
        s = s.replace("S_LIST_DIV", sf.div)
        # Run dxl code in server
        s_ret = sf.run_dxl(s)
        # Error management to be implemented
        if s_ret == "False" or s_ret == "":
            return []
        l_data = coarse_to_list(s_ret, sf.div)
        if len(l_data) % 6 != 0:
            raise CommunicationOrDxlError("Wrong data returned, the "
                                          "getBaselines function shall return "
                                          " a list of 3 element for each "
                                          "baseline. Returned data: "
                                          f"{l_data} = {s_ret}")
        l_ret = []
        for i in range(0, len(l_data), 6):
            key = bs_to_string(major=int(l_data[i]),
                               minor=int(l_data[i+1]),
                               suffix=l_data[i+2])
            
            l_ret.append({S_BS_ID: key,
                          S_BS_ANNOTATION: l_data[i+3],
                          S_BS_DATE: datetime.strptime(l_data[i+4],
                                                       '%d %B %Y'),
                          S_BS_CREATOR: l_data[i+5]})

        return l_ret

    def baseline_exists(sf, bs_id: str):
        """Return True if the baseline bs_id (<suffix>_<major>.<minor>) exists.
    
        Args:
            bs_id (str): the baseline id.

        Returns:
            bool: True if the baseline exists.
        """
        l_bs = sf.get_baselines()
        return bs_id in [bs[S_BS_ID] for bs in l_bs]


    S_MAKE_BASELINE = """
    s = makeBaseline(m, B_MAJOR, \"S_SUFFIX\", \"S_DESCR\", \"S_LIST_DIV\")
    return_ \"S_STARTER\" s
    """


    D_BASELINE_STRUCT = {"name": 1, "major": 1, "descr": 1}

    def make_baseline(sf, s_suffix: str, s_descr: str, b_major: bool):
        """Make a baseline of the setted DOORS module.

        Args:
            s_suffix (str): suffix of the baseline name.
            s_descr (str): description of the baseline.
            b_major (bool): True if the baseline is major.

        Returns:
            dict: the baseline information.
        """
        sf.open(sf.mod, "w")
        s = sf.S_MAKE_BASELINE.replace("S_STARTER", sf.starter)
        s = s.replace("S_SUFFIX", s_suffix)
        s = s.replace("S_DESCR", s_descr)
        s = s.replace("B_MAJOR", "true" if b_major else "false")
        s = s.replace("S_LIST_DIV", sf.div)

        # Run dxl code in server
        s_ret = sf.run_dxl(s)
        # Error management to be implemented
        return coarse_to_dic(s_ret, sf.D_BASELINE_STRUCT, sf.div)

    def get_last_baseline(sf):
        """Get the last baseline of the setted DOORS module.
        return a dict with the baseline information like

        {'id': 'ExampleModule_1.6',
            'annotation': 'Minor Baseline before latote import',
            'date': datetime.datetime(2024, 2, 24, 0, 0),
            'user': 'user01'}
    
        """
        l_bs = sf.get_baselines()
        if len(l_bs) == 0:
            return None
        return l_bs[-1]

     
    S_DXL_NEW_MODULE = """
    m = create(\"S_MOD\", \"S_DESCR\", \"S_PREFIX\", 1, false)
    save m
    """

    def new_mod(sf, fullname: str, description: str, prefix: str):
        """Create a new rational DOORS module.

        The module folder must exists.

        Args:
            fullname (str): name with fullpath of the new module
            s_description (str): description to add at the module metadata.
            s_prefix (str): prefix for module ID attribute
                ,it can be an empty str.

        Returns:
            bool: True if the new module is created correctly
        """
        s = sf.S_DXL_NEW_MODULE.replace("S_MOD", fullname)
        s = s.replace("S_STARTER", sf.starter)
        s = s.replace("S_DESCR", description)
        s = s.replace("S_PREFIX", prefix)

        # Run dxl code in server
        s_ret = sf.run_dxl(s)
        return coarse_to_bool(s_ret)

    S_DXL_DEL_MODULE = """
    softDelete module(\"S_MOD\")
    """
    S_DXL_PURGE_MODULE = """
    hardDelete module(\"S_MOD\")
    """

    def del_mod(sf, purge: bool = False):
        """Delete a DOORS module.

        Args:
            purge (bool, optional): if True the module will be purged.
        """
        if not sf.mod_exists(sf.mod):
            return True
        try:
            sf.close()
        except:
            pass
        s = sf.S_DXL_DEL_MODULE.replace("S_MOD", sf.mod)
        if purge:
            s = s + sf.S_DXL_PURGE_MODULE.replace("S_MOD", sf.mod)
        # Run dxl code in server
        s_ret = sf.run_dxl(s)
        return coarse_to_bool(s_ret)

    S_DXL_DEF_ENUM_TYPE = """
    string names[] = { L_ENUM_NAMES }
    int values[] = { L_VALUES }
    int colors[] = { L_COLORS }
    s = defEnumType(m, \"S_TYPE_NAME\", names, values, colors)
    return_ \"S_STARTER\" s
    """

    l_colors = [16, 46, 31, 21, 11, 13, 14, 15, 17, 18, 19, 20,
                22, 23, 24, 25, 26, 27, 28, 29, 30, 32, 39]

    def __color(sf, n):
        return sf.l_colors[n % len(sf.l_colors)]

    def def_enum_type(sf, name: str, values: list):
        """Create a new enum type which can be used to create Attributes.

        Args:
            name (str): name of the new enumerative
            values (list): list of enum possible values

        Returns:
            bool: True if the enum is succesfull created.
        """
        s = sf.S_DXL_DEF_ENUM_TYPE.replace("S_TYPE_NAME", name)
        s = s.replace("S_STARTER", sf.starter)

        # Values list creation
        s_enum_names = ""
        s_values = ""
        s_colors = ""
        for i, name in enumerate(values):
            s_end = ", " if name != values[-1] else ""
            s_enum_names += "\"" + name + "\"" + s_end
            s_values += str(i) + s_end
            s_colors += str(sf.__color(i)) + s_end

        s = s.replace("L_ENUM_NAMES", s_enum_names)
        s = s.replace("L_VALUES", s_values)
        s = s.replace("L_COLORS", s_colors)

        # Run dxl code in server
        s_ret = sf.run_dxl(s)
        return coarse_to_bool(s_ret)

    S_DXL_DEF_TYPE = """
    s = defType(m, \"S_TYPE_NAME\", \"S_BASETYPE\")
    return_ \"S_STARTER\" s
    """

    def def_type(sf, name: str, basetype: str):
        """Create a type in current DOORS module

        Args:
            name (str): type name to be created
            basetype (str): one of L_POSSIBLE_TYPENAMES

        Returns:
            bool: True if the deletion succeed
        """
        if type(basetype) == sf.typename:
            basetype = basetype.value
        if basetype not in sf.L_POSSIBLE_TYPENAMES:
            raise Exception(f"Wrong basename {basetype}.")

        s = sf.S_DXL_DEF_TYPE.replace("S_TYPE_NAME", name)
        s = s.replace("S_STARTER", sf.starter)
        s = s.replace("S_BASETYPE", basetype)

        # Run dxl code in server
        s_ret = sf.run_dxl(s)
        return coarse_to_bool(s_ret)

    S_DXL_DEL_TYPE = """
    s = delType(m, \"S_TYPE_NAME\")
    return_ \"S_STARTER\" s
    """

    def del_type(sf, name: str):
        """Delete a type in current DOORS module

        Args:
            name (str): type name to be deleted.

        Returns:
            bool: True if the deletion succeed
        """
        s = sf.S_DXL_DEL_TYPE.replace("S_TYPE_NAME", name)
        s = s.replace("S_STARTER", sf.starter)

        # Run dxl code in server
        s_ret = sf.run_dxl(s)
        return coarse_to_bool(s_ret)

    S_DXL_DEF_ATTR = """
    s = defAttr(m, \"ATTR_NAME\", \"S_TYPE_NAME\", \"S_DEFAULT\", \"S_MULTI\")
    return_ \"S_STARTER\" s
    """

    L_POSSIBLE_TYPENAMES = ["String",
                            "Text",
                            "Integer",
                            "Date",
                            "Username",
                            "Real"]
    # convert the previous list to a enumeration

    def def_attr(sf, attr: str,
                 typename: str,
                 basetype=None,
                 l_enum=None,
                 multi=False,
                 default=""):
        """Create a new attribute in the current DOORS module.

        You can create typename previously using *def_enum_type* function
        or you can use the standard typename (String, Text,
        Integer, Date, Username or Real).

        Precondition:
            Open the module in write mode.

        Args:
            attr (str): the new attribute name.
            typename (str): the name of the type to use for the attribute,
                you can use a default type like: *String*,
                *Text*, *Integer*, *Date*, *Username*, *Real*. If you use a
                type not already defined it will be defined, anyway
                in this case the *basetype* argument is mandatory.
            basetype (str): It must be between: *String*,
                *Text*, *Integer*, *Date*, *Username* or *Real*. It can
                also be *Enumeration* but in this case the *l_enum* argument
                became mandatory.
            l_enum (list): list of string of the possibility of
                the enumeration.
            multi (bool, optional): to use only with enumeration types,
                if True the enumeration has multiselection property.
                Defaults to False.
            default (str, optional): to use only with enumeration types,
                the default value of the enumeration. Defaults to "".

        Returns:
            bool: True if the new attribute is succesfull created.
        """
        # If the type don't exists I've to create it.
        if type(typename) == sf.typename:
            typename = typename.value
        if type(basetype) == sf.typename:
            basetype = basetype.value
        if typename not in sf.L_POSSIBLE_TYPENAMES:
            if not sf.type_exists(typename):
                # Create new type
                if basetype is None:
                    return [False, "New type needs basetype definition."]
                if basetype == "Enumeration":
                    if l_enum is None:
                        return [False, "l_enum is needed."]
                    sf.def_enum_type(typename, l_enum)
                else:
                    sf.def_type(typename, basetype)
        # Create the new attribute
        s = sf.S_DXL_DEF_ATTR.replace("S_TYPE_NAME", typename)
        s = s.replace("S_STARTER", sf.starter)
        s = s.replace("ATTR_NAME", attr)
        s = s.replace("S_MULTI", str(multi))
        s = s.replace("S_DEFAULT", default)

        # Run dxl code in server
        s_ret = sf.run_dxl(s)
        return [coarse_to_bool(s_ret), ""]

    def del_attr(sf, attr: str):
        """ Deleta an attribute
        """
        pass

    S_DXL_DEF_VIEW = """
    string l_attr[] = {L_ATTR}
    s = defView(m, \"S_VIEWNAME\", l_attr, BOOL_SET_DEFAULT)
    return_ \"S_STARTER\" s
    """

    def def_view(sf, viewname: str, attrs: list, set_default=False):
        """Create a new view disposing the attributes in order.

        The order of the attribute is the same of attrs list.

        Precondition:
            Open the module in write mode.

        Args:
            sf (_type_): _description_
            viewname (str): _description_
            attr (list): _description_

        Returns:
            bool: True if the view creation succeed.
        """
        s_attr = ", ".join(["\"" + attr + "\"" for attr in attrs])
        s = sf.S_DXL_DEF_VIEW.replace("S_VIEWNAME", viewname)
        s = s.replace("S_STARTER", sf.starter)
        s = s.replace("L_ATTR", s_attr)
        s = s.replace("BOOL_SET_DEFAULT", "true" if set_default else "false")

        # Run dxl code in server
        s_ret = sf.run_dxl(s)
        return coarse_to_bool(s_ret)

    S_DXL_NEW_OBJECT = """
    Object new_o = create S_FIRST_LAST m
    return_ \"S_STARTER\" new_o."Absolute Number" ""
    """
    S_DXL_NEW_CHILD_OBJECT = """
    Object o = object(ABSNO, m)
    Object new_o = create S_FIRST_LAST S_BELOW_AFTER o
    return_ \"S_STARTER\" new_o."Absolute Number" ""
    """

    LAST = "last"
    FIRST = "first"
    BELOW = "below"
    AFTER = "after"

    def new_obj(sf, where=None, below_after=None, absno=None):
        """ Create a new object below the s_absno_father object if != False

        Note:
            A current module must be opened (with :func:`~dxl.dxl.open`)
            or setted (with :func:`~dxl.dxl.set`) if it already opened.
            Write mode needed.

        Args:
            where (first/last/None): first of last of already created
                object at the same level with the same father.
                Use sf.LAST and sf.FIRST.
            below_after (below/after/None): If the object must be below
                the object indicated or after. can be used only
                if you specify an absno. Use sf.BELOW and sf.AFTER.
            absno (int/None): if None the object is created at the level 0
                like: "Object o = create first/last m".
        Return:
            int: absolute number of the new object.

        Example:
            Possible combination::

                s_where s_below_after   s_absno
                first        None            None   -> S_DXL_NEW_OBJECT
                last         None            None   -> S_DXL_NEW_OBJECT
                first        below           int    -> S_DXL_NEW_CHILD_OBJECT
                last         below           int    -> S_DXL_NEW_CHILD_OBJECT
                None         after           int    -> S_DXL_NEW_CHILD_OBJECT
                None         after           int    -> S_DXL_NEW_CHILD_OBJECT
                None         None            None   -> S_DXL_NEW_OBJECT

        """
        if absno is None:
            # Verify that at least one object exist (otherwise first or last
            # give error)
            if where is None or sf.mod_absnos == []:
                s = sf.S_DXL_NEW_OBJECT.replace("S_FIRST_LAST", "")
            else:
                s = sf.S_DXL_NEW_OBJECT.replace("S_FIRST_LAST", where)
        else:
            if not isinstance(absno, int):
                try:
                    absno = int(absno)
                except:
                    raise Exception("Invalid absno value: _%s_" % absno)
            if absno < 0:
                Exception("Invalid absno value: _%s_ < 0 " % absno)
            s = sf.S_DXL_NEW_CHILD_OBJECT.replace("ABSNO", str(absno))
            s = s.replace("S_BELOW_AFTER", below_after)
            if where is None or below_after == "after":
                s = s.replace("S_FIRST_LAST", "")
            else:
                s = s.replace("S_FIRST_LAST", where)
        s = s.replace("S_STARTER", sf.starter)
        s_ret = sf.run_dxl(s)
        return coarse_to_int(s_ret)

    S_DXL_NEW_EXTLINK = """
    s = objCreateExtLink(m, ABSNO, \"S_NAME\", \"S_DESCR\", \"S_URL\")
    return_ \"S_STARTER\" "True"
    """

    S_DXL_DEL_EXTLINK = """
    s = objDeleteExtLink(m, ABSNO, \"S_NAME\")
    return_ \"S_STARTER\" "True"
    """

    S_DXL_SOFT_DELETE_OBJECT = """
    Object o = object(ABSNO, m)
    if (canDelete(o) != null)
        return_ \"S_STARTER\" "False"
    softDelete(o)
    return_ \"S_STARTER\" "True"
    """

    def del_obj(sf, absno: int):
        """Delete the object with the given absno

        If you need to delete object with a specific attribute value
        you can use the function :func:`~dxl.dxl.get_absno_by_attr`

        Note:
            A current module must be opened (with :func:`~dxl.dxl.open`)
            or setted (with :func:`~dxl.dxl.set`) if it already opened.
            Write mode needed.

        Args:
            absno (int): absolute number to delete

        Returns:
            bool: True if the deletion is successfull otherwise you probably
                aren't in write mode, set it with :func:`~dxl.dxl.open`
                function
        """
        s = sf.S_DXL_SOFT_DELETE_OBJECT.replace("ABSNO", str(absno))
        s_ret = sf.run_dxl(s)
        return coarse_to_bool(s_ret)

    def new_ext_link(sf, absno: int, name: str, url: str, s_descr=""):
        """Create a new external link to an http url

        Note:
            A current module must be opened (with :func:`~dxl.dxl.open`)
            or setted (with :func:`~dxl.dxl.set`) if it already opened.
            Write mode needed.

        Args:
            absno (int): absolute number of object in which create extlink
            name (str): name of the link displayed
            url (str): http url of the external file/website/svn etc.
            s_descr (str, optional): Description of the link. Defaults to "".

        Returns:
            bool: True if the link has been succesfull created.
        """
        s = sf.S_DXL_NEW_EXTLINK.replace("ABSNO", str(absno))
        s = s.replace("S_NAME", name)
        if s_descr == "":
            s_descr = name
        s = s.replace("S_DESCR", s_descr)
        s = s.replace("S_URL", url)
        s_ret = sf.run_dxl(s)
        return coarse_to_bool(s_ret)


    def del_ext_link(sf, absno: int, name: str):
        """Delete the external link with the given name

        Note:
            A current module must be opened (with :func:`~dxl.dxl.open`)
            or setted (with :func:`~dxl.dxl.set`) if it already opened.
            Write mode needed.

        Args:
            absno (int): absolute number of object in which create extlink
            name (str): name of the link displayed

        Returns:
            bool: True if the link has been succesfull deleted.
        """
        s = sf.S_DXL_DEL_EXTLINK.replace("ABSNO", str(absno))
        s = s.replace("S_NAME", name)
        s_ret = sf.run_dxl(s)
        return coarse_to_bool(s_ret)


    def new_linkset(sf, linkmodname):
        """Create a new link module if not exists and set it as linkset.

        The linkmodname is setted as the linkset in the current module

        Warning:
            Not implemented

        Note:
            A current module must be opened (with :func:`~dxl.dxl.open`)
            or setted (with :func:`~dxl.dxl.set`) if it already opened.
            Write mode needed.

        Args:
            linkmodname (str): fullpath of the link module to be used.

        Returns:
            bool: True if the new linkset is created successfull.
        """
        pass

    ##########################################################################
    # Functions write data in doors                         #########

    S_DXL_SET_ATTRIBUTES = """
    string l_attr[] = { L_ATTR }
    string l_val[] = { L_VAL }
    string l_mode[] = { L_MODE }
    s = setAttributes(m, N_ABSNO, l_attr, l_val, l_mode)
    return_ \"S_STARTER\" s
    """

    # These are the value the user must use to fill thel l_mode list
    ATTR_APPEND = "apnd"
    ATTR_PREPEND = "pre"
    ATTR_REPLACE = "repl"
    ATTR_ADD = "add"

    def set_obj_attr_values(sf, absno: int, data: dict, mode=ATTR_REPLACE):
        """Create a set of attribute value according to *data*

        Note:
            A current module must be opened (with :func:`~dxl.dxl.open`)
            or setted (with :func:`~dxl.dxl.set`) if it already opened.
            Write mode needed.

        Warning:
            No check on attribute is done, data keys must be correct
            attribute name in the current module.

        Args:
            absno (int): absolute number of the object to modify
            data (dict): dictionary with attribute as key and the value
                to set as value like {"Object ID": "STR_11", ...}
            mode (str, optional): it define how to modify the current value,
                the possible value of mode are:

                -   sf.ATTR_APPPEND:
                        append the data to the current value valid only
                        for text and string
                -   sf.ATTR_PREPEND:
                        prepend data, valid for text and string
                -   sf.ATTR_REPLACE:
                        replace the current value with the
                        given one.
                -   sf.ATTR_ADD:
                        add the value to the one alredy present
                        in DOORS, valid only for integer and real.

                Defaults to None.

        Raises:
            AttributeError: If the mode value is wrong.

        Returns:
            bool: True if the attributes are correctly setted
        """
        # Checks to verify the integrity of l_attr, l_val and l_mode
        if mode is not sf.ATTR_APPEND and mode is not sf.ATTR_PREPEND\
                and mode is not sf.ATTR_REPLACE and\
                mode is not sf.ATTR_ADD:
            raise AttributeError("mode value is wrong.")

        s = sf.S_DXL_SET_ATTRIBUTES.replace("N_ABSNO", str(absno))
        if type(data) != dict:
            try:
                data = data.to_dict()
            except Exception as e:
                raise Exception("data must be a dictionary")
        l_attr = list(data.keys())
        for attr in l_attr:
            if pd.isna(data[attr]):
                data.pop(attr, None)

        def jjoin(l_data):
            return "\"" + "\", \"".join([str(d) for d in l_data]) + "\""
        s = s.replace("L_ATTR", jjoin(data.keys()))
        s = s.replace("L_VAL", jjoin(data.values()))
        s = s.replace("L_MODE", jjoin([mode]*len(list(data.keys()))))
        s = s.replace("S_STARTER", sf.starter)

        s_ret = sf.run_dxl(s)
        return coarse_to_bool(s_ret)


##########################################################################
# Tests                a########################################

if __name__ == "__main__":
    pass
