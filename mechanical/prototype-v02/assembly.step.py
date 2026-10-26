import os,sys
from pathlib import Path
os.environ['PHYLLO_COMPONENT_REVISION']='prototype-v02'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from parts import assembly

def gen_step():return assembly()
