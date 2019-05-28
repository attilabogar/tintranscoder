FROM archlinux/base
LABEL authors="Attila Bogár <attila.bogar@gmail.com>"

RUN echo -e '[multilib]\nInclude = /etc/pacman.d/mirrorlist' >> /etc/pacman.conf
RUN echo -e '[avb]\nServer = https://s3.eu-west-2.amazonaws.com/avb-repo/$repo/$arch\nSigLevel = Optional TrustAll' >> /etc/pacman.conf

RUN pacman --noconfirm -Syy && pacman --noconfirm -S \
  python python-mutagen python-yaml flac opus-tools lame neroaac ffmpeg imagemagick \
  rgain gst-plugins-bad gst-plugins-good

RUN useradd \
  --shell /bin/bash  \
  --create-home \
  --uid 1000 \
  user

USER user
