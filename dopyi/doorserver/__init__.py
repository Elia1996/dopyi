from os.path import join as pjoin
from os.path import realpath as prealpath
from os.path import dirname

import dopyi as dopyi

S_DOORSERVER = pjoin(dirname(prealpath(__file__)), "doorserver.dxl")
S_DOORSERVER_LIB = pjoin(dirname(prealpath(__file__)), "lib_doorserver.dxl")

# The absolute path of lib_doorserver.dxl is injected in the per-port
# generated dxl file by server.run(): the packaged template must never
# be rewritten in place (read-only installs, dirty git tree).

S_DOORSERVER_NEW = pjoin(dopyi.P_DATA_SAVE, "doorserver_")
S_DOORSKEY = pjoin(dopyi.P_DATA_SAVE, "userpassw.txt")
