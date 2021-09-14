#!/bin/sh -e

sudo apt -y install libsm6 libxrender1 libfontconfig1 python3.6-dev
cd `dirname $0`
virtualenv --python `which python3.6` .
. bin/activate
pip install -r requirements.txt
sed -i -e '1iimport _festival' -e '1,6{/^try:$/,/^[[:space:]]*import _festival/{d}}' lib/python3.6/site-packages/festival.py
