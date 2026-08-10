# -*- coding: utf-8 -*-
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
from icecream import ic
import pandas as pd
import os
from multiprocessing import Process, Pipe
# import of the dxl class

from dopyi.dxl import dxl
from dopyi.dxl import N_PORT, S_STD_DIV, S_STD_STARTER

##########################################################################
# default path in which store metadata and data

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
L_MAN_GENERATED = [S_INLINK, S_OUTLINK]

# Read Write object attributes
L_DEFAULT_ATTR_RW = ["Absolute Number",
                     "Object Text",
                     "Object Heading"]
# Custome attributes for management
L_MAN_ATTR = ["__cmd"]


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

        -   read() DONE, Read the DOORS module and create two local pandas
            object, an internal object and a working copy which you can
            modify (dsm.wcd).
        -   write() DONE, Write the working copy to the DOORS module.
        -   compare() DONE, This function compare wcd and wc_attrdef you modify
            with the original one, the resulting dataframe is written in
            *self.diff* and self.attrdiff. Return True if there are differences
            and False if there are not.
        -   clean() TODO
        -   wc_checker() TODO
        -   insert() DONE, Insert a new object in the DOORS module.

    Property:

        -   name
        -   mode

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
            dsm.insert({"Object Text": "Hello", "ASIL": "A"}, position="after",
                       absno=10)

            # Check the modification at the working copy
            dsm.wc_checker() # not already implemented
            # Apply changes to the server
            dsm.write()

        It is also possible to read in/out links of the objects, they are
        also saved in the dsm.wcd dataframe::

            absno = 12     # Suppose you want the link of absolute number 12
            dsm.wcd.loc[absno, "inlink"]  # this is an inlink dictionary as below:
            [{'absno': '209', # Absno of the object from which the link came
              'linkmod': '/xxx_SYS_TestsProject/connect', # Link module name
              'mod': '/xxx_SYS_TestsProject/SoW_Example2'}, # Source module name
             {'absno': '211',
              'linkmod': '/xxx_SYS_TestsProject/connect',
              'mod': '/xxx_SYS_TestsProject/SoW_Example2'}]
            dsm.wcd.loc[absno, "outlink"] # this is an outlink dictionary as below:
            [{'absno': '175',     # Target object Absolute number
              'linkmod': '/xxx_SYS_TestsProject/connect',     # Link module
              'mod': '/xxx_SYS_TestsProject/SoW_Example2'}# Target module
             }]

        At the moment link are in read only mode, you can't change it with this
        library.

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
                    for d_inlink in row["inlink"]:
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

            dsm.wc_checker()
            dsm.write()


    Note:
        If you create new pandas object always use :func:`~dxl.dxl.insert`
        function. It will create internal attributes starting with "__"

    Warning:
        At the moment it is avoided to modify the attribute name of
        the *wcd* dataframe, DOORS attribute are the master.
        Not aldready implemented:

            -   sf.wc_attrdef support
            -   sf.wc_moddata support

        Only data modification is available, it is suggested to upload
        only string/text attribute to avoid problem.

    """
    CLOSED = "closed"
    READ = "r"
    WRITE = "w"
    s_inlinks = S_INLINK
    s_outlinks = S_OUTLINK 

    def __init__(sf,
                 name: str,
                 port=N_PORT,
                 div=S_STD_DIV,
                 starter=S_STD_STARTER):
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
        sf.__moddata = None
        # This is the working copy
        sf.wc_moddata = None

        #########################################################
        # Creation of the pikle files in which store module data
        # I recreate the same folder structure of DOORS
        onlyname = os.path.basename(name)
        dir = os.path.join(P_DATA_SAVE, os.path.dirname(name)[1:], onlyname)
        if not os.path.exists(dir):
            os.makedirs(dir)
        sf._p_attrdef = os.path.join(dir, "attrdef.pkl")
        sf._p_moddata = os.path.join(dir, "moddata.pkl")
        sf._p_data = os.path.join(dir, "data.pkl")

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
            conn (Connection): a pipe connection through which
                will be sent the information about the current
                status of the download and elaboration.

        After you run this function you can modify the module
        through the Dataframes:

            -   sf.wcd:
                It is the module data as dataframe so e.g.
                sf.wcd.columns get the module attribute list.
            -   sf.wc_attrdef:
                definition of the existing attribute in the module
            -   sf.wc_moddata:
                the module data like prefix and so on.
        """
        # if the pickles files exist i load it instead of
        # read from DOORS
        if os.path.exists(sf._p_data) and\
                os.path.exists(sf._p_attrdef) and not force:
            sf.__attrdef = pd.read_pickle(sf._p_attrdef)
            sf.wc_attrdef = sf.__attrdef.copy()
            sf.__data = pd.read_pickle(sf._p_data)
            sf.wcd = sf.__data.copy()
        else:
            # check the name of the module
            if not sf.mod_exists(sf.__name):
                raise ModuleNotExistsError(sf.__name)
            return sf.__doorsread(conn)
        return True

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

            -   sf.wcd:
                It is the module data as dataframe so e.g.
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
        l_attr_wc = L_MAN_ATTR + L_DEFAULT_ATTR_RO + l_attr_wc

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
        imax = len(l_absno) + 1 + len(l_attr)
        for absno in l_absno:
            ################################################
            # Loading all attribute available in pandas object
            i = pgr(conn, f"Reading Attributes/Links of {absno}.", i, imax)
            l_values = sf.get_obj_attr_values(absno, l_attr)
            sf.__data.loc[absno, l_attr] = l_values
            # the wc is the same without read only attrs.
            sf.wcd.loc[absno, l_attr] = l_values
            ################################################
            # Loading links in pandas object
            d_links = sf.get_links(absno)
            sf.__data.at[absno, sf.s_inlinks] = cget(d_links, "in")
            sf.wcd.at[absno, sf.s_inlinks] = cget(d_links, "in")
            sf.__data.at[absno, sf.s_outlinks] = cget(d_links, "out")
            sf.wcd.at[absno, sf.s_outlinks] = cget(d_links, "out")

        # Save the data in pickle object
        sf.__data.to_pickle(sf._p_data)

        # Create the attrdef dataframe
        l_attr_def_columns = ["type", "basetype", "l_enum", "multi", "default"]
        sf.__attrdef = pd.DataFrame("", index=l_attr[len(L_DEFAULT_ATTR_RO):],
                                    columns=l_attr_def_columns)
        sf.wc_attrdef = pd.DataFrame("", index=l_attr[len(L_DEFAULT_ATTR_RO):],
                                     columns=l_attr_def_columns)
        for attr in l_attr[len(L_DEFAULT_ATTR_RO):]:
            attr_def = sf.get_attr_def(attr)
            if not attr_def:
                return False
            # Create a list from the dict attr_def
            l_row = []
            for attr_key in l_attr_def_columns:
                l_row.append(attr_def.get(attr_key, ""))
            # Write the list in the internal and wc dataframe
            sf.__attrdef.loc[attr, l_attr_def_columns] = l_row
            sf.wc_attrdef.loc[attr, l_attr_def_columns] = l_row

        # Save the attrdef in pickle object
        sf.__attrdef.to_pickle(sf._p_attrdef)

        pgr(conn, f"Download finished", i, imax)
        if conn:
            conn.send(None)
        sf.__data.set_index("Absolute Number", inplace=True)
        sf.wcd.set_index("Absolute Number", inplace=True)
        return True

    def wc_checker(sf):
        """check if the working copy of the dataframes are consistent

        This function consider the actual feature of write command and
        according to this verify the integrity of the dataframes (wcd,
        wc_moddata and wc_attrdef), e.g. if it is not supported the
        adding of new attribute and the wc has new attribute a returning
        string with the error is get.

        Returns:
            bool/str: True if it is ok, otherwise an error string.
        """
        # TODO check that no new object is created without use insert funct
        pass

    def compare(sf):
        """This function compare *wcd*, *wc_attrdef" dataframes with original.

        The resulting dataframe is written in *self.diff* and self.attrdiff.

        Returns:
            bool: false if the two dataframe are equal.
        """
        # We consider that no modification at the attribute of wcd is done
        n_ma = len(L_DEFAULT_ATTR_RO)
        l_attr_to_cmp = sf.__data.columns[n_ma:]
        if sf.__data[l_attr_to_cmp].equals(sf.wcd[l_attr_to_cmp]):
            if hasattr(sf, "diff"):
                del sf.diff
            if hasattr(sf, "mat_diff"):
                del sf.mat_diff
        else:
            l_common_absno = [x for x in sf.wcd.index if x in sf.__data.index]
            cmp_data = sf.__data.loc[l_common_absno]
            cmp_wcd = sf.wcd.loc[l_common_absno]
            # select the correct attributes and compare
            l_common_attr = [x for x in l_attr_to_cmp if x in sf.__data.columns]

            sf.diff = cmp_data[l_common_attr].compare(cmp_wcd[l_common_attr])

            sf.mat_diff = []
            sf.mat_diff.append([sf.diff.index.name] +
                               list(set(sf.diff.columns.get_level_values(0))))
            for absno, row in sf.diff.iterrows():
                sf.mat_diff.append([absno])
                for attr in sf.mat_diff[0][1:]:
                    ff = row[attr]["self"]
                    tt = row[attr]["other"]
                    s_msg = ""
                    if ff != tt:
                        s_msg = f"from: \"{ff}\"\nto: \"{tt}\""
                    sf.mat_diff[-1].append(s_msg)
        if sf.__attrdef.equals(sf.wc_attrdef):
            if hasattr(sf, "attrdiff"):
                del sf.attrdiff
            if hasattr(sf, "mat_attrdiff"):
                del sf.mat_attrdiff
        else:
            sf.attrdiff = sf.__attrdef.compare(sf.wc_attrdef)

            sf.mat_attrdiff = []
            sf.mat_attrdiff.append([sf.attrdiff.index.name] +
                                   list(set(sf.attrdiff.columns.
                                            get_level_values(0))))
            for attrname, row in sf.attrdiff.iterrows():
                sf.mat_attrdiff.append([attrname])
                for attr in sf.mat_attrdiff[0][1:]:
                    ff = row[attr]["self"]
                    tt = row[attr]["other"]
                    s_msg = ""
                    if ff != tt:
                        s_msg = f"from: \"{ff}\"\nto: \"{tt}\""
                    sf.mat_attrdiff[-1].append(s_msg)
        return True

    def write(sf):
        """Write local dataframe modification on the DOORS module.

        Write permitt are necessary.

        Warning:
            Be careful using this function, you will directly modify data in
            DOORS module, no ctrl-z like management is already implemented.

        Returns:
            bool: false if it is not possible to open the module in write mode
        """
        # We consider that no modification at the attribute of wcd is done
        n_ma = len(L_MAN_ATTR) + len(L_DEFAULT_ATTR_RO)
        l_attr_to_cmp = sf.wcd.columns[n_ma:]
        if sf.__data[l_attr_to_cmp].equals(sf.wcd[l_attr_to_cmp]):
            return True

        # Find data modification and apply to DOORS

        ###########################################################
        # Modification Management

        #####################################
        # Changed data preparation
        sf.compare()  # the diff dataframe is saved in sf.diff

        # Upload difference
        d_changes = {}
        if not sf.open(sf.name, "w"):
            return False
        sf.mod = sf.name

        #####################################
        # new object preparation
        l_new_obj_absno = [x for x in sf.wcd.index if x not in sf.__data.index]
        pd_new = sf.wcd.loc[l_new_obj_absno]

        ##########################################################
        # Apply data changes and new object creation
        try:
            ######################
            # Data changes
            if hasattr(sf, "diff"):
                for absno, row in sf.diff.iterrows():
                    # get data for row management
                    # row_man = sf.wcd.loc[absno][L_MAN_ATTR]
                    # drop nan value
                    drow = row.dropna()
                    for attr in list(set(drow.keys().get_level_values(0))):
                        # other get the value in the working copy.
                        d_changes[attr] = row[attr]["other"]
                    # ic(d_changes)
                    d_changes.pop("Object Level", None)
                    sf.set_obj_attr_values(absno, d_changes)
                    d_changes.clear()

            ######################
            # New object Creation
            for absno, row in pd_new.iterrows():
                # TODO further checks
                cmd = pd_new.loc[absno, "__cmd"]
                if "new" in cmd:
                    d_data = dict(row)
                    d_data.pop("__cmd", None)
                    # new object after/below and existing one
                    if len(cmd.split(":")) == 3:
                        wt, position, fth_absno = cmd.split(":")
                        new_absno = sf.new_obj(below_after=position,
                                               absno=fth_absno)
                        d_data.pop("Object Level", None)
                        sf.set_obj_attr_values(new_absno, d_data)
                    # new object at level 1
                    elif cmd == "new:last" or cmd == "new:first":
                        new_absno = sf.new_obj(where=cmd.split(":")[1])
                        d_data.pop("Object Level", None)
                        sf.set_obj_attr_values(new_absno, d_data)
                    else:
                        raise ImplementationError()
                    if str(new_absno) != str(absno):
                        # Update local absno in the working copy
                        # All absno in commands are replaced also
                        # the commands which refers to the new absno.
                        old_index = sf.wcd.index.name
                        i = list(sf.wcd.index).index(absno)
                        sf.wcd = sf.wcd.reset_index()
                        sf.wcd.loc[i, old_index] = new_absno
                        sf.wcd = sf.wcd.set_index(old_index)
                        cmds = ["new:below:" + str(absno),
                                "new:after:" + str(absno)]
                        to_cmds = ["new:below:" + str(new_absno),
                                   "new:after:" + str(new_absno)]
                        sf.wcd = sf.wcd.replace(cmds, to_cmds)
            #######################
            # New column creation
            if hasattr(sf, "attrdiff"):
                # The following is the list of new attributes
                # which has data in wcd (because there is the case)
                # in which you want simply to add a new attribute.
                l_new_attr_with_data = []
                for attr, row in sf.attrdiff.iterrows():
                    sf.def_attr(attr,
                                row["typename"],
                                row["basetype"],
                                row["l_enum"],
                                row["multi"],
                                row["default"])
                    if attr in sf.wcd.columns:
                        l_new_attr_with_data.append(attr)
                for absno, row in sf.wcd.iterrows():
                    pass  # TODO

        except AttributeError:
            pass
        finally:
            sf.close()

        return True

    def clean(sf):
        """Clear all data of the object

        Returns:
            bool: True if succeed
        """
        pass

    @property
    def name(sf):
        return sf.__name

    @name.setter
    def name(sf, newname):
        if newname != sf.name:
            sf.clean()
            sf.__init__(newname)

    @property
    def status(sf):  # only read property
        """Get the current status of module.

        It can be write/read/closed
        """
        return sf.__status

    def newattr(sf,
                name: str,
                typename: str,
                basename=None,
                l_enum=None,
                multi=False,
                default=""):
        """Create a new attribute in the working copy..

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
            bool: True if the new attribute is succesfull added.
        """
        if typename not in dxl.L_POSSIBLE_TYPENAMES:
            if basename is None:
                return False
            if basename == "Enumeration":
                if l_enum is None:
                    return False
                    "type", "basetype", "l_enum", "multi", "default"
        df = pd.DataFrame({name: [typename, basename, l_enum, multi, default]},
                          columns=["type", "basetype", "l_enum", "multi",
                          "default"],
                          orient="index")
        sf.wc_attrdef = sf.wc_attrdef.append(df)

    def insert(sf, data: dict, position="after", where="last", absno=None):
        """Insert a row in the working copy dataframe (new doors object)

        The new row will be filled with data in "data" dict

        Note:
            Don't define *"Absolute Number"* and *"Object Level"* in the
            data dict, they are automatically internally defined.

        Warning:
            The new object will have a new *Absolute Number" autogenerated
            considering the downloaded object. Anyway if the user create new
            object in DOORS and then delete it the absolute number generated
            by the python code will be different of the real absno when the
            object will be written in DOORS.

            Example

                -   Manually Open an exisiting module and create a new object,\
                        suppose that the new absno is 100
                -   Delete the absno just created.
                -   Create a new doormod object and read the module with\
                    doorsmod
                -   Create a new object locally, the new absno will be 100
                -   Now when you call the write function Python will create\
                        the new object but its **absolute number** in DOORS\
                        will be **101** !!
                -   The write function will update the absolute number in the\
                        working copy. So after write call you will have the\
                        correct absolute number in the wc.

        Args:
            data (dict): it must contain the data to write in the new
                object.
            absno (int/str): absolute number of the object below/after which
                create the new object.
            position (*after*/*below*): define if the new object must
                be after or below the *absno* object. **below** means that the
                new object is a child of *absno* object, instead **after**
                means that it is at the same level.
            where (*last*/*first*): where place the new object

        Returns:
            int: absolute number of the new object
        """

        if absno is None:
            if len(sf.wcd.index) > 0:
                new_absno = pd.to_numeric(sf.wcd.index).max()\
                    + 1
            else:
                new_absno = 0
            data["Absolute Number"] = str(new_absno)
            data["__cmd"] = "new:" + where
            ic(data)
            pdnew = pd.DataFrame(data, index=[0])
            pdnew = pdnew.set_index("Absolute Number")
            sf.wcd = sf.wcd.append(pdnew)
        else:
            absno = str(absno)
            old_index = sf.wcd.index.name
            i = str(sf.wcd.index.get_loc(absno) + 1)
            lev = sf.wcd.loc[absno, "Object Level"]
            sf.wcd = sf.wcd.reset_index()
            # Find the new absno
            new_absno = str(pd.to_numeric(sf.wcd["Absolute Number"]).max() + 1)

            # Starting value of upper half
            start_upper = 0
            # End value of upper half
            end_upper = int(i)
            # Start value of lower half
            start_lower = int(i)
            # End value of lower half
            end_lower = sf.wcd.shape[0]
            # Create a list of upper_half index
            upper_half = [*range(start_upper, end_upper, 1)]
            # Create a list of lower_half index
            lower_half = [*range(start_lower, end_lower, 1)]
            # Increment the value of lower half by 1
            lower_half = [x.__add__(1) for x in lower_half]
            # Combine the two lists
            index_ = upper_half + lower_half
            # Update the index of the dataframe
            sf.wcd.index = index_

            # Insert a row at the end
            for key, val in data.items():
                if key in sf.wcd.columns:
                    sf.wcd.loc[i, key] = val
                else:
                    return False
            if position == "after":
                sf.wcd.loc[i, "Object Level"] = lev
            elif position == "below":
                sf.wcd.loc[i, "Object Level"] = lev + 1

            sf.wcd.loc[i, "Absolute Number"] = new_absno
            sf.wcd.loc[i, "__cmd"] = "new:" + position + ":" + absno

            # Sort the index labels
            sf.wcd = sf.wcd.sort_index()
            sf.wcd = sf.wcd.set_index(old_index)

        # return the dataframe
        return new_absno

    ###################################################################
    # Internal function in which will be done the upgrade
