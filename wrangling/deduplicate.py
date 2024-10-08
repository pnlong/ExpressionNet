# README
# Phillip Long
# July 26, 2024

# Dataset deduplication efforts. Outputs a list of filepaths.
# Each filepath is the 'best' version of a unique song.
# In other words, we group songs with duplicate artists and titles together,
# and from that grouping, we choose the best version within that group.

# python /home/pnlong/model_musescore/wrangling/deduplicate.py

# IMPORTS
##################################################

import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from re import sub
import os
from os.path import dirname, basename, exists
from tqdm import tqdm
import multiprocessing
from typing import List
import torch
import logging

from sentence_transformers import SentenceTransformer

from os.path import dirname, realpath
import sys
sys.path.insert(0, dirname(realpath(__file__)))
sys.path.insert(0, dirname(dirname(realpath(__file__))))

from full import OUTPUT_DIR, DATASET_DIR_NAME, CHUNK_SIZE, MMT_STATISTIC_COLUMNS
from quality import PLOTS_DIR_NAME, make_facet_name_fancy
import utils

os.environ["TOKENIZERS_PARALLELISM"] = "true"
plt.style.use("default")
# plt.rcParams["font.family"] = "serif"
# plt.rcParams["mathtext.fontset"] = "dejavuserif"

##################################################


# GET FACET NAME FOR LATEX TABLE
##################################################

# make the facet name fancy for the latex table
make_facet_for_table = lambda facet: "\\RaggedRight{\\textbf{" + "$\cap$".join(map(lambda word: word[0].upper(), facet.split("_"))) + "}}" # display facet for table
# make_facet_for_table = lambda facet: f"\\RaggedRight{{{make_facet_name_fancy(facet = facet)}}}" # display facet for table

##################################################


# CONSTANTS
##################################################

# default batch size for encoding song titles as sentence embeddings
BATCH_SIZE = 32

# column names in dataset from which we can create a description of the song that can be used for deduplication
DESCRIPTOR_COLUMNS = ["song_name", "title", "subtitle", "artist_name", "composer_name"]

# column names for how to determine the best version of a song
BEST_VERSION_METRIC_COLUMNS = ["rating", "n_ratings", "n_notes", "n_tokens"]

# column names to include in the output
OUTPUT_COLUMNS = ["path", "best_path", "is_best_path", "best_arrangement", "is_best_arrangement", "best_unique_arrangement", "is_best_unique_arrangement"]

# facets of the dataset
FACETS = ["all", "rated", "deduplicated", "rated_deduplicated"]

# minimum similarity (0 to 1) between two song titles for them to be considered duplicates
SIMILARITY_THRESHOLD = 0.8

# fraction difference in number of notes necessary for two songs when those songs have the same instrumentation to be considered 'unique' arrangements
UNIQUENESS_DIFFERENTIATION_COLUMN = "n_notes"
UNIQUENESS_THRESHOLD = 0.05

##################################################


# FUNCTION THAT CREATES SONG DESCRIPTORS
##################################################

def get_song_descriptor_from_index(i: int) -> str:
    """
    Given the index of a row in the dataset, generate a song 'descriptor'
    based off the songs title and composer, as well as any other relevant attributes.
    """

    # extract relevant attributes from the dataset, replacing NA values with empty strings
    song_name, title, subtitle, artist_name, composer_name = dataset.loc[i, DESCRIPTOR_COLUMNS].fillna(value = "")

    # deal with song name
    song = ""
    if (song_name.lower() == title.lower()) or ((len(song_name) > 0) and (len(title) == 0)):
        song = song_name
    elif (len(song_name) > 0) and (len(title) > 0):
        song = f"{song_name}, also known as {title}"
    elif len(title) > 0:
        song = title
    if len(subtitle) > 0:
        song += f": {subtitle}"

    # deal with artist name
    artist = ""
    if (len(artist_name) > 0) and (len(composer_name) > 0): # if both are defined
        artist = f"{artist_name}, and composed by {composer_name}"
    elif len(artist_name) > 0:
        artist = artist_name
    elif len(composer_name) > 0:
        artist = composer_name

    # create descriptor, while doing some string processing
    descriptor = f"{song}; by {artist}"
    if descriptor[-1] not in ".?!": # add punctuation to the end if there isn't any
        descriptor += "."
    descriptor = sub(pattern = r'[^ \w0-9,.?!;:()&-]', repl = " ", string = descriptor)
    descriptor = " ".join(descriptor.split()) # remove wierd whitespace

    # return the descriptor
    return descriptor

##################################################


# TOP SONG CHOOSER
##################################################

def choose_best_song_from_indicies(indicies: List[int]) -> int:
    """
    Given a set of indicies in the dataset, return the index representing the 'best' song
    from those indicies. Our definition of best is the song with the highest ratings.
    """

    # default best index
    best_index = indicies[0]

    # avoid unnecessary computations if possible
    if len(indicies) == 1: # if a song has no duplicates
        return best_index # simply return that song's index
    
    # get all the duplicates in one data frame
    duplicates = dataset.loc[indicies, BEST_VERSION_METRIC_COLUMNS]

    # determine best version of song
    duplicates = duplicates.sort_values(by = BEST_VERSION_METRIC_COLUMNS, axis = 0, ascending = False, na_position = "last", ignore_index = False)
    best_index = duplicates.index[0] # the top index is the best index

    # return the best index
    return best_index

##################################################


# FINDS THE BEST ARRANGMENTS WITHIN DESCRIPTOR-DUPLICATES
##################################################

def choose_unique_arrangements_from_indicies(indicies: List[int]) -> pd.DataFrame:
    """
    Given a set of indicies within the dataset, find and label unique arrangments.
    """

    # get subset of dataset
    duplicates = dataset.loc[indicies]

    # get all unique instrumentations of a song
    instrumentations = pd.unique(values = duplicates["tracks"])

    # avoid unnecessary computations if possible; if there are no duplicates or if each duplicate is a different instrumentation
    if (len(duplicates) == 1) or (len(instrumentations) == len(duplicates)):
        return duplicates

    # within each instrumentation choose the best arrangement
    for instrumentation in instrumentations:
        duplicates_instrumentation = duplicates[duplicates["tracks"] == instrumentation]

        # find the best arrangement with this instrumentation
        if len(duplicates_instrumentation) > 1: # if there are duplicates within the instrumentation

            # update data
            best_arrangement_index = choose_best_song_from_indicies(indicies = duplicates_instrumentation.index) # get the index of the best arrangement with this instrumentation
            not_best_arrangement_indicies = list(filter(lambda index: index != best_arrangement_index, duplicates_instrumentation.index)) # get the indicies that are not the best arrangement
            duplicates.loc[not_best_arrangement_indicies, "best_arrangement"] = duplicates.at[best_arrangement_index, "path"] # the path of the best arrangement with this instrumentation
            duplicates.loc[not_best_arrangement_indicies, "is_best_arrangement"] = False # these indicies are not the best arrangment with this instrumentation
            
            # find unique arrangements within this instrumentation; group songs with similar number of tokens together
            duplicates_instrumentation = duplicates_instrumentation.sort_values(by = UNIQUENESS_DIFFERENTIATION_COLUMN, axis = 0, ascending = True, na_position = "last", ignore_index = False)
            groups = [[duplicates_instrumentation.index[0]]]
            for i in range(1, len(duplicates_instrumentation)):
                i_previous, i_current = duplicates_instrumentation.index[(i - 1):(i + 1)]
                value_previous, value_current = duplicates_instrumentation.loc[[i_previous, i_current], UNIQUENESS_DIFFERENTIATION_COLUMN]
                if abs((2 * (value_current - value_previous)) / (value_current + value_previous)) <= UNIQUENESS_THRESHOLD:
                    groups[-1].append(i_current)
                else:
                    groups.append([i_current])

            # update data
            for group in groups:
                if len(group) > 1: # if there are duplicates within the group
                    unique_arrangement_index = choose_best_song_from_indicies(indicies = group) # get the index of the best arrangement within this group
                    not_unique_arrangement_indicies = list(filter(lambda index: index != unique_arrangement_index, group)) # get the indicies that are not the one
                    duplicates.loc[not_unique_arrangement_indicies, "best_unique_arrangement"] = duplicates.at[unique_arrangement_index, "path"] # the path of the best unique arrangement within this group
                    duplicates.loc[not_unique_arrangement_indicies, "is_best_unique_arrangement"] = False # these indicies are not the best unique arrangment within this group

    # return edited dataframe
    return duplicates

##################################################


# ARGUMENTS
##################################################

def parse_args(args = None, namespace = None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(prog = "Deduplicate", description = "Deduplicate songs in full dataset.")
    parser.add_argument("-df", "--dataset_filepath", default = f"{OUTPUT_DIR}/{DATASET_DIR_NAME}_full.csv", type = str, help = "Filepath to full dataset")
    parser.add_argument("-r", "--reset", action = "store_true", help = "Whether or not to recreate intermediate data tables")
    parser.add_argument("-bs", "--batch_size", default = BATCH_SIZE, type = int, help = "Batch size")
    parser.add_argument("-g", "--gpu", default = -1, type = int, help = "GPU number")
    parser.add_argument("-j", "--jobs", default = int(multiprocessing.cpu_count() / 4), type = int, help = "Number of Jobs")
    return parser.parse_args(args = args, namespace = namespace)

##################################################


# MAIN METHOD
##################################################

if __name__ == "__main__":

    # BASIC SETUP
    ##################################################

    # parse arguments
    args = parse_args()

    # directory to output files
    output_dir = dirname(args.dataset_filepath)
    extra_output_dir = f"{output_dir}/.deduplicate_intermediate_data" # make the directory hidden
    if not exists(extra_output_dir):
        os.mkdir(extra_output_dir)

    # get device for gpu calculations
    device = f"cuda:{abs(args.gpu)}" if (torch.cuda.is_available() and args.gpu != -1) else "cpu"

    # set up logging
    logging.basicConfig(level = logging.INFO, format = "%(message)s")

    # load in dataset
    logging.info("Loading in Dataset.")
    dataset = pd.read_csv(filepath_or_buffer = args.dataset_filepath, sep = ",", header = 0, index_col = False)
    
    # output filepaths
    output_filepath_embeddings = f"{extra_output_dir}/embeddings.csv"
    output_filepath_magnitudes = f"{extra_output_dir}/magnitudes.csv"
    output_filepath = f"{output_dir}/{basename(dirname(args.dataset_filepath))}_deduplicated.csv"
    output_filepath_merged = f"{output_dir}/{basename(dirname(args.dataset_filepath))}.csv"
    plots_dir = f"{output_dir}/{PLOTS_DIR_NAME}"
    output_filepath_plot = f"{plots_dir}/duplicates.pdf"
    output_filepath_table = f"{plots_dir}/subsets.txt"

    ##################################################


    # USE EMBEDDING MODEL TO ENCODE SONG DESCRIPTORS
    ##################################################
    # we use Sentence-BERT to embed song titles as vectors
    # https://github.com/UKPLab/sentence-transformers

    # do we need to generate the embeddings here?
    if (not exists(output_filepath_embeddings)) or args.reset:

        # update on progress
        logging.info("Computing Vector Embeddings.")

        # load in Sentence-BERT model
        model = SentenceTransformer(model_name_or_path = "all-MiniLM-L6-v2", device = device)

        # generate descriptors from which embeddings will be created
        with multiprocessing.Pool(processes = args.jobs) as pool:
            descriptors = list(pool.map(func = get_song_descriptor_from_index, iterable = dataset.index, chunksize = CHUNK_SIZE))

        # generate embeddings for each song descriptor
        embeddings = model.encode(sentences = descriptors,
                                  batch_size = args.batch_size,
                                  show_progress_bar = True,
                                  output_value = "sentence_embedding",
                                  device = device)
        del descriptors, model # free up memory

        # write embeddings to file for future use
        pd.DataFrame(data = embeddings).to_csv(path_or_buf = output_filepath_embeddings, sep = ",", header = False, index = False, mode = "w")

    # can we load them instead
    elif not exists(output_filepath):

        # update on progress
        logging.info("Loading Vector Embeddings.")

        # read in embeddings and turn into numpy array
        embeddings = pd.read_csv(filepath_or_buffer = output_filepath_embeddings, sep = ",", header = None, index_col = False).values

    ##################################################


    # CALCULATE MAGNITUDES OF EMBEDDINGS
    ##################################################

    # do we need to generate the magnitudes here?
    if (not exists(output_filepath_magnitudes)) or args.reset:

        # for calculating cosine similarity, calculate the magnitude of each song title vector embedding
        with multiprocessing.Pool(processes = args.jobs) as pool:
            magnitudes = np.array(list(pool.map(func = np.linalg.norm, iterable = tqdm(iterable = embeddings, desc = "Computing Embedding Magnitudes", total = len(embeddings)), chunksize = CHUNK_SIZE)))
        
        # write magnitudes to file for future use
        pd.DataFrame(data = magnitudes).to_csv(path_or_buf = output_filepath_magnitudes, sep = ",", header = False, index = False, mode = "w")

    # can we load them instead
    elif not exists(output_filepath):

        # update on progress
        logging.info("Loading Embedding Magnitudes.")

        # read in magnitudes and turn into numpy array
        magnitudes = pd.read_csv(filepath_or_buffer = output_filepath_magnitudes, sep = ",", header = None, index_col = False)[0].values    

    ##################################################


    # CALCULATE DEDUPLICATED DATASET
    ##################################################

    # do we need to generate the similarities here?
    if (not exists(output_filepath)) or args.reset:

        # GROUP TOGETHER SIMILAR SONG NAMES INTO A DICTIONARY
        ##################################################

        # move stuff to gpu for fast matrix operations
        embeddings = torch.from_numpy(embeddings).to(device)
        magnitudes = torch.from_numpy(magnitudes).to(device)
        
        # stores lists of indicies, where each list represents a song
        songs = []
        songs_already_grouped = set() # store indicies of songs that have already been placed in a group
        
        # group duplicates together, reading in similarities line by line
        for i in tqdm(iterable = range(len(dataset) - 1), desc = "Grouping Duplicates Together", total = len(dataset) - 1):

            # don't deal with songs that have already been grouped
            if i in songs_already_grouped:
                continue

            # calculate similarities
            similarities = torch.matmul(input = embeddings[(i + 1):], other = embeddings[i]) # calculate dot products (numerator of cosine similarity)
            similarities = similarities / (magnitudes[(i + 1):] * magnitudes[i]) # calculate cosine similarities
            similarities = (similarities + 1) / 2 # normalize

            # create a song group
            song = torch.where(similarities >= SIMILARITY_THRESHOLD)[0] + (i + 1) # get indicies of duplicates for the `i`th song, add `i` + 1 to account for the fact the matrix is a triangle
            song = list(filter(lambda index: index not in songs_already_grouped, song.tolist())) # remove indicies that have already been grouped with another song; not needed anymore, as this is done in similarity function calculations
            song.append(i) # a song is similar to itself

            # add song group to lists
            songs.append(song) # add song group to songs
            songs_already_grouped.update(song) # all these indicies have already been grouped

        # account for the last song, i.e. if it hasn't been grouped yet
        last_song_index = len(dataset) - 1
        if last_song_index not in songs_already_grouped:
            song = [last_song_index]
            songs.append(song)
            songs_already_grouped.update(song)
        
        # free up memory
        del similarities, song, songs_already_grouped, last_song_index

        ##################################################
        

        # ASSEMBLE DEDUPLICATED DATASET
        ##################################################

        # get deduplicated indicies
        logging.info("Choosing the Best Version of Each Song.") # update
        with multiprocessing.Pool(processes = args.jobs) as pool:
            deduplicated_indicies = list(pool.map(func = choose_best_song_from_indicies, iterable = songs, chunksize = CHUNK_SIZE))

        # dictionary mapping each path to its best version
        path_to_best_path = dict()
        for best_path, duplicate_path_indicies in zip(dataset.loc[deduplicated_indicies, "path"], songs):
            path_to_best_path.update({dataset.at[i, "path"]: best_path for i in duplicate_path_indicies})
        dataset["best_path"] = list(map(lambda path: path_to_best_path.get(path, None), dataset["path"]))
        dataset["is_best_path"] = (dataset["path"] == dataset["best_path"])

        # free up memory
        del deduplicated_indicies, path_to_best_path

        ##################################################


        # FOR EACH BEST PATH, THOUGH THE TITLE IS THE SAME, THERE COULD BE DIFFERENT ARRANGEMENTS
        ##################################################

        # set default values and a list of dataframes for each best path
        dataset["best_arrangement"] = dataset["path"]
        dataset["is_best_arrangement"] = True
        dataset["best_unique_arrangement"] = dataset["path"]
        dataset["is_best_unique_arrangement"] = True
                
        # find unique arrangements
        logging.info("Finding Unique Arrangements within Each Best Version.") # update
        with multiprocessing.Pool(processes = args.jobs) as pool:
            best_path_groups = list(pool.map(func = choose_unique_arrangements_from_indicies, iterable = songs, chunksize = CHUNK_SIZE))
        dataset = pd.concat(objs = best_path_groups, axis = 0, ignore_index = False) # regroup groups into dataframe
        
        # free up memory
        del songs, best_path_groups

        # write to file
        dataset = dataset.sort_index(axis = 0, ascending = True, na_position = "last", ignore_index = False) # sort indicies so they align with indicies in original dataset
        dataset[OUTPUT_COLUMNS].to_csv(path_or_buf = output_filepath, sep = ",", na_rep = utils.NA_STRING, header = True, index = False, mode = "w") # write to file

        # write combined dataset
        dataset[f"facet:{FACETS[0]}"] = True
        dataset[f"facet:{FACETS[1]}"] = dataset["is_rated"]
        dataset[f"facet:{FACETS[2]}"] = dataset["is_best_unique_arrangement"]
        dataset[f"facet:{FACETS[3]}"] = (dataset["is_rated"] & dataset["is_best_unique_arrangement"])
        dataset.to_csv(path_or_buf = output_filepath_merged, sep = ",", na_rep = utils.NA_STRING, header = True, index = False, mode = "w") # write to file

        ##################################################
    
    else:

        # LOAD IN ALREADY CALCULATED DATASET
        ##################################################

        # load in dataset
        dataset = pd.read_csv(filepath_or_buffer = output_filepath_merged, sep = ",", header = 0, index_col = False)

        ##################################################

    ##################################################
    

    # OUTPUT STATISTICS
    ##################################################

    # make necessary conversions
    for mmt_statistic_column in MMT_STATISTIC_COLUMNS[1:]:
        dataset[mmt_statistic_column] *= 100 # convert consistency columns to percentages

    # bar
    bar_width = 104 # how wide are the separation bars

    # output mmt statistics of real data facets
    float_formatter = lambda num: f"{num:.2f}"
    logging.info(f"\n{' MMT STATISTICS ':=^{bar_width}}\n")
    faceted = pd.concat(objs = list(map(lambda facet: dataset[dataset[f"facet:{facet}"]][MMT_STATISTIC_COLUMNS].assign(facet = facet), FACETS)), axis = 0)
    faceted = faceted.groupby(by = "facet").agg(["mean", "sem"])
    logging.info(faceted.to_string(float_format = float_formatter))
    
    # output latex table to file
    with open(output_filepath_table, "w") as output_file:
        table = pd.DataFrame(
            data = {
                "facet": list(map(make_facet_for_table, faceted.index)),
                "timesize": list(map(lambda facet: f"{round(sum(dataset.loc[dataset[f'facet:{facet}'], 'song_length.seconds']) / (60 * 60)):,} / {sum(dataset[f'facet:{facet}']) // 1000:,}K", faceted.index))
            }
        )
        for mmt_statistic in MMT_STATISTIC_COLUMNS:
            table[mmt_statistic] = list(map(lambda facet: f"{faceted.at[facet, (mmt_statistic, 'mean')]:.2f} $\pm$ {faceted.at[facet, (mmt_statistic, 'sem')]:.2f}", faceted.index))
            # significant_function = np.argmax if mmt_statistic != MMT_STATISTIC_COLUMNS[1] else np.argmin
            # i_significant = significant_function(faceted[(mmt_statistic, "mean")])
            # table.at[i_significant, mmt_statistic] = "\\bf{" + table.at[i_significant, mmt_statistic] + "}"
        for i in table.index:
            output_file.write(" & ".join(table.loc[i, :].values.tolist()) + " \\\\\n")
        output_file.write("\\midrule\n")
        fine_tuned = dataset[dataset[f"facet:{FACETS[-1]}"] & (dataset["rating"] > np.percentile(a = dataset.loc[dataset[f"facet:{FACETS[-1]}"], "rating"], q = 50))]
        output_file.write(" & ".join([
            "\\RaggedRight{{Fine-Tuning*}}",
            f"{round(sum(fine_tuned['song_length.seconds']) / (60 * 60)):,} / {len(fine_tuned) // 1000:,}K",
            ] + list(map(lambda mmt_statistic: f"{fine_tuned[mmt_statistic].mean():.2f} $\pm$ {fine_tuned[mmt_statistic].sem():.2f}", MMT_STATISTIC_COLUMNS))
            ) + " \\\\\n")
    logging.info(f"Saved table to {output_filepath_table}.")
    del fine_tuned, table, faceted

    # helper function to output statistics
    def output_statistics(rated_only: bool = False) -> None:
        """Helper function to output statistics."""

        # filter dataset if needed
        if rated_only:
            data = dataset[dataset["is_rated"]]
        else:
            data = dataset

        # update on how many unique arrangments
        n_best_paths = sum(data["is_best_path"])
        n_arrangements = sum(data["is_best_arrangement"])
        n_unique_arrangements = sum(data["is_best_unique_arrangement"])

        # log info
        title = "rated" if rated_only else "all"
        print(f"\n{f' {title} songs '.upper():=^{bar_width}}\n")
        word = " rated" if rated_only else ""
        logging.info(f"{len(data):,} total{word} songs.")
        logging.info(f"{n_best_paths:,} unique songs, excluding different instrumentations ({100 * (n_best_paths / len(data)):.2f}% of all{word} songs); {len(data) - n_best_paths:,} duplicates.")
        logging.info(f"{n_arrangements:,} unique songs, including different instrumentations ({100 * (n_arrangements / len(data)):.2f}% of all{word} songs); {len(data) - n_arrangements:,} duplicates.")
        logging.info(f"{n_unique_arrangements:,} unique arrangements ({100 * (n_unique_arrangements / len(data)):.2f}% of all{word} songs); {len(data) - n_unique_arrangements:,} duplicates.")
        
        # free up memory
        del n_best_paths, n_arrangements, n_unique_arrangements, title, word

    # output statistics
    output_statistics(rated_only = False)
    output_statistics(rated_only = True)
    print("\n" + "".join(("=" for _ in range(bar_width))) + "\n")

    # free up memory
    del bar_width

    ##################################################


    # MAKE A PLOT
    ##################################################

    if not exists(dirname(output_filepath_plot)): # make sure output directory exists
        os.mkdir(dirname(output_filepath_plot))

    # create plot
    fig, axes = plt.subplot_mosaic(mosaic = [["duplicates"]], constrained_layout = True, figsize = (4, 4))
    fig.suptitle("Deduplication", fontweight = "bold")

    # helper function to plot quantile plot
    percentile_step = 0.005
    def make_quantile_plot(rated_only: bool = False, apply_log_scale: bool = True) -> None:
        """
        Helper function to create a quantile plot.
        """

        # filter dataset if needed
        if rated_only:
            data = dataset[dataset["is_rated"]]
        else:
            data = dataset

        # get percentiles
        percentiles = np.arange(start = 0, stop = 100 + percentile_step, step = percentile_step)
        percentile_values = np.percentile(a = data.groupby(by = "best_unique_arrangement").size(), q = percentiles)

        # plot
        axes["duplicates"].plot(percentiles, percentile_values, label = "Rated" if rated_only else "All")
    
    # plot
    apply_log_scale = True
    make_quantile_plot(rated_only = False, apply_log_scale = apply_log_scale)
    make_quantile_plot(rated_only = True, apply_log_scale = apply_log_scale)
    axes["duplicates"].set_xlabel("Percentile (%)")
    axes["duplicates"].set_xlim(left = 50) # information below 50th percentile is unnecessary
    axes["duplicates"].set_ylabel("Number of Duplicates")
    if apply_log_scale:
        axes["duplicates"].set_yscale("log") # use log scale
        yticks = axes["duplicates"].get_yticks()
        axes["duplicates"].set_yticks(ticks = yticks, labels = list(map(lambda ytick: f"{int(ytick):,}", yticks)))
        axes["duplicates"].set_ylim(bottom = 0.8, top = 1000)
        del yticks # free up memory
    axes["duplicates"].grid()
    axes["duplicates"].legend()

    # save image
    fig.savefig(output_filepath_plot, dpi = 200, transparent = True, bbox_inches = "tight")
    logging.info(f"Saved figure to {output_filepath_plot}.")

    ##################################################

##################################################