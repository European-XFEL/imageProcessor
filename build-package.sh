#!/bin/bash

if [ -z $KARABO ]; then
    if [ -e $HOME/.karabo/karaboFramework ]; then
        KARABO=$(cat $HOME/.karabo/karaboFramework)
    else
      echo "ERROR Could not find karaboFramework. Make sure you have installed the karaboFramework."
      exit 1
    fi
fi

$KARABO/bin/.bundle-pythonplugin.sh $@
