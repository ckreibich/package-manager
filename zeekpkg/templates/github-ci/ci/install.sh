#! /bin/bash

# Bail on any error, show commands
set -e

package="$1"

if [ -z "$package" ]; then
    echo "Need package name to install."
    exit 1
fi

sudo apt-get install $package

for dir in /opt/zeek*/bin; do
    export PATH=$PATH:$dir
done

# If this Zeek didn't include zkg, install via pip:
if ! command -v zkg &> /dev/null; then
    pip install zkg
    export PATH=$PATH:$HOME/.local/bin
fi

echo -e "\nZeek install info:"
echo "zeek: $(zeek-config --version)"
echo "zkg:  $(zkg --version)"
