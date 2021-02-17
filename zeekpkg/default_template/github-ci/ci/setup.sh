#! /bin/bash

# Set up repo to install from SUSE OBS, as per
# https://software.opensuse.org//download.html?project=security%3Azeek&package=zeek-nightly:
echo 'deb http://download.opensuse.org/repositories/security:/zeek/xUbuntu_20.04/ /' \
    | sudo tee /etc/apt/sources.list.d/security:zeek.list
curl -fsSL https://download.opensuse.org/repositories/security:zeek/xUbuntu_20.04/Release.key \
    | gpg --dearmor \
    | sudo tee /etc/apt/trusted.gpg.d/security_zeek.gpg > /dev/null

sudo apt-get update
