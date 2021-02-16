#! /bin/bash

set -e

for dir in /opt/zeek*/bin; do
    export PATH=$PATH:$dir
done

export PATH="$PATH:$HOME/.local/bin"

test_head() {
    echo -e "\nInstalling locally from $GITHUB_SHA:"
    $zkg install --force .
    local res=$?

    if [ $res -eq 0 ]; then
        echo -e "\nSuccess, wiping package state"
        $zkg purge --force
    fi

    return $res
}

test_latest_tag() {
    local tag=$($zkg info --json . | jq -r '.[].versions[-1]')

    if [ -z "$tag" ] || [ "$tag" = null ]; then
        # Package doesn't have tags
        return 0
    fi

    echo -e "\nInstalling $tag:"
    $zkg install --force --version "$tag" .
    local res=$?

    if [ $res -eq 0 ]; then
        echo -e "\nSuccess, wiping package state"
        $zkg purge --force
    fi

    return $res
}

# Check if our zkg supports --user, and if so, use it:
# Use home directory to avoid sudo for all zkg invocations
if zkg --help | grep -q -- '--user' >/dev/null; then
    zkg="zkg --user"
else
    zkg=zkg
fi

echo -e "Package information:"
$zkg info .

while [ "$1" != "" ]; do
    case "$1" in
        "head")
            test_head
            shift
            ;;
        "latest-tag")
            test_latest_tag
            shift
            ;;
        *)
            break;
            ;;
    esac
done
