"""Simulate a Formal Rational DOORS module in python.

This module contain the **doorsmod** class, each object
of this class is associated with a Formal DOORS module.

After the object creation the DOORS module is downloaded
locally in a pandas Dataframe (some local data saving
will be also implemented). Then you can modify the dataframe
and at the end upload the changes, the class will make
the difference between the modified database and the
first one and will upload only the differencies.

Author: Elia Ribaldone, ribaldoneelia@gmail.com
Starting Date: 10/10/2022
"""
from hashlib import new
from itertools import chain
from pathlib import Path
from typing import Any, List
import pandas as pd
import numpy as np
import polars as pl
import os
from multiprocessing import Process, Pipe
import logging
import json
from dopyi.reqint import ReqModule, Req,  ExtLink
# import of the dxl class

from dopyi.dxl import dxl
from dopyi.dxl import (
    N_PORT, S_STD_DIV, S_STD_STARTER,
    S_INFO_LAST_MODIFIED, S_INFO_URL, S_INFO_PREFIX,
    S_BS_ANNOTATION, S_BS_DATE, S_BS_CREATOR,
    S_BS_ID
)

S_L_LINKMOD_KEY = dxl.S_L_LINKMOD_KEY
S_L_MOD_KEY = dxl.S_L_MOD_KEY
S_L_ABSNO_KEY = dxl.S_L_ABSNO_KEY


##########################################################################
# default path in which store metadata and data

# Set the output file of the logger
logging.basicConfig(filename='doorsmod.log', level=logging.DEBUG)

P_DATA_SAVE = os.path.join(os.path.expanduser('~'),
                           "DoorsLocalDatabase", "DOORS_Data")
if not os.path.exists(P_DATA_SAVE):
    os.makedirs(P_DATA_SAVE)

##########################################################################
# doorsmod constants

# Read only object attributes
L_DEFAULT_ATTR_RO = ["Object Level",
                     "Created By",
                     "Created On",
                     "Created Thru",
                     "Last Modified By",
                     "Last Modified On",
                     "Object Short Text",
                     'OLE',
                     'OLEIconic',
                     'Picture',
                     'PictureName',
                     'PictureNum',
                     'TableBottomBorder',
                     'TableCellAlign',
                     'TableCellWidth',
                     'TableChangeBars',
                     'TableLeftBorder',
                     'TableLinkIndicators',
                     'TableRightBorder',
                     'TableShowAttrs',
                     'TableShowBookform',
                     'TableShowWide',
                     'TableTopBorder',
                     'TableType']
# Attributes generated internally
S_INLINK = "__inlinks"
S_OUTLINK = "__outlinks"
S_EXTLINK = "__extlinks"
S_CMD = "__cmd"
S_ID = "__id"
L_MAN_GENERATED = [S_INLINK, S_OUTLINK, S_EXTLINK, S_CMD, S_ID]

# Read Write object attributes
S_ABSNO = "Absolute Number"
L_DEFAULT_ATTR_RW = [S_ABSNO,
                     "Object Text",
                     "Object Heading"]

# cmd
CMD_BELOW = "below"
CMD_AFTER = "after"


##########################################################################
# doorsmod class errors


class DoorsmodError(Exception):
    # Exception class for the function in this module
    pass


class ModuleNotExistsError(DoorsmodError):
    """When you try to create a new doorsmod obj with a not existing module
    """

    def __init__(self, modname: str):
        self.message = f"The module \"{modname}\" not exists in DOORS."
        super().__init__(self.message)


class ImplementationError(DoorsmodError):
    """When there is an internal implementation error
    """

    def __init__(self):
        self.message = f"There is an implementation error"
        super().__init__(self.message)

###########################################################################
# doorsmod class functions


def intersection_changes(df1, df2, i_intersection, col_intersection):
    """Return a DataFrame with the changes between df1 and df2 for the common
    intersection of df1 and df2.

    _extended_summary_

    Args:
        df1 (pd.Dataframe): Old data frame
        df2 (pd.Dataframe): New data frame
        i_intersection (list): Index intersection list
        col_intersection (list): Column intersection list

    Returns:
        pd.DataFrame: The dataframe with the changes between df1 and df2 for
            the common intersection of df1 and df2.
    """
    # Create a copy of df1 with only the common columns and the common indexes
    df1_samelabel = df1.loc[i_intersection, col_intersection]
    df2_samelabel = df2.loc[i_intersection, col_intersection]

    comparison = df1_samelabel.compare(df2_samelabel, align_axis=0)
    if not comparison.empty:
        comparison = comparison.swaplevel().loc["other"]
    return comparison


def new_columns(df1, df2, i_intersection):
    """Get the columns in df2 that are not in df1.

    Args:
        df1 (pd.Dataframe): Old data frame
        df2 (pd.Dataframe): New data frame
        i_intersection (list): list of indexes to be used for the comparison

    Returns:
        list, pd.Dataframe: The list of the columns in df1 and the
            data frame with the columns in df2 that are not in df1.
    """
    # Find the common columns
    new_columns = df2.columns.difference(df1.columns)
    # Create a copy of df1 with only the common columns and the common indexes
    df2_new_columns = df2.loc[i_intersection, new_columns]
    return list(df2_new_columns.columns), df2_new_columns


def new_rows(df1, df2):
    """Get the rows in df2 that are not in df1.

    Args:
        df1 (pd.Dataframe): Old dataframe
        df2 (pd.Dataframe): New Dataframe

    Returns:
        list, pd.Dataframe: The list of the rows in df1 and the
            data frame with the rows in df2 that are not in df1.
    """
    # Find the common indexes
    new_index = df2.index.difference(df1.index)
    # Create a copy of df1 with only the common columns and the common indexes
    df2_new_index = df2.loc[new_index]
    return list(df2_new_index.index), df2_new_index


def deleted_rows(df1, df2):
    """Get the rows in df1 that are not in df2.

    Args:
        df1 (pd.Dataframe): Old dartaframe
        df2 (pd.Dataframe): New dataframe

    Returns:
        list, pd.Dataframe: List of the rows in df1 and the deleted rows in
            df1.
    """
    # Find the common indexes
    del_index = df1.index.difference(df2.index)
    # Create a copy of df1 with only the common columns and the common indexes
    df1_del_index = df1.loc[del_index]
    return list(df1_del_index.index), df1_del_index


def deleted_columns(df1, df2):
    """Get the columns in df1 that are not in df2.

    Args:
        df1 (pd.Dataframe): Old Dataframe
        df2 (pd.Dataframe): New Dataframe

    Returns:
        list, pd.Dataframe : List of the columns in df1 and the deleted columns
            in df1.
    """
    # Find the common columns
    del_columns = df1.columns.difference(df2.columns)
    # Create a copy of df1 with only the common columns and the common indexes
    df1_del_columns = df1.loc[:, del_columns]
    return list(df1_del_columns.columns), df1_del_columns


def intersections(df1, df2):
    """Get the common indexes and columns between df1 and df2.

    Args:
        df1 (pd.Dataframe): Old Dataframe
        df2 (pd.Dataframe): New Dataframe

    Returns:
        pd.Dataframe, pd.Dataframe: _description_
    """
    samelabel_index = df1.index.intersection(df2.index)
    # Find the common columns
    samelabel_columns = df1.columns.intersection(df2.columns)
    return samelabel_index, samelabel_columns


def df_update(df1, df2):
    """Get the changes between df1 and df2.

    The changes between df1 and df2 are returned as a DataFrame with all the
    modifications to do (the del rows and cols are not considered), it is
    also returned the list of the new indexes and columns and the list of
    deleted rows and columns.

    Args:
        df1 (pd.Dataframe): Old Dataframe
        df2 (pd.Dataframe): New Dataframe

    Returns:
        pd.Dataframe: The changes between df1 and df2.
        list: The list of the new indexes.
        list: The list of the new columns.
        list: The list of the deleted rows.
        list: The list of the deleted columns.
    """
    # Check that df1 and df2 doesn't have duplicated indexes
    if df1.index.duplicated().any():
        raise Exception("df1 has duplicated indexes")
    if df2.index.duplicated().any():
        raise Exception("df2 has duplicated indexes")

    # Find the new row and adjust the absolute number accordingly
    """new_index = df2.index.difference(df1.index)
    imax = max([int(x) for x in df1.index]) + 1
    for i, newi in enumerate(new_index):
        df1.rename({str(newi): str(imax+i)}, inplace=True)"""

    i_intersection, col_intersection = intersections(df1, df2)
    df_intersect = intersection_changes(df1, df2, i_intersection,
                                        col_intersection)
    l_new_cols_name, df_new_columns = new_columns(df1, df2, i_intersection)
    l_new_rows_index, df_new_rows = new_rows(df1, df2)
    l_del_rows_index, df_del_rows = deleted_rows(df1, df2)
    l_del_cols_name, df_del_columns = deleted_columns(df1, df2)

    def take_second(df1, df2):
        """Get the second element of a list."""
        return df2.combine_first(df1)
    dfnew = pd.DataFrame()
    if df_intersect.empty:
        # Create a dataframe like df2 with all values to NaN
        df_intersect = df2.apply(lambda x: [np.nan] * len(x), axis=1,
                                 result_type='broadcast')
    dfnew = df_intersect.combine(df_new_columns, take_second)
    dfnew = dfnew.combine(df_new_rows, take_second)
    return dfnew, l_new_cols_name, l_new_rows_index,\
        l_del_rows_index, l_del_cols_name


def previous_indexes(df2, l_index):
    """Get a list of the indexes of the previous rows in df1.

    Each index in l_index corresponds to a row in df1, this row has a
    previous row, this function returns a list of the indexes of the previous
    rows.

    Args:
        df1 (pd.Dataframe): Old Dataframe
        l_index (list): List of indexes of the rows in df1
    Returns:
        list: List of indexes of the previous rows.
    """
    # Check if the l_index is in the df1.index otherwise return an empty list
    if not all([True if i in df2.index else False for i in l_index]):
        return False
    s_index = "index" if df2.index.name is None else df2.index.name
    l_prev_index = []
    for i in l_index:
        prev_i = df2.index.get_loc(i) - 1
        if prev_i >= 0 and i in df2.index:
            l_prev_index.append(int(df2.reset_index().loc[prev_i][s_index]))
        else:
            l_prev_index.append(None)
    return l_prev_index


def compare(df1, df2, f_excel=None):
    """Compare the module data and the working copy.

    This function compare the module data and the working copy and
    if f_excel is not None print the result in excel file.

    Args:
        df1 (pd.Dataframe): Old Dataframe
        df2 (pd.Dataframe): New Dataframe
        f_excel (str, optional): The name of the excel file where to print the
            result. Defaults to None.
    """
    dfnew, l_new_cols_name, l_new_rows_index,\
        l_del_rows_index, l_del_cols_name = df_update(df1, df2)
    if isinstance(f_excel, str):
        try:
            writer = pd.ExcelWriter(f_excel, engine='xlsxwriter')
            dfnew.to_excel(writer, sheet_name='Compare')
            # Create a dataframe with one column for each l_ attribute
            pdiff = pd.DataFrame(columns=["New Cols Name", "New Rows Index",
                                          "Del Rows index", "Del Cols Name"])
            lmax = max(len(l_new_cols_name), len(l_new_rows_index),
                       len(l_del_rows_index), len(l_del_cols_name))
            pdiff["New Cols Name"] = l_new_cols_name + [""] * \
                (lmax - len(l_new_cols_name))
            pdiff["New Rows Index"] = l_new_rows_index + [""] * \
                (lmax - len(l_new_rows_index))
            pdiff["Del Rows index"] = l_del_rows_index + [""] * \
                (lmax - len(l_del_rows_index))
            pdiff["Del Cols Name"] = l_del_cols_name + [""] * \
                (lmax - len(l_del_cols_name))
            pdiff.to_excel(writer, sheet_name='Compare lists', index=False)
            writer.close()
        except PermissionError:
            raise Exception("The file is open, close it and retry")
    l_new_row_previous_i = previous_indexes(df2, l_new_rows_index)

    return dfnew, l_new_cols_name, l_new_rows_index,\
        l_del_rows_index, l_del_cols_name, l_new_row_previous_i


def iter_not_empty(df, management_attr=False):
    df = df.applymap(lambda x: np.nan if x == "" else x)
    df.dropna(axis=0, how="all", inplace=True)
    df.dropna(axis=1, how="all", inplace=True)
    if not management_attr:
        df.drop(L_MAN_GENERATED + L_DEFAULT_ATTR_RO,
                axis=1, inplace=True, errors="ignore")
    if df.empty:
        return iter([])
    else:
        for index, row in df.iterrows():
            if row.notnull().any():
                row_ne = row.dropna()
                yield index, row_ne


def encode_absno(n: int):
    return hex(n*10+1238512)[2:].upper()


def decode_absno(n: str):
    return int((int(n, 16) - 1238512)/10)


DF_ATTRDEF_EXAMPLE = pd.DataFrame(
    {
        "type": ["Text", "String", "Integer", "Real", "Date", "Username",
                 "<enumeration name>"],
        "basetype": ["Text", "String", "Integer", "Real", "Date", "Username",
                     "Enumeration"],
        "l_enum": [""]*6 + ["[<enum value1>, ..., <enum valueN>]"],
        "multi": [""]*6 + ["<TRUE/FALSE>"],
        "default": ["<default value or empty>"]*7
    },
    columns=["type", "basetype", "l_enum", "multi", "default"],
    index=[f"<Attribute{i} Name>" for i in range(7)]
)

##########################################################################
# doorsmod class


class doorsmod(dxl):
    """Simulate a Formal DOORS module using pandas Dataframe

    Brief inside in the implementation:
    The DOORS module is represented in two pandas dataframe, one is the working
    copy (wcd) which is the one returned from the read() function and which
    you can modify, the other is the original copy which you have no access and
    it always represent the DOORS data (used for comparison).

    This is the list of available functions:
        -   read() Read the DOORS module and create two local pandas
            object, an internal object and a working copy which you can
            modify (dsm.wcd).
        -   write() Write the working copy to the DOORS module after comparison.
        -   compare() This function compare wcd with the DOORS data and create
            a variable with the difference (self.__compdata), ideally you
            should call this function before write(), check the comparison
            excel created and then call write(). If you want to bypass this
            check you can call write() and the comparison will be done
            automatically.
        -   create_links_by_attr() Create links from this module to others
            using the id specified in an attribute as target. Here you can
            specify which are the possible target modules and the link modules
            to use.
        -   check_mod() Check if the module is a valid DOORS module, if not
            can crete it if create_if_not_exist is True.
        -   check_create_attr() Help you to create an attributes in wcd
            if not exist.
        -   new_view() Create a new view in the module

    Capabilities:
        -   Read a DOORS module and convert it to a dataframe.
        -   Creation of new doors module.
        -   Add new rows and columns to a module.
        -   Modify the content of a module.
        -   Delete existing rows (but not columns).
        -   Create links to other modules using ID as target.
        -   Create new views in the module.
        -   Creation of Baseline and get last baseline number

    Example:
        This is an example which explain the basic use::

            # Import the doorsmod class
            from dopyi.doorsmod import doorsmod
            # Create the doorsmod object of the DOORS module
            dsm = doorsmod("/xxx_SYS_TestsProject/SoW_Example")
            # Read the DOORS module and create two local pandas object, an
            # internal
            # object and a working copy which you can modify (dsm.wcd)
            dsm.read()

            # Now we have access to the data with the pandas object dsm.wcd
            # we can modify the working copy as we want, e.g.
            absno = "10"
            dsm.wcd[absno, "Object Text"] = "Text loaded from doorsmod"
            # we can also add object
            dsm.wcd.loc["11", "Object Text"] = "Text added from doorsmod"

            # Create comparison in excel
            dsm.compare("compare.xlsx")
            # After that if the comparison is ok we can write the changes
            dsm.write()

        It is also possible to read in/out/eternal links of the objects,
        they are saved in the dsm.wcd dataframe::

            absno = 12     # Suppose you want the link of absolute number 12

            dsm.wcd.loc[absno, S_INLINKS]  # this is an inlink dictionary
            as below:
            [{'absno': '209', # Absno of the object from which the link came
              'linkmod': '/xxx_SYS_TestsProject/connect', # Link module name
              'mod': '/xxx_SYS_TestsProject/SoW_Example2'}, # Source module name
             {'absno': '211',
              'linkmod': '/xxx_SYS_TestsProject/connect',
              'mod': '/xxx_SYS_TestsProject/SoW_Example2'}]

            dsm.wcd.loc[absno, S_OUTLINK] # this is an outlink dictionary
            as below:
            [{'absno': '175',     # Target object Absolute number
              'linkmod': '/xxx_SYS_TestsProject/connect',     # Link module
              'mod': '/xxx_SYS_TestsProject/SoW_Example2'}# Target module
             }]

            dsm.wcd.loc[absno, S_EXTLINK]

        The links can be modified using the function create_links_by_attr() or
        dxl functions (you can use it since doorsmod is inherited from dxl):
            - delete_links()
            - delete_all_obj_links()
            - create_links()


        This is an example which cycle in every inlink of a module ad print
        an attribute from the source objects, we also copy an attribute::

            from dopyi.doorsmod import doorsmod
            dsm = doorsmod("/xxx_SYS_TestsProject/SoW_Example")
            dsm.read()
            d_dsm = []
            s_status = "Status"
            s_coverage = "SYS3 coverage"

            for absno, row in dsm.wcd.iterrows():
                # If the object is a requirement
                if row["Object Type"] == "requirement":
                    n_link = 0
                    for d_inlink in row[S_INLINK]:
                        inabsno = d_inlink["absno"]
                        inmod = d_inlink["mod"]
                        print(f"Object {absno} has an inlink from object"
                              f"{inabsno}, module {inmod}")
                        if inmod not in d_dsm.keys():
                            d_dsm[inmod] = doorsmod(inmod)
                            d_dsm[inmod].read()
                        if d_dsm[inmod].wcd.loc[inabsno, s_status] ==\
                                "Released":
                            n_link += 1

                    if n_link > 0:
                        dsm.wcd.loc[absno, s_coverage] = f"Covered by:"\
                            f"{n_link} released sys3 req."
                    else:
                        dsm.wcd.loc[absno, s_coverage] = "Not Covered"

            dsm.write()


    Warning:
        At the moment the only limit in the write function is that no checks
        are done on the wc_attrdef dataframe. It is used only to create new
        attributes in the module, but if you want to modify the attributes
        you have to do it manually in DOORS.

    """
    CLOSED = "closed"
    READ = "r"
    WRITE = "w"

    l_attr_def_columns = ["type", "basetype", "l_enum", "multi", "default"]

    def __init__(sf,
                 name: str,
                 port=N_PORT,
                 div=S_STD_DIV,
                 starter=S_STD_STARTER,
                 remote=True):
        """Init the doorsmod class

        Args:
            name (str): fullpath and name of a DOORS module
            port (int, optional): port number for socket connection with
                DOORS server. Defaults to N_PORT.
            div (str, optional): divider of returning lists.
                Defaults to S_STD_DIV.
            starter (str, optional): Starting string of the received
                data from DOORS. Defaults to S_STD_STARTER.
        Raises:
            ModuleNotExistsError: If the module don't exists
        """
        # Init the dxl super class
        super().__init__(port=port, div=div, starter=starter)

        # Check if the name is a url
        url = sf.get_mod_from_url(name)
        if url:
            sf._url = name
            name = url
        else:
            sf._url = None

        sf.__name = name
        sf.__status = sf.CLOSED

        # This is the pandas Dataframe used internally, it is the
        # copy of DOORS module.
        sf.__data = None  # no access by the user.
        # This instead is the pandas Dataframe that the user can
        # modify, the modification on the DOORS object will be
        # done at the end with the write function.
        # it is called wcd, means Working Copy data
        sf.wcd = None

        # Same management of data is done for attribute definition
        sf.__attrdef = None
        # this is the working copy
        sf.wc_attrdef = None

        # And finally the same is done for module attributes
        sf.__modinfo = None

        # Comparison Datas
        sf.__compdata = None

        #########################################################
        # Creation of the pikle files in which store module data
        # I recreate the same folder structure of DOORS
        onlyname = os.path.basename(name)
        dir = os.path.join(P_DATA_SAVE, os.path.dirname(name)[1:], onlyname)
        if not os.path.exists(dir):
            os.makedirs(dir)
        sf._p_attrdef = os.path.join(dir, "attrdef.pkl")
        sf._p_modinfo = Path(os.path.join(dir, "modinfo.json"))
        sf._p_data = os.path.join(dir, "data.pkl")
        # dxl attributes
        if remote:
            sf.mod = sf.name

    @property
    def columns(self):
        # return the list of columns without L_DEFAULT_ATTR_RO, L_MAN_GENERATED
        # and L_DEFAULT_ATTR_RW
        return [x for x in self.wcd.columns if x not in L_DEFAULT_ATTR_RO and
                x not in L_MAN_GENERATED]

    def get_mod_info(self):
        """Get the module information in a dict format like this:

        >>> from dopyi.doorsmod import S_INFO_PREFIX, S_INFO_LAST_MODIFIED, S_INFO_URL
        >>> dsm = doorsmod("/xxx_SYS_TestsProject/SoW_Example")
        >>> dsm.get_mod_info()
        {S_INFO_PREFIX: "<module id to use after in the link>",
         S_INFO_LAST_MODIFIED: "<last modified date>",
         S_INFO_URL: "<url of the module including baseline if it is a baseline>"
         }

        Returns:
            dict: The module information
        """
        self.mod = self.__name
        info = super().mod_info
        info["name"] = self.name
        return info

    def _mod_info(self, update: bool = False) -> dict:
        """Get the module information in a dict format like this:

        >>> from dopyi.doorsmod import S_INFO_PREFIX, S_INFO_LAST_MODIFIED, S_INFO_URL
        >>> dsm = doorsmod("/xxx_SYS_TestsProject/SoW_Example")
        >>> dsm.mod_info
        {S_INFO_PREFIX: "<module id to use after in the link>",
         S_INFO_LAST_MODIFIED: "<last modified date>",
         S_INFO_URL: "<url of the module including baseline if it is a baseline>"
         }

        Returns:
            dict: The module information
        """
        if self._p_modinfo.exists() and not update:
            info = json.load(self._p_modinfo.open())
            # convert string to datetime
            from datetime import datetime
            info[S_INFO_LAST_MODIFIED] = datetime.strptime(
                info[S_INFO_LAST_MODIFIED], "%Y-%m-%d %H:%M:%S")
        else:
            info = self.get_mod_info()
            info_write = info.copy()
            # Write the info in the json file
            # convert datetime to string
            info_write[S_INFO_LAST_MODIFIED] = \
                info_write[S_INFO_LAST_MODIFIED].strftime(
                "%Y-%m-%d %H:%M:%S")
            with self._p_modinfo.open("w") as f:
                json.dump(info_write, f)
        return info

    @property
    def mod_info(self) -> dict:
        """Get the module information in a dict format like this:

        >>> from dopyi.doorsmod import S_INFO_PREFIX, S_INFO_LAST_MODIFIED, S_INFO_URL
        >>> dsm = doorsmod("/xxx_SYS_TestsProject/SoW_Example")
        >>> dsm.mod_info
        {S_INFO_PREFIX: "<module id to use after in the link>",
         S_INFO_LAST_MODIFIED: "<last modified date>",
         S_INFO_URL: "<url of the module including baseline if it is a baseline>"
         }

        Returns:
            dict: The module information
        """
        return self._mod_info()

    def should_be_updated(self) -> bool:
        """Check if the module should be updated.

        Returns:
            bool: True if the module should be updated, False otherwise.
        """
        if "@" in self.name:
            return False
        info = self.mod_info
        real_info = self.get_mod_info()
        if info[S_INFO_LAST_MODIFIED] != real_info[S_INFO_LAST_MODIFIED]:
            return True
        return False

    @property
    def last_baseline_obj(self) -> "doorsmod":
        """Get the last baseline doorsmod object.
        """
        bs = self.get_last_baseline()
        if bs is None:
            return None
        name = self.name
        if "@" in self.name:
            name = self.name.split("@")[0]
        mod = name + "@" + bs[S_BS_ID]
        return doorsmod(mod)

    def read(sf, force=False, conn=None):
        """Load data of the module in dataframe

        This function call sf.doorsread if the module whas not already
        downloaded in the pikle.

        Example:
            You can run this function getting the download status
            in this way::

                dsm = doorsmod("/Example_Project/10_System/05_"
                               "Stakeholder/SoW_Example")
                pconn, cconn = Pipe()
                p = Process(target=dsm.read, args=(cconn,))
                p.start()
                while True:
                    dic = pconn.recv()
                    if dic is None:
                        break
                    print(dic)

        Args:
            force (bool, optional): If True the module will be downloaded.
                Defaults to False.
            conn (Connection): a pipe connection through which
                will be sent the information about the current
                status of the download and elaboration.
                Keys: msg, perc
                   - msg: string with the current status
                   - perc: percentage of download

        After you run this function you can modify the module
        through the Dataframes:

            -   sf.wcd: It is the module data as dataframe so e.g.
                sf.wcd.columns get the module attribute list. There are some
                specific attribute which starts with "__", these contains some
                informations about the links and ID. The string used as
                attribute is saved in a python constant for each attribute.
            -   sf.columns: list of the module attributes (no __ attributes)
            -   sf.wc_attrdef: definition of the existing attribute
                    in the module, here are specified also the enumerations.
        """
        # if the pickles files exist i load it instead of
        # read from DOORS
        # check the name of the module

        if sf.should_be_updated():
            force = True

        ret = True
        if os.path.exists(sf._p_data) and\
                os.path.exists(sf._p_attrdef) and not force:
            sf.__attrdef = pd.read_pickle(sf._p_attrdef)
            sf.wc_attrdef = sf.__attrdef.copy()
            sf.__data = pd.read_pickle(sf._p_data)
            sf.wcd = sf.__data.copy()
            if conn:
                conn.send("{\"msg\": \"Module loaded from pickle\", "
                          "\"perc\": 100}")
                conn.send(None)
        else:
            if not sf.mod_exists(sf.__name):
                raise ModuleNotExistsError(sf.__name)
            ret = sf.__doorsread(conn)
        # Setting the index of the dataframe to absolute number
        sf.__data.set_index("Absolute Number", inplace=True)
        sf.wcd.set_index("Absolute Number", inplace=True)
        return ret

    def prompt_read(self, force: bool = False):
        pconn, cconn = Pipe()
        p = Process(target=self.read, args=(force, cconn,))
        p.start()
        print(f"Reading module {self.name}:")
        while True:
            dic = pconn.recv()
            if dic is None:
                break
            if isinstance(dic, str):
                dic = eval(dic)
            if isinstance(dic, dict):
                print(f"    {dic['msg']:<50} {dic['perc']}%{' '*100}", end="\r")
        p.terminate()
        # the following line is important, the read() function is runned above in a
        # process, so the data are not shared between the process and the main
        # but are stored i nthe pickle file, so we have to reload the data
        # using the read without force
        self.read()

    def __str__(self) -> str:
        s_descr = f"Doorsmod object of module {self.name}:\n"
        modinfo = self.mod_info
        s_descr += f"    - last modified: {modinfo[S_INFO_LAST_MODIFIED]}\n"
        s_descr += f"    - url: {modinfo[S_INFO_URL]}\n"
        s_descr += f"    - prefix: {modinfo[S_INFO_PREFIX]}\n"
        bs = self.get_last_baseline()
        if bs:
            s_descr += f"    - last baseline: {bs[S_BS_ID]}\n"
            s_descr += f"    - baseline date: {bs[S_BS_DATE]}\n"
            s_descr += f"    - baseline creator: {bs[S_BS_CREATOR]}\n"
        if self.wcd is not None:
            s_descr += f"    - wcd: {self.wcd.shape[0]} rows, {self.wcd.shape[1]} columns\n"
            s_descr += f"    - wcd data: {self.wcd.head()}\n"
        return s_descr

    def __doorsread(sf, conn=None):
        """Read data from module and save it in dataframe.

        Example:
            You can run this function getting the download status
            in this way::

                dsm = doorsmod("/Example_Project/10_System/05_"
                               "Stakeholder/SoW_Example")
                pconn, cconn = Pipe()
                p = Process(target=dsm.read, args=(cconn,))
                p.start()
                while True:
                    dic = pconn.recv()
                    if dic is None:
                        break
                    print(dic)

        Args:
            conn (Connection): a pipe connection through which
                will be sent the information about the current
                status of the download and elaboration.

        After you run this function you can modify the module
        through the Dataframes:

            -   sf.wcd: It is the module data as dataframe so e.g.
                sf.wcd.columns get the module attribute list.
            -   sf.wc_attrdef:
                definition of the existing attribute in the module
            -   sf.wc_moddata:
                the module data like prefix and so on.
        """
        ###########################################################
        # Reading data from module
        def pgr(conn, msg, i, imax):
            if conn:
                conn.send("{\"msg\": \"" + msg + "\", \"perc\": " +
                          str(int((i/imax)*1000)/10) + "}")
            return i + 1
        # Open the module in read mode
        i = pgr(conn, f"Opening module {sf.name} in read mode", 0, 100)
        sf.open(sf.name, sf.READ)
        # set the module in the "m" Module variable on the server
        sf.mod = sf.name

        # Get the absolute numbers
        l_absno = sf.mod_absnos
        # Get the attribute list
        l_attr = sf.attr_names
        # Remove RO attribute from the list
        l_attr_wc = l_attr
        for attr in L_DEFAULT_ATTR_RO:
            if attr in l_attr:
                l_attr_wc.remove(attr)
        # I position the read only attribute at the beginning of the
        # dataframe to simplify the access.
        l_attr = L_DEFAULT_ATTR_RO + l_attr_wc

        # Add the management attributes to working copy
        # Also readonly attribute is added but they cannot be
        # modified by user
        l_attr_wc = L_DEFAULT_ATTR_RO + l_attr_wc

        # Create the two empty dataframe for data
        sf.__data = pd.DataFrame("", index=l_absno, columns=l_attr +
                                 L_MAN_GENERATED)
        sf.wcd = pd.DataFrame("", index=l_absno, columns=l_attr_wc +
                              L_MAN_GENERATED)

        def cget(x, key):
            if x is False:
                return []
            if key in x.keys():
                return x[key]
            return []

        # Cycle over the absolute number and get the values
        imax = len(l_absno) + 1 + len(l_attr[len(L_DEFAULT_ATTR_RO):])
        for absno in l_absno:
            ################################################
            # Loading all attribute available in pandas object
            i = pgr(conn, f"Reading Attributes and Links of  Absno: {absno}.",
                    i, imax)
            l_values = sf.get_obj_attr_values(absno, l_attr)
            sf.__data.loc[absno, l_attr] = l_values
            sf.__data.loc[absno, S_ID] = encode_absno(absno)
            # the wc is the same without read only attrs.
            sf.wcd.loc[absno, l_attr] = l_values
            sf.wcd.loc[absno, S_ID] = encode_absno(absno)
            ################################################
            # Loading links in pandas object
            d_links = sf.get_links(absno)
            sf.__data.at[absno, S_INLINK] = cget(d_links, "in")
            sf.wcd.at[absno, S_INLINK] = cget(d_links, "in")
            sf.__data.at[absno, S_OUTLINK] = cget(d_links, "out")
            sf.wcd.at[absno, S_OUTLINK] = cget(d_links, "out")
            sf.__data.at[absno, S_EXTLINK] = cget(d_links, "ext")
            sf.wcd.at[absno, S_EXTLINK] = cget(d_links, "ext")

        # Save the data in pickle object
        sf.__data.to_pickle(sf._p_data)

        # Create the attrdef dataframe
        sf.__attrdef = pd.DataFrame("", index=l_attr[len(L_DEFAULT_ATTR_RO):],
                                    columns=sf.l_attr_def_columns)
        sf.wc_attrdef = pd.DataFrame("", index=l_attr[len(L_DEFAULT_ATTR_RO):],
                                     columns=sf.l_attr_def_columns)
        for attr in l_attr[len(L_DEFAULT_ATTR_RO):]:
            i = pgr(conn, f"Reading definition of attr: {attr}", i, imax)
            attr_def = sf.get_attr_def(attr)
            if not attr_def:
                return False
            # Create a list from the dict attr_def
            l_row = []
            for attr_key in sf.l_attr_def_columns:
                l_row.append(attr_def.get(attr_key, ""))
            # Write the list in the internal and wc dataframe
            sf.__attrdef.loc[attr, sf.l_attr_def_columns] = l_row
            sf.wc_attrdef.loc[attr, sf.l_attr_def_columns] = l_row

        # Save the attrdef in pickle object
        sf.__attrdef.to_pickle(sf._p_attrdef)

        pgr(conn, f"Download finished", i, imax)
        if conn:
            conn.send(None)
        return True

    def __get_abnso_by_id(self, id):
        """Get the absolute number from the id using __data """
        if id in self.__data[:, S_ID].values:
            return decode_absno(id)
        return None

    def compare(sf, f_excel=None):
        """Compare the module data and the working copy.

        This function compare the module data and the working copy and
        if f_excel is not None print the result in excel file.

        This function create the __compdata attribute which is a list, you
        can deccompress it using:
            dfcmp, l_new_cols_name, l_new_rows_index,\
                l_del_rows_index, l_del_cols_name,\
                l_new_row_previous_i = sf.__compdata
        - dfcmp is the dataframe with the comparison result
        - l_new_cols_name is the list of the new columns name
        - l_new_rows_index is the list of the new rows index
        - l_del_rows_index is the list of the deleted rows index$
        - l_del_cols_name is the list of the deleted columns name
        - l_new_row_previous_i is the list of the previous index of the
            new rows.

        These data describe the modification to be applied to the DOORS module.

        Args:
            f_excel (str): The excel file name where to print the result.

        Returns:
            bool: True if the module and the working copy are the same.
        """
        # Drop empty rows from the working copy
        sf.wcd.dropna(axis=0, how="all", inplace=True)
        # Remove the L_DEFAULT_ATTR_RO attributes from the working copy
        # and from the comparison dataframe because they cannot be modified
        # by the user.
        dfnew = sf.wcd.copy()
        # dfnew.drop(L_DEFAULT_ATTR_RO, axis=1, inplace=True, errors="ignore")
        dfdoors = sf.__data.copy()
        # dfdoors.drop(L_DEFAULT_ATTR_RO, axis=1, inplace=True, errors="ignore")

        # If there is not the Absolute Number attribute  raise an exception
        if S_ABSNO not in dfnew.columns and dfnew.index.name != S_ABSNO:
            raise Exception("The dataframe you provided has not the "
                            f" '{S_ABSNO}' attribute")
        # If the attribute L_MAN_GENERATED are not present in the working copy
        # raise an exception
        if not all([x in dfnew.columns for x in L_MAN_GENERATED]):
            raise Exception("The dataframe you provided has not the "
                            "management attributes: "
                            f"{L_MAN_GENERATED}")

        # If default attribute L_DEFAULT_ATTR_RO are not present in
        # the working copy add them empty column
        for attr in L_DEFAULT_ATTR_RO:
            if attr not in dfnew.columns:
                dfnew[attr] = ""

        # Correct the absno in the working copy if they was changed
        index = dfnew.index.name
        if index != S_ABSNO:
            index = S_ABSNO
        if dfdoors is not None and list(dfdoors.index) != []:
            imax = max([int(x) for x in dfdoors.index]) + 1
        else:
            imax = 0
        dfnew.reset_index(inplace=True)
        for i, row in dfnew.iterrows():
            # If there is not the __id attribute or it is empty
            if str(row[S_ID]) == "" or str(row[S_ID]) == "nan":
                dfnew.loc[i, S_ABSNO] = str(imax)
                imax += 1
            else:
                try:
                    correct_absno = decode_absno(str(row[S_ID]))
                except:
                    raise Exception("You cannot change the __id attribute")
                dfnew.loc[i, S_ABSNO] = str(correct_absno)
        dfnew.set_index(index, inplace=True)

        # Compare the two dataframe
        sf.__compdata = compare(dfdoors, dfnew, f_excel)
        dfcmp, l_new_cols_name, l_new_rows_index,\
            l_del_rows_index, l_del_cols_name,\
            l_new_row_previous_i = sf.__compdata
        bl_dfcmp = False
        for absno, row in iter_not_empty(dfcmp):
            bl_dfcmp = True
            break
        bl_ret = False
        if bl_dfcmp or l_del_cols_name != [] or l_del_rows_index != [] or\
                not l_new_cols_name == [] or not l_new_rows_index == [] or\
                not l_new_row_previous_i == []:
            bl_ret = True
        return bl_ret

    def write(sf, f_excel=None, conn=None):
        """Write local dataframe modification on the DOORS module.

        Write permitt are necessary.
        The write function works on the last self.compare() runned, if it is
        not runned it will be runned automatically.
        The self.s_cmd ("__cmd") attribute is used to specify some commands,
        at the moment the implemented commands are:
            - "below": to be used for new object, indicate that the the new obj
                will be created below the previous one.
            - "after": (default if not specified) to be used for new object,
                indicate that the the new obj will be created after the previous
                one.

        Warning:
            Be careful using this function, you will directly modify data in
            DOORS module, no ctrl-z like management is already implemented.
            Anyway you can do baselines before and after the modification in
            order to have a backup of the module.
            e.g. :
                dsm = doorsmod("my_module")
                dsm.make_baseline("suffix", "comment", False) # False for minor
                ... modify the dsm.wcd dataframe ...
                dsm.write()  # write the dsm.wcd dataframe to DOORS
                dsm.make_baseline("suffix", "comment", True) # True for major

        New attribute warnings:
            When you create new attributes, you have to specify the attribute
            type in the wc_attrdef, if not specified the attribute are
            created using text type.
            If instead the type is specified be care that no checks are
            done.
            If the name of an attribute is changed a new attribute is created
            and the data copied, the previous one remains unchanged.
            The deletion of a column is not possible, you can only delete
            rows.
            To easily create new attributes in the wcd dataframe use the funct
            self.check_create_attr(l_attr) and then modify manually the
            self.wc_attrdef.

        Rows warnings:
            Be care the deletion or rows are removed in DOORS but not purged.
            This means that the deleted rows are still present in the module
            but marked as deleted (exactly as when you do it manually).
            New rows are added to the module according to __cmd attribute.

        Returns:
            bool: false if it is not possible to open the module in write mode
        """
        def pgr(conn, msg, i, imax):
            if conn:
                conn.send("{\"msg\": \"" + msg + "\", \"perc\": " +
                          str(int((i/imax)*1000)/10) + "}")
            return i + 1

        # Check if the comparison is done
        imax = 100
        pgr(conn, f"Compare doors with excel...", 0, imax)
        if sf.__compdata is None:
            sf.compare(f_excel)

        pgr(conn, f"Start DOORS writing...", 1, imax)
        # Get the differences
        dfcmp, l_new_cols_name, l_new_rows_index,\
            l_del_rows_index, l_del_cols_name,\
            l_new_row_previous_i = sf.__compdata

        # Try to open the module in write mode, return False if is not possible
        if not sf.open(sf.name, "w"):
            pgr(conn, f"Unable to open the module!!", 1, imax)
            if conn:
                conn.send(None)
            return False

        bl_ret = True
        try:
            ##############################################################
            # Create the new rows
            j = 0
            imax = len(l_new_rows_index) + 1 + len(l_new_cols_name) \
                + dfcmp.shape[0] + len(l_del_rows_index)
            l_new_rows_index_real = []
            for i, absno in enumerate(l_new_rows_index):
                j = pgr(conn, f"Creating New Rows with absno: {absno}.",
                        j, imax)
                # Get the previous row absno
                absno_prev = l_new_row_previous_i[i]
                # If the prev absolute number is not in the absno of
                # the module this means that is the absno created in the prev
                # iteration, so I have to get the correct absno.
                if absno_prev not in sf.__data.index and i != 0:
                    absno_prev = l_new_rows_index_real[i-1]

                # get from __cmd if the new row should be below or after
                # the previous row
                l_cmd = str(dfcmp.loc[absno][S_CMD]).split(":")
                if CMD_BELOW in l_cmd:
                    new_absno = sf.new_obj("last", CMD_BELOW, absno_prev)
                else:
                    new_absno = sf.new_obj("last", CMD_AFTER, absno_prev)

                l_new_rows_index_real.append(new_absno)
                # Replace the supposed absno with the correct one in the
                # previous abnso list.
                l_new_row_previous_i = [new_absno if val == absno else val
                                        for val in l_new_row_previous_i]

            ################################################################
            # Create the new columns
            for attr in l_new_cols_name:
                j = pgr(conn, f"Creating New Attribute with name: {attr}.",
                        j, imax)
                # If not specified the type is text
                l_attr_def = ["Text"] + [None] * 2 + [False] + [""]
                # Get the correct type if exists
                if attr in sf.wc_attrdef.index:
                    l_attr_def = sf.wc_attrdef.loc[attr][sf.l_attr_def_columns]
                    # TODO checks
                # Create the new column
                sf.def_attr(attr, *l_attr_def)

            ################################################################
            # Delete the old rows
            pgr(conn, f"3--{l_del_rows_index}-", 1, imax)
            for absno in l_del_rows_index:
                pgr(conn, f"4--{l_del_rows_index}-", 1, imax)
                j = pgr(conn, f"Deleting row with absno: {absno}.",
                        j, imax)
                sf.del_obj(absno)

            ################################################################
            # Delete the old columns

            ################################################################
            # Modify the data
            for absno, row in iter_not_empty(dfcmp):
                if absno in l_new_rows_index:
                    absno = l_new_rows_index_real[l_new_rows_index.
                                                  index(absno)]
                j = pgr(conn, f"Modifying data of absno: {absno}.",
                        j, imax)
                sf.set_obj_attr_values(absno, row)

        except AttributeError:
            bl_ret = False
        finally:
            sf.close()

        pgr(conn, f"Reading DOORS Module again for consistency", j, imax)
        sf.read(force=True, conn=conn)
        sf.__compdata = None

        pgr(conn, f"Download finished", j, imax)
        if conn:
            conn.send(None)
        return bl_ret

    def create_links_by_attr(self, attr: str, l_target_mod: list,
                             l_link_mods: list, log_file=None,
                             reload_target_mods: bool = True,
                             exclude_empty_target: bool = False,
                             delete_old_links: bool = False):
        """Create the module links directly in doors

        The function from the current module to the id listed in the attr
        attribute. For each object the attr value is readed, the id should
        be divided using newline, each id is searched in each of the
        l_target_mod module, if it is found the outlink from the current
        module is created using the corresponding link module in l_link_mods.

        Args:
            attr (str): The attribute name to use to create the links
            l_target_mod (list): The list of target module fullname. The object
                identifiers in the attr attribute should be in one of these
                modules. Otherwise the link is not created, no error occurred.
            l_link_mods (list): The list of link module fullname, the list
                should have the same length as l_target_mod and the links from
                the l_target_mod will be created using these corresponding
                link modules.
            log_file (str, optional): The log file name, print down the log
                of the link creation. Defaults to None.
            reload_target_mods (bool, optional): If True the target modules
                are reloaded before the link creation. Defaults to True.
            delete_old_links (bool, optional): If True the old links are
                deleted before the new links are created. This means that
                only the links in the attr attribute will be present in the
                module. Defaults to True.
        """
        try:
            # Try to open the log file in write mode
            if log_file is not None:
                f_log = open(log_file, "w")
            else:
                f_log = None
        except:
            raise ValueError("The log file cannot be open")

        s_all_msg = ""

        if attr not in self.wcd.columns:
            raise Exception(f"The attribute {attr} does not exist")

        # Get the prefix of each taget module
        d_prefix = {}
        d_dsm = {}
        # check the existing of link modules
        for mod in l_link_mods:
            ddsm = doorsmod(mod)
            if not ddsm.check_mod():
                raise Exception(f"The link module {mod} does not exist")

        # Check the existing target modules and found the prefixes
        for mod in l_target_mod:
            d_dsm[mod] = doorsmod(mod)
            if not d_dsm[mod].check_mod():
                raise Exception(f"The module {mod} does not exist")
            d_dsm[mod].read(force=reload_target_mods)
            d_ret = d_dsm[mod].mod_info
            if not d_ret:
                raise Exception(f"The module {mod} does not exist")
            d_prefix[d_ret["prefix"]] = mod

        def get_prefix(identifier):
            if len(identifier.split("_")) == 1:
                return identifier
            return "_".join(identifier.split("_")[:-1]).strip() + "_"

        def get_absno(identifier):
            return identifier.split("_")[-1]

        """ Create a dictionary with absnos as keys, each key corresponds to a
        dictionary with the taget module names as keys and this contains
        the list of the target absno like:
            {absno1: {"fullname_mod1": [absno1, absno2, ...],
                        "fullname_mod2": [absno1, absno2, ...]}
             absno2: {"fullname_mod1": [absno1, absno2, ...],
                        "fullname_mod2": [absno1, absno2, ...]}}
        """
        ###############################################################
        # Get all the link to do
        d_links_tbd = {}
        for absno, row in self.wcd.iterrows():
            s_ids = str(row[attr]).strip()
            if s_ids == "" or s_ids == "nan":
                continue
            l_ids = s_ids.split("\n")
            l_ids = [s.strip() for s in l_ids if s.strip() != ""]
            for s_id in l_ids:
                # Check if the prefix and the absno are correct.
                s_prefix = get_prefix(s_id)
                if s_prefix not in d_prefix.keys():
                    msg = f"The prefix {s_prefix} does not exist"\
                        f" in the list of target modules"
                    if f_log is not None:
                        f_log.write(msg)
                    logging.warning(msg)
                    s_all_msg += msg + "\n"
                    continue
                s_absno = get_absno(s_id)
                if not s_absno.isnumeric():
                    msg = f"ID {s_id} absno {s_absno} is not numeric."
                    if f_log is not None:
                        f_log.write(msg)
                    logging.warning(msg)
                    s_all_msg += msg + "\n"
                    continue
                s_mod = d_prefix[s_prefix]
                # Add the absno to the list if it does not exist
                if s_absno not in d_dsm[s_mod].wcd.index.values:
                    msg = f"Link set in absno{absno} has as target mod"\
                        f" {s_mod} obj number {s_absno} which does not"\
                        " exists."
                    if f_log is not None:
                        f_log.write(msg)
                    logging.warning(msg)
                    s_all_msg += msg + "\n"
                    continue
                # Create the key in d_links_tbd if not exists
                if absno not in d_links_tbd.keys():
                    d_links_tbd[absno] = {}
                # Create the list with s_mod as key if not exists
                if s_mod not in d_links_tbd[absno].keys():
                    d_links_tbd[absno][s_mod] = []
                if absno not in d_links_tbd[absno][s_mod]:
                    d_links_tbd[absno][s_mod].append(s_absno)

        if f_log is not None:
            f_log.write("-"*100 + "\n" + "All links:\n")
            logging.info(d_links_tbd)
            logging.info(f_log)
            f_log.write("\n" + "-"*100)

        ####################################################################
        # Found the current links with the target modules
        d_cur_links = {}

        for absno, row in self.wcd.iterrows():
            s_id = str(row[attr]).strip()
            if (s_id == "" or s_id == "nan") and exclude_empty_target:
                continue
            for d_link in row[S_OUTLINK]:
                logging.info(f"Absno: {absno}: {d_link}")
                # Check that the target module is one of the required ones
                if d_link[S_L_MOD_KEY] not in l_target_mod:
                    continue
                s_target_mod = d_link[S_L_MOD_KEY]
                s_lnkmod = l_link_mods[l_target_mod.index(s_target_mod)]
                # Check that the link module is the correct one for the target
                if d_link[S_L_LINKMOD_KEY] != s_lnkmod:
                    continue
                # Create the key in d_cur_links if not exists
                if absno not in d_cur_links.keys():
                    d_cur_links[absno] = {}
                # Add the absno to the list
                if s_target_mod not in d_cur_links[absno].keys():
                    d_cur_links[absno][s_target_mod] = []
                if d_link[S_L_ABSNO_KEY] not in \
                        d_cur_links[absno][s_target_mod]:
                    d_cur_links[absno][s_target_mod].\
                        append(d_link[S_L_ABSNO_KEY])

        if f_log is not None:
            f_log.write("-"*100 + "\n" + "Current matching links with"
                        f" required target mods ({l_target_mod}) and the "
                        f" correct link mods ({l_link_mods})\n")
            logging.info(d_cur_links)
            logging.info(f_log)
            f_log.write("\n" + "-"*100)

        ####################################################################
        # Found the link to create and to be deleted
        d_link_cmd = {}
        S_DEL = "del"
        S_NEW = "new"

        l_common_absno = list(set(d_cur_links.keys()) &
                              set(d_links_tbd.keys()))
        l_del_absnos = list(set(d_cur_links.keys()) -
                            set(d_links_tbd.keys()))
        l_new_absnos = list(set(d_links_tbd.keys()) -
                            set(d_cur_links.keys()))

        for absno in l_common_absno:
            # analyse the target module asked in the attribute
            for s_mod, l_absno in d_links_tbd[absno].items():
                l_new = []
                l_del = []
                if s_mod in d_cur_links[absno].keys():
                    l_new = list(set(l_absno) - set(d_cur_links[absno][s_mod]))
                    l_del = list(set(d_cur_links[absno][s_mod]) - set(l_absno))
                    if l_del != []:
                        if absno not in d_link_cmd.keys():
                            d_link_cmd[absno] = {}
                        if s_mod not in d_link_cmd[absno].keys():
                            d_link_cmd[absno][s_mod] = {}
                        d_link_cmd[absno][s_mod][S_DEL] = l_del
                else:
                    l_new = l_absno
                if l_new != []:
                    if absno not in d_link_cmd.keys():
                        d_link_cmd[absno] = {}
                    if s_mod not in d_link_cmd[absno].keys():
                        d_link_cmd[absno][s_mod] = {}
                    d_link_cmd[absno][s_mod][S_NEW] = l_new

            # The remaining links to other module should be deleted
            # for other module is intended the l_target_mod not in d_links_tbd
            l_mod_tbdel = list(set(d_cur_links[absno].keys()) -
                               set(d_links_tbd[absno].keys()))
            for s_mod in l_mod_tbdel:
                if absno not in d_link_cmd.keys():
                    d_link_cmd[absno] = {}
                if s_mod not in d_link_cmd[absno].keys():
                    d_link_cmd[absno][s_mod] = {}
                if S_DEL in d_link_cmd[absno][s_mod].keys():
                    d_link_cmd[absno][s_mod][S_DEL] +=\
                        d_cur_links[absno][s_mod]
                else:
                    d_link_cmd[absno][s_mod][S_DEL] = d_cur_links[absno][s_mod]

        # The remaining link should be deleted
        for absno in l_del_absnos:
            for s_mod in d_cur_links[absno].keys():
                if absno not in d_link_cmd.keys():
                    d_link_cmd[absno] = {}
                if s_mod not in d_link_cmd[absno].keys():
                    d_link_cmd[absno][s_mod] = {}
                d_link_cmd[absno][s_mod][S_DEL] = d_cur_links[absno][s_mod]

        # The remaining links should be created
        for absno in l_new_absnos:
            for s_mod in d_links_tbd[absno].keys():
                if absno not in d_link_cmd.keys():
                    d_link_cmd[absno] = {}
                if s_mod not in d_link_cmd[absno].keys():
                    d_link_cmd[absno][s_mod] = {}
                d_link_cmd[absno][s_mod][S_NEW] = d_links_tbd[absno][s_mod]

        if f_log is not None:
            f_log.write("-"*100 + "\n" + "Link commands:\n")
            logging.info(d_link_cmd)
            logging.info(f_log)
            f_log.write("-------------------------------------------\n")
            f_log.write(f"l_del_absnos: {l_del_absnos}\n")
            f_log.write(f"l_new_absnos: {l_new_absnos}\n")
            f_log.write(f"l_common_absno: {l_common_absno}\n")
            f_log.write("\n" + "-"*100)

        ####################################################################
        # Create and delete the links in the module as specified
        bl_open = False
        try:
            for absno, d_mod_cmd in d_link_cmd.items():
                for s_mod, d_cmd in d_mod_cmd.items():
                    if S_NEW in d_cmd.keys():
                        l_absno = d_cmd[S_NEW]
                        if not bl_open:
                            self.open(self.name, "w")
                        ret = self.create_links(s_mod, absno, l_absno,
                                                l_link_mods[l_target_mod.
                                                            index(s_mod)])
                        if not ret:
                            msg = f"Links from {absno} to {s_mod} " \
                                f"not created, l_target_absno: {l_absno}"
                            if f_log is not None:
                                f_log.write(msg)
                            logging.warning(msg)
                            s_all_msg += msg + "\n"
                    if S_DEL in d_cmd.keys() and delete_old_links:
                        self.close()
                        raise Exception("Delete links not permitted")
                        l_absno = d_cmd[S_DEL]
                        if not bl_open:
                            self.open(self.name, "w")
                        ret = self.delete_links(s_mod, absno, l_absno,
                                                l_link_mods[l_target_mod.
                                                            index(s_mod)])
                        if not ret:
                            msg = f"Links from {absno} to {s_mod} " \
                                f"not deleted, l_target_absno: {l_absno}"
                            if f_log is not None:
                                f_log.write(msg)
                            logging.warning(msg)
                            s_all_msg += msg + "\n"
        except Exception as e:
            raise Exception("Error during changing the links: " + str(e))
        finally:
            self.close()

        # Close the log file
        if f_log is not None:
            f_log.close()
        # Return the message if not empty
        if s_all_msg != "":
            return s_all_msg
        return True

    def check_mod(sf, create_if_not_exists=False,
                  description="No Description", prefix="REQ") -> bool:
        """Check if the module exists in the working copy.

        Args:
            create_if_not_exists (bool, optional): If True, the module is
                created if it does not exist. Defaults to False.
            description (str, optional): The description of the module used
                if the module shall be created. Defaults to "No Description".
            prefix (str, optional): The prefix of the module used if the
                module shall be created. Defaults to "REQ".

        Returns:
            bool: True if the module exists or was created, False otherwise.
        """
        if not sf.mod_exists(sf.name):
            if create_if_not_exists:
                sf.new_mod(sf.name, description, prefix)
                sf.close()
                return True
            return False
        return True

    def check_create_attr(self, l_attr):
        """Create the attribute in the working copy if it does not exist."""
        b_set = False
        for attr in l_attr:
            if attr not in self.wcd.columns:
                self.wcd[attr] = ""
                b_set = True
        # Return True if the attribute was set
        return b_set

    def new_view(sf, name: str, l_attr: list, set_default: bool = False):
        """Create a new view using the given l_attr and set_default

        Args:
            name (str): The name of the view
            l_attr (list): The list of attributes to be shown in the view
            set_default (bool, optional): If True, the view is set as default.
                Defaults to False.

        Returns:
            bool: True if succeed
        """
        if not sf.open(sf.name, "w"):
            return False
        try:
            sf.def_view(name, l_attr, set_default)
        except Exception as e:
            return False
        finally:
            sf.close()
        return True

    @property
    def name(sf):
        return sf.__name

    @name.setter
    def name(sf, newname):
        if newname != sf.name:
            sf.__init__(newname)

    def copy(sf, newname: str, description: str = "No Description",
             prefix: str = "REQ", abort_if_exists: bool = False)\
                 -> "doorsmod":
        """Copy the module to a new module or replace data in an existing one.

        Args:
            newname (str): The name of the new module
            create_if_not_exists (bool, optional): If True, the module is
                created if it does not exist. Defaults to False.
            description (str, optional): The description of the module used
                if the module shall be created. Defaults to "No Description".
            prefix (str, optional): The prefix of the module used if the
                module shall be created. Defaults to "REQ".
            abort_if_exists (bool, optional): If True, the function returns
                False if the module already exists. Defaults to False.
        Returns:
            bool: True if the module was copied or exists, False otherwise.
        """
        if not (already_exists := sf.mod_exists(newname)):
            print(f"The module {newname} exists")
            iscreated = sf.new_mod(newname, description, prefix)
            if not iscreated:
                return False
            sf.close(newname)
        if already_exists and abort_if_exists:
            return False
        dsm = doorsmod(newname)
        dsm.read()
        if sf.wcd is not None:
            dsm.wcd = sf.wcd.copy()
            # clear the __id attribute
            dsm.wcd[S_ID] = ""
        # Copy the attrdef
        if sf.wc_attrdef is not None:
            dsm.wc_attrdef = sf.wc_attrdef.copy()
            dsm.write()
        return dsm


class DoorsReq(Req):
    """Doors single requirement class.
    """
    def __init__(self, module: "DoorsmodStd", id: str) -> None:
        """Create a new DoorsReq object.

        Args:
            module (DoorsmodStd): The module where the requirement is
                stored.
            id (str): The id of the requirement.
        """
        self._drobj = module
        self._id = id
        self._url = None
        ################################################
        # Solve the inlinks and outlinks

        self.__inlinks = lambda: self._drobj._dsm.wcd.loc[self._id, S_INLINK]
        self.__outlinks = lambda: self._drobj._dsm.wcd.loc[self._id, S_OUTLINK]
        self.__extlinks = lambda: self._drobj._dsm.wcd.loc[self._id, S_EXTLINK]
        self.__inlinks_solved = None
        self.__outlinks_solved = None

    @property
    def module(self) -> "DoorsmodStd":
        return self._drobj

    @property
    def id(self) -> str:
        return self._id

    @property
    def url(self) -> str:
        if self._url is None:
            self._url = self._drobj._dsm.get_obj_url(self._id)
        return self._url

    @property
    def data(self) -> dict:
        return self._drobj._dsm.wcd.loc[self._id].to_dict()

    def __getitem__(self, key: str) -> Any:
        return self._drobj._dsm.wcd.loc[self._id, key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._drobj._dsm.wcd.loc[self._id, key] = value

    def _get_inlinks(self) -> List["DoorsReq"]:
        inlinks_solved = []
        for dlink in self.__inlinks():
            mod = dlink[S_L_MOD_KEY]
            absno = dlink[S_L_ABSNO_KEY]
            mod = DoorsmodStd.get_mod_loaded(mod)
            inlinks_solved.append(DoorsReq(mod, absno))
        return inlinks_solved

    def _get_outlinks(self) -> List["DoorsReq"]:
        outlinks_solved = []
        for dlink in self.__outlinks():
            mod = dlink[S_L_MOD_KEY]
            absno = dlink[S_L_ABSNO_KEY]
            mod = DoorsmodStd.get_mod_loaded(mod)
            outlinks_solved.append(DoorsReq(mod, absno))
        return outlinks_solved

    @property
    def inlinks(self) -> List["DoorsReq"]:
        if self.__inlinks_solved is None:
            self.__inlinks_solved = self._get_inlinks()
        return self.__inlinks_solved

    @property
    def outlinks(self) -> List["DoorsReq"]:
        if self.__outlinks_solved is None:
            self.__outlinks_solved = self._get_outlinks()
        return self.__outlinks_solved

    def _get_outlink_linkmod(self, target_modname: str) -> str | None:
        target_modname = target_modname.split("@")[0]
        if target_modname not in self._drobj._dsm.linksets["outlinks"]:
            return None
        return self._drobj._dsm.linksets["outlinks"][target_modname]

    @outlinks.setter
    def outlinks(self, value: List["DoorsReq"]) -> None:
        self.__outlinks_solved = value
        # Add the link to the dataframe
        l_links = []
        for req in value:
            lmod = self._get_outlink_linkmod(req.module.name)
            if lmod is None:
                raise ValueError(f"Link module for {req.module.name} "
                                 "not found, available linksets are: "
                                 f"{self._drobj._dsm.linksets['outlinks']}")
            l_links.append({S_L_MOD_KEY: req.module.name.split("@")[0],
                            S_L_LINKMOD_KEY: lmod,
                            S_L_ABSNO_KEY: req.id})
        self._drobj._dsm.wcd.loc[self._id, S_OUTLINK] = l_links

    @property
    def extlinks(self) -> List[str]:
        return self.__extlinks()


class DoorsmodStd(ReqModule):
    """DoorsmodStd class is a standard doorsmod class with some predefined
    attributes and methods.

    """
    d_mods = {}

    def __init__(self, name: str) -> None:
        """Create a new DoorsmodStd object.

        Args:
            name (str): The name of the module, if it is a baseline
                you have to specify the suffix, major and minor version inside
                the name with the following format:
                    </path/to/modulename>@[<suffix>_]<major>.<minor>
                So if suffix does not exist you have to specify the name
                of the module only like:
                    </path/to/modulename>@<major>.<minor>
        """
        self._dsm: doorsmod = doorsmod(name)
        self._dsm.check_mod()
        # Flag to avoid circular loading
        self._isloading = False
        self._reqs: List[DoorsReq] = []
        self._linksets = None

    @classmethod
    def versions(cls, name_no_version: str) -> List[str]:
        """Get the list of the versions of the module.

        Args:
            name_no_version (str): The name of the module without the version
                suffix.

        Returns:
            List[str]: The list of the versions of the module
                is in the format:
                    <name>@[<suffix>_]<major>.<minor>
                where suffix is optional.
        """
        dsm = doorsmod(name_no_version)
        bs = dsm.get_baselines()
        if bs is None:
            return []
        return [f"{name_no_version}@{b[S_BS_ID]}" for b in bs]

    def load(self) -> bool:
        """Load the module with the specified version.

        Args:
            version (str): The version of the module to load.

        Returns:
            bool: True if the module was loaded, False otherwise.
        """
        shoud_load = self._dsm.should_be_updated()
        ret = self._dsm.read()
        if shoud_load or self._linksets is None:
            self._linksets = self._dsm.linksets
            self._isloading = True
            # Creation of the req objects
            self._reqs = []
            for absno in self._dsm.wcd.index:
                self._reqs.append(DoorsReq(self, absno))
            self._isloading = False
        DoorsmodStd.d_mods[self._dsm.name] = self
        return ret

    def upload(self) -> bool:
        """Upload the module."""
        return self._dsm.write()

    def copy_obj(self) -> "DoorsmodStd":
        """Copy the object."""
        return DoorsmodStd(self._dsm.name)

    ####################################################################
    # Dunder methods

    def __iter__(self) -> DoorsReq:
        for req in self._reqs:
            yield req

    def __len__(self) -> int:
        return len(self._reqs)

    def __getitem__(self, id: str) -> DoorsReq:
        if self._reqs == []:
            self.load()
        for req in self._reqs:
            if req.id == id:
                return req
        return None

    ####################################################################
    # Properties
    @property
    def name(self) -> str:
        return self._dsm.name

    @property
    def url(self) -> str:
        return self._dsm.mod_info[S_INFO_URL]

    @property
    def reqs(self) -> List[DoorsReq]:
        return self._reqs

    @property
    def columns(self) -> List[str]:
        return self._dsm.columns

    @property
    def df_polars(self) -> pl.DataFrame:
        return pl.DataFrame(self._dsm.wcd)

    @classmethod
    def from_polars(cls, df: pl.DataFrame) -> "DoorsmodStd":
        raise NotImplementedError("Method not implemented")

    @classmethod
    def get_mod_loaded(cls, name: str) -> "DoorsmodStd":
        """Get mod from memory."""
        if name not in cls.d_mods.keys():
            cls.d_mods[name] = cls(name)
        return cls.d_mods[name]


if __name__ == "__main__":
    dsm = DoorsmodStd("/xxx_SYS_TestsProject/TestDoorsmod")
    dsm.load()
    dsm.reqs[0].inlinks[0].inlinks