FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# The base image ships an apt source for yarn whose signing key is no longer
# available, so `apt-get update` fails with NO_PUBKEY 62D54FD4003F6525. Every
# dev container feature runs apt-get update before installing, which made
# desktop-lite (and with it the noVNC game desktop) fail to install at all.
# Features are layered on top of this image, so the source has to go here.
RUN rm -f /etc/apt/sources.list.d/yarn.list; \
    grep -rl 'dl\.yarnpkg\.com' /etc/apt/sources.list.d/ 2>/dev/null | xargs -r rm -f; \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        swig \
        libsdl2-2.0-0 \
        libsdl2-image-2.0-0 \
        libsdl2-mixer-2.0-0 \
        libsdl2-ttf-2.0-0 \
    && rm -rf /var/lib/apt/lists/*
