#!/usr/bin/env bash

function inotif()
{
	inotifywait . -rm -e close_write | while read dir event file
	do
		[ "$(<<<"$dir" grep git)" != "" ] && continue
		path="$dir$file"
		scp "$path" games:/home/ubuntu/mc-discord-bot/"$path"
		ssh -t games "sudo systemctl restart discord"
	done
}

function simulate_inotify()
{
	echo "WARNING: Inotify utils not found! Simulating behavior."
	echo "         This will consume more resources than Inotify!"

	echo "Building initial list of files..."
	declare -A files
	while read i
	do
		files["$i"]=$(date +%s -r "$i")
	done < <(git status --porcelain | cut -b 3-)

	echo "Watching files..."
	while true
	do
		#Make sure new modified files are watched
		while read file
		do
			if [ "${files["$file"]}" == '' ]
			then
				files["$file"]=NEW
			fi
		done < <(git status --porcelain | cut -b 3-)

		#Check file modify time, and copy up if it's not the same as last mod time
		for file in "${!files[@]}"
		do
			modtime=$(date +%s -r "$file")
			if [ "$modtime" != "${files["$file"]}" ]
			then
				files["$file"]="$modtime"
				scp "$file" games:/home/ubuntu/mc-discord-bot/"$file"
				ssh -t games "sudo systemctl restart discord"
			fi
		done
	done
}

function sync_files()
{
	if which inotifywait &>/dev/null
	then
		inotif
	else
		simulate_inotify
	fi
}

ssh -t games "sudo systemctl stop discord" &

ssh -oConnectTimeout=10 -n games "cd /home/ubuntu/mc-discord-bot && git checkout . && git clean -fd && git fetch origin && git checkout $(git branch | grep '*' | cut -b 2-) && git pull" || exit 1
for i in $(git status --porcelain | cut -b 3-)
do
	scp "$i" games:/home/ubuntu/mc-discord-bot/"$i" &
done
wait

sync_files &

ssh -t games "sudo systemctl start discord"

echo "Starting server..."

ssh -t games "
	trap 'cd /home/ubuntu/mc-discord-bot; git checkout .; git clean -fd; sudo systemctl restart discord; exit' INT
	journalctl -n 0 -f -u discord
"

kill -TERM -$$
