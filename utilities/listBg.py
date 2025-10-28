import json
import argparse
import sys
import os

parser = argparse.ArgumentParser()
parser.add_argument("songlist", help="path to songlist", nargs='?', default="../files/cb/active/songs/songlist")
args = parser.parse_args()

songlist = args.songlist
if not os.path.isfile(songlist):
        parser.print_help()
        sys.exit()
    
bgTypes = set()

with open(songlist, encoding="utf8") as f:  
    songlist = json.load(f)['songs']

with open("../skin.json", encoding="utf8") as f:
    skinlist = json.load(f)

for song in songlist:

    try:
        difficulties = song['difficulties']
    except KeyError:
        if song.get('deleted'):
            continue

    for diff in difficulties:
        if diff.get('hidden_until') == 'always': # lastcheck
                continue
        try:
            bg = diff.get('bg') or song.get('bg')
            bgTypes.add(bg)
        except:
            bg = diff.get('bg_inverse') or song.get('bg_inverse')
            bgTypes.add(bg)

bgTypes = sorted(bgTypes)

for bg in bgTypes:
    if bg not in skinlist.keys():
        skinlist[bg] = "NEW !!! <-- <-- <-- <-- <-- <-- <-- <-- <-- <-- <-- <-- <-- <-- "

fname = "skin.json"
i = 1
while os.path.isfile(fname):
    fname = f"skin{i}.json"
    i += 1

out = json.dumps(skinlist, indent=2, separators=(", ", ": "), sort_keys=True)
with open(fname, mode="x", encoding="utf8") as f:
    f.write(out)