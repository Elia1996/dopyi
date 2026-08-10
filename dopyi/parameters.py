#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parameters management for all the project

Here are defined the class used to manage the parameters of the project

Created on 2023-10-19 by Elia Ribaldone
"""
# Standard library imports
import logging
from ast import literal_eval
from pathlib import Path
from typing import Any, Optional
from re import match
from pandas import DataFrame
from dataclasses import dataclass
from enum import Enum
import json
from numpy import ndarray

# Third party imports
from pint import UnitRegistry

ureg = UnitRegistry()
ureg.default_format = '~.3fP'
Q_ = ureg.Quantity

# Current Package imports


##############################################################################

# Constants Path Definitions

#######################################
# Constants Filename Definitions

#######################################
# Constants String Definitions

STRING_UNIT = r"[sS]tring"
ADIMENSIONAL_UNIT = r"[aA]dimensional"
DICT_UNIT = r"[dD]ict|[dD]ictionary"
ENUM_UNIT = r"[eE]num"
BOOL_UNIT = r"[bB]ool|[bB]oolean"

UNIT_ERROR = "Unit \"{0}\" not recognized, must be one of: "\
    f"{STRING_UNIT}, "\
    f"{ADIMENSIONAL_UNIT}, {DICT_UNIT}, {ENUM_UNIT}, or a pint unit "\
    f"(https://github.com/hgrecco/pint/blob/master/pint/default_en.txt)"

DICT_VALUE_ERROR = "Value \"{0}\" not recognized, must be a dictionary if "\
    f"unit is {DICT_UNIT}"

ENUM_VALUE_ERROR = "Value \"{0}\" not recognized, must be a dictionary if "\
    f"unit is {ENUM_UNIT}"

VALUE_ERROR = "Value \"{0}\" not recognized, must be a number or a list of "\
    f"numbers if unit is no one of these units: {STRING_UNIT}, "\
    f"{ADIMENSIONAL_UNIT}, {DICT_UNIT}, or {ENUM_UNIT}"

ADIMENSIONAL_VALUE_ERROR = "Value \"{0}\" not recognized, must be a "\
    "number or a list of numbers if unit is [aA]dimensional"

BOOL_VALUE_ERROR = "Value \"{0}\" not recognized, must be a "\
    "boolean if unit is [bB]ool|[bB]oolean, ('False' or 'True')"

#######################################
# Constants List Definitions

#######################################
# Constants Dictionary Definitions

#######################################
# Other Constants Definitions

# Create the logger
name = __name__.split('.')[0]
logger = logging.getLogger(name)
logger.setLevel(logging.DEBUG)

flog = Path('.log') / f'{name}.log'
if not flog.parent.exists():
    flog.parent.mkdir()

if not flog.exists():
    flog.touch()

fh = logging.FileHandler(f'.log/{name}.log')
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

##############################################################################
# Support Functions

##############################################################################
# Main Functions


##############################################################################
# Classes


class BaseParamUnitError(Exception):
    """Base class for exceptions in this module."""
    def __init__(self, unit, message=UNIT_ERROR):
        self.unit = unit
        self.message = message.format(unit)
        super().__init__(self.message)


class BaseParamQuantityValueError(Exception):
    """Base class for exceptions in this module."""
    def __init__(self, value, message=VALUE_ERROR):
        self.value = value
        self.message = message.format(value)
        super().__init__(self.message)


class BaseParamDictValueError(Exception):
    """Base class for exceptions in this module."""
    def __init__(self, value, message=DICT_VALUE_ERROR):
        self.value = value
        self.message = message.format(value)
        super().__init__(self.message)


class BaseParamEnumValueError(Exception):
    """Base class for exceptions in this module."""
    def __init__(self, value, message=ENUM_VALUE_ERROR):
        self.value = value
        self.message = message.format(value)
        super().__init__(self.message)


class BaseParamAdimensionalValueError(Exception):
    """Base class for exceptions in this module."""
    def __init__(self, value, message=ADIMENSIONAL_VALUE_ERROR):
        self.value = value
        self.message = message.format(value)
        super().__init__(self.message)


class BaseParamBoolValueError(Exception):
    """Base class for exceptions in this module."""
    def __init__(self, value, message=BOOL_VALUE_ERROR):
        self.value = value
        self.message = message.format(value)
        super().__init__(self.message)


def dumps_json(self, *args, **kwargs):
    """Dumps the object in json format"""
    return json.dumps(to_dict(self), *args, **kwargs)


def to_dict(self):
    """Return a dictionary with the object attributes"""
    if self.unit == "quantity":
        value = self.magnitude
        if type(value) is ndarray:
            value = list(value)
        return {"name": self.name, "value": str(value),
                "unit": format(self.units, "~P"),
                "descr": self.descr, "id": self.id}
    return {"name": self.name, "value": self.value,
            "unit": self.unit, "descr": self.descr,
            "id": self.id}


@dataclass(frozen=True)
class BaseParam():
    name: str
    value: Any
    unit: str
    descr: Optional[str] = ""
    id: Optional[str] = ""

    @classmethod
    def from_raw(cls, name, value, unit, descr="", id=""):
        """Create a BaseParam from raw data"""
        value, unit = cls.value_conversion(value, unit)
        if unit == "quantity":
            value.unit = "quantity"
            value.value = value.magnitude
            value.name = name
            value.descr = descr
            value.id = id
            return value
        return cls(name, value, unit, descr, id)

    @classmethod
    def from_dict(cls, d):
        """Create a BaseParam from a dictionary"""
        return cls.from_raw(d["name"], d["value"], d["unit"],
                            descr="" if "descr" not in d else d["descr"],
                            id="" if "id" not in d else d["id"])

    def dumps_json(self, *args, **kwargs):
        """Dump the object in json format"""
        return dumps_json(self, *args, **kwargs)

    def dump_json(self, outfile, indent=1):
        """Dump the object in json format in a file"""
        with open(outfile, "w") as f:
            json.dump(self.dumps_json(), f, indent=indent)

    def to_dict(self):
        """Return a dictionary with the object attributes"""
        return to_dict(self)

    def freeze_setattr(self, name, value):
        """Freeze the object"""
        raise Exception("Cannot set attribute")

    @classmethod
    def from_json(cls, json_str):
        """Create a BaseParam from a json string"""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def value_conversion(cls, value, unit):
        """Get correct class for the value"""
        setattr(ureg.Quantity, "dumps_json", dumps_json)
        setattr(ureg.Quantity, "to_dict", to_dict)
        if match(STRING_UNIT, unit):
            # String
            return str(value), unit.lower()
        elif match(BOOL_UNIT, unit):
            # Bool
            try:
                ret = eval(value)
            except:
                raise BaseParamBoolValueError(value)
            if type(ret) is not bool:
                raise BaseParamBoolValueError(value)
            return ret, unit.lower()
        elif match(ADIMENSIONAL_UNIT, unit):
            # Adimensional
            try:
                ret = eval(value)
            except:
                raise BaseParamAdimensionalValueError(value)
            val = ureg.Quantity(val, "dimensionless")
            # Int, float, Lists
            return val, "quantity"
        elif (is_enumunit := match(ENUM_UNIT, unit)) or match(DICT_UNIT, unit):
            try:
                d_vals = eval(value)
            except:
                if is_enumunit:
                    raise BaseParamEnumValueError(value)
                else:
                    raise BaseParamDictValueError(value)
            if type(d_vals) is not dict:
                if is_enumunit:
                    raise BaseParamEnumValueError(value)
                else:
                    raise BaseParamDictValueError(value)
            if is_enumunit:
                e_vals = Enum("BaseParamEnum", d_vals)
                # Enum
                return e_vals, unit.lower()
            # Dict
            return d_vals, unit.lower()
        else:
            # Try evaluate pint unit
            try:
                if "Ohm" in unit:
                    unit = unit.replace("Ohm", "ohm")
                ureg(unit)
            except:
                raise BaseParamUnitError(unit)
            # Verify that the value is a number
            try:
                val = eval(str(value))
            except:
                raise BaseParamQuantityValueError(value)
            else:
                if type(val) is list or type(val) is int or type(val) is float\
                        or type(val) is complex:
                    val = ureg.Quantity(val, unit)
                    # Int, float, Lists
                    return val, "quantity"
                else:
                    raise BaseParamQuantityValueError(value)


class ParamDuplicateError(Exception):
    """Raised when the parameter is already defined"""
    pass


class ParamCreationError(Exception):
    """Raised when user try to create a parameter even if it is not allowed"""
    pass


class BaseParamCollection():
    """Class to collect a set of BaseParam object

    The class is used to collect a set of BaseParam objects and to manage them
    as a single object. It is possible to add a new parameter to the collection
    using the add_param method. The class is also able to create a collection
    from a dataframe or from a json file

    Methods:
        from_df (method): method to create a collection from a dataframe
        to_df (method): method to create a dataframe from the collection
        dumps_json (method): method to dump the collection in json format
        dump_json (method): method to dump the collection in json format in a
            file
        to_dict (method): method to return a dictionary with the collection
            attributes

    Examples:
        Basic use: creation from a dataframe and use:

            >>> from latote.core.parameters import BaseParamCollection
            >>> import pandas as pd
            >>> bc = BaseParamCollection()
            >>> df = pd.DataFrame([["name1", 1, "m", "descr1", "id1"],
            ...                    ["name2", 2, "mm", "descr2", "id2"]],
            ...                   columns=["name", "value", "unit", "descr",
            ...                            "id"])
            >>> bl_res, df_err, df_log = bc.from_df(df)
            >>> bc.name1
            <Quantity(1, 'meter')>
            >>> bc.name2
            <Quantity(2, 'millimeter')>
            >>> bc.name1.to("cm")
            <Quantity(100.0, 'centimeter')>

        This instead is an example which use parameters from a dataframe
        exported from DOORS using dopyi:

            >>> from latote.core.parameters import BaseParamCollection, Q_
            >>> import pandas as pd
            >>> bc = BaseParamCollection()
            >>> df = pd.DataFrame(
            ...     [["P_DC_ULV_Nominal", 14, "V", "", "10"],
            ...      ["P_DC_UHV_NominalMin", 7, "V", "", "11"],
            ...      ["P_DC_UHV_LVRangeMin", [6, 10], "V", "", "12"],
            ...      ["P_DC_ULV_OvershootDynLd", 500, "V/s", "", "13"],
            ...      ["P_DC_SLRATE_LVDynLd", 0.9, "A/ms", "", "14"],
            ...      ["P_DC_CAP_HVBasic", 100, "uF", "", "15"]],
            ...     columns=["Object Text", "Value", "Unit", "Description",
            ...              "Absolute Number"])
            >>> rt = bc.from_df(df, d_map={"name": "Object Text",
            ...                            "value": "Value",
            ...                            "unit": "Unit",
            ...                            "descr": "Description",
            ...                            "id": "Absolute Number"})
            >>> bl_res, df_err, df_log = rt
            >>> bc.P_DC_ULV_Nominal
            <Quantity(14, 'volt')>
            >>> bc.P_DC_UHV_NominalMin
            <Quantity(7, 'volt')>
            >>> bc.P_DC_UHV_LVRangeMin.to("mV")
            <Quantity([ 6000. 10000.], 'millivolt')>
            >>> bc.P_DC_ULV_OvershootDynLd.to("V/s")
            <Quantity(500, 'volt / second')>
            >>> bc.P_DC_SLRATE_LVDynLd * 2 + Q_(1, "A/ms")
            <Quantity(2.8, 'ampere / millisecond')>
            >>> print(bc.P_DC_CAP_HVBasic)
            100.000 µF
            >>> format(bc.P_DC_CAP_HVBasic, "~.1fP")
            '100.0 µF'
    """
    _enable_setattr = False

    def __init__(self, name=""):
        """Create a BaseParamCollection object

        Args:
            name (str, optional): Name of the collection. Defaults to "".
        """
        self._enable_setattr = True
        self._name = name
        self._enable_setattr = False

    @property
    def name(self):
        """Return the name of the collection"""
        return self._name

    def from_df(self, df: DataFrame, d_map=None, ignore_empty=True):
        """Convert each line of the df in a BaseParam object addin to the attr

        Args:
            df (DataFrame): Dataframe with a parameter per line
            d_map (_type_, optional): mapping between the dataframe attribute
                (values) and the name of baseparam. These are the attributes
                that should be in the keys:

                    - name: name of the parameter
                    - value: value of the parameter
                    - unit: unit of the parameter
                    - descr: description of the parameter
                    - id: id of the parameter (DOORS/PTC id)

                The default mapping will remain for the attributes not
                specified.
                Defaults to None.

        Returns:
            bool: True if the conversion is successful, False otherwise
            DataFrame: Dataframe with the list of the parameters that are not
                converted
        """
        d_map_default = {"name": "name", "value": "value", "unit": "unit",
                         "descr": "descr", "id": "id"}
        if d_map is not None:
            d_map_default.update(d_map)
        d_map = d_map_default
        df = df.reset_index()
        l_error = {"name": [], "id": [], "Error Type": [],
                   "Error Log": []}
        d_conversion = {"name": [], "id": [],
                        "Original Value": [],
                        "Value": [],
                        "Original Unit": [],
                        "Unit": []}

        bl_res = True

        for _, row in df.iterrows():
            try:
                d_mapped = {k: row[v] for k, v in d_map.items()}
                if not ignore_empty or d_mapped["name"] != "":
                    self.add_param(**d_mapped)
                    unit = getattr(self, d_mapped["name"]).unit
                    if unit == "quantity":
                        value = getattr(self, d_mapped["name"]).magnitude
                        unit = getattr(self, d_mapped["name"]).units
                    else:
                        value = getattr(self, d_mapped["name"]).value
                    logger.debug(f'Parameter "{d_mapped["name"]}" added with '
                                 f'value {value} {unit}')
            except ParamDuplicateError or ParamCreationError as e:
                logger.error(f'Parameter "{row[d_map["name"]]}" is already '
                             f'defined in the collection, skipping it')
                l_error["name"].append(row[d_map["name"]])
                l_error["Error Log"].append(e)
                if d_map["id"] in df.columns:
                    l_error["id"].append(row[d_map["id"]])
                l_error["Error Type"].append(type(e).__name__)
                bl_res = False
            except Exception as e:
                logger.error(f'Parameter "{row[d_map["name"]]}" is not valid, '
                             f'skipping it')
                l_error["name"].append(row[d_map["name"]])
                l_error["Error Log"].append(e)
                l_error["Error Type"].append(type(e).__name__)
                if d_map["id"] in df.columns:
                    l_error["id"].append(row[d_map["id"]])
                bl_res = False
            else:
                if not ignore_empty or d_mapped["name"] != "":
                    d_conversion["name"].append(row[d_map["name"]])
                    if d_map["id"] in df.columns:
                        d_conversion["id"].\
                            append(row[d_map["id"]])
                    d_conversion["Value"].append(value)
                    d_conversion["Original Value"].append(row[d_map["value"]])
                    d_conversion["Unit"].append(unit)
                    d_conversion["Original Unit"].append(row[d_map["unit"]])

        df_err = DataFrame(columns=l_error.keys(),
                           data=l_error)
        df_log = DataFrame(columns=d_conversion.keys(),
                           data=d_conversion)
        df_err.set_index("name", inplace=True)
        df_log.set_index("name", inplace=True)

        return bl_res, df_err, df_log

    def to_df(self, columns: dict = None):
        """Return a dataframe with the list of the parameters"""
        df = DataFrame([getattr(self, k).to_dict()
                        for k in self.__dict__ if not k.startswith("_")]).\
            set_index("name")
        if columns is not None:
            df.rename(columns=columns, inplace=True)
        return df

    def add_param(self, name, value, unit, descr="", id=""):
        """Add a parameter to the collection

        Args:
            name (str): Name of the parameter
            value (Any): Value of the parameter
            unit (str): Unit of the parameter
            descr (str, optional): Description of the parameter.
                Defaults to "".
            id (str, optional): ID of the parameter. Defaults to "".
        """
        if hasattr(self, name):
            raise ParamDuplicateError(
                f'Parameter "{name}" already exists in the collection, '
                f'please avoid name duplication')
        self._enable_setattr = True
        setattr(self, name, BaseParam.
                from_raw(name=str(name), value=str(value),
                         unit=str(unit), descr=str(descr),
                         id=str(id)))
        self._enable_setattr = False

    def dumps_json(self, *args, **kwargs):
        """Dump the object in json format"""
        return json.dumps(self.to_dict(), *args, **kwargs)

    def dump_json(self, fp_outfile, indent=1):
        """Dump the object in json format in a file"""
        json.dump(self.to_dict(), fp_outfile, indent=indent)

    def to_dict(self):
        """Return a dictionary with the object attributes"""
        return {getattr(self, k).name: getattr(self, k).to_dict()
                for k in self.__dict__ if not k.startswith("_")}

    def __setattr__(self, name, value):
        """Set attribute to the class only if it is enabled"""
        if name == "_enable_setattr" or self._enable_setattr:
            super().__setattr__(name, value)
        else:
            raise ParamCreationError("While trying to create a new attribute "
                                     f" with name {name} and value {value}, "
                                     " avoid to create new attributes!")


class BaseParamMultiCollection():
    """Class to collect a set of BaseParamCollection objects

    The class is used to collect a set of BaseParamCollection objects and to
    manage them as a single object.

    """
    def from_df(self, df: DataFrame, l_value_cols: list[str],
                d_map: dict = None, ignore_empty=True):
        """Convert each value column of the df in a BaseParamCollection object

        Args:
            df (DataFrame): Dataframe with a parameter per line, it shall
                have these mandatory columns:

                    - A name column with the name of the parameter
                    - A unit column with the unit of the parameter
                    - A descr column with the description of the parameter
                    - A id column with the id of the parameter, it is
                        optional and can be the Absolute Number of DOORS
                        export for example.
                    - At least one column with the values of the parameters
                        the name of the column to use as value shall be
                        specified in the l_value_cols argument.
            l_value_cols (list[str]): list of the columns with the values
            d_map (dict, optional): mapping between the dataframe attribute
                and the name of baseparam. These are the attributes
                that should be in the keys:

                    - name: name of the parameter
                    - unit: unit of the parameter
                    - descr: description of the parameter
                    - id: id of the parameter (DOORS/PTC id)
                The default mapping will remain for the attributes not
                specified.
                An example of mapping is:
                    {"name": "Object Text",
                     "unit": "Unit", "descr": "Description",
                     "id": "Absolute Number"}
                Defaults to None.
        """
        ####################################################################
        # Map Update
        d_map_default = {"name": "name", "value": "value", "unit": "unit",
                         "descr": "descr", "id": "id"}
        if d_map is not None:
            for key in d_map.keys():
                if d_map[key] not in df.columns:
                    raise Exception(f"Column {d_map[key]} not found in the "
                                    "dataframe")
                if key not in d_map_default.keys():
                    raise Exception(f"Key {key} not recognized, must be one "
                                    "of: name, unit, descr, id")
            d_map_default.update(d_map)

        d_map = d_map_default
        ####################################################################
        # Columns Check
        l_colname = l_value_cols.copy()
        for col in l_value_cols:
            if col not in df.columns:
                raise Exception(f"Column {col} not found in the dataframe")
            if " " in col:
                raise Exception(f"Column {col} cannot contain spaces")
            if "." in col:
                logger.warning(f"Column {col} contains dots, this can cause "
                               "problems with the attribute creation")
                l_colname[l_value_cols.index(col)] = col.replace(".", "_")
            if "-" in col:
                raise Exception(f"Column {col} cannot contain dashes")

        ####################################################################
        # Create the collections
        bl_res_all = True
        for col, colname in zip(l_value_cols, l_colname):
            d_map["value"] = col
            bc = BaseParamCollection(colname)
            bl_res, df_err, df_log = bc.from_df(df, d_map=d_map,
                                                ignore_empty=ignore_empty)
            setattr(self, colname, bc)
            bl_res_all = bl_res_all and bl_res

        return bl_res_all, df_err, df_log

    def __getitem__(self, key):
        """Return the attribute of the collection"""
        return getattr(self, key)

    def to_df(self):
        """Return a dataframe with the list of the parameters"""
        # Create a list with a dataframe for each collection
        l_var = [k for k in self.__dict__ if not k.startswith("_")]
        l_df = [getattr(self, k).to_df({"value": k}) for k in l_var]
        # Merge the list of dataframe
        df = l_df[0]
        for df2, variant in zip(l_df[1:], l_var[1:]):
            df = df.merge(df2[variant], how="outer", left_index=True,
                          right_index=True)
            # Check that the units are the same
        return df

##############################################################################
# Main


if __name__ == '__main__':
    pass
