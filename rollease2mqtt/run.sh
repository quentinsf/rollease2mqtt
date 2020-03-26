#! /bin/bash

CONFIG_PATH=/data/options.json

DEVICE="$(jq --raw-output '.device' $CONFIG_PATH)"
MQTT_URL="$(jq --raw-output '.mqtt_url' $CONFIG_PATH)"

python3 main.py -d ${DEVICE} -m ${MQTT_URL}
