# README
# Phillip Long
# October 3, 2023

# child class of Muspy.Music better suited for storing expressive features from musescore
# Music class -- a universal container for symbolic music.
# copied mostly from https://github.com/salu133445/muspy/blob/b2d4265c6279e730903d8abe9dddda8484511903/muspy/music.py
# Classes
# -------
# - Music
# Variables
# ---------
# - DEFAULT_RESOLUTION

# ./music.py


# IMPORTS
##################################################
import muspy
from .classes import *
from collections import OrderedDict
from typing import List
from re import sub
import yaml # for printing
import json
import gzip

from .output import write_midi, write_audio, write_musicxml
##################################################


# CONSTANTS
##################################################

DIVIDE_BY_ZERO_CONSTANT = 1e-10

##################################################


# HELPER FUNCTIONS
##################################################

def to_dict(obj) -> dict:
    """Convert an object into a dictionary (for .json output)."""

    # base case
    if isinstance(obj, bool) or isinstance(obj, str) or isinstance(obj, int) or isinstance(obj, float) or obj is None:
        return obj

    # deal with lists
    elif isinstance(obj, list) or isinstance(obj, tuple) or isinstance(obj, set):
        return [to_dict(obj = value) for value in obj]
    
    # deal with dictionaries
    elif isinstance(obj, dict):
        return {key: to_dict(obj = value) for key, value in obj.items()}

    # deal with objects
    else:
        return {key: to_dict(obj = value) for key, value in ([("name", obj.__class__.__name__)] + list(vars(obj).items()))}


def load_annotation(annotation: dict):
    """Return an expressive feature object given an annotation dictionary. For loading from .json."""

    match annotation["name"]:
        case "Text":
            return Text(text = str(annotation["text"]), is_system = bool(annotation["is_system"]), style = str(annotation["style"]))
        case "Subtype":
            return Subtype(subtype = str(annotation["subtype"]))                                                                                                                                                   
        case "RehearsalMark":
            return RehearsalMark(text = str(annotation["text"]))
        case "TechAnnotation":
            return TechAnnotation(text = str(annotation["text"]), tech_type = str(annotation["tech_type"]), is_system = bool(annotation["is_system"]))
        case "Dynamic":
            return Dynamic(subtype = str(annotation["subtype"]), velocity = int(annotation["velocity"]))
        case "Fermata":
            return Fermata(is_fermata_above = bool(annotation["is_fermata_above"]))
        case "Arpeggio":
            return Arpeggio(subtype = Arpeggio.SUBTYPES.index(annotation["subtype"]))
        case "Tremolo":
            return Tremolo(subtype = str(annotation["subtype"]))
        case "ChordLine":
            return ChordLine(subtype = ChordLine.SUBTYPES.index(annotation["subtype"]), is_straight = bool(annotation["is_straight"]))
        case "Ornament":
            return Ornament(subtype = str(annotation["subtype"]))
        case "Articulation":
            return Articulation(subtype = str(annotation["subtype"]))
        case "Notehead":
            return Notehead(subtype = str(annotation["subtype"]))
        case "Symbol":
            return Symbol(subtype = str(annotation["subtype"]))
        case "Bend":
            return Bend(points = [Point(time = int(point["time"]), pitch = int(point["pitch"]), vibrato = int(point["vibrato"])) for point in annotation["points"]])
        case "TremoloBar":
            return TremoloBar(points = [Point(time = int(point["time"]), pitch = int(point["pitch"]), vibrato = int(point["vibrato"])) for point in annotation["points"]])
        case "Spanner":
            return Spanner(duration = int(annotation["duration"]))
        case "SubtypeSpanner":
            return SubtypeSpanner(duration = int(annotation["duration"]), subtype = annotation["subtype"])
        case "TempoSpanner":
            return TempoSpanner(duration = int(annotation["duration"]), subtype = str(annotation["subtype"]))
        case "TextSpanner":
            return TextSpanner(duration = int(annotation["duration"]), text = str(annotation["text"]), is_system = bool(annotation["is_system"]))
        case "HairPinSpanner":
            return HairPinSpanner(duration = int(annotation["duration"]), subtype = str(annotation["subtype"]), hairpin_type = int(annotation["hairpin_type"]))
        case "SlurSpanner":
            return SlurSpanner(duration = int(annotation["duration"]), is_slur = bool(annotation["is_slur"]))
        case "PedalSpanner":
            return PedalSpanner(duration = int(annotation["duration"]))
        case "TrillSpanner":
            return TrillSpanner(duration = int(annotation["duration"]), subtype = str(annotation["subtype"]), ornament = str(annotation["ornament"]))
        case "VibratoSpanner":
            return VibratoSpanner(duration = int(annotation["duration"]), subtype = str(annotation["subtype"]))
        case "GlissandoSpanner":
            return GlissandoSpanner(duration = int(annotation["duration"]), is_wavy = bool(annotation["is_wavy"]))
        case "OttavaSpanner":
            return OttavaSpanner(duration = int(annotation["duration"]), subtype = str(annotation["subtype"]))
        case _:
            raise KeyError("Unknown annotation type.")

##################################################

# BETTER MUSIC CLASS
##################################################

class BetterMusic(muspy.music.Music):
    """A universal container for symbolic music, better suited for storing expressive features than MusPy.

    Attributes
    ----------
    metadata : :class:`read_mscz.Metadata`, default: `Metadata()`
        Metadata.
    resolution : int, default: `muspy.DEFAULT_RESOLUTION` (24)
        Time steps per quarter note.
    tempos : list of :class:`read_mscz.Tempo`, default: []
        Tempo changes.
    key_signatures : list of :class:`read_mscz.KeySignature`, default: []
        Key signatures changes.
    time_signatures : list of :class:`read_mscz.TimeSignature`, default: []
        Time signature changes.
    barlines : list of :class:`read_mscz.Barline`, default: []
        Barlines.
    beats : list of :class:`read_mscz.Beat`, default: []
        Beats.
    lyrics : list of :class:`read_mscz.Lyric`, default: []
        Lyrics.
    annotations : list of :class:`read_mscz.Annotation`, default: []
        Annotations.
    tracks : list of :class:`read_mscz.Track`, default: []
        Music tracks.
    song_length : int
        The length of the song (in time steps).

    Note
    ----
    Indexing a BetterMusic object returns the track of a certain index. That is, ``music[idx]`` returns ``music.tracks[idx]``. Length of a Music object is the number of tracks. That is, ``len(music)`` returns ``len(music.tracks)``.

    """


    _attributes = OrderedDict([("metadata", Metadata), ("resolution", int), ("tempos", Tempo), ("key_signatures", KeySignature), ("time_signatures", TimeSignature), ("barlines", Barline), ("beats", Beat), ("lyrics", Lyric), ("annotations", Annotation), ("tracks", Track), ("song_length", int)])
    _optional_attributes = ["metadata", "resolution", "tempos", "key_signatures", "time_signatures", "barlines", "beats", "lyrics", "annotations", "tracks", "song_length"]
    _list_attributes = ["tempos", "key_signatures", "time_signatures", "barlines", "beats", "lyrics", "annotations", "tracks"]


    # INITIALIZER
    ##################################################

    def __init__(self, metadata: Metadata = None, resolution: int = None, tempos: List[Tempo] = None, key_signatures: List[KeySignature] = None, time_signatures: List[TimeSignature] = None, barlines: List[Barline] = None, beats: List[Beat] = None, lyrics: List[Lyric] = None, annotations: List[Annotation] = None, tracks: List[Track] = None, song_length: int = None):
        self.metadata = metadata if metadata is not None else Metadata()
        self.resolution = resolution if resolution is not None else muspy.DEFAULT_RESOLUTION
        self.tempos = tempos if tempos is not None else []
        self.key_signatures = key_signatures if key_signatures is not None else []
        self.time_signatures = time_signatures if time_signatures is not None else []
        self.beats = beats if beats is not None else []
        self.barlines = barlines if barlines is not None else []
        self.lyrics = lyrics if lyrics is not None else []
        self.annotations = annotations if annotations is not None else []
        self.tracks = tracks if tracks is not None else []
        self.song_length = self.get_song_length() if song_length is None else song_length

    ##################################################


    # PRETTY PRINTING
    ##################################################

    def print(self, output_filepath: str = None, remove_empty_lines: bool = True):
        """Print the BetterMusic object in a pretty way.
        
        Parameters
        ---------
        output_filepath : str, optional
            If provided, outputs the yaml to the provided filepath. If not provided, prints to stdout
        remove_empty_lines : bool, optional, default: True
            Whether or not to remove empty lines from the output

        """

        # instantiate output
        output = ""
        divider = "".join(("=" for _ in range(100))) + "\n" # divider

        # loop through fields to maintain order
        for attribute in self.__dict__.keys():
            
            output += divider

            # yaml dump normally
            if attribute != "resolution":
                output += f"{attribute.upper()}\n"
                output += sub(pattern = "!!python/object:.*classes.", repl = "", string = yaml.dump(data = self.__dict__[attribute]))

            # resolution is special, since it's just a number
            else:
                output += f"{attribute.upper()}: {self.__dict__[attribute]}\n"
        output += divider

        # remove_empty_lines
        if remove_empty_lines:

            output_filtered = "" # instantiate
            for line in output.splitlines():
                if not any((hitword in line for hitword in ("null", "[]"))): # if line contains null or empty list
                    output_filtered += line + "\n"

            output = output_filtered # reset output
                
        # output
        if output_filepath:
            with open(output_filepath, "w") as file:
                file.write(output)
        else:
            print(output)
    
    ##################################################


    # CONVERSIONS BETWEEN MUSPY TIME SYSTEM AND REAL TIME / MEASURES
    ##################################################
    
    def metrical_time_to_absolute_time(self, time_steps: int) -> float:
        """Convert from MusPy time (in time steps) to Absolute time (in seconds).
        
        Parameters
        ---------
        time_steps : int
            The time_steps value to convert
        """

        # create list of temporal features (tempo and time_signature)
        temporal_features = sorted(self.time_signatures + self.tempos, key = lambda obj: obj.time)
        temporal_features.insert(0, TimeSignature(time = 0, measure = 1, numerator = 4, denominator = 4)) # add default starting time_signature
        temporal_features.insert(1, Tempo(time = 0, measure = 1, qpm = 60)) # add default starting tempo
        temporal_features.append(TimeSignature(time = self.song_length, measure = 1, numerator = 4, denominator = 4)) # add default ending time_signature

        # initialize some variables
        time_signature_idx = 0 # keep track of most recent time_signature
        tempo_idx = 1 # keep track of most recent tempo
        most_recent_time_step = 0 # keep track of most recent time step
        reached_time_steps = False # check if we ever reached time_steps, if we didnt, raise an error
        time = 0.0 # running count of time elapsed

        # loop through temporal features
        for i in range(2, len(temporal_features)):

            # check if we reached time_steps
            if time_steps <= temporal_features[i].time:
                end = time_steps
                reached_time_steps = True # update boolean flag
            else:
                end = temporal_features[i].time
            period_length = end - most_recent_time_step
            
            # update time elapsed
            quarters_per_minute_at_tempo = temporal_features[tempo_idx].qpm + DIVIDE_BY_ZERO_CONSTANT # to avoid divide by zero error
            time_signature_denominator = temporal_features[time_signature_idx].denominator + DIVIDE_BY_ZERO_CONSTANT
            time += (period_length / self.resolution) * (60 / quarters_per_minute_at_tempo) * (4 / time_signature_denominator)

            # break if reached time steps
            if reached_time_steps:
                return time

            # update most recent time step
            most_recent_time_step += period_length

            # check for temporal feature type
            if type(temporal_features[i]) is TimeSignature:
                time_signature_idx = i
            elif type(temporal_features[i]) is Tempo:
                tempo_idx = i

        # return end time if we never reached time steps
        return time
    
        # if still haven't reached time steps by the time we've parsed through the whole song
        # if not reached_time_steps: # go on with pace at the end
        #     period_length = time_steps - self.song_length
        #     time += (period_length / self.resolution) * (60 / temporal_features[tempo_idx].qpm) * (4 / temporal_features[time_signature_idx].denominator)
        #     return time

    ##################################################


    # GET THE LENGTH OF THE SONG IN TIME STEPS
    ##################################################

    def _get_max_time_obj_helper(self, obj) -> int:
        end_time = obj.time
        if hasattr(obj, "duration"): # look for duration at top-level
            end_time += obj.duration
        elif hasattr(obj, "annotation"): # look for duration
            if hasattr(obj.annotation, "duration"): # within an annotation
                end_time += obj.annotation.duration
        return end_time
    def get_song_length(self) -> int:
        """Return the length of the song in time steps."""
        all_objs = self.tempos + self.key_signatures + self.time_signatures + self.beats + self.barlines + self.lyrics + self.annotations + sum([track.notes + track.annotations + track.lyrics for track in self.tracks], [])
        if len(all_objs) > 0:
            max_time_obj = max(all_objs, key = self._get_max_time_obj_helper)
            max_time = max_time_obj.time + (max_time_obj.duration if hasattr(max_time_obj, "duration") else 0) # + self.resolution # add a quarter note at the end for buffer
        else:
            max_time = 0
        # final_beat = self.beats[-1].time if len(self.beats) >= 1 else 0 # (2 * self.beats[-1].time) - self.beats[-2].time
        # return int(max(max_time, final_beat))
        return max_time

    ##################################################


    # SAVE AS JSON
    ##################################################

    def save_json(self, path: str, ensure_ascii: bool = False, compressed: bool = None, **kwargs) -> str:
        """Save a Music object to a JSON file.

        Parameters
        ----------
        path : str
            Path to save the JSON data.
        ensure_ascii : bool, default: False
            Whether to escape non-ASCII characters. Will be passed to PyYAML's `yaml.dump`.
        compressed : bool, optional
            Whether to save as a compressed JSON file (`.json.gz`). Has no effect when `path` is a file object. Defaults to infer from the extension (`.gz`).
        **kwargs
            Keyword arguments to pass to :py:func:`json.dumps`.

        Notes
        -----
        When a path is given, use UTF-8 encoding and gzip compression if `compressed=True`.

        """
        
        # convert self to dictionary
        data = {
            "metadata": to_dict(obj = self.metadata),
            "resolution": self.resolution,
            "tempos": to_dict(obj = self.tempos),
            "key_signatures": to_dict(obj = self.key_signatures),
            "time_signatures": to_dict(obj = self.time_signatures),
            "beats": to_dict(obj = self.beats),
            "barlines": to_dict(obj = self.barlines),
            "lyrics": to_dict(obj = self.lyrics),
            "annotations": to_dict(obj = self.annotations),
            "tracks": to_dict(obj = self.tracks),
            "song_length": self.song_length
        }

        # convert dictionary to json obj
        data = json.dumps(obj = data, ensure_ascii = ensure_ascii, **kwargs)

        # determine if compression is inferred
        if compressed is None:
            compressed = str(path).lower().endswith(".gz")

        # either compress or not
        if compressed:
            path += "" if path.lower().endswith(".gz") else ".gz" # make sure it ends with gz
            with gzip.open(path, "wt", encoding = "utf-8") as file:
                file.write(data)
        else:
            with open(path, "w", encoding = "utf-8") as file:
                file.write(data)
        
        # return the path to which it was saved
        return path

    # wraps the main load_json() function into an instance method
    def load_json(self, path: str):
        """Load a Music object from a JSON file.

        Parameters
        ----------
        path : str
            Path to the JSON data.
        """

        # load .json file
        music = load_json(path = path)

        # set equal to self
        self.metadata = music.metadata
        self.resolution = music.resolution
        self.tempos = music.tempos
        self.key_signatures = music.key_signatures
        self.time_signatures = music.time_signatures
        self.beats = music.beats
        self.barlines = music.barlines
        self.lyrics = music.lyrics
        self.annotations = music.annotations
        self.tracks = music.tracks
        self.song_length = music.song_length

    ##################################################


    # TRIM
    ##################################################

    def trim(self, start: int = 0, end: int = -1):
        """Trim the BetterMusic object.

        Parameters
        ----------
        start : int, default: 0
            Time step at which to trim. Anything before this timestep will be removed.
        end : int, default: song_length
            Time step at which to trim. Anything after this timestep will be removed.
        """

        # deal with start and end arguments
        if end < start:
            end = self.song_length

        # tempos, key_signatures, time_signatures, beats, barlines, and lyrics, all of which lack duration
        self.tempos = [tempo for tempo in self.tempos if (start <= tempo.time and tempo.time < end)] # trim tempos
        self.key_signatures = [key_signature for key_signature in self.key_signatures if (start <= key_signature.time and key_signature.time < end)] # trim key_signatures
        self.time_signatures = [time_signature for time_signature in self.time_signatures if (start <= time_signature.time and time_signature.time < end)] # trim time_signatures
        self.beats = [beat for beat in self.beats if (start <= beat.time and beat.time < end)] # trim beats
        self.barlines = [barline for barline in self.barlines if (start <= barline.time and barline.time < end)] # trim barlines
        self.lyrics = [lyric for lyric in self.lyrics if (start <= lyric.time and lyric.time < end)] # trim lyrics

        # system annotations
        self.annotations = [annotation for annotation in self.annotations if (start <= annotation.time and annotation.time < end)] # trim system annotations
        for i, annotation in enumerate(self.annotations): # loop through system annotations
            if hasattr(annotation.annotation, "duration"): # check for duration
                if (annotation.time + annotation.annotation.duration) > end: # if end of annotation is past the end
                    self.annotations[i].annotation.duration = end - annotation.time # cut duration off duration at end

        # tracks (lyrics, notes, chords, staff_annotations)
        for i in range(len(self.tracks)): # loop through tracks

            # lyrics (no duration)
            self.tracks[i].lyrics = [lyric for lyric in self.tracks[i].lyrics if (start <= lyric.time and lyric.time < end)]

            # notes
            self.tracks[i].notes = [note for note in self.tracks[i].notes if (start <= note.time and note.time < end)] # trim notes
            for j, note in enumerate(self.tracks[i].notes): # loop through notes
                if (note.time + note.duration) > end: # if end of note is past the end
                    self.tracks[i].notes[j].duration = end - note.time # cut duration off at end

            # chords
            self.tracks[i].chords = [chord for chord in self.tracks[i].chords if (start <= chord.time and chord.time < end)] # trim chords
            for j, chord in enumerate(self.tracks[i].chords): # loop through chords
                if (chord.time + chord.duration) > end: # if end of chord is past the end
                    self.tracks[i].chords[j].duration = end - chord.time # cut duration off at end

            # staff annotations
            self.tracks[i].annotations = [annotation for annotation in self.tracks[i].annotations if (start <= annotation.time and annotation.time < end)]
            for j, annotation in enumerate(self.tracks[i].annotations): # loop through system annotations
                if hasattr(annotation.annotation, "duration"): # check for duration
                    if (annotation.time + annotation.annotation.duration) > end: # if end of annotation is past the end
                        self.tracks[i].annotations[j].annotation.duration = end - annotation.time # cut duration off duration at end
        
        # update song_length
        self.song_length = self.get_song_length()

    ##################################################


    # WRITE
    ##################################################

    def write(self, path: str, kind: str = None, **kwargs):
        """Write a BetterMusic object in various file formats.

        Parameters
        ----------
        path : str
            Path to write to. File format can be inferred.
        kind : str, default: None
            File format of output. If not provided, the file format is inferred from `path`.
        """

        # infer kind if necessary
        if kind is None:
            if path.lower().endswith((".mid", ".midi")):
                kind = "midi"
            elif path.lower().endswith((".mxl", ".xml", ".mxml", ".musicxml")):
                kind = "musicxml"
            elif path.lower().endswith(("wav", "aiff", "flac", "oga")):
                kind = "audio"
            else:
                raise ValueError("Cannot infer file format from the extension (expect MIDI, MusicXML, WAV, AIFF, FLAC or OGA).")
        
        # output
        if kind.lower() == "midi": # write midi
            return write_midi(path = path, music = self, **kwargs)
        elif kind.lower() == "musicxml": # write musicxml
            return write_musicxml(path = path, music = self, **kwargs)
        elif kind.lower() == "audio": # write audio
            return write_audio(path = path, music = self, **kwargs)
        else:
            raise ValueError(f"Expect `kind` to be 'midi', 'musicxml', or 'audio', but got : {kind}.")

    ##################################################

##################################################


# LOAD A BETTERMUSIC OBJECT FROM JSON FILE
##################################################

def load_json(path: str) -> BetterMusic:
    """Load a Music object from a JSON file.

    Parameters
    ----------
    path : str
        Path to the JSON data.
    """

    # if file is compressed
    if path.lower().endswith(".gz"):
        with gzip.open(path, "rt", encoding = "utf-8") as file:
            data = json.load(fp = file)
    else:
        with open(path, "rt", encoding = "utf-8") as file:
            data = json.load(fp = file)

    # extract info from nested dictionaries
    metadata = Metadata(
        schema_version = str(data["metadata"]["schema_version"]) if data["metadata"]["schema_version"] is not None else None,
        title = str(data["metadata"]["title"]) if data["metadata"]["title"] is not None else None,
        subtitle = str(data["metadata"]["subtitle"]) if data["metadata"]["subtitle"] is not None else None,
        creators = data["metadata"]["creators"] if data["metadata"]["creators"] is not None else None,
        copyright = str(data["metadata"]["copyright"]) if data["metadata"]["copyright"] is not None else None,
        collection = str(data["metadata"]["collection"]) if data["metadata"]["collection"] is not None else None,
        source_filename = str(data["metadata"]["source_filename"]) if data["metadata"]["source_filename"] is not None else None,
        source_format = str(data["metadata"]["source_format"]) if data["metadata"]["source_format"] is not None else None
    )
    tempos = [Tempo(
        time = int(tempo["time"]),
        qpm = float(tempo["qpm"]) if tempo["qpm"] is not None else None,
        text = str(tempo["text"]) if tempo["text"] is not None else None,
        measure = int(tempo["measure"]) if tempo["measure"] is not None else None
    ) for tempo in data["tempos"]]
    key_signatures = [KeySignature(
        time = int(key_signature["time"]),
        root = int(key_signature["root"]) if key_signature["root"] is not None else None,
        mode = str(key_signature["mode"]) if key_signature["mode"] is not None else None,
        fifths = int(key_signature["fifths"]) if key_signature["fifths"] is not None else None,
        root_str = str(key_signature["root_str"]) if key_signature["root_str"] is not None else None,
        measure = int(key_signature["measure"]) if key_signature["measure"] is not None else None
    ) for key_signature in data["key_signatures"]]
    time_signatures = [TimeSignature(
        time = int(time_signature["time"]),
        numerator = int(time_signature["numerator"]) if time_signature["numerator"] is not None else None,
        denominator = int(time_signature["denominator"]) if time_signature["denominator"] is not None else None,
        measure = int(time_signature["measure"]) if time_signature["measure"] is not None else None
    ) for time_signature in data["time_signatures"]]
    beats = [Beat(
        time = int(beat["time"]),
        is_downbeat = bool(beat["is_downbeat"]) if beat["is_downbeat"] is not None else None,
        measure = int(beat["measure"]) if beat["measure"] is not None else None
    ) for beat in data["beats"]]
    barlines = [Barline(
        time = int(barline["time"]),
        subtype = str(barline["subtype"]) if barline["subtype"] is not None else None,
        measure = int(barline["measure"]) if barline["measure"] is not None else None
    ) for barline in data["barlines"]]
    lyrics = [Lyric(
        time = int(lyric["time"]),
        lyric = str(lyric["lyric"]) if lyric["lyric"] is not None else None,
        measure = int(lyric["measure"]) if lyric["measure"] is not None else None
    ) for lyric in data["lyrics"]]
    annotations = [Annotation(
        time = int(annotation["time"]),
        annotation = load_annotation(annotation = annotation["annotation"]) if annotation["annotation"] is not None else None,
        measure = int(annotation["measure"]) if annotation["measure"] is not None else None,
        group = str(annotation["group"]) if annotation["group"] is not None else None
    ) for annotation in data["annotations"]]
    tracks = [Track(
        program = int(track["program"]) if track["program"] is not None else None,
        is_drum = bool(track["is_drum"]) if track["is_drum"] is not None else None,
        name = str(track["name"]) if track["name"] is not None else None,
        notes = [Note(
            time = int(note["time"]),
            pitch = int(note["pitch"]) if note["pitch"] is not None else None,
            duration = int(note["duration"]) if note["duration"] is not None else None,
            velocity = int(note["velocity"]) if note["velocity"] is not None else None,
            pitch_str = str(note["pitch_str"]) if note["pitch_str"] is not None else None,
            is_grace = bool(note["is_grace"]) if note["is_grace"] is not None else None,
            measure = int(note["measure"]) if note["measure"] is not None else None
            ) for note in track["notes"]],
        chords = [Chord(
            time = int(chord["time"]),
            pitches = [int(pitch) for pitch in chord["pitches"]] if chord["pitches"] is not None else None,
            duration = int(chord["duration"]) if chord["duration"] is not None else None,
            velocity = int(chord["velocity"]) if chord["velocity"] is not None else None,
            pitches_str = [str(pitch_str) for pitch_str in chord["pitches_str"]] if chord["pitches_str"] is not None else None,
            measure = int(chord["measure"]) if chord["measure"] is not None else None
            ) for chord in track["chords"]],
        lyrics = [Lyric(
            time = int(lyric["time"]),
            lyric = str(lyric["lyric"]) if lyric["lyric"] is not None else None,
            measure = int(lyric["measure"]) if lyric["measure"] is not None else None
            ) for lyric in track["lyrics"]],
        annotations = [Annotation(
            time = int(annotation["time"]),
            annotation = load_annotation(annotation = annotation["annotation"]) if annotation["annotation"] is not None else None,
            measure = int(annotation["measure"]) if annotation["measure"] is not None else None,
            group = str(annotation["group"]) if annotation["group"] is not None else None
            ) for annotation in track["annotations"]]
    ) for track in data["tracks"]]

    # return a BetterMusic object
    return BetterMusic(
        metadata = metadata,
        resolution = int(data["resolution"]),
        tempos = tempos,
        key_signatures = key_signatures,
        time_signatures = time_signatures,
        beats = beats,
        barlines = barlines,
        lyrics = lyrics,
        annotations = annotations,
        tracks = tracks
    )

##################################################