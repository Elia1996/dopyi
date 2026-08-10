"""Requirement Interface
"""
from abc import ABC, abstractmethod
from typing import List
from pydantic import BaseModel
import polars as pl
from enum import Enum

class ExtLink(BaseModel):
    """External Link
    """
    url: str
    description: str


class Req(ABC):
    """Class representing a requirement or a test
    """
    @abstractmethod
    def __init__(self, module: "ReqModule", id: str) -> None:
        pass

    ############################################################
    # mandatory attributes
    @property
    @abstractmethod
    def module(self) -> "ReqModule":
        """Returns the module of the requirement
        """
        pass

    @property
    @abstractmethod
    def id(self) -> str:
        """Returns the id of the requirement
        """
        pass

    @property
    @abstractmethod
    def url(self) -> str:
        """Returns the url of the requirement
        """
        pass

    @property
    @abstractmethod
    def data(self) -> dict:
        """Returns the data of the requirement in the form of a dictionary
        """
        pass

    @abstractmethod
    def __getitem__(self, key: str) -> str:
        """Returns the value of the key of the requirement from the data,
        it is the same as req.data[key]
        """
        pass

    @abstractmethod
    def __setitem__(self, key: str, value: str) -> None:
        """Sets the value of the key of the requirement from the data,
        it is the same as req.data[key] = value
        """
        pass

    ############################################################
    # Links getter/setter
    @property
    @abstractmethod
    def inlinks(self) -> List["Req"]:
        """Returns the inlinks of the requirement, they shall be
        objects of type Req
        """
        pass

    @property
    @abstractmethod
    def outlinks(self) -> List["Req"]:
        """Returns the outlinks of the requirement, they shall be
        objects of type Req
        """
        pass

    @outlinks.setter
    @abstractmethod
    def outlinks(self, value: List["Req"]) -> None:
        """Sets the outlinks of the requirement
        """
        pass

    @property
    @abstractmethod
    def extlinks(self) -> List[ExtLink]:
        """Returns the external links of the requirement
        """
        pass

    @extlinks.setter
    @abstractmethod
    def extlinks(self, value: List[ExtLink]) -> None:
        """Sets the external links of the requirement
        """
        pass


class ReqModule(ABC):
    """Requirement Interface

    If you want to implement a requirement interface you shall
    inherit from this class and implement the methods below.

    !!! note
    You should also implement the Req class.

    !!! note
    To correctly implement the ReqModule you should maintain a
    local copy of the requirements in order to be able to do the
    comparison between the local copy and the source. and upload
    the differences to the source.
    """
    ############################################################
    # Creation methods
    @abstractmethod
    def __init__(self, name: str) -> None:
        """Initializes the object from the name, the name shall
        be unique and include the version of the module in some way.
        """
        pass

    @classmethod
    @abstractmethod
    def versions(self, name_no_version: str) -> List[str]:
        """Returns the available versions of the module in the server
        for the name without the version.
        From this output the user can choose the version to and use that
        identifier to create the module ReqNodule(name)
        """
        pass

    @abstractmethod
    def load(self) -> bool:
        """Loads the requirements from the source or from the local
        copy if available.
        """
        pass

    @abstractmethod
    def upload(self) -> bool:
        """Writes the differences of the working copy with the
        source in the source.
        """
        pass

    @abstractmethod
    def copy_obj(self) -> "ReqModule":
        """Copies the module
        """
        pass

    ############################################################
    # Dunder methods
    @abstractmethod
    def __iter__(self) -> Req:
        """Iterates over the requirements
        """
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Returns the number of requirements
        """
        pass

    @abstractmethod
    def __getitem__(self, id: str) -> Req:
        """Returns the requirement with the given id
        """
        pass

    ############################################################
    # Properties
    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the name of the module, the name shall include also the
        version of the module
        """
        pass

    @property
    @abstractmethod
    def url(self) -> str:
        """Returns the url of the module
        """
        pass

    @property
    @abstractmethod
    def reqs(self) -> List[Req]:
        """Returns the list of requirements
        """
        pass

    @property
    @abstractmethod
    def columns(self) -> List[str]:
        """Returns the columns of the requirements excluding the links
        and the id column.
        """
        pass

    ############################################################
    # Conversion methods

    @property
    @abstractmethod
    def df_polars(self) -> "pl.DataFrame":
        """Returns the requirements in a polars dataframe, it shall
        contain also the links
        """
        pass

    @classmethod
    @abstractmethod
    def from_polars(cls, df) -> "ReqModule":
        """Creates a module from a polars dataframe
        """
        pass