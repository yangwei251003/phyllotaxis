"""Isolated installed KiCad SES import. No production or source-file writes."""
import sys
import pcbnew as K
src,ses,dst=sys.argv[1:]
b=K.LoadBoard(src)
assert K.ImportSpecctraSES(b,ses)
assert K.SaveBoard(dst,b)
print('Native SES import/save succeeded; fresh-process verification still required.')
