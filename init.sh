#!/bin/bash

git submodule init
git submodule update
rm -rf ./eth2deposit
cp -r ./eth2.0-deposit-cli/eth2deposit ./eth2deposit

pip3 install -r requirements.txt