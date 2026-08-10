from os.path import join as pjoin
from os.path import realpath as prealpath
from os.path import dirname

import dopyi as dopyi

S_DOORSERVER = pjoin(dirname(prealpath(__file__)), "doorserver.dxl")
S_DOORSERVER_LIB = pjoin(dirname(prealpath(__file__)), "lib_doorserver.dxl")

fp = open(S_DOORSERVER, "r")
data = fp.read()
if len(data) < 10:
    raise Exception("Errorr dooreserver not found")
l_data = data.split("\n")
i_to_change = l_data.index('//INCLUDE_LIB_DOORSERVER')+1
l_data[i_to_change] = "#include <" + S_DOORSERVER_LIB + ">"
data = "\n".join(l_data)
fp = open(S_DOORSERVER, "w")
fp.write(data)
fp.close()

S_DOORSERVER_NEW = pjoin(dopyi.P_DATA_SAVE, "doorserver_")
S_DOORSKEY = pjoin(dopyi.P_DATA_SAVE, "userpassw.txt")
