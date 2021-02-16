#!/bin/sh -e

sudo apt -y install libsm6 libxrender1 libfontconfig1 python3.6-dev
cd `dirname $0`
virtualenv --python `which python3.6` .
. bin/activate
wget https://files.pythonhosted.org/packages/56/bb/905529e614a391170089578b0f4ec763a9f90d625f3996560ac57baae752/pyfestival-0.5.tar.gz -O pyfestival.tar.gz
tar zxf pyfestival.tar.gz
cd pyfestival-*
./setup.py install
cd ..
rm -fR pyfestival-* pyfestival.tar.gz
pip install -r requirements.txt
sed -i -e '1iimport _festival' -e '1,6{/^try:$/,/^[[:space:]]*import _festival/{d}}' lib/python3.6/site-packages/festival.py
