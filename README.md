# MpdCast DAB
=====================

MPD to Google cast streaming application with support for DAB+ radio

MpdCast DAB is a fork from welle.io (https://github.com/AlbrechtL/welle.io).

Table of contents
====

  * [Download](#download)
  * [Usage](#usage)
  * [Supported Hardware](#supported-hardware)
  * [Building](#building)

Download
========
### Stable binaries
* **Debian** or **Ubuntu** 24.04+
  * `add-apt-repository ppa:lamarqe/ppa`
  * `apt update`
  * `apt install mpdcast-dab`

Usage
=====
The command-line parameters are:

Parameter | Description | Default Value
------ | ---------- | ---------- 
--silent | Print errors only | False (True when running as systemd service) 
--conf | Show version | /etc/mpd.conf

Supported Hardware
====================
MpdCast DAB is intended to be used with an RTL-SDR device (https://www.rtl-sdr.com/)

Building
====================

General Information
---
The following libraries and their development files are needed:
* Python >= 3.11 
* FFTW3f
* libfaad
* librtlsdr

Debian / Ubuntu Linux
---
This section shows how to compile welle.io on Debian or Ubuntu (tested with Ubuntu 24.04).

1. Install the base requirements

```
sudo apt install git build-essential cmake
```

2. Install the following packages

```
sudo apt install python3-dev libfftw3-dev libfaad-dev librtlsdr-dev
```

3. Clone MpdCast DAB

```
git clone https://github.com/Lamarqe/mpdcast-dab.git
```

4. Build MpdCast DAB (using cmake)

```
mkdir build
cd build
cmake ..
make -j3
cd ..
cp build/libwelle_py.so mpdcast_dab/welle_python
```

5. Run MpdCast DAB and enjoy it

```
sudo ./mpdcast_dab/cast_sender/__main__.py
```
