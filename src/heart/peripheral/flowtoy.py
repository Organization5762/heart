# This uses the Flowtoy Bridge
from dataclasses import dataclass

# Here's the basic information:
# https://github.com/benkuper/FlowtoysConnectBridge/blob/master/RFGroup.h
#
# But we don't get RF packets, we get 
@dataclass
class SyncPacket:
    groupID: int
    padding: int
    lfo: list[int]
    global_hue: int
    global_sat: int
    global_val: int
    global_speed: int
    global_density: int
    lfo_active: int
    hue_active: int
    sat_active: int
    val_active: int
    speed_active: int
    density_active: int
    reserved: list[int]
    page: int
    mode: int
    adjust_active: int
    wakeup: int
    poweroff: int
    force_reload: int
    save: int
    _delete: int
    alternate: int

    @classmethod
    def parse_sync_packet(cls, data: bytes) -> 'SyncPacket':
        groupID = int.from_bytes(data[0:2], "little")
        padding = int.from_bytes(data[2:6], "little")
        lfo = list(data[6:10])
        global_hue = data[10]
        global_sat = data[11]
        global_val = data[12]
        global_speed = data[13]
        global_density = data[14]

        flags1 = data[15]
        lfo_active     = (flags1 >> 0) & 1
        hue_active     = (flags1 >> 1) & 1
        sat_active     = (flags1 >> 2) & 1
        val_active     = (flags1 >> 3) & 1
        speed_active   = (flags1 >> 4) & 1
        density_active = (flags1 >> 5) & 1

        reserved = list(data[16:18])
        page = data[18]
        mode = data[19]

        flags2 = data[20]
        adjust_active = (flags2 >> 0) & 1
        wakeup        = (flags2 >> 1) & 1
        poweroff      = (flags2 >> 2) & 1
        force_reload  = (flags2 >> 3) & 1
        save          = (flags2 >> 4) & 1
        _delete       = (flags2 >> 5) & 1
        alternate     = (flags2 >> 6) & 1

        return SyncPacket(
            groupID, padding, lfo,
            global_hue, global_sat, global_val,
            global_speed, global_density,
            lfo_active, hue_active, sat_active, val_active,
            speed_active, density_active,
            reserved, page, mode,
            adjust_active, wakeup, poweroff,
            force_reload, save, _delete, alternate
        )
