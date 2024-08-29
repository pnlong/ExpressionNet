[![GitHub license](https://img.shields.io/github/license/pnlong/PDMX)](https://github.com/pnlong/PDMX/blob/master/LICENSE)

# PDMX: A Large-Scale *P*ublic *D*omain *M*usic*X*ML Dataset for Symbolic Music Processing

Recent [copyright infringement lawsuits against leading music generation companies](https://www.riaa.com/record-companies-bring-landmark-cases-for-responsible-ai-againstsuno-and-udio-in-boston-and-new-york-federal-courts-respectively) have sent shockwaves throughout the AI-Music community, highlighting the need for copyright-free training data. Meanwhile, the most prevalent format for symbolic music processing, MIDI, is well-suited for modeling sequences of notes but omits an abundance of extra musical information present in sheet music, which the MusicXML format addresses. To mitigate these gaps, we present **PDMX**: a large-scale open-source dataset of over 250K public domain MusicXML scores. We also introduce `MusicRender`, an extension of the Python library [MusPy](https://hermandong.com/muspy/doc/muspy.html)'s universal `Music` object, designed specifically to handle MusicXML.

---

## Installation



# Important Methods

We present a few important contributions to interact with both the PDMX dataset and MusicXML-like files.

### `MusicRender`

We introduce `MusicRender`, an extension of [MusPy](https://hermandong.com/muspy/doc/muspy.html)'s universal `Music` object, that can hold musical performance directives through its `annotations` field. `MusicRender` objects are accessible by calling:

```python
from pdmx import MusicRender
```

Let's say `music` is a `MusicRender` object. We can save `music` to the JSON file `path`, from which can later reinstate as another `MusicRender` object, with:

```python
music.save_json(path = path)
```

Additionally, if we want to write `music` as audio, we can use:

```python
music.write(path = path)
```

Where the output filetype is inferred from the filetype of `path` (`wav` is audio, `midi` is symbolic).

### `load_json()`

We store PDMX as JSONified `MusicRender` objects. We can reinstate these objects into Python by loading them with the `load_json()` function, which returns a `MusicRender` object given the JSON's path, `path`.

```python
from pdmx import load_json
music = load_json(path = path)
```

### `read_musescore()`

PDMX was created by scraping the public domain content of [MuseScore](https://musescore.com), a score-sharing online platform on which users can upload their own sheet music arrangements in a MusicXML-like format. MusPy alone lacked the ability to fully parse these files. Our `read_musescore()` function can, and returns a `MusicRender` object given the path to the MuseScore file, `path`.

```python
from pdmx import read_musescore
music = read_musescore(path = path)
```


## Citing & Authors

If you find this repository helpful, feel free to cite our publication [PDMX: A Large-Scale Public Domain MusicXML Dataset for Symbolic Music Processing]():

```tex

```

