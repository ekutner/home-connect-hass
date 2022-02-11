#!/usr/bin/env bash

SCRIPT_PATH=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

$SCRIPT_PATH/post-start.sh
$SCRIPT_PATH/proxy.sh