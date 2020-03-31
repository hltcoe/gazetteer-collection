"""
clean gazetteers in a directory writing cleaned versions to another directory

USAGE: python gazclean_directory.py indir outdir

"""

import argparse
import gazclean

def get_args():
    """Get command line arguments"""
    pargs = argparse.ArgumentParser(description=DESCRIPTION, epilog=USAGE_EXAMPLE)
    pargs.add_argument('indir', help='input directory')
    pargs.add_argument('outdir', help='output directory')    
    return pargs.parse_args()

DESCRIPTION = "clean gazetteers in a directory writing cleaned versions to another directory"
USAGE_EXAMPLE = "  e.g.: python gazclean_dir.py lists cleanlists"

if __name__ == '__main__':
    """ if invoked from command line """
    args = get_args()
    gazclean.clean_directory(args.indir, args.outdir)
