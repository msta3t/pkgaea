import os
import json
import argparse
import sys
from bs4 import BeautifulSoup
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument("songlist", help="path to songlist", nargs='?', default="../files/cb/active/songs/songlist")
args = parser.parse_args()

songlist = args.songlist
if not os.path.isfile(songlist):
        parser.print_help()
        sys.exit()

url = "https://arcaea.miraheze.org/wiki/Chart_list"
headers = {"User-Agent": "Mozilla/5.0"}

req = Request(url, headers=headers)

with urlopen(req) as response:
    html = response.read().decode("utf-8")
    soup = BeautifulSoup(html, 'html.parser')

with open(songlist, encoding="utf8") as f:  
    songlist = json.load(f)['songs']

songs = {}

rows = soup.find("table").find("tbody").find_all("tr")

for row in rows:
    try:
        mapping = {1:0, 2:1, 3:2, 4:4, 5:3}
        cells = row.find_all("td")
        title = cells[1].find("a").get('title')
        rc = int(cells[3].get('data-sort-value'))
        diffname = cells[3].get_text()
        rc = mapping[rc]
        cc = cells[5].get_text()

        
        for song in songlist:
            try:
                difficulties = song['difficulties']
            except KeyError:
                if song.get('deleted'):
                    continue
    
            songid = song['id']
            songname = song.get('title_localized').get('en')

            songs.setdefault(songid, {"title": songname, "difficulties": dict()})

            if songname.casefold() == title.casefold():
                for diff in difficulties:
                    diffclass = diff.get('ratingClass')
                    if diffclass == rc:
                        songs[songid]["difficulties"].update({diffclass: cc})
                    else:
                        continue
    except IndexError:
        pass

fname = "cc.json"
i = 1

while os.path.isfile(fname):
    fname = f"cc{i}.json"
    i += 1

out = json.dumps(songs, indent=2, separators=(", ", ": "), sort_keys=True)
with open(fname, mode="x", encoding="utf8") as f:
    f.write(out)

failed = ""
j = 0
for song in songs:
    if len(songs.get(song).get('difficulties')) == 0:
        j += 1
        failed += f"{song}\n"

print(f"Got chart constants for {len(songs)-j} songs\n")
if j != 0:
    print(f"Failed to get chart constants for {j} songs:") 
    print(failed)