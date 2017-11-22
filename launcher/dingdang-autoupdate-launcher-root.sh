#!/bin/bash
sleep 1

# tmux session name
session_name="dingdang"

#Delete Cache
sudo rm -r /root/.cache
sudo rm -r /root/.netease-musicbox
sudo rm -r /root/userInfo
sleep 1

#Update dingdang-robot
cd /root/software/dingdang
git pull

#Update dingdang Requirements
sudo pip install --upgrade -r client/requirements.txt
sleep 1

#Update dingdang-contrib
cd /root/.dingdang/contrib
git pull

#Update dingdang-contrib Requirements
sudo pip install --upgrade -r requirements.txt
sleep 1

#Restore Configuration of AlsaMixer
if [ -f /root/asound.state ]; then
    alsactl --file=/root/asound.state restore
    sleep 1
fi

#Launch Dingdang in tmux
sudo tmux new-session -d -s $session_name $HOME/software/dingdang/dingdang.py
sleep 1

#Start Respeaker-Switcher in Background
if [ -d /root/ReSpeaker-Switcher ]; then
    sudo python /root/ReSpeaker-Switcher/switcher.py &
fi
