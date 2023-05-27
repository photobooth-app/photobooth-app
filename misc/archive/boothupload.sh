#!/bin/bash

#setup rclone with "rclone config" first! use "boothupload" as remote name

SOURCE_DIR="$HOME/photobooth-app/data/original/"
DEST_DIR="boothupload:/"

#wait until wifi established for init sync.
sleep 10

while [[ true ]] ; do
	rclone sync --progress $SOURCE_DIR $DEST_DIR
	sleep 1
	inotifywait --timeout 300 -e modify,delete,create,move $SOURCE_DIR
done
