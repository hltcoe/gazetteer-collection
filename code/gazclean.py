"""
clean gazetteers by removing string that do not seem appropriate to their type

USAGE: python gazclean.py lang type gazetteer cleanedgazetteer

"""

import argparse
import os
import re
from collections import defaultdict

def get_args():
    """Get command line arguments"""
    pargs = argparse.ArgumentParser(description=DESCRIPTION, epilog=USAGE_EXAMPLE)
    pargs.add_argument('language', help='language, e.g. eng, rus cmn')
    pargs.add_argument('type', help='type, e.g. PER')
    pargs.add_argument('gazin', help='input file of gazetteer names')
    pargs.add_argument('gazout', help='output file of gazetteer names')        
    return pargs.parse_args()

DESCRIPTION = "clean gazetteers by removing string that do not seem appropriate to their type"
USAGE_EXAMPLE = "python gaz_clean PER lists/eng-PER-names-wd.txt  cleaned/eng-PER-names-wd.txt"


# some global variables
LANGS = "eng rus cmn".split()
TYPES = "AIR AIRC CHEM COMM COMP EVNT FAC FNAM GNAM GOVT GPE LANG LOC MIL MONEY NORP ORG PER POL TITLE VEH".split()
MODES = "name alias".split()


def compile_pats(dictionary):
    for atype, patterns in dictionary.items():
        dictionary[atype] = [re.compile(pat) for pat in patterns]
    return dictionary 

def merge(d1, d2):
    d = defaultdict(list)
    for key in set(d1.keys()).union(set(d2.keys())):
        d[key] = d1[key] + d2[key]
    return d

##### patterns for cleaning all

bad_substrings_all = defaultdict(list)
bad_patterns_all = defaultdict(list)
for T in TYPES:
    # kill any name that's all digits
    bad_patterns_all[T] = ["""^\d+$"""]
compile_pats(bad_patterns_all)
remove_patterns_all = defaultdict(list)
for T in TYPES:
    if T != 'CHEM':
        # remove any substring in parens
        remove_patterns_all[T] = ["""\(.*\)""", """\(.*$"""]
compile_pats(remove_patterns_all)

##### patterns for cleaning eng
bad_substrings_eng = defaultdict(list,
    {'PER':[" of ", " the ", "/" ],
     'ORG':["season"],
     'GPE':["local electoral", " for ", "/", "ward no"],
     'FAC':["barn "],
     'FNAM':['фамилия', 'значения', ' of'],
     'LANG':['ISO'],
     'CHEM':['/', '(', ' of ', ' the ']
     })
bad_patterns_eng = compile_pats(defaultdict(list,
    {'PER': [],
     'ORG': ["""\d\d\d\d"""],
     'CHEM':["""\(.\)"""] }))
remove_patterns_eng = compile_pats(defaultdict(list))

##### patterns for cleaning rus
bad_substrings_rus = defaultdict(list)
bad_patterns_rus = defaultdict(list)
remove_patterns_rus = defaultdict(list)

##### patterns for cleaning cmn
bad_substrings_cmn = defaultdict(list)
bad_patterns_cmn = defaultdict(list)
remove_patterns_cmn = defaultdict(list)

# merge the patterns for all 
bad_substrings = defaultdict(dict, {
    'eng':merge(bad_substrings_eng, bad_substrings_all),
    'rus':merge(bad_substrings_rus, bad_substrings_all),
    'cmn':merge(bad_substrings_cmn, bad_substrings_all) })
bad_patterns = defaultdict(dict, {
    'eng': merge(bad_patterns_eng, bad_patterns_all),
    'rus': merge(bad_patterns_rus, bad_patterns_all),
    'cmn': merge(bad_patterns_cmn, bad_patterns_all) })
remove_patterns = defaultdict(dict,
    {'eng': merge(remove_patterns_eng, remove_patterns_all),
     'rus': merge(remove_patterns_rus, remove_patterns_all),
     'cmn': merge(remove_patterns_cmn, remove_patterns_all)})


def infer_from_file_name(fileOrPath):
    """ returns (lang, type, nameOrAlias) by insecing the filename.
    Returns (None,None,None) if it fails.  We assume files are named like
    eng-PER-name-..."""
    failed = (None, None, None)
    lang = atype = mode = None
    fname = os.path.basename(fileOrPath)
    elements = fname.split('-')
    if len(elements) >= 3:
        if elements[0] in LANGS:
            lang = elements[0]
        if elements[1] in TYPES:
            atype = elements[1]
        if elements[2] in MODES:
            mode = elements[1]
    if lang and atype and mode:
        return (lang, atype, mode)
    else:
        print('Unrecognized gazetteer file name', fname, 'with elements', lang, type, mode)
        return (None, None, None)

def clean_directory(indir, outdir):
    """ clean all the files in indir and write cleaned versions to outdir """
    # create outdir if neccessary
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    files = [f for f in os.listdir(indir) if os.path.isfile(os.path.join(indir, f))]
    for infile_name in files:
        infile =  os.path.join(indir, infile_name)
        outfile = os.path.join(outdir, infile_name)
        lang, atype, mode = infer_from_file_name(infile)
        if lang and atype and mode:
            clean_file(lang, atype, infile, outfile)
            #print("clean_file({},{},{},{})".format(lang,atype,infile,outfile))

def clean_file(lang, atype, gazin, gazout):
    """ clean one file """
    print('cleaning', gazin)
    linesin = modified = deleted = 0
    with open(gazin) as infile:
        with open(gazout, 'w') as outfile:
            seen = set()
            for linein in infile:
                linesin += 1
                line = linein.strip().lower()
                delete = modify = False
                for pat in remove_patterns[lang][atype]:
                    if pat.search(linein):
                        #if modify: print('Second bite', linein)
                        linein = re.sub(pat, '', linein)
                        #if modify: print('  result', linein)
                        modify = True
                for bad in bad_substrings[lang][atype]:
                    if bad in line:
                        delete = True
                        break
                if not delete:
                    for pat in bad_patterns[lang][atype]:
                        if pat.search(line):
                            delete = True
                            break
                if delete:
                        deleted += 1
                else:
                    # awlays remove extra spaces
                    linein = re.sub(' +', ' ', linein)
                    if linein not in seen:
                        outfile.write(linein)
                        seen.add(linein)
                        if modify:
                            modified += 1

    print("Gaz {}: deleted {} ({:.2f}%), modified {} ({:.2f}%) of {} names".format(gazin, deleted, 100*deleted/linesin, modified, 100*modified/linesin, linesin))
    

if __name__ == '__main__':
    """ if invoked from command line """
    args = get_args()
    clean_file(args.language, args.type, args.gazin, args.gazout)
