# Data gather where my heart rate went up from ~60 to 100
# 
# Just playing around with some different values and methods to get more interesting,
# but still roughly truthful sensor values.
# Effectively, it seems like most sensors average over a much longer duration to get their values but we can choose a different window to make the acceleration and deaceleration more fun

data = [
    (19.583984375, 24, 73),
    (20.39453125, 25, 74),
    (20.39453125, 25, 74),
    (21.18359375, 26, 76),
    (21.18359375, 26, 76),
    (21.93359375, 27, 80),
    (22.65625, 28, 83),
    (23.3701171875, 29, 84),
    (24.0595703125, 30, 87),
    (24.7255859375, 31, 90),
    (25.384765625, 32, 91),
    (25.384765625, 32, 91),
    (26.0361328125, 33, 92),
    (26.673828125, 34, 94),
    (27.3115234375, 35, 94),
    (27.3115234375, 35, 94),
    (27.9365234375, 36, 96),
    (28.5546875, 37, 97),
    (29.1728515625, 38, 97),
    (29.1728515625, 38, 97),
    (35.0703125, 48, 105),
    (35.6357421875, 49, 106),
    (36.1962890625, 50, 107),
    (36.1962890625, 50, 107),
    (36.7509765625, 51, 108),
    (37.3056640625, 52, 108),
    (37.85546875, 53, 109),
    (38.4052734375, 54, 109),
    (38.9453125, 55, 111),
    (39.48046875, 56, 112),
    (40.5556640625, 58, 111),
    (41.095703125, 59, 111),
    (41.640625, 60, 110),
    (42.185546875, 61, 110),
    (42.185546875, 61, 110),
    (42.73046875, 62, 110),
    (43.275390625, 63, 110),
    (43.8203125, 64, 110),
    (44.365234375, 65, 110),
    (44.91015625, 66, 110),
    (45.4501953125, 67, 111),
    (45.9951171875, 68, 110),
]


def compute_bpm(data):
    time_it_took = data[-1][0] - data[0][0]
    beats  = data[-1][1] - data[0][1]
    
    expected = data[-1][2]
    
    if time_it_took == 0 or beats == 0:
        return expected, expected
    
    bpm = (60 / time_it_took) * beats
    return bpm, expected

def full_window(window_size: int):
    for idx in range(len(data) - window_size - 1):
        this_data = data[idx:idx+window_size]
        # Let's just do the ASAP distance, so time between two betweens normalized to a minute
        bpm, expected = compute_bpm(this_data)
        
        print(f"BPM: {bpm} -- Sensor said {expected}")
    
def mean_windows(window_size: int):
    for idx in range(len(data) - window_size - 1):
        this_data = data[idx:idx+window_size]
        
        # Let's just do the ASAP distance, so time between two betweens normalized to a minute
        
        all_values = [
            compute_bpm(this_data[i:i+2])[0] for i in range(window_size - 2)
        ]
        
        bpm = sum(all_values) / len(all_values)
        expected = this_data[-1][2]
        
        print(f"BPM: {bpm} -- Sensor said {expected}")
   

if __name__ == "__main__":
    # full_window(3)
    # full_window(4)
    
    mean_windows(3)
    mean_windows(4)