## 0.7 - 2019-12-16

* Another bug-fix: apologies!

## 0.6 - 2019-12-16

* Fix a bug in the periodic-update code.

## 0.5 - 2019-12-16

* Periodically request motor positions.   I don't know the effect this might have on motor battery life if done too frequently, so the frequency can be specified with the refresh_mins option.  This process will also register any new motors, so if they weren't online at startup time, they may now be discovered later.

## 0.4 - 2019-11-03

* Starting to be structured more like a standard Hassio addon, with prebuilt Docker images.

* Documentation updates.

## 0.3 - 2019-11-03

Changelog starts.

* Default MQTT topics live under 'homeassistant', like everything else, rather than 'home-assistant'. You may need to update your config to match.

* Added one-second pause between motor requests, to reduce collisions on the serial bus.

* README updated to include info on installing as a Home Assistant local add-on.

* Repository moves to 'git-flow'.  Latest developments will be on the 'develop' branch.  Releases will be on 'master'.

