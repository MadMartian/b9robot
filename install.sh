#!/bin/sh -e

apt -y install libsm6 libxrender1 libfontconfig1 libxslt1-dev
cd `dirname $0`
virtualenv --python `which python3` .
. bin/activate
pip install -r requirements.txt
[ -d lib/python3.6/site-packages/festival.py ] && sed -i -e '1iimport _festival' -e '1,6{/^try:$/,/^[[:space:]]*import _festival/{d}}' lib/python3.6/site-packages/festival.py

mkdir -p /etc/b9robot/
cp logging.conf /etc/b9robot/
chmod go+rX -R /etc/b9robot/

cp b9robot.py /usr/local/bin/
cp b9robot.service /lib/systemd/user/
systemctl --user enable b9robot
