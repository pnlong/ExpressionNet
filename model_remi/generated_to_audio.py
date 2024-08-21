# README
# Phillip Long
# August 3, 2024

# Given a path to a sequence generated by the REMI-Style model, synthesize it as audio.

# python /home/pnlong/model_musescore/model_remi/generated_to_audio.py

# IMPORTS
##################################################

import argparse
from os.path import exists, dirname, realpath
from os import makedirs
import logging
import numpy as np

import sys
sys.path.insert(0, dirname(realpath(__file__)))
sys.path.insert(0, dirname(dirname(realpath(__file__))))

from representation import Indexer, get_encoding, decode
import utils

##################################################


# GENERATE AUDIO GIVEN CODES
##################################################

def generated_to_audio(path: str, output_path: str, encoding: dict, vocabulary: dict) -> None:
    """
    Generate audio sample from codes. 
    """

    # load codes
    codes = np.load(file = path)

    # convert codes to a music object
    music = decode(codes = codes, encoding = encoding, vocabulary = vocabulary) # convert to a MusicRender object

    # write as audio (actually, can write as whatever kind of file we want)
    music.write(path = output_path)

    return

##################################################


# ARGUMENTS
##################################################

def parse_args(args = None, namespace = None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(prog = "Generated to Audio", description = "Synthesize generated content as audio.")
    parser.add_argument("-p", "--path", required = True, type = str, help = "Path to generated sequence (.npy file)")
    parser.add_argument("-o", "--output_path", default = None, type = str, help = "Output path")
    return parser.parse_args(args = args, namespace = namespace)

##################################################


# MAIN METHOD
##################################################

if __name__ == "__main__":

    # parse the command-line arguments
    args = parse_args()

    # set up logger
    logging.basicConfig(level = logging.INFO, format = "%(message)s")
    
    # get variables
    encoding = get_encoding() # load the encoding
    vocabulary = utils.inverse_dict(Indexer(data = encoding["event_code_map"]).get_dict()) # for decoding

    # output codes as audio
    output_path = args.output_path
    if output_path is None:
        path_info = args.path[:-len(".npy")].split("/")[-4:]
        output_dir = f"/home/pnlong/musescore/remi/generated_audio/{path_info[1]}"
        if not exists(output_dir):
            makedirs(output_dir, exist_ok = True)
        output_path = f"{output_dir}/{path_info[0]}.{path_info[-1]}.wav"

    # generate audio
    generated_to_audio(path = args.path, output_path = output_path, encoding = encoding, vocabulary = vocabulary)
    logging.info(f"Saved to {output_path}.")

##################################################