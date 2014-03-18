#!/bin/bash

set -e
set -x

flake8 --ignore=H302,H802 --show-source ./

