FROM ubuntu:24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        coreutils \
        gawk \
        grep \
        sed \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /data /output

COPY access.log /data/access.log

WORKDIR /app
