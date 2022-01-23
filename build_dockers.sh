#!/bin/bash

url="localhost:6880/reddit-bots/"
imagePrefix="animemes-"
# Make a loop for each docker image in the repo
imageNames=(
    "new-stream-save"
    "new-stream-comment-automod-save"
    "modque-stream"
    )
# imageName=new-stream-save
dateTag="$(date +%Y-%m-%d-%H%M)"
isFirst=true

for imageName in "${imageNames[@]}" ; do
    # Fully build image on first run, afterwards use cache
    if [ "$isFirst" = true ] ; then
        buildParameters="--pull --no-cache"
        isFirst=false
    else
        buildParameters=""
    fi

    # find and replace the dashes to also get the file name from the tag name
    # dockerfileName="$($imageName//-/_)"
    dockerfileName=$(echo "$imageName" | sed "s/-/_/g")
    #build + tag docker images
    docker build $buildParameters -t $url$imagePrefix$imageName:latest -t $url$imagePrefix$imageName:$dateTag -f $dockerfileName.dockerfile .
    #Push all docker images
    docker push --all-tags $url$imagePrefix$imageName
done