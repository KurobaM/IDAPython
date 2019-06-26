
# This script will do the following things:
# - open idc.idc
# - advance to the compatibility macros section
# - read, and parse each of those
# - if the symbol doesn't exist in the 'idc' module, dump its alias into the output file

import argparse
p = argparse.ArgumentParser()
p.add_argument("-i", "--idc", required=True, help="Path to the idc.idc file")
p.add_argument("-o", "--output", required=True, help="Path to the output file")
p.add_argument("-d", "--debug-out", default=False, action="store_true", help="Dump code that shows, at ida start-time, what symbols would be overriden by the compat layer")
args = p.parse_args()

import os

with open(args.idc, "r") as fin:
    inlines = fin.readlines()

# search for compat macros section, and remove uninteresting lines
for idx in xrange(len(inlines)):
    if inlines[idx].replace(" ", "").find("COMPATIBILITYMACROS") > -1:
        break
assert(idx < len(inlines))
inlines=inlines[idx:]

def nextline():
    global inlines
    l = inlines[0].strip()
    inlines=inlines[1:]
    idx = l.find("//")
    if idx > -1:
        l = l[0:idx].strip()
    return l

# set of symbols that must not be redefined
forbidden = [
    "GetLocalType",
    "AddSeg",
    "SetType",
    "GetDisasm",
    "SetPrcsr",
    "GetFloat",
    "GetDouble",
    "AutoMark",
    "is_pack_real",
    "set_local_type",
    "WriteMap",
    "WriteTxt",
    "WriteExe",
    "CompileEx",
    "uprint",
    "form",
    "Appcall",
    "ApplyType",
    "GetManyBytes",
    "GetString",
    "ClearTraceFile",
    "FindBinary",
    "FindText",
    "NextHead",
    "ParseTypes",
    "PrevHead",
    "ProcessUiAction",
    "SaveBase",
    "eval",
    "MakeStr",
    "GetProcessorName",
    "SegStart",
    "SegEnd",
    "SetSegmentType",
    "CleanupAppcall",
]

symbols_modules = {
    "AF_ANORET" : "ida_ida",
    "AF_ANORET" : "ida_ida",
    "AF_CHKUNI" : "ida_ida",
    "AF_DATOFF" : "ida_ida",
    "AF_DOCODE" : "ida_ida",
    "AF_DODATA" : "ida_ida",
    "AF_FTAIL" : "ida_ida",
    "AF_HFLIRT" : "ida_ida",
    "AF_JUMPTBL" : "ida_ida",
    "AF_PURDAT" : "ida_ida",
    "AF_REGARG" : "ida_ida",
    "AF_SIGCMT" : "ida_ida",
    "AF_SIGMLT" : "ida_ida",
    "AF_STKARG" : "ida_ida",
    "AF_STRLIT" : "ida_ida",
    "AF_TRFUNC" : "ida_ida",
    "AF_VERSP" : "ida_ida",
    "BADADDR" : "ida_idaapi",
    "FF_UNUSED" : "ida_bytes",
    "FIXUPF_CREATED" : "ida_fixup",
    "FIXUPF_EXTDEF" : "ida_fixup",
    "FIXUPF_REL" : "ida_fixup",
    "FIXUPF_UNUSED" : "ida_fixup",
    "FIXUP_OFF8" : "ida_fixup",
    "GN_VISIBLE" : "ida_name",
    "SEGMOD_KEEP" : "ida_segment",
    "SEGMOD_KILL" : "ida_segment",
    "SEGMOD_SILENT" : "ida_segment",
    "SETPROC_IDB" : "ida_idp",
    "SETPROC_LOADER" : "ida_idp",
    "SETPROC_LOADER_NON_FATAL" : "ida_idp",
    "STRF_AUTO" : "ida_ida",
    "STRF_COMMENT" : "ida_ida",
    "STRF_GEN" : "ida_ida",
    "STRF_SAVECASE" : "ida_ida",
    "STRF_SERIAL" : "ida_ida",
    "STRTYPE_C" : "ida_nalt",
    "STRTYPE_C_16" : "ida_nalt",
    "STRTYPE_C_32" : "ida_nalt",
    "STRTYPE_LEN2_16" : "ida_nalt",
    "STRTYPE_LEN4_16" : "ida_nalt",
    "STRTYPE_PASCAL" : "ida_nalt",
    "STRTYPE_TERMCHR" : "ida_nalt",
    "V695_REF_VHIGH" : "ida_nalt",
    "V695_REF_VLOW" : "ida_nalt",
    "error" : "ida_kernwin",
    "warning" : "ida_kernwin",
    "ask_str" : "ida_kernwin",
    "ask_file" : "ida_kernwin",
    "ask_addr" : "ida_kernwin",
    "ask_long" : "ida_kernwin",
    "is_mapped" : "ida_bytes",
    "decode_insn" : "ida_ua",
    "HIST_IDENT" : "ida_kernwin",
}

import re
def maybe_qualify(s):
    last_idx = -1
    for sym, mod in symbols_modules.items():
        idx = s.find(sym)
        if idx > last_idx:
            s = s.replace(sym, "%s.%s" % (mod, sym))
            last_idx = idx + 1 + len(mod)
    return s

def remove_parens(arg):
    m = re.match(r'\s*\((.*)\)\s*$', arg)
    if m:
      arg = m.group(1)
    return arg.strip()

def fix_ternary_operator(code):
    match = re.match(r'([^(]+)\((.*)\)', code)
    if match:
      changed = False
      func = match.group(1)
      args = match.group(2)
      out  = []
      for arg in args.split(','):
        m2 = re.match(r'([^?]+)\?(.*):(.*)', arg)
        if m2:
          cond  = remove_parens(m2.group(1))
          ithen = remove_parens(m2.group(2))
          ielse = remove_parens(m2.group(3))
          arg = ithen + ' if ' + cond + ' else ' + ielse
          changed = True
        out.append(arg.strip())
      if changed:
        code = func + '(' + ', '.join(out) + ')'
    return code

import time
funcall_pat = re.compile(r"#define\s+([a-zA-Z0-9_]*)\s*(\([^\)]*\))\s*(.*)")
alias_pat = re.compile(r"#define\s+([a-zA-Z0-9_]*)\s*([a-zA-Z0-9_/\*\.]*)\s*$")
with open(args.output, "w") as fout:
    fout.write("# Autogenerated on: %s\n\n" % time.strftime("%c"))
    for mod in sorted(list(set(symbols_modules.values()))):
        fout.write("import %s\n" % mod)
    fout.write("from idc import *\n\n")
    while len(inlines):
        l = nextline()
        if l == "":
            continue
        repl = None
        match = funcall_pat.match(l)
        if match:
            symbol = match.group(1)
            parms = match.group(2)
            code = match.group(3)
            while True:
                has_more = code.endswith("\\")
                if has_more:
                    code = code[0:-1]
                    code = code + nextline()
                else:
                    break
            code = fix_ternary_operator(code)
            code = maybe_qualify(code)
            repl = "def %s%s: return %s\n" % (symbol, parms, code)
        else:
            match = alias_pat.match(l)
            if match:
                symbol = match.group(1)
                newsym = match.group(2)
                newsym = maybe_qualify(newsym)
                repl = "%s=%s\n" % (symbol, newsym)

        if repl and symbol not in forbidden:
            if not args.debug_out:
                fout.write(repl)
            else:
                fout.write("""
try:
    import idc
    x = idc.%s
    print("Would override %s")
except:
    pass
""" % (symbol, symbol))
