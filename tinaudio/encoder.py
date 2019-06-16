from .shared import *
from .album import TrackMeta

class Encoder(object):
    """
    Encoder

    Output support for (FLAC, Opus, AAC, MP3)
    Downmix capability for multichannel audio
    """
    def __init__(self, codec, downmix) -> None:
        self.codec = codec
        self.downmix = downmix

    def suffix(self) -> str:
        if self.codec == 'aac':
            return "m4a"
        else:
            return self.codec

    def downmixWAV(self, wavf: str) -> None:
        """
        Downmix to 2 channels if multichannel audio

        Arguments:
            wavf {str} -- WAV file
        """
        # HACK: https://github.com/jiaaro/pydub/issues/129
        # FIXME: a reliable method to get number of wav channels
        multichannel = True
        try:
            w = wave.open(wavf, 'rb')
            if w.getnchannels() < 3:
                multichannel = False
            w.close()
        except Exception:
            pass
        if multichannel:
            newwavf = wavf[:-4] + "-stereo.wav"
            FNULL = open(os.devnull, 'w')
            subprocess.call(['ffmpeg', '-y', '-i', wavf, '-c:a', 'pcm_s24le', '-ac', '2', newwavf], stdout=FNULL, stderr=FNULL)
            FNULL.close()
            os.remove(wavf)
            os.rename(newwavf, wavf)

    def encode(self, wavf: str, dstf: str, cover: str, meta: TrackMeta) -> None:
        """
        Entrypoint to encode a PCM WAV according to self.codec

        Calls the corresponding encoding flavour subroutine

        Arguments:
            wavf {str} -- PCM WAV file
            dstf {str} -- Output file
            cover {str} -- Cover file
            meta {TrackMeta} -- Metadata

        Raises:
            Exception: Invalid output format called
        """
        if self.downmix:
            self.downmixWAV(wavf)
        if self.codec == 'opus':
            self.encodeOpus(wavf, dstf, cover, meta)
        elif self.codec == 'flac':
            self.encodeFLAC(wavf, dstf, cover, meta)
        elif self.codec == 'aac':
            self.encodeAAC(wavf, dstf, cover, meta)
        elif self.codec == 'mp3':
            self.encodeMP3(wavf, dstf, cover, meta)
        else:
            raise Exception('Unsupported encoder: ' + self.codec)

    def encodeOpus(self, wavf: str, dstf: str, cover: str, meta: TrackMeta) -> None:
        """
        Encodes a PCM WAV file to Opus format

        Arguments:
            wavf {str} -- PCM WAV file
            dstf {str} -- Output file
            cover {str} -- Cover file
            meta {TrackMeta} -- Metadata
        """
        # TODO: bitrate 160/128
        FNULL = open(os.devnull, 'w')
        args = ['opusenc', '--bitrate', '192', '--quiet']
        if cover:
            args.append('--picture')
            args.append(cover)
        args.append(wavf)
        args.append(dstf)
        subprocess.call(args, stdout=FNULL, stderr=FNULL)
        FNULL.close()
        # tag the file
        opus = OggOpus(dstf)
        # no need to save r128_track_gain
        for c in sorted(meta.keys()):
            opus[c] = meta[c]
        opus.save()

    def encodeFLAC(self, wavf: str, dstf: str, cover: str, meta: TrackMeta) -> None:
        """
        Encodes a PCM WAV file to FLAC format

        Arguments:
            wavf {str} -- PCM WAV file
            dstf {str} -- Output file
            cover {str} -- Cover file
            meta {TrackMeta} -- Metadata
        """
        FNULL = open(os.devnull, 'w')
        args = ['flac', '-f', '--totally-silent', '--best']
        if cover:
            args.append('--picture')
            args.append(cover)
        args.append('-o')
        args.append(dstf)
        args.append(wavf)
        subprocess.call(args, stdout=FNULL, stderr=FNULL)
        FNULL.close()
        # tag the file
        f = FLAC(dstf)
        for c in sorted(meta.keys()):
            f[c] = meta[c]
        f.save()

    def encodeAAC(self, wavf: str, dstf: str, cover: str, meta: TrackMeta) -> None:
        """
        Encodes a PCM WAV file to MPEG-4 AAC format (using NeroAAC)

        Arguments:
            wavf {str} -- PCM WAV file
            dstf {str} -- Output file
            cover {str} -- Cover file
            meta {TrackMeta} -- Metadata
        """
        FNULL = open(os.devnull, 'w')
        subprocess.call(['neroAacEnc', '-q', '0.5',
                         '-if', wavf, '-of', dstf], stdout=FNULL, stderr=FNULL)
        FNULL.close()
        # tag AAC
        mm = TrackMeta(meta)
        aac = MP4(dstf)
        aac['\xa9nam'] = mm.title()
        aac['\xa9ART'] = mm.artist()
        aac['\xa9alb'] = mm.album()
        aac['aART'] = mm.albumartist()
        if mm.date():
            aac['\xa9day'] = mm.date()

        # calculating tracknumbers
        t = mm.tracknumber()
        tt = mm.tracktotal()
        aac["trkn"] = [(int(t), int(tt))]

        # calculating discnumber
        d = mm.discnumber()
        dd = mm.disctotal()
        aac["disk"] = [(int(d), int(dd))]

        # composer
        if mm.composer():
            aac['\xa9wrt'] = mm.composer()

        # cover
        if cover:
            data = open(cover, 'rb').read()
            covr = []
            if cover.endswith('png'):
                covr.append(MP4Cover(data, MP4Cover.FORMAT_PNG))
            else:
                covr.append(MP4Cover(data, MP4Cover.FORMAT_JPEG))
            aac['covr'] = covr

        # save AAC tags
        aac.save()

    def encodeMP3(self, wavf: str, dstf: str, cover: str, meta: TrackMeta) -> None:
        """
        Encodes a PCM WAV file to MPEG-1 Audio Layer 3 format

        Arguments:
            wavf {str} -- PCM WAV file
            dstf {str} -- Output file
            cover {str} -- Cover file
            meta {TrackMeta} -- Metadata
        """
        FNULL = open(os.devnull, 'w')
        subprocess.call(['lame', '-V2', wavf, dstf], stdout=FNULL, stderr=FNULL)
        FNULL.close()
        # tag MP3
        mm = TrackMeta(meta)
        mp3 = MP3(dstf, ID3=ID3)
        mp3["TIT2"] = TIT2(encoding=3, text=mm.title())
        mp3["TPE1"] = TPE1(encoding=3, text=mm.artist())
        mp3["TALB"] = TALB(encoding=3, text=mm.album())
        mp3["TPE2"] = TPE2(encoding=3, text=mm.albumartist())
        if mm.date():
            mp3["TDRC"] = TDRC(encoding=3, text=mm.date())
        mp3["TRCK"] = TRCK(encoding=3,
                           text=mm.tracknumber() + "/" + mm.tracktotal())
        mp3["TPOS"] = TPOS(encoding=3,
                           text=mm.discnumber() + "/" + mm.disctotal())

        # composer
        if mm.composer():
            mp3["TCM"] = TCM(encoding=3, text=mm.composer())

        # cover
        if cover:
            data = open(cover, 'rb').read()
            if cover.endswith('png'):
                mime = 'image/png'
            else:
                mime = 'image/jpeg'
            mp3.tags.add(APIC(encoding=3, mime=mime, type=3, desc=u'Cover', data=data))

        # save
        mp3.save()