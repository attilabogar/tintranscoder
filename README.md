# tintranscoder

Tin (Audio Album) Transcoder


## Description

CD album transcoder prototype implemented in python 3

+ Input: Audio albums (CD & High-Fidelity Pure Audio)
  + FLAC (CD-Image or split-tracks)
  + DTS
+ Output:
  + FLAC
  + OPUS
  + AAC (using NeroAAC)
  + MP3 (using lame)
+ Multi-Album support
+ Cover Image (conversion) + embedding
+ Parallel Execution (using all available CPU's)
+ Audio Channel downmixing (using ffmpeg)


## Status

Prototype - Work in Progress


## TODO

+ tests
  + unit tests
  + doctests
  + coverage
  + pyflakes
+ modularise
+ re-factor into library
+ type hints
+ documentation
+ usage
