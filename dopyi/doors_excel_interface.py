from multiprocessing import Pipe, Process
from pathlib import Path
import pandas as pd
import FreeSimpleGUI as sg
import time
from dopyi.doorsmod import doorsmod
from dopyi.doorserver.server import show_prompt
from dopyi.dxl import dxl
from dopyi.doorserver.server import run as run_server
from dopyi.parameters import BaseParamCollection
import os

dexter = dxl()

S_PATH = os.path.dirname(os.path.abspath(__file__))
PORT = 5098
S_LOGO = Path(S_PATH, "logo", "dopyi.ico").resolve().absolute()
VERBOSE = False


def myprin(*args):
    if VERBOSE:
        print(*args)


myprin(S_LOGO)

SHOW_PROMPT_DEFAULT = True
DOWN_SHEET_NAME_DEFAULT = "Sheet1"
UP_SHEET_NAME_DEFAULT = "Sheet1"
DEF_MODULE = "/xxx_SYS_TestsProject/TestDoorsmod3"
COMPARE_FILE_DEFAULT = "Compare.xlsx"

show_prompt(SHOW_PROMPT_DEFAULT)


dsm_glob = None
force_download = True
f_down_excel = None
f_up_excel = None
down_sheet_name = DOWN_SHEET_NAME_DEFAULT
force_download_in_upload = True
module = None
up_sheet_name = UP_SHEET_NAME_DEFAULT
f_compare = COMPARE_FILE_DEFAULT


# Create the process where to run the download and upload
def server_dsm(conn):
    try:
        run_server(n_port=PORT)
    except Exception as e:
        myprin(e)
        myprin("Server don't start")
        conn.send("stop")
        return
    conn.send("Alive")
    while True:
        received = conn.recv()
        if received == "download":
            module = conn.recv()
            force = eval(str(conn.recv()))
            dsm_glob = doorsmod(module, port=PORT)
            try:
                dsm_glob.read(force, conn)
            except Exception as e:
                conn.send({"perc": 0, "msg": f"Error in the download!! {e}"})
        elif received == "write":
            module = conn.recv()
            excel_name = conn.recv()
            up_sheet_name = conn.recv()
            f_compare = conn.recv()
            conn.send({"perc": 0, "msg": "Reading the module"})
            dsm_glob = doorsmod(module, port=PORT)
            dsm_glob.read()
            conn.send({"perc": 1, "msg": "Reading the excel"})
            dsm_glob.wcd = pd.read_excel(excel_name, index_col=0,
                                         sheet_name=up_sheet_name)
            conn.send({"perc": 2, "msg": "Compare and writing the module..."})
            try:
                dsm_glob.write(f_compare, conn)
            except Exception as e:
                conn.send({"perc": 0, "msg": f"Error in the writing!! {e}"})
        elif received == "showterminal":
            show_prompt(True)
        elif received == "hideterminal":
            show_prompt(False)
        elif received == "open_excel":
            filename = Path(conn.recv())
            try:
                os.system(f"cd \"{filename.parent}\" && start {filename.name}")
            except Exception as e:
                myprin(e)
        elif received == "stop":
            break
        elif received == "exist":
            module = conn.recv()
            dsm = doorsmod(module, port=PORT)
            conn.send(dsm.mod_exists(module))
    conn.close()


S_PARAMETER_HELP = """The parameter module shall contain the following columns:
- Unit: the unit of the parameter, the name can be different but the content shall
    be the unit of the parameter. These are the allowed units:
    - String: the parameter value shall be  a string
    - Dictionary: the parameter value shall be a dictionary like {"key": "value", "key2": "value2"}
    - Adimensional: the parameter value has no dimension, like the number of
        cuncurrent process in a processor or the number of cores in a uc.
    - Enum: the parameter value shall be like a dictionary, the difference respect to the
        dictionary is that you cannot have nested dictionary and the value will be
        converted in a Enum in python.
    - Standard Unit: the other possible units are the usual physical units like m, kg, s, A,
        K, mol, cd, rad, sr, Hz, N, Pa, J, W, C, V, F, Ohm, you can also use the prefix like
        m, u, n, p, f etc. It is also possible to have division like m/s, V/us, etc. The unit
        are parsed using the pint library, at this link you can find the list of all the
        units https://github.com/hgrecco/pint/blob/master/pint/default_en.txt .
- Description: the description of the parameter, it is not mandatory but it is suggested.
- Name: the name of the parameter, usually the Object Text in DOORS
- Value: the value of the parameter, in DOORS there must be a column for each variant with
    the relative name.
"""


def gui():
    global show_dxl
    global pconn
    global dsm_glob
    global force_download
    global f_down_excel
    global f_up_excel
    global down_sheet_name
    global force_download_in_upload
    global module
    global up_sheet_name
    global f_compare

    par_attributes = []

    sg.theme("Reddit")  # Add a touch of color

    layout_excel = [
        [sg.Text("Excel side", font='bold 18')],
        [],
        [sg.Frame("Downloading from DOORS", layout=[
            [sg.Text("Select an Excel file in which download "
                     "the DOORS module")],
            [sg.In(size=(50, 1), enable_events=True,
                   key="-DOWNLOAD_EXCEL_NAME-"),
             sg.FileBrowse(file_types=(("Excel Files", "*.xlsx"),))],
            [sg.In(size=(50, 1), enable_events=True, key="-DOWN_SHEET_NAME-",
                   default_text=DOWN_SHEET_NAME_DEFAULT)],
            [sg.Text("Download", font='bold'),
             sg.Checkbox("Force Download", key="-FORCE_DOWNLOAD-",
                         default=True,
                         enable_events=True),],
            [sg.ProgressBar(100, orientation='h', size=(32, 20),
                            key='-DOWN_PROG-'),
             sg.Button("Download", key="-BT_DOWNLOAD_FROM_DOORS-")],
            [sg.Text("", key="-DOWN_LOG-", size=(50, 3))],
            ], font='bold 12', expand_x=True)],

        [sg.Frame("Uploading in DOORS", font='bold 12', expand_x=True, layout=[
            [sg.Text("Select the Excel file to upload in DOORS")],
            [sg.In(size=(50, 1), enable_events=True,
                   key="-UPLOAD_EXCEL_NAME-"),
             sg.FileBrowse(file_types=(("Excel Files", "*.xlsx"),))],
            [sg.In(size=(50, 1), enable_events=True, key="-UP_SHEET_NAME-",
                   default_text=UP_SHEET_NAME_DEFAULT)],
            [sg.In(size=(50, 1), enable_events=True,
                   key="-COMPARE_EXCEL_NAME-",
                   default_text=COMPARE_FILE_DEFAULT),
             sg.FileBrowse(file_types=(("Excel File for Compare",
                                        "*.xlsx"),))],
            [sg.Button("Check Delta", key="-BT_DELTA-"),
             sg.Text("An excel will be displayed with the delta")],
            [sg.Text("Upload", font='bold'),
             sg.Checkbox("Force download before upload",
                         key="-FORCE_DOWN_IN_UPLOAD-",
                         default=True,
                         enable_events=True),],
            [sg.ProgressBar(100, orientation='h', size=(32, 20),
                            key='-UP_PROG-'),
             sg.Button("Upload", key="-BT_UPLOAD_IN_DOORS-")],
            [sg.Text("", key="-UP_LOG-", size=(40, 1))],
            ])],
        [sg.Frame("Parameter Module Check", font='bold 12', layout=[
            [sg.Text("Please download the Parameter module from DOORS using "
                     "the normal Download Section, then select the column "
                     "map to check below.", size=(50, 2))],
            [sg.Text("Please Select below the corresponding attribute name"
                     " in the doors module for parameters.", size=(30, 1)),
             sg.Button("Refresh Attributes", key="-REFRESH_ATTR-")],
            [sg.Text("Parameter Name Attribute: ", size=(30, 1)),
             sg.Combo(values=par_attributes, size=(30, 1), key="-PAR_NAME-",
                      enable_events=True)],
            [sg.Text("Parameter Value Attribute: ", size=(20, 1)),
             sg.Combo(values=par_attributes, size=(30, 1), key="-PAR_VAL-",
                      enable_events=True)],
            [sg.Text("Parameter Unit Attribute: ", size=(20, 1)),
                sg.Combo(values=par_attributes, size=(30, 1),
                         key="-PAR_UNIT-", enable_events=True)],
            [sg.Text("Parameter Description Attribute: ", size=(20, 1)),
                sg.Combo(values=par_attributes, size=(30, 1),
                         key="-PAR_DESC-", enable_events=True)],
            [sg.Button("Check", key="-BT_CHECK-")],
            [sg.Text("", key="-CHECK_LOG-", size=(50, 6))],
            ], expand_x=True)],
    ]
    layout_doors = [
        [sg.Text("DOORS side", font='bold 18', )],
        [sg.Frame("Module selection", font='bold 12', expand_x=True, layout=[
            [sg.Checkbox("Show Dxl Terminal", key="-SHOW_DXL-",
                         default=SHOW_PROMPT_DEFAULT, enable_events=True,
                         disabled=True)],
            [sg.Text("Plese write down here the full path of the DOORS"
                     " module, this will be used both for download and "
                     " in the section on the left.", size=(50, 3))],
            [sg.In(size=(50, 1), enable_events=True, key="-MODULE-",
                   default_text=DEF_MODULE)]])],
        # Baseline definition
        [sg.Frame("Baseline definition", font='bold 12', layout=[
            [sg.Text("Baseline Suffix", size=(20, 1)),
             sg.InputText("", size=(20, 1), key="-SUFFIX-")],
            [sg.Text("Baseline Description", size=(20, 1))],
            [sg.Multiline("", size=(50, 5), key="-DESC-")],
            [sg.Checkbox("Major", key="-MAJOR-",
                         default=False)],
            [sg.Text(" ", size=(50, 1), key="-BASELINE_LOG-")]])],
        [],
        [sg.Text("Help", font='bold 15')],
        [sg.Text("Download: download the module from DOORS in the excel file",
                 size=(50, 1))],
        [sg.Text("Upload: upload the excel file in DOORS", size=(50, 1))],
        [sg.Text("Check Delta: compare the excel file with the DOORS module",
                 size=(50, 1))],
        [sg.Text("Force download before upload: force the download of the "
                 "module before upload in doors, it is suggested.",
                 size=(50, 2))],
        [sg.Text("Check carefully the delta before upload, "
                 "look also in the second sheet to see the delta.",
                 size=(50, 2), text_color="blue")],
        [sg.Frame("Parameter Help", layout=[[
            sg.Text(S_PARAMETER_HELP, size=(70, 22), font='bold 8')]],
            expand_x=True)],
    ]

    layout = [
        [sg.Text("Excel - DOORS Exchange", font='bold 20')],
        [
            sg.Column(layout_doors, vertical_alignment="top"),
            sg.Column(layout_excel, vertical_alignment="top"),
        ],
        [
            sg.Text("Disclaimer: this software is provided as is, without any "
                    "warranty, use it at your own risk", font='bold 7')
        ],
    ]

    pconn, cconn = Pipe()
    proc_dsm = Process(target=server_dsm, args=(cconn,),
                       name="DoorsBatchInterface")
    proc_dsm.start()

    window1 = sg.Window('Waiting DOORS connection',
                        layout=[[sg.ProgressBar(max_value=100,
                                                size=(30, 10),
                                                key='bar')]])

    progress = 0
    step = 1

    while pconn.poll(0.05) is False:
        window1.read(timeout=50)
        window1['bar'].update_bar(progress)
        progress += step

        if progress > 100 or progress < 0:
            step *= -1

    rec = pconn.recv()
    if rec != "Alive":
        raise Exception("Error in the server process, received: " + str(rec))
    window1.close()

    # Create the window
    window = sg.Window("Excel - DOORS Exchange", layout, icon=S_LOGO)

    def mod_exists(module):
        pconn.send("exist")
        pconn.send(module)
        return pconn.recv()

    # Create an event loop
    while True:
        event, values = window.read()
        # End program if user closes window or
        # presses the OK button
        myprin(event, values)
        if event == "OK" or event == sg.WIN_CLOSED:
            break
        # Save the input data
        if event == "-FORCE_DOWNLOAD-":
            force_download = values["-FORCE_DOWNLOAD-"]
        if event == "-FORCE_DOWN_IN_UPLOAD-":
            force_download_in_upload = values["-FORCE_DOWN_IN_UPLOAD-"]
        if event == "-DOWNLOAD_EXCEL_NAME-":
            f_down_excel = values["-DOWNLOAD_EXCEL_NAME-"]
        if event == "-DOWN_SHEET_NAME-":
            down_sheet_name = values["-DOWN_SHEET_NAME-"]
        if event == "-UPLOAD_EXCEL_NAME-":
            f_up_excel = values["-UPLOAD_EXCEL_NAME-"]
        if event == "-UP_SHEET_NAME-":
            up_sheet_name = values["-UP_SHEET_NAME-"]
        if event == "-COMPARE_EXCEL_NAME-":
            f_compare = values["-COMPARE_EXCEL_NAME-"]
        if event == "-MODULE-":
            module = values["-MODULE-"]
        elif module is None:
            module = DEF_MODULE
        if event == "-SHOW_DXL-":
            show_dxl = values["-SHOW_DXL-"]
            if show_dxl:
                pconn.send("showterminal")
            else:
                pconn.send("hideterminal")
        if event == "-PAR_NAME-":
            par_name = values["-PAR_NAME-"]
        if event == "-PAR_VAL-":
            par_val = values["-PAR_VAL-"]
        if event == "-PAR_UNIT-":
            par_unit = values["-PAR_UNIT-"]
        if event == "-PAR_DESC-":
            par_desc = values["-PAR_DESC-"]
        if event == "-REFRESH_ATTR-":
            dsm = doorsmod(module, port=PORT)
            dsm.read()
            par_attributes = dsm.columns
            window["-PAR_NAME-"].update(values=par_attributes)
            window["-PAR_VAL-"].update(values=par_attributes)
            window["-PAR_UNIT-"].update(values=par_attributes)
            window["-PAR_DESC-"].update(values=par_attributes)

        if event == "-BT_CHECK-":
            window["-CHECK_LOG-"].update("Checking...")
            parcollect = BaseParamCollection()
            bl, df_err, df_log = parcollect.from_df(dsm.wcd,
                d_map={"name": par_name, "value": par_val,
                       "unit": par_unit, "descr": par_desc,
                       "id": "Absolute Number"})
            if bl:
                window["-CHECK_LOG-"].update("Check completed, all Correct!!",
                                             text_color="blue")
            else:
                # Get the current path
                current_path = Path(".").resolve().absolute()
                error_excel = str(current_path / "Error.xlsx")
                log_excel = str(current_path / "Log.xlsx")
                try:
                    df_err.to_excel(error_excel)
                    df_log.to_excel(str(current_path / "Log.xlsx"))
                except Exception as e:
                    sg.popup_error(f"Error in the excel writing!! {e}, "
                                   "CLOSE THE EXCELS LOG and ERROR and retry")
                finally:
                    window["-CHECK_LOG-"].update("Check completed, some error!"
                                                 " Please check the excel file"
                                                 f" {error_excel}, for convers"
                                                 f"ion check excel file "
                                                 f"{log_excel}",
                                                 text_color="red")
                    pconn.send("open_excel")
                    pconn.send(error_excel)

        ######################################################################
        # Download from DOORS in Excel
        if event == "-BT_DOWNLOAD_FROM_DOORS-":
            if type(f_down_excel) != str or not Path(f_down_excel).exists():
                window["-DOWN_LOG-"].update("Wrong excel file name!!",
                                            text_color="red")
            # chek the existence of the doors module
            elif mod_exists(module) is False:
                window["-DOWN_LOG-"].update("Wrong DOORS module name!!",
                                            text_color="red")

            else:
                ############################################################
                # Donwload section
                myprin("Downloading")
                pconn.send("download")
                pconn.send(module)
                pconn.send(force_download)
                window["-DOWN_LOG-"].update("Downloading start soon, "
                                            "please wait...")
                bl_error = False
                while True:
                    myprin("Waiting for download")
                    dic = pconn.recv()
                    myprin(dic)
                    if dic is None:
                        window["-DOWN_LOG-"].update("Download completed!!")
                        break
                    else:
                        dic = eval(dic)
                        if "Error" in dic["msg"]:
                            window["-UP_LOG-"].update(dic["msg"],
                                                      text_color="red")
                            bl_error = True
                            break
                        window["-DOWN_PROG-"].update(min(int(dic["perc"]),
                                                         100))
                        window["-DOWN_LOG-"].update(dic["msg"],
                                                    text_color="blue")
                if not bl_error:
                    window["-DOWN_LOG-"].update("Download completed!!, "
                                                "exporting to excel...")
                    window["-DOWN_PROG-"].update(0)

                ############################################################
                # Export to excel section
                dsm_glob = doorsmod(module, port=PORT)
                dsm_glob.read()
                if Path(f_down_excel).exists():
                    while True:
                        try:
                            dsm_glob.wcd.to_excel(str(Path(f_down_excel)),
                                                  sheet_name=down_sheet_name)
                        except Exception as e:
                            sg.popup_error(f"Please close the Excel!! \n{e}")
                        else:
                            break

                    pconn.send("open_excel")
                    pconn.send(f_down_excel)
                window["-DOWN_LOG-"].update("")

        ######################################################################
        # Upload in DOORS
        if event == "-BT_UPLOAD_IN_DOORS-" or event == "-BT_DELTA-":
            if dsm_glob is None:
                dsm_glob = doorsmod(module, port=PORT)
            if type(f_up_excel) != str or not Path(f_up_excel).exists():
                window["-UP_LOG-"].update("Wrong excel file name!!",
                                          text_color="red")
            # chek the existence of the doors module
            elif mod_exists(module) is False:
                window["-UP_LOG-"].update("Wrong DOORS module name!!",
                                          text_color="red")
            # chek if the sheet name up_sheet_name exists in the excel
            elif up_sheet_name not in pd.ExcelFile(f_up_excel).sheet_names:
                sheets = pd.ExcelFile(f_up_excel).sheet_names
                window["-UP_LOG-"].update(f"Wrong sheet name!! avilable "
                                          f"sheets: {sheets}",
                                          text_color="red")
            else:
                n_div = 1
                if event == "-BT_UPLOAD_IN_DOORS-":
                    n_div = 2
                    ######################################################
                    # Baseline section
                    if values["-SUFFIX-"] == "":
                        window["-UP_LOG-"].update("Please insert a "
                                                  "suffix for the "
                                                  "baseline",
                                                  text_color="red")
                        continue
                    if values["-DESC-"] == "":
                        window["-UP_LOG-"].update("Please insert a "
                                                  "description for "
                                                  "the baseline",
                                                  text_color="red")
                        continue
                    try:
                        dsm = doorsmod(module, port=PORT)
                        dsm.make_baseline(values["-SUFFIX-"],
                                          values["-DESC-"],
                                          values["-MAJOR-"])
                        dsm.open(module)
                        major, minor = dsm.get_last_baseline()
                        window["-BASELINE_LOG-"].update(
                            f"Baseline with number {major}.{minor} "
                            "created before upload.", text_color="blue")
                    except Exception as e:
                        window["-UP_LOG-"].update(f"Error in the "
                                                  f"baseline creation"
                                                  f" {e}",
                                                  text_color="red")
                        continue
                
                ###########################################################
                # Donwload section 
                pconn.send("download")
                pconn.send(module)
                pconn.send(force_download_in_upload)
                window["-UP_LOG-"].update("Downloading start soon, "
                                          "please wait...")
                
                bl_error = False
                while True:
                    dic = pconn.recv()
                    myprin(dic)
                    if dic is None:
                        window["-UP_LOG-"].update("Download completed!!")
                        break
                    else:
                        dic = eval(str(dic))
                        if "Error" in dic["msg"]:
                            window["-UP_LOG-"].update(dic["msg"],
                                                      text_color="red")
                            bl_error = True
                            break
                        window["-UP_PROG-"].update(
                            min(int(dic["perc"])/n_div, 100))
                        window["-UP_LOG-"].update(dic["msg"],
                                                  text_color="blue")

                if not bl_error:
                    window["-UP_LOG-"].update("Download completed!!")
                    window["-UP_PROG-"].update(0)
                    while True:
                        try:
                            dsm = doorsmod(module, port=PORT)
                            dsm.read()
                            dsm.wcd = pd.read_excel(f_up_excel, index_col=0,
                                                    sheet_name=up_sheet_name)
                        except Exception as e:
                            sg.popup_error(f"Please close the Excel!! {e}")
                        else:
                            break

                    if event == "-BT_UPLOAD_IN_DOORS-":
                        ######################################################
                        # Write section
                        f_compare = str(Path(f_compare).resolve().absolute())
                        pconn.send("write")
                        pconn.send(module)
                        pconn.send(f_up_excel)
                        pconn.send(up_sheet_name)
                        pconn.send(f_compare)
                        bl_error = False
                        while True:
                            dic = pconn.recv()
                            myprin(dic, type(dic))
                            if dic is None:
                                window["-UP_LOG-"].update("Upload completed!!")
                                break
                            else:
                                dic = eval(str(dic))
                                if "Error" in dic["msg"]:
                                    window["-UP_LOG-"].update(dic["msg"],
                                                              text_color="red")
                                    bl_error = True
                                    break
                                window["-UP_PROG-"].update(
                                    min(int(dic["perc"])/2 + 50, 100))
                                window["-UP_LOG-"].update(dic["msg"],
                                                          text_color="blue")
                        if bl_error:
                            window["-UP_LOG-"].update("Upload completed!!, "
                                                      "data now in bad DOORS")
                            window["-UP_PROG-"].update(0)
                            pconn.send("open_excel")
                            pconn.send(f_compare)
                    else:
                        #######################################################
                        # Compare section
                        f_compare = str(Path(f_compare).resolve().absolute())
                        window["-UP_LOG-"].update("Comparing...")
                        try:
                            dsm = doorsmod(module, port=PORT)
                            dsm.read()
                            dsm.wcd = pd.read_excel(f_up_excel, index_col=0,
                                                    sheet_name=up_sheet_name)
                            dsm.compare(f_compare)
                        except Exception as e:
                            window["-UP_LOG-"].update("Error in the comparisn!"
                                                      f"   {e}",
                                                      text_color="red")
                            myprin(e)
                        else:
                            window["-UP_LOG-"].update("Comparing completed!! "
                                                      "excel comparison will "
                                                      "be opened soon",
                                                      text_color="blue")
                            pconn.send("open_excel")
                            pconn.send(f_compare)
                            window["-UP_LOG-"].update("")
 
        if event == "-BT_DELTA-":
            myprin("Delta")

    pconn.send("stop")
    window.close()


if __name__ == "__main__":
    gui()
