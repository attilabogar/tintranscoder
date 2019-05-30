# tintranscoder

Tin (Audio Album) Transcoder

[![Build Status][1]][2]
[![SonarCloud Status][3]][4]
[![Coverage Status][5]][6]

[1]: https://travis-ci.org/attilabogar/tintranscoder.svg?branch=master
[2]: https://travis-ci.org/attilabogar/tintranscoder
[3]: https://sonarcloud.io/api/project_badges/measure?project=attilabogar_tintranscoder&metric=alert_status
[4]: https://sonarcloud.io/dashboard?id=attilabogar_tintranscoder
[5]: https://codecov.io/gh/attilabogar/tintranscoder/branch/master/graph/badge.svg
[6]: https://codecov.io/gh/attilabogar/tintranscoder


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

## License

    MIT License

    Copyright (c) 2019 Attila Bogár

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.

**NOTE**: This software depends on other packages that may be licensed under
different open source licenses.
