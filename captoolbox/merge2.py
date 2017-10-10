#!/usr/bin/env python
"""
Merges several HDF5 files into a single file or multiple larger files.

Example
    merge.py ifiles_*.h5 -o ofile.h5
    merge.py ifiles_*.h5 -o ofile.h5 -m 5 -n 5

Notes
    * The parallel option (-n) only works for multiple outputs (-m)!
    * It merges files in the order they are read.
    # If receive "Argument list too long", pass a string.
    * See complementary program: split.py

"""
import os
import sys
import h5py
import argparse
import numpy as np
from glob import glob


def get_args():
    """ Pass command-line arguments. """
    parser = argparse.ArgumentParser(
            description='Merges several HDF5 files.')
    parser.add_argument(
            'file', metavar='file', type=str, nargs='+',
            help='HDF5 files to merge')
    parser.add_argument(
            '-o', metavar='ofile', dest='ofile', type=str, nargs=1,
            help=('output file name'),
            default=[None], required=True,)
    parser.add_argument(
            '-m', metavar='nfiles', dest='nfiles', type=int, nargs=1,
            help=('number of merged files (blocks)'),
            default=[1],)
    parser.add_argument(
            '-v', metavar='var', dest='vnames', type=str, nargs='+',
            help=('only merge specific vars if given, otherwise merge all'),
            default=[],)
    parser.add_argument(
            '-n', metavar='njobs', dest='njobs', type=int, nargs=1,
            help=('number of jobs for parallel processing when using -m'),
            default=[1],)
    return parser.parse_args()


def get_total_len(ifiles):
    """ Get total output length from all input files. """
    N = 0
    for fn in ifiles:
        with h5py.File(fn) as f:
            N += f.values()[0].shape[0]
    return N


def get_var_names(ifile):
    """ Return all '/variable' names in the HDF5. """
    with h5py.File(ifile, 'r') as f:
        vnames = f.keys()
    return vnames


def get_multi_io(ifiles, ofile, nfiles):
    """ Construct multiple input/output file names. """
    # List of groups of input files
    ifiles = [list(arr) for arr in np.array_split(ifiles, nfiles)]
    # List of output file names
    fname = os.path.splitext(ofile)[0] + '_%02d.h5'
    ofiles = [(fname % k) for k in xrange(len(ifiles))]
    return ifiles, ofiles


def main(ifiles, ofile, vnames):
    """
    Merge variables from several input files into a single file.

    Args:
        ifiles (list): input file names.
        ofile (str): output file name.
        vnames (list): name of vars to merge.
    """
    # Get length of output containers (from all input files)
    N = get_total_len(ifiles)

    with h5py.File(ofile, 'w') as f:

        # Create empty output containers (w/compression optimized for speed)
        [f.create_dataset(key, (N,), dtype='float64', compression='lzf') \
                for key in vnames]

        # Iterate over the input files
        k1 = 0
        for ifile in ifiles:
            print ifile
    
            # Write next chunk (the input file)
            with h5py.File(ifile) as f2:
                k2 = k1 + f2.values()[0].shape[0]  # first var/first dim

                # Iterate over all variables
                for key in vnames:
                    f[key][k1:k2] = f2[key][:]

            k1 = k2
    
    print 'merged', len(ifiles), 'files'
    print 'output ->', ofile


if __name__ == '__main__':

    args = get_args() 
    ifile = args.file[:]  # list
    ofile = args.ofile[0]  # str
    nfiles = args.nfiles[0]
    vnames = args.vnames[:]
    njobs = args.njobs[0]

    # In case a string is passed to avoid "Argument list too long"
    if len(ifile) == 1:
        ifile = glob(ifile[0])

    # Get var names from first file, if not provided
    vnames = get_var_names(ifile[0]) if not vnames else vnames

    # Groups of input files -> multiple output files 
    if nfiles > 1:
        ifile, ofile = get_multi_io(ifile, ofile, nfiles)
    else:
        ifile, ofile = [ifile], [ofile]

    if njobs > 1 and nfiles > 1:
        print 'Running parallel code (%d jobs) ...' % njobs
        from joblib import Parallel, delayed
        Parallel(n_jobs=njobs, verbose=5)(
                delayed(main)(fi, fo, vnames) for fi,fo in zip(ifile, ofile))
    else:
        print 'Running sequential code ...'
        [main(fi, fo, vnames) for fi,fo in zip(ifile, ofile)]
