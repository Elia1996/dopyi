import os
from pathlib import Path
S_PATH = os.path.dirname(os.path.abspath(__file__))


def gui():
    pt = str(Path(S_PATH, "doors_excel_interface.py").resolve().absolute())
    os.system(f"python \"{pt}\"")


if __name__ == "__main__":
    gui()
