#!/bin/bash

#this is for development purposes only, to stop the automattically
#running piparty scripts
#sudo supervisorctl stop joustmania
kill -9 $(ps aux | grep 'piparty' | awk '/Joust/{print $2}')
