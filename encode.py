# README
# Phillip Long
# December 3, 2023

# Any functions related to encoding.


# IMPORTS
##################################################
import numpy as np
import pandas as pd
import warnings
import argparse
from unidecode import unidecode
from typing import List
from re import sub, IGNORECASE
import utils
import representation
from read_mscz.music import BetterMusic
from read_mscz.classes import *
from read_mscz.read_mscz import read_musescore
##################################################


# CONSTANTS
##################################################

CONDITIONINGS = ("sort", "prefix", "anticipation") # there are three options for conditioning 
DEFAULT_CONDITIONING = CONDITIONINGS[0]
SIGMA = 5.0 # for anticipation conditioning
ENCODING_ARRAY_TYPE = np.int64
ANNOTATION_CLASS_NAME_STRING = "annotation_class_name"

##################################################


# INFORMATION TO SCRAPE
##################################################
# ['Metadata', 'Tempo', 'KeySignature', 'TimeSignature', 'Beat', 'Barline', 'Lyric', 'Annotation', 'Note', 'Chord', 'Track', 'Text', 'Subtype', 'RehearsalMark', 'TechAnnotation', 'Dynamic', 'Fermata', 'Arpeggio', 'Tremolo', 'ChordLine', 'Ornament', 'Articulation', 'Notehead', 'Symbol', 'Point', 'Bend', 'TremoloBar', 'Spanner', 'SubtypeSpanner', 'TempoSpanner', 'TextSpanner', 'HairPinSpanner', 'SlurSpanner', 'PedalSpanner', 'TrillSpanner', 'VibratoSpanner', 'GlissandoSpanner', 'OttavaSpanner']
# Explicit objects to scrape:
#   - Notes >
#   - Grace Notes (type field) >
#   - Barlines >
#   - Time Signatures >
#   - Key Signatures >
#   - Tempo, TempoSpanner >
#   - Text, TextSpanner >
#   - RehearsalMark >
#   - Dynamic >
#   - HairPinSpanner >
#   - Fermata >
#   - TechAnnotation >
#   - Symbol >
# Implicit objects to scrape:
#   - Articulation (Total # in some time; 4 horizontally in a row) -- we are looking for articulation chunks! >
#   - SlurSpanner, higher the tempo, the longer the slur needs to be >
#   - PedalSpanner, higher the tempo, the longer the slur needs to be >
# Punting on:
#   - Notehead
#   - Arpeggio
#   - Ornament
#   - Ottava
#   - Bend
#   - TrillSpanner
#   - VibratoSpanner
#   - GlissandoSpanner
#   - Tremolo, TremoloBar
#   - Vertical Density
#   - Horizontal Density
#   - Any Drum Tracks
##################################################


# TEXT CLEANUP FUNCTIONS FOR SCRAPING
##################################################

# make sure text is ok
def check_text(text: str):
    if text is not None:
        return sub(pattern = ": ", repl = ":", string = sub(pattern = ", ", repl = ",", string = " ".join(text.split()))).strip()
    return None

# clean up text objects
def clean_up_text(text: str):
    if text is not None:
        text = sub(pattern = "-", repl = " ", string = utils.split_camel_case(string = text)) # get rid of camel case, deal with long spins of dashes
        text = sub(pattern = " ", repl = "-", string = check_text(text = text)) # replace any whitespace with dashes
        text = sub(pattern = "[^\w-]", repl = "", string = text) # extract alphanumeric
        return text.lower() # convert to lower case
    return None

##################################################


# SCRAPE EXPLICIT FEATURES
##################################################

desired_expressive_feature_types = ("Text", "TextSpanner", "RehearsalMark", "Dynamic", "HairPinSpanner", "Fermata", "TempoSpanner", "TechAnnotation") # "Symbol"
def scrape_annotations(annotations: List[Annotation], song_length: int, use_implied_duration: bool = True, include_annotation_class_name: bool = False) -> pd.DataFrame:
    """Scrape annotations. song_length is the length of the song (in time steps). use_implied_duration is whether or not to calculate an 'implied duration' value for features without duration."""

    output_columns = representation.DIMENSIONS + ([ANNOTATION_CLASS_NAME_STRING,] if include_annotation_class_name else []) # output columns
    annotations_encoded = {key: [] for key in output_columns} # create dictionary of lists
    if use_implied_duration:
        encounters = dict(zip(desired_expressive_feature_types, utils.rep(x = None, times = len(desired_expressive_feature_types)))) # to track durations

    for annotation in annotations:

        # get the expressive feature type we are working with
        expressive_feature_type = annotation.annotation.__class__.__name__
        if expressive_feature_type not in desired_expressive_feature_types: # ignore expressive we are not interested in
            continue
        
        # time
        annotations_encoded["time"].append(annotation.time)

        # event type
        annotations_encoded["type"].append(representation.EXPRESSIVE_FEATURE_TYPE_STRING)

        # annotation class name (if necessary)
        if include_annotation_class_name:
            annotations_encoded[ANNOTATION_CLASS_NAME_STRING].append(expressive_feature_type)

        # deal withspecial case when the dynamic is a hike dynamic (e.g. sfz or rf)
        is_hike_dynamic = False
        if expressive_feature_type == "Dynamic":
            if annotation.annotation.subtype.lower() not in representation.DYNAMIC_DYNAMICS:
                is_hike_dynamic = True
        # duration
        if hasattr(annotation.annotation, "duration"):
            duration = annotation.annotation.duration # get the duration
        elif (not use_implied_duration) or (use_implied_duration and is_hike_dynamic): # not using implied duration or this is a hike dynamic
            duration = 0
        else: # deal with implied duration (time until next of same type)
            if encounters[expressive_feature_type] is not None: # to deal with the first encounter
                annotations_encoded["duration"][encounters[expressive_feature_type]] = annotation.time - annotations_encoded["time"][encounters[expressive_feature_type]]
            encounters[expressive_feature_type] = len(annotations_encoded["duration"]) # update encounter index
            duration = None # append None for current duration, will be fixed later           
        annotations_encoded["duration"].append(duration) # add a duration value if there is one
        
        # deal with value field
        value = None
        if hasattr(annotation.annotation, "text"):
            value = clean_up_text(text = annotation.annotation.text)
        elif hasattr(annotation.annotation, "subtype"):
            value = utils.split_camel_case(string = annotation.annotation.subtype)
        if (value is None) or (value == ""): # if there is no text or subtype value, make the value the expressive feature type (e.g. "TempoSpanner")
            value = utils.split_camel_case(string = sub(pattern = "Spanner", repl = "", string = expressive_feature_type))
        # deal with special cases
        if value in ("dynamic", "other-dynamics"):
            value = representation.DEFAULT_EXPRESSIVE_FEATURE_VALUES["Dynamic"]
        elif expressive_feature_type == "Fermata":
            value = representation.DEFAULT_EXPRESSIVE_FEATURE_VALUES["Fermata"]
        elif expressive_feature_type == "RehearsalMark" and value.isdigit():
            value = representation.DEFAULT_EXPRESSIVE_FEATURE_VALUES["RehearsalMark"]
        annotations_encoded["value"].append(check_text(text = value))
    
    # get final if using implied durations
    if use_implied_duration:
        for expressive_feature_type in tuple(encounters.keys()):
            if encounters[expressive_feature_type] is not None:
                annotations_encoded["duration"][encounters[expressive_feature_type]] = song_length - annotations_encoded["time"][encounters[expressive_feature_type]]
        
    # make sure untouched columns get filled
    for dimension in filter(lambda dimension: len(annotations_encoded[dimension]) == 0, tuple(annotations_encoded.keys())):
        annotations_encoded[dimension] = utils.rep(x = None, times = len(annotations_encoded["type"]))

    # create dataframe from scraped values
    return pd.DataFrame(data = annotations_encoded, columns = output_columns)


def scrape_barlines(barlines: List[Barline], song_length: int, use_implied_duration: bool = True, include_annotation_class_name: bool = False) -> pd.DataFrame:
    """Scrape barlines. song_length is the length of the song (in time steps). use_implied_duration is whether or not to calculate an 'implied duration' value for features without duration."""
    output_columns = representation.DIMENSIONS + ([ANNOTATION_CLASS_NAME_STRING,] if include_annotation_class_name else []) # output columns
    barlines = list(filter(lambda barline: not ((barline.subtype == "single") or ("repeat" in barline.subtype.lower())), barlines)) # filter out single barlines
    barlines_encoded = {key: utils.rep(x = None, times = len(barlines)) for key in output_columns} # create dictionary of lists
    if include_annotation_class_name:
        barlines_encoded[ANNOTATION_CLASS_NAME_STRING] = utils.rep(x = "Barline", times = len(barlines)) # if include the annotation class name
    barlines.append(Barline(time = song_length, measure = 0)) # for duration
    for i, barline in enumerate(barlines[:-1]):
        barlines_encoded["type"][i] = representation.EXPRESSIVE_FEATURE_TYPE_STRING
        barlines_encoded["value"][i] = check_text(text = (f"{barline.subtype.lower()}-" if barline.subtype is not None else "") + "barline")
        barlines_encoded["duration"][i] = (barlines[i + 1].time - barline.time) if use_implied_duration else 0
        barlines_encoded["time"][i] = barline.time
        if include_annotation_class_name:
            barlines_encoded[ANNOTATION_CLASS_NAME_STRING][i] = "Barline"
    return pd.DataFrame(data = barlines_encoded, columns = output_columns) # create dataframe from scraped values


def scrape_time_signatures(time_signatures: List[TimeSignature], song_length: int, use_implied_duration: bool = True, include_annotation_class_name: bool = False) -> pd.DataFrame:
    """Scrape time_signatures. song_length is the length of the song (in time steps). use_implied_duration is whether or not to calculate an 'implied duration' value for features without duration."""
    output_columns = representation.DIMENSIONS + ([ANNOTATION_CLASS_NAME_STRING,] if include_annotation_class_name else []) # output columns
    time_signatures_encoded = {key: utils.rep(x = None, times = len(time_signatures) - 1) for key in output_columns} # create dictionary of lists
    if include_annotation_class_name:
        time_signatures_encoded[ANNOTATION_CLASS_NAME_STRING] = utils.rep(x = "TimeSignature", times = len(time_signatures) - 1) # if include the annotation class name
    time_signatures.append(TimeSignature(time = song_length, measure = 0, numerator = 4, denominator = 4)) # for duration
    for i in range(1, len(time_signatures) - 1): # ignore first time_signature, since we are tracking changes in time_signature; also ignore last one, since it is used for duration
        time_signatures_encoded["type"][i - 1] = representation.EXPRESSIVE_FEATURE_TYPE_STRING
        time_signature_change_ratio = ((time_signatures[i].numerator / time_signatures[i].denominator) / (time_signatures[i - 1].numerator / time_signatures[i - 1].denominator)) if all(((time_signature.numerator != None and time_signature.denominator != None) for time_signature in time_signatures[i - 1:i + 1])) else -1e6 # ratio between time signatures
        time_signatures_encoded["value"][i - 1] = check_text(text = representation.TIME_SIGNATURE_CHANGE_MAPPER(time_signature_change_ratio = time_signature_change_ratio)) # check_text(text = f"{time_signatures[i].numerator}/{time_signatures[i].denominator}")
        time_signatures_encoded["duration"][i - 1] = (time_signatures[i + 1].time - time_signatures[i].time) if use_implied_duration else 0
        time_signatures_encoded["time"][i - 1] = time_signatures[i].time
    return pd.DataFrame(data = time_signatures_encoded, columns = output_columns) # create dataframe from scraped values


def scrape_key_signatures(key_signatures: List[KeySignature], song_length: int, use_implied_duration: bool = True, include_annotation_class_name: bool = False) -> pd.DataFrame:
    """Scrape key_signatures. song_length is the length of the song (in time steps). use_implied_duration is whether or not to calculate an 'implied duration' value for features without duration."""
    output_columns = representation.DIMENSIONS + ([ANNOTATION_CLASS_NAME_STRING,] if include_annotation_class_name else []) # output columns
    key_signatures_encoded = {key: utils.rep(x = None, times = len(key_signatures) - 1) for key in output_columns} # create dictionary of lists
    if include_annotation_class_name:
        key_signatures_encoded[ANNOTATION_CLASS_NAME_STRING] = utils.rep(x = "KeySignature", times = len(key_signatures) - 1) # if include the annotation class name
    key_signatures.append(KeySignature(time = song_length, measure = 0)) # for duration
    for i in range(1, len(key_signatures) - 1): # ignore first key_signature, since we are tracking changes in key_signature; also ignore last one, since it is used for duration
        key_signatures_encoded["type"][i - 1] = representation.EXPRESSIVE_FEATURE_TYPE_STRING
        distance = key_signatures[i].fifths - key_signatures[i - 1].fifths if all((key_signature.fifths != None for key_signature in key_signatures[i - 1:i + 1])) else 0 # calculate key change distance in circle of fifths
        key_signatures_encoded["value"][i - 1] = check_text(text = f"key-signature-change-{int(min((distance, (-(distance / abs(distance)) * 12) + distance), key = lambda dist: abs(dist))) if distance != 0 else 0}") # check_text(text = f"{key_signatures[i].root_str} {key_signatures[i].mode}") # or key_signatures[i].root or key_signatures[i].fifths
        key_signatures_encoded["duration"][i - 1] = (key_signatures[i + 1].time - key_signatures[i].time) if use_implied_duration else 0
        key_signatures_encoded["time"][i - 1] = key_signatures[i].time
    return pd.DataFrame(data = key_signatures_encoded, columns = output_columns) # create dataframe from scraped values


def scrape_tempos(tempos: List[Tempo], song_length: int, use_implied_duration: bool = True, include_annotation_class_name: bool = False) -> pd.DataFrame:
    """Scrape tempos. song_length is the length of the song (in time steps). use_implied_duration is whether or not to calculate an 'implied duration' value for features without duration."""
    output_columns = representation.DIMENSIONS + ([ANNOTATION_CLASS_NAME_STRING,] if include_annotation_class_name else []) # output columns
    tempos_encoded = {key: utils.rep(x = None, times = len(tempos)) for key in output_columns} # create dictionary of lists
    if include_annotation_class_name:
        tempos_encoded[ANNOTATION_CLASS_NAME_STRING] = utils.rep(x = "Tempo", times = len(tempos)) # if include the annotation class name
    tempos.append(Tempo(time = song_length, measure = 0, qpm = 0.0)) # for duration
    for i, tempo in enumerate(tempos[:-1]):
        tempos_encoded["type"][i] = representation.EXPRESSIVE_FEATURE_TYPE_STRING
        tempos_encoded["value"][i] = check_text(text = representation.QPM_TEMPO_MAPPER(qpm = tempo.qpm)) # check_text(text = tempo.text.lower() if tempo.text is not None else "tempo-marking")
        tempos_encoded["duration"][i] = (tempos[i + 1].time - tempo.time) if use_implied_duration else 0
        tempos_encoded["time"][i] = tempo.time
    return pd.DataFrame(data = tempos_encoded, columns = output_columns) # create dataframe from scraped values


def scrape_notes(notes: List[Note], include_annotation_class_name: bool = False) -> pd.DataFrame:
    """Scrape notes (and grace notes)."""
    output_columns = representation.DIMENSIONS + ([ANNOTATION_CLASS_NAME_STRING,] if include_annotation_class_name else []) # output columns
    notes_encoded = {key: utils.rep(x = None, times = len(notes)) for key in output_columns} # create dictionary of lists
    if include_annotation_class_name:
        notes_encoded[ANNOTATION_CLASS_NAME_STRING] = utils.rep(x = "Note", times = len(notes)) # if include the annotation class name
    for i, note in enumerate(notes):
        notes_encoded["type"][i] = "grace-note" if note.is_grace else "note" # get the note type (grace or normal)
        notes_encoded["value"][i] = note.pitch # or note.pitch_str
        notes_encoded["duration"][i] = note.duration
        notes_encoded["time"][i] = note.time
    return pd.DataFrame(data = notes_encoded, columns = output_columns) # create dataframe from scraped values

##################################################


# SCRAPE IMPLICIT FEATURES
##################################################

def scrape_articulations(annotations: List[Annotation], maximum_gap: int, articulation_count_threshold: int = 4, include_annotation_class_name: bool = False) -> pd.DataFrame:
    """Scrape articulations. maximum_gap is the maximum distance (in time steps) between articulations, which, when exceeded, forces the ending of the current articulation chunk and the creation of a new one. articulation_count_threshold is the minimum number of articulations in a chunk to make it worthwhile recording."""
    output_columns = representation.DIMENSIONS + ([ANNOTATION_CLASS_NAME_STRING,] if include_annotation_class_name else []) # output columns
    articulations_encoded = {key: [] for key in output_columns} # create dictionary of lists
    encounters = {}
    def check_all_subtypes_for_chunk_ending(time): # helper function to check if articulation subtypes chunk ended
        for articulation_subtype in tuple(encounters.keys()):
            if (time - encounters[articulation_subtype]["end"]) > maximum_gap: # if the articulation chunk is over
                if encounters[articulation_subtype]["count"] >= articulation_count_threshold:
                    value = utils.split_camel_case(string = check_text(text = sub(pattern = "artic|below|above|ornament|strings|up|down|inverted", repl = "", string = articulation_subtype, flags = IGNORECASE) if articulation_subtype is not None else "articulation"))
                    if any((keyword in value for keyword in ("lutefingering", "lute-fingering"))): # skip certain articulations
                        continue
                    elif "prall" in value:
                        value = "trill"
                    elif value.startswith("u") or value.startswith("d"): # get rid of u or d prefix (up or down)
                        value = value[1:]
                    articulations_encoded["type"].append(representation.EXPRESSIVE_FEATURE_TYPE_STRING)
                    articulations_encoded["value"].append(value)
                    articulations_encoded["duration"].append(encounters[articulation_subtype]["end"] - encounters[articulation_subtype]["start"])
                    articulations_encoded["time"].append(encounters[articulation_subtype]["start"])
                del encounters[articulation_subtype] # erase articulation subtype, let it be recreated when it comes up again
    for annotation in annotations:
        check_all_subtypes_for_chunk_ending(time = annotation.time)
        if annotation.annotation.__class__.__name__ == "Articulation":
            articulation_subtype = annotation.annotation.subtype # get the articulation subtype
            if articulation_subtype in encounters.keys(): # if we've encountered this articulation before
                encounters[articulation_subtype]["end"] = annotation.time
                encounters[articulation_subtype]["count"] += 1
            else:
                encounters[articulation_subtype] = {"start": annotation.time, "end": annotation.time, "count": 1} # if we are yet to encounter this articulation
        else: # ignore non Articulations
            continue
    if len(annotations) > 0: # to avoid index error
        check_all_subtypes_for_chunk_ending(time = annotations[-1].time + (2 * maximum_gap)) # one final check
    for dimension in filter(lambda dimension: len(articulations_encoded[dimension]) == 0, tuple(articulations_encoded.keys())): # make sure untouched columns get filled
        articulations_encoded[dimension] = utils.rep(x = "Articulation" if (dimension == ANNOTATION_CLASS_NAME_STRING) else None, times = len(articulations_encoded["type"]))
    return pd.DataFrame(data = articulations_encoded, columns = output_columns) # create dataframe from scraped values


def scrape_slurs(annotations: List[Annotation], minimum_duration: float, music: BetterMusic, include_annotation_class_name: bool = False) -> pd.DataFrame:
    """Scrape slurs. minimum_duration is the minimum duration (in seconds) a slur needs to be to make it worthwhile recording."""
    output_columns = representation.DIMENSIONS + ([ANNOTATION_CLASS_NAME_STRING,] if include_annotation_class_name else []) # output columns
    slurs_encoded = {key: [] for key in output_columns} # create dictionary of lists
    for annotation in annotations:
        if annotation.annotation.__class__.__name__ == "SlurSpanner":
            if annotation.annotation.is_slur:
                start = music.metrical_time_to_absolute_time(time_steps = annotation.time)
                duration = music.metrical_time_to_absolute_time(time_steps = annotation.time + annotation.annotation.duration) - start
                if duration > minimum_duration:
                    slurs_encoded["type"].append(representation.EXPRESSIVE_FEATURE_TYPE_STRING)
                    slurs_encoded["value"].append(check_text(text = "slur"))
                    slurs_encoded["duration"].append(annotation.annotation.duration)
                    slurs_encoded["time"].append(annotation.time)
                else: # if slur is too short
                    continue
            else: # if annotation is a tie
                continue
        else: # ignore non slurs
            continue
    for dimension in filter(lambda dimension: len(slurs_encoded[dimension]) == 0, tuple(slurs_encoded.keys())): # make sure untouched columns get filled
        slurs_encoded[dimension] = utils.rep(x = "SlurSpanner" if (dimension == ANNOTATION_CLASS_NAME_STRING) else None, times = len(slurs_encoded["type"]))
    return pd.DataFrame(data = slurs_encoded, columns = output_columns) # create dataframe from scraped values


def scrape_pedals(annotations: List[Annotation], minimum_duration: float, music: BetterMusic, include_annotation_class_name: bool = False) -> pd.DataFrame:
    """Scrape pedals. minimum_duration is the minimum duration (in seconds) a pedal needs to be to make it worthwhile recording."""
    output_columns = representation.DIMENSIONS + ([ANNOTATION_CLASS_NAME_STRING,] if include_annotation_class_name else []) # output columns
    pedals_encoded = {key: [] for key in output_columns} # create dictionary of lists
    for annotation in annotations:
        if annotation.annotation.__class__.__name__ == "PedalSpanner":
            start = music.metrical_time_to_absolute_time(time_steps = annotation.time)
            duration = music.metrical_time_to_absolute_time(time_steps = annotation.time + annotation.annotation.duration) - start
            if duration > minimum_duration:
                pedals_encoded["type"].append(representation.EXPRESSIVE_FEATURE_TYPE_STRING)
                pedals_encoded["value"].append(check_text(text = "pedal"))
                pedals_encoded["duration"].append(annotation.annotation.duration)
                pedals_encoded["time"].append(annotation.time)
            else: # if pedal is too short
                continue
        else: # ignore non pedals
            continue
    for dimension in filter(lambda dimension: len(pedals_encoded[dimension]) == 0, tuple(pedals_encoded.keys())): # make sure untouched columns get filled
        pedals_encoded[dimension] = utils.rep(x = "PedalSpanner" if (dimension == ANNOTATION_CLASS_NAME_STRING) else None, times = len(pedals_encoded["type"]))
    return pd.DataFrame(data = pedals_encoded, columns = output_columns) # create dataframe from scraped values

##################################################


# WRAPPER FUNCTIONS MAKE CODE EASIER TO READ
##################################################

def get_system_level_expressive_features(music: BetterMusic, use_implied_duration: bool = True, include_annotation_class_name: bool = False) -> pd.DataFrame:
    """Wrapper function to make code more readable. Extracts system-level expressive features."""
    system_annotations = scrape_annotations(annotations = music.annotations, song_length = music.song_length, use_implied_duration = use_implied_duration, include_annotation_class_name = include_annotation_class_name)
    system_barlines = scrape_barlines(barlines = music.barlines, song_length = music.song_length, use_implied_duration = use_implied_duration, include_annotation_class_name = include_annotation_class_name)
    system_time_signatures = scrape_time_signatures(time_signatures = music.time_signatures, song_length = music.song_length, use_implied_duration = use_implied_duration, include_annotation_class_name = include_annotation_class_name)
    system_key_signatures = scrape_key_signatures(key_signatures = music.key_signatures, song_length = music.song_length, use_implied_duration = use_implied_duration, include_annotation_class_name = include_annotation_class_name)
    system_tempos = scrape_tempos(tempos = music.tempos, song_length = music.song_length, use_implied_duration = use_implied_duration, include_annotation_class_name = include_annotation_class_name)
    return pd.concat(objs = (system_annotations, system_barlines, system_time_signatures, system_key_signatures, system_tempos), axis = 0, ignore_index = True)

def get_staff_level_expressive_features(track: Track, music: BetterMusic, use_implied_duration: bool = True, include_annotation_class_name: bool = False) -> pd.DataFrame:
    """Wrapper function to make code more readable. Extracts staff-level expressive features."""
    staff_notes = scrape_notes(notes = track.notes, include_annotation_class_name = include_annotation_class_name)
    staff_annotations = scrape_annotations(annotations = track.annotations, song_length = music.song_length, use_implied_duration = use_implied_duration, include_annotation_class_name = include_annotation_class_name)
    staff_articulations = scrape_articulations(annotations = track.annotations, maximum_gap = 2 * music.resolution, include_annotation_class_name = include_annotation_class_name) # 2 beats = 2 * music.resolution
    staff_slurs = scrape_slurs(annotations = track.annotations, minimum_duration = 1.5, music = music, include_annotation_class_name = include_annotation_class_name) # minimum duration for slurs to be recorded is 1.5 seconds
    staff_pedals = scrape_pedals(annotations = track.annotations, minimum_duration = 1.5, music = music, include_annotation_class_name = include_annotation_class_name) # minimum duration for pedals to be recorded is 1.5 seconds
    return pd.concat(objs = (staff_notes, staff_annotations, staff_articulations, staff_slurs, staff_pedals), axis = 0, ignore_index = True)

##################################################


# ENCODER FUNCTIONS
##################################################

def extract_data(music: BetterMusic, use_implied_duration: bool = True, include_annotation_class_name: bool = False) -> np.array:
    """Return a BetterMusic object as a data sequence.
    Each row of the output is a note specified as follows.
        (event_type, beat, position, value, duration, program, time, time (in seconds), annotation_class_name (if argument is `True`))
    """

    # output columns
    output_columns = representation.DIMENSIONS + ([ANNOTATION_CLASS_NAME_STRING,] if include_annotation_class_name else [])

    # create output dataframe
    output = np.empty(shape = (0, len(output_columns)), dtype = np.object_)

    # time column index
    time_dim = output_columns.index("time")

    # scrape system level expressive features
    system_level_expressive_features = get_system_level_expressive_features(music = music, use_implied_duration = use_implied_duration, include_annotation_class_name = include_annotation_class_name)

    for track in music.tracks:

        # do not record if track is drum or is an unknown program
        if track.is_drum or track.program not in representation.KNOWN_PROGRAMS:
            continue

        # scrape staff-level features
        staff_level_expressive_features = get_staff_level_expressive_features(track = track, music = music, use_implied_duration = use_implied_duration, include_annotation_class_name = include_annotation_class_name)

        # create dataframe, do some wrangling to semi-encode values
        data = pd.concat(objs = (pd.DataFrame(columns = output_columns), system_level_expressive_features, staff_level_expressive_features), axis = 0, ignore_index = True) # combine system and staff expressive features
        data["type"] = data["type"].apply(lambda type_: type_ if type_ is not None else representation.EXPRESSIVE_FEATURE_TYPE_STRING) # make sure no missing type values
        data["instrument"] = utils.rep(x = track.program, times = len(data)) # add the instrument column
        data["duration"] = (representation.RESOLUTION / music.resolution) * data["duration"].apply(lambda duration: duration if not np.isnan(duration) else 0) # semi-encode duration, checking for missing values

        # convert time to seconds for certain types of sorting that might require it
        data["time.s"] = data["time"].apply(lambda time_steps: music.metrical_time_to_absolute_time(time_steps = time_steps)) # get time in seconds
        # data = data.sort_values(by = "time").reset_index(drop = True) # sort by time

        # calculate beat and position values (time signature agnostic)
        data["beat"] = data["time"].apply(lambda time_steps: int(time_steps / music.resolution) if not np.isnan(time_steps) else 0) # add beat
        data["position"] = data["time"].apply(lambda time_steps: int((representation.RESOLUTION / music.resolution) * (time_steps % music.resolution)) if not np.isnan(time_steps) else 0) # add position
        # get beats (accounting for time signature) # beats = sorted(list(set([beat.time for beat in music.beats] + [music.song_length,]))) # add song length to end of beats for calculating position
        # if len(music.time_signatures) > 0:
        #     beats = []
        #     time_signatures = music.time_signatures + [TimeSignature(time = music.song_length, measure = 0, numerator = 4, denominator = 4),]
        #     for i in range(len(time_signatures) - 1):
        #         beats += list(range(time_signatures[i].time, time_signatures[i + 1].time, int(music.resolution * (4 / time_signatures[i].denominator))))
        # else: # assume 4/4
        #     beats = list(range(0, music.song_length + music.resolution, music.resolution))        
        # beat_index = 0
        # for i in data.index: # assumes data is sorted by time_step values
        #     if data.at[i, "time"] >= beats[beat_index + 1]: # if we've moved to the next beat
        #         beat_index += 1 # increment beat index
        #     data.at[i, "beat"] = beat_index  # convert base to base 0
        #     data.at[i, "position"] = int((RESOLUTION * (data.at[i, "time"] - beats[beat_index])) / (beats[beat_index + 1] - beats[beat_index]))

        # remove duplicates due to beat and position quantization
        data = data.drop_duplicates(subset = output_columns[:time_dim], keep = "first", ignore_index = True)

        # don't save low-quality data
        # if len(data) < 50:
        #     continue

        # convert to np array so that we can save as npy file, which loads faster
        data = np.array(object = data, dtype = np.object_)

        # add to output array
        output = np.concatenate((output, data), axis = 0, dtype = np.object_)

    # sort by time
    output = output[np.lexsort(keys = ([representation.TYPE_CODE_MAP[type_] for type_ in output[:, 0]], output[:, time_dim]), axis = 0)] # sort order
    if len(output) > 0:
        output[:, output_columns.index("beat")] = output[:, output_columns.index("beat")] - output[0, output_columns.index("beat")] # start beat to 0
        output[:, time_dim] = output[:, time_dim] - output[0, time_dim] # start time to 0
        output[:, time_dim + 1] = output[:, time_dim + 1] - output[0, time_dim + 1] # start time.s to 0

    return output


def encode_data(data: np.array, encoding: dict, conditioning: str = DEFAULT_CONDITIONING, sigma: float = SIGMA) -> np.array:
    """Encode a note sequence into a sequence of codes.
    Each row of the input is a note specified as follows.
        (event_type, beat, position, value, duration, program, time, time (in seconds))
    Each row of the output is encoded as follows.
        (event_type, beat, position, value, duration, instrument)
    """

    # LOAD IN DATA

    # load in npy file from path parameter
    # data = np.load(file = path, allow_pickle = True)

    # get variables
    max_beat = encoding["max_beat"]
    max_duration = encoding["max_duration"]

    # get maps
    type_code_map = encoding["type_code_map"]
    beat_code_map = encoding["beat_code_map"]
    position_code_map = encoding["position_code_map"]
    value_code_map = encoding["value_code_map"]
    duration_code_map = encoding["duration_code_map"]
    instrument_code_map = encoding["instrument_code_map"]
    program_instrument_map = encoding["program_instrument_map"]

    # get the dimension indices
    beat_dim = encoding["dimensions"].index("beat")
    position_dim = encoding["dimensions"].index("position")
    value_dim = encoding["dimensions"].index("value")
    duration_dim = encoding["dimensions"].index("duration")
    instrument_dim = encoding["dimensions"].index("instrument")

    # make sure conditioning value is correct
    if conditioning not in CONDITIONINGS:
        conditioning = DEFAULT_CONDITIONING
    
    # ENCODE

    # start the codes with an SOS row
    codes = np.array(object = [(type_code_map["start-of-song"], 0, 0, 0, 0, 0)], dtype = ENCODING_ARRAY_TYPE)

    # extract/encode instruments
    programs = np.unique(ar = data[:, instrument_dim]) # get unique instrument values
    instrument_codes = np.zeros(shape = (len(programs), codes.shape[1]), dtype = ENCODING_ARRAY_TYPE) # create empty array
    for i, program in enumerate(programs):
        if program is None: # skip unknown programs
            continue
        instrument_codes[i, 0] = type_code_map["instrument"] # set the type to instrument
        instrument_codes[i, instrument_dim] = instrument_code_map[program_instrument_map[program]] # encode the instrument value
    instrument_codes = instrument_codes[np.argsort(a = instrument_codes[:, instrument_dim], axis = 0)] # sort the instruments
    codes = np.concatenate((codes, instrument_codes), axis = 0) # append them to the code sequence
    del instrument_codes # clear up memory

    # add start of notes row
    codes = np.append(arr = codes, values = [(type_code_map["start-of-notes"], 0, 0, 0, 0, 0)], axis = 0)

    # helper functions for mapping
    def value_code_mapper(value) -> int:
        try:
            code = value_code_map[None if value == "" else value]
        except KeyError:
            value = sub(pattern = "-", repl = "", string = value) # try wrangling value a bit to get a key
            value = unidecode(string = value) # get rid of accented characters (normalize)
            try:
                code = value_code_map[None if value == "" else value]
            except KeyError:
                code = representation.DEFAULT_VALUE_CODE
        return code
    def program_instrument_mapper(program) -> int:
        instrument = instrument_code_map[program_instrument_map[int(program)]]
        if instrument is None:
            return -1
        return instrument
    
    # encode the notes / expressive features
    core_codes = np.zeros(shape = (data.shape[0], codes.shape[1]), dtype = ENCODING_ARRAY_TYPE)
    core_codes[:, 0] = list(map(lambda type_: type_code_map[str(type_)], data[:, 0])) # encode type column
    core_codes[:, beat_dim] = list(map(lambda beat: beat_code_map[int(max(0, beat))], data[:, beat_dim])) # encode beat
    core_codes[:, position_dim] = list(map(lambda position: position_code_map[int(max(0, position))], data[:, position_dim])) # encode position
    core_codes[:, value_dim] = list(map(value_code_mapper, data[:, value_dim])) # encode value column
    core_codes[:, duration_dim] = list(map(lambda duration: duration_code_map[int(min(max_duration, max(0, duration)))], data[:, duration_dim])) # encode duration
    core_codes[:, instrument_dim] = list(map(program_instrument_mapper, data[:, instrument_dim])) # encode instrument column
    core_codes = core_codes[core_codes[:, beat_dim] <= max_beat] # remove data if beat greater than max beat
    core_codes = core_codes[core_codes[:, instrument_dim] >= 0] # skip unknown instruments

    # apply conditioning to core_codes
    if conditioning == CONDITIONINGS[0]: # sort-order
        core_codes_with_time_steps = np.concatenate((core_codes, data[:, data.shape[1] - 2].reshape(data.shape[0], 1)), axis = 1) # add time steps column
        time_steps_column = core_codes_with_time_steps.shape[1] - 1
        core_codes_with_time_steps = core_codes_with_time_steps[np.lexsort(keys = (core_codes_with_time_steps[:, 0], core_codes_with_time_steps[:, time_steps_column]), axis = 0)] # sort by time (time steps)
        core_codes = np.delete(arr = core_codes_with_time_steps, obj = time_steps_column, axis = 1).astype(ENCODING_ARRAY_TYPE) # remove time steps column
        del core_codes_with_time_steps, time_steps_column
    elif conditioning == CONDITIONINGS[1]: # prefix
        core_codes_with_time_steps = np.concatenate((core_codes, data[:, data.shape[1] - 2].reshape(data.shape[0], 1)), axis = 1) # add time steps column
        time_steps_column = core_codes_with_time_steps.shape[1] - 1
        expressive_feature_indicies = sorted(np.where(core_codes[:, 0] == type_code_map[representation.EXPRESSIVE_FEATURE_TYPE_STRING])[0]) # get indicies of expressive features
        expressive_features = core_codes_with_time_steps[expressive_feature_indicies] # extract expressive features
        expressive_features = expressive_features[expressive_features[:, time_steps_column].argsort()] # sort by time, just argsort because the only type is expressive-feature
        expressive_features = np.delete(arr = expressive_features, obj = time_steps_column, axis = 1).astype(ENCODING_ARRAY_TYPE) # delete time steps column
        notes = np.delete(arr = core_codes_with_time_steps, obj = expressive_feature_indicies, axis = 0) # delete expressive features from core
        notes = notes[np.lexsort(keys = (notes[:, 0], notes[:, time_steps_column]), axis = 0)] # sort by time
        notes = np.delete(arr = notes, obj = time_steps_column, axis = 1).astype(ENCODING_ARRAY_TYPE) # delete time steps column
        core_codes = np.concatenate((expressive_features, codes[len(codes) - 1].reshape(1, codes.shape[1]), notes), axis = 0, dtype = ENCODING_ARRAY_TYPE) # sandwich: expressive features, start of notes row, 
        codes = np.delete(arr = codes, obj = len(codes) - 1, axis = 0) # remove start of notes row from codes
        del core_codes_with_time_steps, time_steps_column, expressive_feature_indicies, expressive_features, notes
    elif conditioning == CONDITIONINGS[2]: # anticipation
        if sigma is None: # make sure sigma is not none
            warnings.warn(f"Encountered NoneValue sigma argument for anticipation conditioning. Using sigma = {SIGMA}.", RuntimeWarning)
            sigma = SIGMA
        core_codes_with_seconds = np.concatenate((core_codes, data[:, data.shape[1] - 1].reshape(data.shape[0], 1)), axis = 1) # add seconds column
        seconds_column = core_codes_with_seconds.shape[1] - 1 # get the index of the seconds column
        core_codes_with_seconds[:, seconds_column] -= (core_codes_with_seconds[:, 0] == type_code_map[representation.EXPRESSIVE_FEATURE_TYPE_STRING]) * sigma # subtract anticipation value from expressive features
        core_codes_with_seconds = core_codes_with_seconds[np.lexsort(keys = (core_codes_with_seconds[:, 0], core_codes_with_seconds[:, seconds_column]), axis = 0)] # sort by time (seconds)
        core_codes = np.delete(arr = core_codes_with_seconds, obj = seconds_column, axis = 1).astype(ENCODING_ARRAY_TYPE) # remove seconds column
        del core_codes_with_seconds, seconds_column

    # add core_codes to the general codes matrix
    codes = np.concatenate((codes, core_codes), axis = 0) # append them to the code sequence
    del core_codes # clear up memory

    # end the codes with an EOS row
    codes = np.append(arr = codes, values = [(type_code_map["end-of-song"], 0, 0, 0, 0, 0)], axis = 0)

    return codes


def encode(music: BetterMusic, use_implied_duration: bool = True, encoding: dict = representation.get_encoding(), conditioning: str = DEFAULT_CONDITIONING, sigma: float = SIGMA) -> np.array:
    """Given a BetterMusic object, encode it."""

    # extract data
    data = extract_data(music = music, use_implied_duration = use_implied_duration)

    # encode data
    codes = encode_data(data = data, encoding = encoding, conditioning = conditioning, sigma = sigma)

    return codes

##################################################


# SAVE DATA
##################################################

def save_csv_codes(filepath: str, data: np.array):
    """Save the representation as a CSV file."""
    assert data.shape[1] == len(representation.get_encoding()["dimensions"])
    np.savetxt(fname = filepath, X = data, fmt = "%d", delimiter = ",", header = "type,beat,position,value,duration,instrument", comments = "")

##################################################


# MAIN METHOD
##################################################

if __name__ == "__main__":
    
    ENCODING_FILEPATH = "/data2/pnlong/musescore/encoding.json"

    # get arguments
    parser = argparse.ArgumentParser(prog = "Representation", description = "Test Encoding/Decoding mechanisms for MuseScore data.")
    parser.add_argument("-e", "--encoding", type = str, default = ENCODING_FILEPATH, help = "Absolute filepath to encoding file")
    args = parser.parse_args()

    # load encoding
    encoding = representation.load_encoding(filepath = args.encoding)

    # print an example
    print(f"{'Example':=^40}")
    music = read_musescore(path = "/data2/pnlong/musescore/test_data/laufey/from_the_start.mscz")
    print(f"Music:\n{music}")

    encoded = encode(music = music, encoding = encoding)
    print("-" * 40)
    print(f"Encoded:\n{encoded}")

##################################################
