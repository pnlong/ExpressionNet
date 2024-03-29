# README
# Phillip Long
# October 16, 2023

# Make plots that describe expressive features in musescore files.

# python /home/pnlong/model_musescore/expressive_features_plots.py


# IMPORTS
##################################################

import pickle
import multiprocessing
from os.path import exists
from os import makedirs
from tqdm import tqdm
from time import perf_counter, strftime, gmtime
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
from typing import Tuple
import numpy as np
import argparse
import logging
from parse_mscz import TIME_IN_SECONDS_COLUMN_NAME
from parse_mscz_plots import OUTPUT_DIR, OUTPUT_RESOLUTION_DPI
from read_mscz.music import DIVIDE_BY_ZERO_CONSTANT
from utils import rep, split_camel_case

plt.style.use("bmh")

##################################################


# CONSTANTS
##################################################

INPUT_FILEPATH = "/data2/pnlong/musescore/expressive_features/expressive_features.csv"
FILE_OUTPUT_DIR = "/data2/pnlong/musescore/expressive_features"
NA_VALUE = "NA"

LARGE_PLOTS_DPI = int(1.5 * OUTPUT_RESOLUTION_DPI)

# columns of data tables
DENSITY_COLUMNS = ["path", "time_steps", "seconds", "bars", "beats"]
FEATURE_TYPES_SUMMARY_COLUMNS = ["path", "type", "size"]
SPARSITY_SUCCESSIVE_SUFFIX = "_successive"
SPARSITY_COLUMNS = ["path", "type", "value", "time_steps", "seconds", "beats", "fraction"]
SPARSITY_COLUMNS += [column + SPARSITY_SUCCESSIVE_SUFFIX for column in SPARSITY_COLUMNS[SPARSITY_COLUMNS.index("time_steps"):]]
DISTANCE_COLUMNS = SPARSITY_COLUMNS[SPARSITY_COLUMNS.index("time_steps"):SPARSITY_COLUMNS.index("time_steps" + SPARSITY_SUCCESSIVE_SUFFIX)]
SUCCESSIVE_DISTANCE_COLUMNS = [distance_column + SPARSITY_SUCCESSIVE_SUFFIX for distance_column in DISTANCE_COLUMNS]

##################################################


# ARGUMENTS
##################################################

def parse_args(args = None, namespace = None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(prog = "Expressive Feature Figures", description = "Make plots describing expressive features in MuseScore dataset.")
    parser.add_argument("-i", "--input_filepath", type = str, default = INPUT_FILEPATH, help = "CSV File with expressive feature information generated by parse_mscz.py")
    parser.add_argument("-f", "--file_output_dir", type = str, default = FILE_OUTPUT_DIR, help = "Where to store data tables created for the plots")
    parser.add_argument("-o", "--output_dir", type = str, default = OUTPUT_DIR, help = "Output directory") 
    parser.add_argument("-j", "--jobs", type = int, default = int(multiprocessing.cpu_count() / 4), help = "Number of Jobs")
    return parser.parse_args(args = args, namespace = namespace)

##################################################


# HELPER FUNCTION FOR INFO EXTRACTION
##################################################
# helper function to calculate difference between successive rows
def calculate_difference_between_successive_entries(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    """Calculates the difference between successive features."""
    df = df.copy().sort_values(by = columns[0]) # sort values
    df_values = df[columns] # store values of columns
    for column in columns: # for every column in columns
        df[column] = rep(x = np.nan, times = len(df)) # set columns' values to None
    df_indicies = df.index
    for i in range(len(df_indicies) - 1): # loop through entries
        for column in columns: # calculate for each column
            df.at[df_indicies[i], column] = df_values.at[df_indicies[i + 1], column] - df_values.at[df_indicies[i], column] # calculate differences
    return df
##################################################


# GIVEN PICKLE PATH, EXTRACT INFO
##################################################

def extract_information(path: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Given a path to a pickled expressive-feature information file, extract some information on said file.

    what kinds of expressive text are present?
    what is the relative distance between successive expression markings (both in notes and in seconds)?
      - if markings are relatively dense we can sub select sequences
      - if they're sparse than it really depends on what kinds of expression they are

    """

    # OPEN PICKLE FILE, DO NECESSARY WRANGLING
    ##################################################

    # unpickle
    try:
        with open(path, "rb") as pickle_file:
            unpickled = pickle.load(file = pickle_file)
    except (OSError):
        return None
    
    # extract expressive features dataframe
    expressive_features = unpickled.pop("expressive_features")

    # wrangle expressive features
    expressive_features["type"] = expressive_features["type"].apply(lambda expressive_feature_type: expressive_feature_type.replace("Spanner", ""))

    ##################################################

    
    # CALCULATE DENSITY OF EXPRESSIVE FEATURES
    ##################################################

    density = {time_unit: (song_length_in_time_unit / len(expressive_features)) for time_unit, song_length_in_time_unit in unpickled["track_length"].items()} # time unit per expressive feature
    density["path"] = path
    density = pd.DataFrame(data = [density], columns = DENSITY_COLUMNS)
    density.to_csv(path_or_buf = list(PLOT_DATA_OUTPUT_FILEPATHS.values())[0], sep = ",", na_rep = NA_VALUE, header = False, index = False, mode = "a")

    ##################################################


    # SUMMARIZE TYPES OF TEXT/FEATURES PRESENT
    ##################################################

    feature_types_summary = expressive_features[["type", "value"]].groupby(by = "type").size().reset_index(drop = False).rename(columns = {0: FEATURE_TYPES_SUMMARY_COLUMNS[-1]}) # group by type
    feature_types_summary["path"] = rep(x = path, times = len(feature_types_summary))
    feature_types_summary = feature_types_summary[FEATURE_TYPES_SUMMARY_COLUMNS] # ensure we have just the columns we need
    feature_types_summary.to_csv(path_or_buf = list(PLOT_DATA_OUTPUT_FILEPATHS.values())[1], sep = ",", na_rep = NA_VALUE, header = False, index = False, mode = "a")

    ##################################################


    # RELATIVE DISTANCE BETWEEN SUCCESSIVE MARKINGS
    ##################################################

    # add some columns, set up for calculation of distance
    sparsity = expressive_features[["type", "value", "time", TIME_IN_SECONDS_COLUMN_NAME]]
    sparsity = sparsity.rename(columns = {"time": "time_steps", TIME_IN_SECONDS_COLUMN_NAME: "seconds"})
    sparsity["path"] = rep(x = path, times = len(sparsity))
    sparsity["beats"] = sparsity["time_steps"] / unpickled["resolution"]
    sparsity["fraction"] = sparsity["time_steps"] / (unpickled["track_length"]["time_steps"] + DIVIDE_BY_ZERO_CONSTANT)
    for successive_distance_column, distance_column in zip(SUCCESSIVE_DISTANCE_COLUMNS, DISTANCE_COLUMNS): # add successive times columns
        sparsity[successive_distance_column] = sparsity[distance_column]
    sparsity = sparsity[SPARSITY_COLUMNS].sort_values("time_steps").reset_index(drop = True) # sort by increasing times

    # calculate distances
    sparsity = calculate_difference_between_successive_entries(df = sparsity, columns = DISTANCE_COLUMNS)
    expressive_feature_types = pd.unique(expressive_features["type"]) # get types of expressive features
    distance = pd.DataFrame(columns = SPARSITY_COLUMNS)
    for expressive_feature_type in expressive_feature_types: # get distances between successive features of the same type
        distance_for_expressive_feature_type = calculate_difference_between_successive_entries(df = sparsity[sparsity["type"] == expressive_feature_type], columns = SUCCESSIVE_DISTANCE_COLUMNS) # calculate sparsity for certain feature type
        distance = pd.concat(objs = (distance, distance_for_expressive_feature_type), axis = 0, ignore_index = False) # append to overall distance
    distance = distance.sort_index(axis = 0) # sort by index (return to original index)
    distance.to_csv(path_or_buf = list(PLOT_DATA_OUTPUT_FILEPATHS.values())[2], sep = ",", na_rep = NA_VALUE, header = False, index = False, mode = "a")

    ##################################################
    
    return density, feature_types_summary, distance

##################################################


# DENSITY
##################################################

def make_density_plot(input_filepath: str, output_filepath: str) -> None:

    relevant_density_types = ["seconds", "bars", "beats"]

    # create figure
    fig, axes = plt.subplot_mosaic(mosaic = list(map(list, zip(relevant_density_types))), constrained_layout = True, figsize = (8, 8))
    density = pd.read_csv(filepath_or_buffer = input_filepath, sep = ",", header = 0, index_col = False)
    fig.suptitle(f"Expressive Feature [EF] Densities in Public-Domain Tracks ({len(density):,} total)", fontweight = "bold")

    # create plot
    n_bins = 50
    relevant_ranges = {relevant_density_types[0]: (0, 100), relevant_density_types[1]: (0, 40), relevant_density_types[2]: (0, 100)}
    for i in range(len(relevant_density_types) - 1, -1, -1): # traverse backwards
        relevant_density_type = relevant_density_types[i]
        n_points_excluded = len(density[~((density[relevant_density_type] >= relevant_ranges[relevant_density_type][0]) & (density[relevant_density_type] <= relevant_ranges[relevant_density_type][1]))])
        axes[relevant_density_type].hist(x = density[relevant_density_type], bins = n_bins, range = relevant_ranges[relevant_density_type], orientation = "horizontal", log = False) # , color = COLORS[i], edgecolor = "0"
        axes[relevant_density_type].set_ylabel(relevant_density_type.title())
        axes[relevant_density_type].set_title(f"{relevant_density_type.title()} per EF ({n_points_excluded:,} excluded tracks)")
        axes[relevant_density_type].get_xaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda count, _: f"{int(count):,}"))
        if i < len(relevant_density_types) - 1: # remove x axis stuff for top 2 columns
            axes[relevant_density_type].sharex(axes[relevant_density_types[-1]])
        else:
            axes[relevant_density_type].set_xlabel("Count")
    
    # remove x axis for upper plots
    # for relevant_density_type in relevant_density_types[:-1]:
    #     axes[relevant_density_type].set_xticks([])
    #     axes[relevant_density_type].set_xticklabels([])

    # save image
    fig.savefig(output_filepath, dpi = OUTPUT_RESOLUTION_DPI) # save image
    logging.info(f"Density plot saved to {output_filepath}.")

    # clear up memory
    del density

    # return none
    return None

##################################################


# SUMMARIZE FEATURE TYPES PRESENT
##################################################

def make_summary_plot(input_filepath: str, output_filepath: str) -> list:

    plot_types = ("total", "mean", "median")

    # create figure
    fig, axes = plt.subplot_mosaic(mosaic = [list(plot_types)], constrained_layout = True, figsize = (12, 8))
    fig.suptitle("Summary of Present Expressive Features", fontweight = "bold")

    # load in table
    summary = pd.read_csv(filepath_or_buffer = input_filepath, sep = ",", header = 0, index_col = False).drop(columns = "path")
    # summary = summary[summary["type"] != "TimeSignature"] # exclude time signatures
    summary = {
        plot_types[0]: summary.groupby(by = "type").sum().reset_index().rename(columns = {"index": "type"}).sort_values(by = "size"),
        plot_types[1]: summary.groupby(by = "type").mean().reset_index().rename(columns = {"index": "type"}).sort_values(by = "size"),
        plot_types[2]: summary.groupby(by = "type").median().reset_index().rename(columns = {"index": "type"}).sort_values(by = "size")
        }
    # summary[plot_types[0]]["size"] = summary[plot_types[0]]["size"].apply(lambda count: np.log10(count + DIVIDE_BY_ZERO_CONSTANT)) # apply log scale to total count

    # create plot
    for i, plot_type in enumerate(plot_types):
        # axes[plot_type].xaxis.grid(True)
        axes[plot_type].barh(y = summary[plot_type]["type"], width = summary[plot_type]["size"]) # , color = COLORS[i], edgecolor = "0"
        axes[plot_type].set_title(f"{plot_type.title()}")
        axes[plot_type].ticklabel_format(axis = "x", style = "scientific", scilimits = (-1, 3))
        if i == 0: # if the left most plot
            axes[plot_type].set_xlabel(f"{plot_type.title()} Count")
            axes[plot_type].set_ylabel("Expressive Feature")
            axes[plot_type].set_yticks(axes[plot_type].get_yticks())
            axes[plot_type].set_yticklabels(axes[plot_type].get_yticklabels(), rotation = 30)
        else:
            axes[plot_type].set_xlabel(f"{plot_type.title()} Amount per Track")
            # axes[plot_type].sharey(axes[plot_types[0]]) # sharey makes it so we cant remove axis ticks and labels
            axes[plot_type].set_yticks([])
            axes[plot_type].set_yticklabels([])        

    # save image
    fig.savefig(output_filepath, dpi = OUTPUT_RESOLUTION_DPI) # save image
    logging.info(f"Summary plot saved to {output_filepath}.")

    # return the order from most common to least
    return summary[plot_types[0]]["type"].tolist()

##################################################


# SHOW SPARSITY OF EXPRESSIVE FEATURES
##################################################

def make_sparsity_plot(input_filepath: str, output_filepath_prefix: str, expressive_feature_types: list, apply_log_percentiles_by_feature: bool = True, apply_log_histogram: bool = True, apply_log_percentiles_by_type: bool = True) -> None:

    # hyper parameters
    relevant_time_units = ["beats", "seconds"]
    relevant_time_units_suffix = [relevant_time_unit + SPARSITY_SUCCESSIVE_SUFFIX for relevant_time_unit in relevant_time_units]
    plot_types = ["total", "mean", "median"]
    output_filepaths = [f"{output_filepath_prefix}.{suffix}.png" for suffix in ("percentiles", "histograms", "percentiles2")]

    # we have distances between successive expressive features in time_steps, beats, seconds, and as a fraction of the length of the song
    sparsity = pd.read_csv(filepath_or_buffer = input_filepath, sep = ",", header = 0, index_col = False)
    # sparsity = sparsity.drop(index = sparsity.index[-1]) # last row is None, since there is no successive expressive features, so drop it
    sparsity = sparsity.drop(columns = "value") # we don't need this column

    # calculate percentiles, save in pickle
    all_features_type_name = "AllFeatures" # name of all features plot name
    expressive_feature_types.insert(0, all_features_type_name) # add a plot for all expressive features
    step = 0.001
    percentiles = np.arange(start = 0, stop = 100 + step, step = step)
    pickle_output = input_filepath.split(".")[0] + "_percentiles.pickle"
    if not exists(pickle_output):

        # helper function to calculate various percentiles
        def calculate_percentiles(df: pd.DataFrame, columns: list) -> tuple:
            n = len(df) # get number of points
            df = df[~pd.isna(df[columns[0]])] # filter out NA values
            df = df[["path"] + columns] # filter down to only necessary columns
            out_columns = [column.replace(SPARSITY_SUCCESSIVE_SUFFIX, "") for column in columns] # get rid of suffix if necessary
            out = dict(zip(plot_types, rep(x = pd.DataFrame(columns = out_columns), times = len(plot_types)))) # create output dataframe
            for plot_type in plot_types:
                if plot_type == "mean":
                    df_temp = df.groupby(by = "path").mean()
                elif plot_type == "median":
                    df_temp = df.groupby(by = "path").median()
                else:
                    df_temp = df
                for column, out_column in zip(columns, out_columns):
                    out[plot_type][out_column] = np.percentile(a = df_temp[column], q = percentiles)
            return (out, n)
        percentile_values = {
            expressive_feature_type: calculate_percentiles(
                df = sparsity[sparsity["type"] == expressive_feature_type],
                columns = relevant_time_units_suffix
                ) 
                for expressive_feature_type in tqdm(iterable = [eft for eft in expressive_feature_types if eft != all_features_type_name], desc = "Calculating Sparsity Percentiles")
            }
        percentile_values[all_features_type_name] = calculate_percentiles(df = sparsity, columns = relevant_time_units)
    
        # save to pickle file
        with open(pickle_output, "wb") as pickle_file:
            pickle.dump(obj = percentile_values, file = pickle_file, protocol = pickle.HIGHEST_PROTOCOL)

    else: # if the pickle already exists, reload it
        with open(pickle_output, "rb") as pickle_file:
            percentile_values = pickle.load(file = pickle_file)

    # create figure of percentiles (faceted by expressive_feature)
    use_twin_axis_percentiles = False
    n_cols = 5
    plot_mosaic = [expressive_feature_types[i:i + n_cols] for i in range(0, len(expressive_feature_types), n_cols)] # create plot grid
    if len(plot_mosaic[-1]) < len(plot_mosaic[-2]):
        plot_mosaic[-1] += rep(x = "legend", times = (len(plot_mosaic[-2]) - len(plot_mosaic[-1])))
    is_bottom_plot = lambda expressive_feature_type: expressive_feature_types.index(expressive_feature_type) >= len(expressive_feature_types) - n_cols
    is_left_plot = lambda expressive_feature_type: expressive_feature_types.index(expressive_feature_type) % n_cols == 0
    fig, axes = plt.subplot_mosaic(mosaic = plot_mosaic, constrained_layout = True, figsize = (24, 16))
    fig.suptitle("Sparsity of Expressive Features", fontweight = "bold")
    # create percentile plot
    for expressive_feature_type in expressive_feature_types:
        if use_twin_axis_percentiles:
            percentile_right_axis = axes[expressive_feature_type].twinx() # create twin x
        for i, plot_type in enumerate(plot_types): # plot lines
            percentiles_values_current = percentile_values[expressive_feature_type][0][plot_type].sort_values(by = relevant_time_units[0])
            if apply_log_percentiles_by_feature: # apply log function
                for column in relevant_time_units:
                    logging.debug(f"{expressive_feature_type}:{column}:{sum(percentiles_values_current[column] < 0)}-{100 * (sum(percentiles_values_current[column] < 0) / len(percentiles)):.2f}%")
                    percentiles_values_current[column] = np.log10(abs(percentiles_values_current[column]) + DIVIDE_BY_ZERO_CONSTANT)
            axes[expressive_feature_type].plot(percentiles, percentiles_values_current[relevant_time_units[0]], label = plot_type.title()) # , color = LINE_COLORS[i], linestyle = LINESTYLES[i]
            if use_twin_axis_percentiles:
                percentile_right_axis.plot(percentiles, percentiles_values_current[relevant_time_units[1]], label = plot_type.title()) # , color = LINE_COLORS[i], linestyle = LINESTYLES[i]
        if is_left_plot(expressive_feature_type = expressive_feature_type) or use_twin_axis_percentiles:
            axes[expressive_feature_type].set_ylabel(f"log({relevant_time_units[0].title()})" if apply_log_percentiles_by_feature else f"{relevant_time_units[0].title()}")
            axes[expressive_feature_type].get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda count, _: f"{int(count):,}")) # add commas
        else:
            axes[expressive_feature_type].sharey(axes[expressive_feature_types[int(expressive_feature_types.index(expressive_feature_type) / n_cols)]])
            axes[expressive_feature_type].set_yticklabels([])
        if use_twin_axis_percentiles:
            percentile_right_axis.set_ylabel(f"log({relevant_time_units[1].title()})" if apply_log_percentiles_by_feature else f"{relevant_time_units[1].title()}") # add
            percentile_right_axis.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda count, _: f"{int(count):,}")) # add commas
        if is_bottom_plot(expressive_feature_type = expressive_feature_type): # if bottom plot, add x labels
            axes[expressive_feature_type].set_xlabel("Percentile (%)")
        else: # is not a bottom plot
            # axes[expressive_feature_type].set_xticks([]) # will keep xticks for now
            axes[expressive_feature_type].set_xticklabels([])
        axes[expressive_feature_type].set_title(f"{split_camel_case(string = expressive_feature_type, sep = ' ').title()} (n = {percentile_values[expressive_feature_type][1]:,})")
        # axes[expressive_feature_type].grid() # add gridlines
    # add a legend
    handles, labels = axes[expressive_feature_types[0]].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    axes["legend"].legend(handles = by_label.values(), labels = by_label.keys(), loc = "center", fontsize = "x-large", title_fontsize = "xx-large", alignment = "center", mode = "expand", title = "Type")
    axes["legend"].axis("off")
    # save image
    fig.savefig(output_filepaths[0], dpi = LARGE_PLOTS_DPI) # save image
    logging.info(f"Sparsity Percentiles plot saved to {output_filepaths[0]}.")

    # create new plot of histograms
    use_twin_axis_histogram = False
    n_bins = 15
    histogram_range = (0, 256) # in beats
    histogram_colors = ("#0004FF", "#FFF400", "#C90000")
    fig, axes = plt.subplot_mosaic(mosaic = plot_mosaic, constrained_layout = True, figsize = (24, 16))
    fig.suptitle("Sparsity of Expressive Features", fontweight = "bold")
    # create histogram plot
    for expressive_feature_type in expressive_feature_types:
        if use_twin_axis_histogram:
            histogram_right_axis = axes[expressive_feature_type].twinx() # create twin x
        histogram_values = sparsity[["path"] + relevant_time_units] if expressive_feature_type == all_features_type_name else sparsity[sparsity["type"] == expressive_feature_type][["path"] + relevant_time_units_suffix].rename(columns = dict(zip(relevant_time_units_suffix, relevant_time_units))) # get subset of sparsity
        histogram_values_current = dict(zip(relevant_time_units, rep(x = dict(zip(plot_types, rep(x = [], times = len(plot_types)))), times = len(relevant_time_units))))
        for i, plot_type in enumerate(plot_types): # plot lines
            histogram_values_current_current = histogram_values
            if plot_type == "mean":
                histogram_values_current_current = histogram_values.groupby(by = "path").mean()
            elif plot_type == "median":
                histogram_values_current_current = histogram_values.groupby(by = "path").median()
            for relevant_time_unit in relevant_time_units:
                histogram_values_current[relevant_time_unit][plot_type] = list(filter(lambda value: value >= histogram_range[0] and value <= histogram_range[1], histogram_values_current_current[relevant_time_unit].tolist())) # extract list
        axes[expressive_feature_type].hist(histogram_values_current[relevant_time_units[0]].values(), bins = n_bins, orientation = "horizontal", histtype = "bar", log = apply_log_histogram, label = [plot_type.title() for plot_type in plot_types], linewidth = 0.5) # plot , color = histogram_colors[:len(plot_types)], edgecolor = "0"
        if use_twin_axis_histogram:
            histogram_right_axis.hist(histogram_values_current[relevant_time_units[1]].values(), bins = n_bins, orientation = "horizontal", histtype = "bar", log = apply_log_histogram, label = [plot_type.title() for plot_type in plot_types], linewidth = 0.5) # plot , color = histogram_colors[:len(plot_types)], edgecolor = "0"
        axes[expressive_feature_type].set_ylabel(relevant_time_units[0].title())
        axes[expressive_feature_type].get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda count, _: f"{int(count):,}")) # add commas
        if use_twin_axis_histogram:
            histogram_right_axis.set_ylabel(relevant_time_units[1].title())
            histogram_right_axis.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda count, _: f"{int(count):,}")) # add commas
        if is_bottom_plot(expressive_feature_type = expressive_feature_type):
            axes[expressive_feature_type].set_xlabel("Count")
        axes[expressive_feature_type].get_xaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda count, _: "$10^{" + str(int(np.log10(count))) + "}$" if int(np.log10(count)) >= 3 and apply_log_histogram else f"{int(count):,}")) # add commas
        # axes[expressive_feature_type].set_xticks(axes[expressive_feature_type].get_xticks())
        # axes[expressive_feature_type].set_xticklabels(axes[expressive_feature_type].get_xticklabels(), rotation = 0)
        axes[expressive_feature_type].set_title(f"{split_camel_case(string = expressive_feature_type, sep = ' ').title()} (n = {percentile_values[expressive_feature_type][1]:,})")
        # axes[expressive_feature_type].grid() # add gridlines
    # add a legend
    handles, labels = axes[expressive_feature_types[0]].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    axes["legend"].legend(handles = by_label.values(), labels = by_label.keys(), loc = "center", fontsize = "x-large", title_fontsize = "xx-large", alignment = "center", mode = "expand", title = "Type")
    axes["legend"].axis("off")
    # save image
    fig.savefig(output_filepaths[1], dpi = LARGE_PLOTS_DPI) # save image
    logging.info(f"Sparsity Histogram plot saved to {output_filepaths[1]}.")

    # new plot of percentiles on different facets (by plot type)
    use_twin_axis_percentiles = False
    n_rows = 2
    n_cols = int(((len(plot_types) - 1) / n_rows)) + 1
    plot_mosaic = [plot_types[i:i + n_cols] for i in range(0, len(plot_types), n_cols)] # create plot grid
    if len(plot_mosaic[-1]) < len(plot_mosaic[-2]):
        plot_mosaic[-1] += rep(x = "legend", times = (len(plot_mosaic[-2]) - len(plot_mosaic[-1])))
    else:
        for i in range(len(plot_mosaic)):
            plot_mosaic[i].append("legend")
    is_bottom_plot = lambda plot_type: plot_types.index(plot_type) >= len(plot_types) - n_cols
    is_left_plot = lambda plot_type: plot_types.index(plot_type) % n_cols == 0
    fig, axes = plt.subplot_mosaic(mosaic = plot_mosaic, constrained_layout = True, figsize = (8, 8))
    fig.suptitle("Sparsity of Expressive Features", fontweight = "bold")
    # create percentile plot
    for plot_type in plot_types:
        if use_twin_axis_percentiles:
            percentile_right_axis = axes[plot_type].twinx() # create twin x
        for i, expressive_feature_type in enumerate(expressive_feature_types):
            percentiles_values_current = percentile_values[expressive_feature_type][0][plot_type].sort_values(by = relevant_time_units[0])
            if apply_log_percentiles_by_type: # apply log function
                for column in relevant_time_units:
                    logging.debug(f"{expressive_feature_type}:{column}:{sum(percentiles_values_current[column] < 0)}-{100 * (sum(percentiles_values_current[column] < 0) / len(percentiles)):.2f}%")
                    percentiles_values_current[column] = np.log10(abs(percentiles_values_current[column]) + DIVIDE_BY_ZERO_CONSTANT)
            axes[plot_type].plot(percentiles, percentiles_values_current[relevant_time_units[0]], label = expressive_feature_type) # , color = LINE_COMBINATIONS[i][0], linestyle = LINE_COMBINATIONS[i][1]
            if use_twin_axis_percentiles:
                percentile_right_axis.plot(percentiles, percentiles_values_current[relevant_time_units[1]], label = expressive_feature_type) # , color = LINE_COMBINATIONS[i][0], linestyle = LINE_COMBINATIONS[i][1]
        if is_left_plot(plot_type = plot_type) or use_twin_axis_percentiles:
            axes[plot_type].set_ylabel(f"log({relevant_time_units[0].title()})" if apply_log_percentiles_by_type else f"{relevant_time_units[0].title()}")
            axes[plot_type].get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda count, _: f"{int(count):,}")) # add commas
        else:
            axes[plot_type].sharey(axes[plot_types[int(plot_types.index(plot_type) / 2)]])
            axes[plot_type].set_yticklabels([])
        if use_twin_axis_percentiles:
            percentile_right_axis.set_ylabel(f"log({relevant_time_units[1].title()})" if apply_log_percentiles_by_type else f"{relevant_time_units[1].title()}") # add
            percentile_right_axis.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda count, _: f"{int(count):,}")) # add commas
        if is_bottom_plot(plot_type = plot_type): # if bottom plot, add x labels
            axes[plot_type].set_xlabel("Percentile (%)")
        else: # is not a bottom plot
            # axes[plot_type].set_xticks([]) # will keep xticks for now
            axes[plot_type].set_xticklabels([])
        axes[plot_type].set_title(plot_type.title())
        # axes[plot_type].grid() # add gridlines
    
    # add a legend
    handles, labels = axes[plot_types[0]].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    axes["legend"].legend(handles = by_label.values(), labels = list(map(lambda expressive_feature_type: split_camel_case(string = expressive_feature_type, sep = " ").title(), by_label.keys())), loc = "center", fontsize = "medium", title_fontsize = "large", alignment = "center", ncol = 2, title = "Expressive Feature", mode = "expand")
    axes["legend"].axis("off")
    # save image
    fig.savefig(output_filepaths[2], dpi = LARGE_PLOTS_DPI) # save image
    logging.info(f"Second Sparsity Percentiles plot saved to {output_filepaths[2]}.")

    # clear up some memory
    del sparsity

    # return nothing
    return None

##################################################


# MAIN CLASS FOR MULTIPROCESSING
##################################################

if __name__ == "__main__":

    # CONSTANTS
    ##################################################

    # command-line arguments
    args = parse_args()

    # make sure files/directories exist
    if not exists(args.input_filepath):
        raise FileNotFoundError(f"{args.input_filepath} does not exist.")
    if not exists(args.file_output_dir):
        makedirs(args.file_output_dir)
    if not exists(args.output_dir):
        makedirs(args.output_dir)

    # output filepaths for data used in plots
    PLOT_DATA_OUTPUT_FILEPATHS = {plot_type : f"{args.file_output_dir}/{plot_type}.csv" for plot_type in ("density", "summary", "sparsity")}

    # set up logging
    logging.basicConfig(level = logging.INFO, format = "%(message)s")

    ##################################################


    # LOOK AT DISTRIBUTION OF EXPRESSIVE FEATURE TYPES IN "RICH" FILES
    ##################################################

    # if any of the plot data doesn't exist, create it
    if not any(exists(path) for path in tuple(PLOT_DATA_OUTPUT_FILEPATHS.values())):

        # load in data
        data = pd.read_csv(filepath_or_buffer = args.input_filepath, sep = ",", header = 0, index_col = False)

        # filter data
        data = data[data["in_dataset"] & (data["expressive_features"].apply(lambda expressive_features_path: exists(str(expressive_features_path))))]

        # create column names
        pd.DataFrame(columns = DENSITY_COLUMNS).to_csv(path_or_buf = list(PLOT_DATA_OUTPUT_FILEPATHS.values())[0], sep = ",", na_rep = NA_VALUE, header = True, index = False, mode = "w") # density
        pd.DataFrame(columns = FEATURE_TYPES_SUMMARY_COLUMNS).to_csv(path_or_buf = list(PLOT_DATA_OUTPUT_FILEPATHS.values())[1], sep = ",", na_rep = NA_VALUE, header = True, index = False, mode = "w") # features summary
        pd.DataFrame(columns = SPARSITY_COLUMNS).to_csv(path_or_buf = list(PLOT_DATA_OUTPUT_FILEPATHS.values())[2], sep = ",", na_rep = NA_VALUE, header = True, index = False, mode = "w") # sparsity

        # parse through data with multiprocessing
        logging.info(f"N_PATHS = {len(data)}") # print number of paths to process
        chunk_size = 1
        start_time = perf_counter() # start the timer
        with multiprocessing.Pool(processes = args.jobs) as pool:
            results = list(tqdm(iterable = pool.imap_unordered(func = extract_information, iterable = data["expressive_features"], chunksize = chunk_size), desc = "Summarizing Expressive Features", total = len(data)))
        end_time = perf_counter() # stop the timer
        total_time = end_time - start_time # compute total time elapsed
        total_time = strftime("%H:%M:%S", gmtime(total_time)) # convert into pretty string
        logging.info(f"Total time: {total_time}")   

    ##################################################


    # CREATE PLOTS
    ##################################################

    plot_output_filepaths = [f"{args.output_dir}/{plot_type}.png" for plot_type in PLOT_DATA_OUTPUT_FILEPATHS.keys()]
    _ = make_density_plot(input_filepath = list(PLOT_DATA_OUTPUT_FILEPATHS.values())[0], output_filepath = plot_output_filepaths[0])
    expressive_feature_types = make_summary_plot(input_filepath = list(PLOT_DATA_OUTPUT_FILEPATHS.values())[1], output_filepath = plot_output_filepaths[1])
    _ = make_sparsity_plot(input_filepath = list(PLOT_DATA_OUTPUT_FILEPATHS.values())[2], output_filepath_prefix = plot_output_filepaths[2].split(".")[0], expressive_feature_types = expressive_feature_types[::-1])

    ##################################################

##################################################
