# webostv
 Extension of home-assistant component webostv as of v0.100.3 to add support for missing button presses.

## Supported buttons
LEFT, RIGHT, DOWN, UP, HOME, BACK, ENTER, DASH, INFO,
1, 2, 3, 4, 5, 6, 7, 8, 9, 0, ASTERISK, CC, EXIT, MUTE, RED, GREEN,
BLUE, VOLUMEUP, VOLUMEDOWN, CHANNELUP, CHANNELDOWN

## Instructions
Place repository files in a web webostv folder in config/custom_components and restart hassio.

### Example configuration.yaml
```
media_player:
  - platform: webostv
    name: lgtv
    host: 192.168.0.17

remote:
  - platform: webostv
    host: 192.168.0.17
    name: lgr
```

### Example Usage
This can be used as per the standard HA remote integration functionality. 

For my purposes I have combined with the media_player card configuration using the HACS mini-media-player

```
entity: media_player.lgtv
hide:
  power_state: false
hide_controls: true
idle_view: true
shortcuts:
  buttons:
    - icon: 'mdi:netflix'
      id: Netflix
      name: Netflix
      type: source
    - icon: 'mdi:amazon'
      id: AmazonPrime
      name: Amazon
      type: source
    - icon: 'mdi:youtube'
      id: YouTube
      name: YouTube
      type: source
    - data:
        command: HOME
        entity_id: remote.lgr
      domain: remote
      id: remote.send_command
      name: Menu
      type: service
    - data:
        command: UP
        entity_id: remote.lgr
      domain: remote
      icon: 'mdi:arrow-up-bold'
      id: remote.send_command
      type: service
    - id: ' '
      type: source
    - data:
        command: LEFT
        entity_id: remote.lgr
      domain: remote
      icon: 'mdi:arrow-left-bold'
      id: remote.send_command
      type: service
    - data:
        command: ENTER
        entity_id: remote.lgr
      domain: remote
      id: remote.send_command
      name: Enter
      type: service
    - data:
        command: RIGHT
        entity_id: remote.lgr
      domain: remote
      icon: 'mdi:arrow-right-bold'
      id: remote.send_command
      type: service
    - id: ' '
      type: source
    - data:
        command: DOWN
        entity_id: remote.lgr
      domain: remote
      icon: 'mdi:arrow-down-bold'
      id: remote.send_command
      type: service
    - id: ' '
      type: source
  columns: 3
type: 'custom:mini-media-player'
volume_stateless: true
```

## Temporary Solution
This acts as a 'temporary' enhancement to the webostv integration included in home assistant to add the much needed functionality for ,left, right, up, down, enter, which was sorely needed when in apps.

## Long Term Solution

Long term solution at time of release looks to be a proposed enhancement by [bendavid]([https://github.com/bendavid](https://github.com/bendavid)) to extend functionality to media_player, negating the need for the remote. See [https://github.com/TheRealLink/pylgtv/pull/19](https://github.com/TheRealLink/pylgtv/pull/19) and [https://github.com/home-assistant/architecture/issues/299#issuecomment-546714758](https://github.com/home-assistant/architecture/issues/299#issuecomment-546714758)



## Credits
The enhancement to pylgtv is thanks to [poroping](https://github.com/poroping) from https://github.com/TheRealLink/pylgtv/pull/18

