#!/usr/bin/env python
"""
Facttools job submitter for ISDC

This script will submit fact-tools jobs to worker nodes
at the ISDC computing cluster.

The output of the analysises will by default be put
into the same folder where this script resides.

As input this script needs to find the files:
    * analysis.xml
    * workernode.sh

Best invoke this script on one of the isdc-inxx machines.

In a decent world, you'd need to call this script once
on any host @isdc. But since only isdc-nx00 has access 
to the internet, you need to call this script once, to 
download the jar-file.
And then a seconds time on e.g. isdc-in04 in order to
submit the jobs. Stupid, hu?


Usage:
  submit.py [options] 

Options:
  -h --help          Show this screen.
  --version          Show version.
  -i --infiles STR   what files should be analysed. [default: /fact/raw/2016/01/01/20160101_0[01]*.fits.fz]
  -p --print         just print the commands, instead of submitting
"""
import sys
from docopt import docopt
import glob
import os
import pandas as pd
from tqdm import tqdm
import requests
import time
import shelve
import subprocess as sp
import shlex

from fact import credentials
import numpy as np

def read_lgamm():
    a = np.genfromtxt('lgamm.txt', delimiter=',', names='NIGHT,RUNID,EventNum,E')
    df = pd.DataFrame(a)
    df['NIGHT'] = df.NIGHT.astype(int)
    df['RUNID'] = df.RUNID.astype(int)
    df['EventNum'] = df.EventNum.astype(int)
    return df

def get_runinfo():
    if os.path.exists("runinfo.h5"):
        with pd.HDFStore("runinfo.h5") as store:
            runinfo = store["runinfo"]
    else:
        factdb = credentials.create_factdb_engine()
        print("reading complete RunInfo table, takes about 1min.")
        runinfo = pd.read_sql_table("RunInfo", factdb)
        with pd.HDFStore("runinfo.h5") as store:
            store.put("runinfo", runinfo)
    return runinfo

def get_infile_info(infile_path):
    infile_base_path, infile_name = os.path.split(infile_path)
    base_name = infile_name.split('.')[0]
    y,m,d = map(int, (base_name[0:4], base_name[4:6], base_name[6:8]))
    night_int = int(base_name[0:8])
    run = int(base_name.split('_')[-1])

    info = {
        "infile_path": infile_path,
        "infile_base_path": infile_base_path,
        "infile_name": infile_name,
        "base_name": base_name,
        "y": y,
        "m": m,
        "d": d,
        "night_int": night_int,
        "run": run
    }
    return info

def is_data_run(info, runinfo):
    """ check if run is data run. 
        if run cannot be found in runinfo table, returns False.
    """
    this_run_in_runinfo = runinfo[
        (runinfo.fNight==info["night_int"])&
        (runinfo.fRunID==info["run"])
    ]
    return len(this_run_in_runinfo) > 0 and this_run_in_runinfo.iloc[0].fRunTypeKey == 1

def add_drs_run_to_info(info, runinfo):
    drs_run_candidates = runinfo[
        (runinfo.fNight == info["night_int"])&
        (runinfo.fDrsStep == 2)&
        (runinfo.fRunTypeKey==2)&
        (runinfo.fRunID < info["run"])
    ]
    
    if len(drs_run_candidates) >= 1:
        info["drs_run"] = drs_run_candidates.iloc[-1].fRunID
    else:
        info["drs_run"] = None
    return info

def security_check(args):

    if not args["--print"] and os.path.isdir("json"):
        msg = "!! DANGER ZONE !!".center(60, '-') + '\n'
        msg += '\n'
        msg += "I found a json/ folder. If I go on, files in that folder will be overwritten.\n"
        msg += "Do you want me to go on?[yes|no]"

        answer = input(msg)
        while not answer in ["yes", "no"]:
            answer = input(msg+"\n please answer 'yes' or 'no':")

        if answer == "no":
            print("Exiting...")
            sys.exit(0)



if __name__ == "__main__":
    arguments = docopt(__doc__, version='Submitter 1.0')
    print(arguments)
    security_check(arguments)

    jar_file_name = "fact-tools-0.17.4.jar"
    infile_search_path = arguments["--infiles"]

    this_path = os.path.dirname(os.path.realpath(__file__))
    path_templates = {
        "jar_path": os.path.join(this_path, jar_file_name),
        "xml_path": os.path.join(this_path, "analysis.xml"),
        "worker_node_script_path": os.path.join(this_path, "workernode.sh"),
        "outdir": os.path.join(this_path, "json/{y:04d}/{m:02d}/{d:02}"),
        "basename": "{base_name}",
        "stdout_path": os.path.join(this_path, "out/{y:04d}/{m:02d}/{d:02}/{base_name}.txt"),
        "stderr_path": os.path.join(this_path, "err/{y:04d}/{m:02d}/{d:02}/{base_name}.txt"),
        "drsfile":"{infile_base_path}/{night_int:08d}_{drs_run:03d}.drs.fits.gz",
        "aux_dir": "/fact/aux/{y:04d}/{m:02d}/{d:02d}/",
        "infile_path": "{infile_path}",
    }

    df = read_lgamm()
    runinfo = get_runinfo()
    for (NIGHT, RUNID), __ in tqdm(df.groupby(['NIGHT', 'RUNID'])):
        infile_path = '/fact/raw/{y:04d}/{m:02d}/{d:02d}/{bsn:08d}_{rrr:03d}.fits.fz'.format(
                y=NIGHT // 10000,
                m=(NIGHT // 100) % 100,
                d=NIGHT % 100,
                bsn=NIGHT,
                rrr=RUNID
        )
        if not os.path.isfile(infile_path):
            continue
        info = get_infile_info(infile_path)

        if not is_data_run(info, runinfo):
            continue

        info = add_drs_run_to_info(info, runinfo)
        if info["drs_run"] is None:
            continue

        paths = {n:p.format(**info) for (n,p) in path_templates.items()}

        cmd = ("qsub "
                "-q fact_short "
                "-o {stdout_path} "
                "-e {stderr_path} "
                "-v "
                "jar_path={jar_path},"
                "xml_path={xml_path},"
                "auxFolder=file:{aux_dir},"
                "outdir={outdir},"
                "basename={basename},"
                "infile={infile_path},"
                "drsfile=file:{drsfile} "
                "{worker_node_script_path}"
        ).format(**paths)
       
        if arguments["--print"]:
            print(cmd)
        else:
            sp.check_output(shlex.split(cmd))

