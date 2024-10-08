# README
# Phillip Long
# July 23, 2024

# Analyze full dataset to see if there are differences between different facets.

# python /home/pnlong/model_musescore/wrangling/quality.py

# IMPORTS
##################################################

import argparse
import pandas as pd
from typing import Union, List
from utils import rep
from os.path import exists, dirname
from os import mkdir
import matplotlib.pyplot as plt
import logging

from os.path import dirname, realpath
import sys
sys.path.insert(0, dirname(realpath(__file__)))
sys.path.insert(0, dirname(dirname(realpath(__file__))))

from full import MMT_STATISTIC_COLUMNS, DATASET_DIR_NAME, OUTPUT_DIR

plt.style.use("default")
# plt.rcParams["font.family"] = "serif"
# plt.rcParams["mathtext.fontset"] = "dejavuserif"

##################################################


# CONSTANTS
##################################################

PLOTS_DIR_NAME = "plots"

RATING_ROUND_TO_THE_NEAREST = 0.05 # round to the nearest n-th to discretize ratings

##################################################


# HELPER FUNCTIONS
##################################################

def discretize_rating(rating: float) -> float:
    """
    Given the rating, convert into a more discrete version.
    """

    # deal with the no rating case
    if rating == 0:
        return 0.0
    
    # round to the nearest 1/5
    return RATING_ROUND_TO_THE_NEAREST * round(rating / RATING_ROUND_TO_THE_NEAREST)

# make facet name fancy
make_facet_name_fancy = lambda facet: facet.title().replace("_", " and ")

##################################################


# GROUP DATASET BY SOME FACET
##################################################

# group dataset by a certain column(s) to see differences in data quality
def group_by(df: pd.DataFrame, by: Union[str, List[str]]) -> pd.DataFrame:
    """
    Function to help facilitate testing differences in data quality by various facets
    """

    # only select relevant columns
    if isinstance(by, str):
        by = [by]
    df = df[by + MMT_STATISTIC_COLUMNS]

    # get sizes by group
    sizes = df.groupby(by = by).size().to_frame(name = "n")
    sizes["fraction"] = sizes["n"] / sum(sizes["n"])

    # perform groupby
    agg_dict = dict(zip(MMT_STATISTIC_COLUMNS, rep(x = ["mean", "sem"], times = len(MMT_STATISTIC_COLUMNS))))
    df = df.groupby(by = by).agg(agg_dict)
    df[sizes.columns] = sizes

    # remove nested parts from index
    if (len(by) > 1):
        by_string = ", ".join(by)
        df[by_string] = list(map(lambda *args: ", ".join((str(arg) for arg in args[0])), df.index))
        df = df.set_index(keys = by_string, drop = True)

    # sort indicies
    df = df.sort_index(ascending = False)

    # return df
    return df

##################################################


# ARGUMENTS
##################################################

def parse_args(args = None, namespace = None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(prog = "Analyze Dataset", description = "Analyze full dataset for music-quality differences within variables.")
    parser.add_argument("-df", "--dataset_filepath", type = str, default = f"{OUTPUT_DIR}/{DATASET_DIR_NAME}.csv", help = "Filepath to full dataset.")
    parser.add_argument("-b", "--by", action = "store", type = str, nargs = "+", help = "Variable(s) on which to facet.")
    return parser.parse_args(args = args, namespace = namespace)

##################################################


# MAIN METHOD
##################################################

if __name__ == "__main__":

    # SET UP
    ##################################################

    # parse arguments
    args = parse_args()

    # set up logging
    logging.basicConfig(level = logging.INFO, format = "%(message)s")
    bar_width = 100

    ##################################################


    # LOAD DATASET, ARRANGE
    ##################################################

    # load in dataset
    dataset = pd.read_csv(filepath_or_buffer = args.dataset_filepath, sep = ",", header = 0, index_col = False)

    # some value checking
    for by in args.by:
        if by not in dataset.columns:
            raise KeyError(f"Invalid `by` argument \"{by}\". Must be a column in {args.dataset_filepath}.")

    # deal with ratings column
    dataset["rating"] = list(map(discretize_rating, dataset["rating"]))

    ##################################################


    # PRINT DATA TABLES
    ##################################################

    # group datasets by arguments
    df = {
        "all": group_by(df = dataset, by = args.by), # get all songs dataset
        "deduplicated": group_by(df = dataset[dataset["facet:deduplicated"]], by = args.by), # get deduplicated dataset
    }

    # output info
    for key in df.keys():
        logging.info(f"\n{f' {key} songs '.upper():=^{bar_width}}\n") # title
        logging.info(df[key].to_string()) # data frame
    logging.info("\n" + "".join("=" for _ in range(bar_width)) + "\n") # extra bar

    ##################################################


    # MAKE PLOT
    ##################################################

    # determine string for how to refer the facet
    facet_name = df["all"].index.name
    facet_name_fancy = make_facet_name_fancy(facet = facet_name)

    # create plot
    fig, axes = plt.subplot_mosaic(mosaic = [list(map(lambda column: f"{column}.{key}", MMT_STATISTIC_COLUMNS)) for key in df.keys()], constrained_layout = True, figsize = (12, 8))
    plt.set_loglevel("WARNING")
    fig.suptitle(facet_name_fancy)
    margin_proportion = 0.2 # what fraction of the range do we extend on both sides

    for key in df.keys():

        # get current data frame
        data = df[key]
        y_values = list(map(str, data.index))

        # make plots
        for mmt_statistic_column in MMT_STATISTIC_COLUMNS:

            # variables
            statistic_fancy = " ".join(mmt_statistic_column.split("_")).title() # stylize the name of the mmt statistic
            column = f"{mmt_statistic_column}.{key}" # axes name

            # little bit of data wrangling
            data_mmt_statistic = data[mmt_statistic_column]
            # data_mmt_statistic = data_mmt_statistic[~pd.isna(data_mmt_statistic["sem"])] # no na values

            # plot
            axes[column].barh(y = y_values, width = data_mmt_statistic["mean"], color = "tab:blue")
            axes[column].errorbar(x = data_mmt_statistic["mean"], y = y_values, xerr = data_mmt_statistic["sem"], fmt = "o", color = "tab:red")            

            # y and x axis labels
            if mmt_statistic_column == MMT_STATISTIC_COLUMNS[0]:
                axes[column].set_ylabel(facet_name_fancy)
            else:
                axes[column].sharey(other = axes[f"{MMT_STATISTIC_COLUMNS[0]}.{key}"])
            axes[column].set_xlabel(statistic_fancy)

            # add margin
            min_val, max_val = min(data_mmt_statistic["mean"] - data_mmt_statistic["sem"]), max(data_mmt_statistic["mean"] + data_mmt_statistic["sem"])
            margin = margin_proportion * (max_val - min_val)
            axes[column].set_xlim(left = min_val - margin, right = max_val + margin)

            # add title (if necessary) and grid
            if mmt_statistic_column == MMT_STATISTIC_COLUMNS[1]:
                axes[column].set_title(f"\n{key.title()} Songs\n", fontweight = "bold")
            axes[column].grid()

        # rotate y-axis ticks if necessary
        # if (facet_name.count(", ") > 0):
        #    for key in df.keys():
        #        for mmt_statistic_column in MMT_STATISTIC_COLUMNS:
        #           column = f"{mmt_statistic_column}.{key}"
        #           axes[column].set_yticks(axes[column].get_xticks())
        #           axes[column].set_yticklabels(axes[column].get_xticklabels(), rotation = 20, ha = "right")

    # save image
    output_filepath = f"{dirname(args.dataset_filepath)}/{PLOTS_DIR_NAME}/{df['all'].index.name.replace(', ', '-')}.pdf" # get output filepath
    if not exists(dirname(output_filepath)): # make sure output directory exists
        mkdir(dirname(output_filepath))
    fig.savefig(output_filepath, dpi = 200, transparent = True, bbox_inches = "tight")
    logging.info(f"Saved figure to {output_filepath}.\n")

    ##################################################

##################################################
