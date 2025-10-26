import json
import shutil
import os
import logging
import re
import time
import argparse
import sys
import textwrap

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\
        Packages songs to .arcpkg
        
        correct folder structure:
        
        files/
        |_ cb
        |  |_ active
        |     |_ songs
        |     |_ img
        |        |_bg
        |          |_1080
        |_ dl
        
    '''))
parser.add_argument("files", help="path to files folder", nargs='?', default="files")
args = parser.parse_args()

filespath = args.files
songpath = filespath + "/cb/active/songs"
dlpath = filespath + "/dl"
bgpath = filespath + "/cb/active/img/bg/1080" 

if os.path.exists(songpath) and os.path.exists(dlpath) and os.path.exists(bgpath):
    pass
else:
    parser.print_help()
    sys.exit()

try:
    from PIL import Image
except ModuleNotFoundError:
    print('"Pillow" not installed: run "pip install Pillow"')
    sys.exit()

print("Processing songs...")

version = 0
publisher = "oriwol"

outdir = ".arctemp"
indexyml = outdir + "/" + "index.yml"

start_time = time.time()

if not os.path.exists(outdir):
    os.mkdir(outdir)

songidentifiers = {}

songlistPath = songpath + "/songlist"

packlistPath = songpath + "/packlist"

with open(packlistPath, encoding="utf8") as f:
    packlist = json.load(f)['packs']
    packlist.insert(6, packlist[13]) # lazy hack to reorder packs
    packlist.insert(7, packlist[15])
    packlist.pop(16)
    packlist.pop(15)
    packlist.insert(1, {"id": "single", "name_localized": {"en": "Memory Archive"}}) # memory archive does not exist in packlist so make it exist


with open(songlistPath, encoding="utf8") as f:  
    songlist = json.load(f)['songs']

for song in songlist:
    id = song.get('id')

    if os.path.isfile(f"{songpath}/{id}/0.aff") or  os.path.isfile(f"{dlpath}/{id}"):
        pass
    else:
        continue

    try:
        difficulties = song['difficulties']
    except KeyError:
        if song.get('deleted'):
            logging.info('%s is deleted', id)
        continue
    
    songset = song.get('set')
    for pack in packlist:
        if songset == pack.get('id'):
            if isinstance(pack.get('pack_parent'), str): # is this a pack append
                songset = pack.get('pack_parent')

    songidentifiers.setdefault(songset, {"identifiers": set(), "bgs": set()})
    
    songdir = f"{outdir}/{id}"
    proj = f"{songdir}/{id}.arcproj"

    logging.info("Current song: %s", id)

    def makeChart():
        if not os.path.exists(songdir):
            os.mkdir(songdir)
        

        with open(proj, encoding="utf8", mode="x") as f:
            f.write("charts:\n")

        for diff in difficulties:
            if diff.get('hidden_until') == 'always': # lastcheck
                continue
            def dataGet(data):
                value = diff.get(data) or song.get(data) # does not work for 'ratingClass' for funny reasons
                # try: # this would work for 'ratingClass' but it does not work for bg or side ??
                #     value = diff.get(data) 
                # except KeyError:
                #     value = song.get(data)
                if data == 'title_localized' and isinstance(value, dict):
                    value = value.get('en')
                if data == 'audioPreviewEnd':
                    if value == 0:
                        value = 999999
                if isinstance(value, str):
                    if data == 'artist' or data == 'chartDesigner' or data == 'jacketDesigner' or data == 'title_localized':
                        value = value.replace("\n", " ")
                        if "'" in value:
                            value = f'"{value}"'
                        else:
                            value = f"'{value}'"
                return value

            def filePath(type):
                override = f"{type}Override"
                if diff.get(override) == True:
                    if type == "audio":
                        return f"{id}_audio_{diff.get('ratingClass')}"
                    else:
                        return f"{diff.get('ratingClass')}"
                else:
                    return f"base"

            def rating():
                ratingClass = {
                    0: "Past",
                    1: "Present",
                    2: "Future",
                    3: "Beyond",
                    4: "Eternal"
                }
                ratingstr = f"{ratingClass.get(diff.get('ratingClass'))} {diff.get('rating')}"
                if dataGet('ratingPlus') == True:
                    ratingstr += "+"
                return ratingstr

            def diffColor(ratingclass):
                difficultyColor = {
                0: '#3A6B78FF', # past
                1: '#566947FF', # present
                2: '#482B54FF', # future
                3: '#7C1C30FF', # beyond
                4: '#433455FF' # eternal
                }
                return f"'{difficultyColor.get(ratingclass)}'"

            def get_skin(bg, side) -> str: 
                with open("skin.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                def resolve(entry): # check if bg has skin associated
                    value = data.get(entry)
                    if value is None:
                        return None
                    if isinstance(value, dict) and "skin" in value: # found one
                        return value["skin"]
                    if isinstance(value, str): # found reference to other skin
                        return resolve(value)
                    return None
                skin_data = resolve(bg)
                # fallback logic
                if not skin_data:
                    logging.warning(f"Skin data for bg {bg} not found in skin.json!")
                    fallback = {0: "base_light", 1: "base_conflict", 2: "epilogue", 3: "base_light"}[side]
                    skin_data = resolve(fallback)
                formatted = (
                    f"  skin:\n"
                    f"    side: {skin_data.get('side', 'conflict')}\n"
                    f"    note: {skin_data.get('note', 'inherit')}\n"
                    f"    particle: {skin_data.get('particle', 'inherit')}\n"
                    f"    track: {skin_data.get('track', 'inherit')}\n"
                    f"    accent: {skin_data.get('accent', 'inherit')}\n"
                    f"    singleLine: {skin_data.get('singleLine', 'none')}"
                )
                return formatted
            def copyFiles(type):
                srcpath = ""
                dstpath = ""
                diffid = diff.get('ratingClass')
                if type == "chart":
                    dstpath = f"{songdir}/{diffid}.aff"
                    if os.path.isfile(dstpath):
                        logging.info("Chart %s.aff already exists, skipping", diffid)
                        return
                    if os.path.isfile(f"{songpath}/{id}/{diffid}.aff"):
                        srcpath = f"{songpath}/{id}/{diffid}.aff"
                        logging.info("Chart %s found in songs", diffid)
                    elif os.path.isfile(f"{dlpath}/{id}_{diffid}"):
                        srcpath = f"{dlpath}/{id}_{diffid}"
                        logging.info("Chart %s found in dl", diffid)
                    else: 
                        logging.warning("%s chart %s not found! Have you unlocked this chart?",id, diffid)
                        raise FileNotFoundError()
                    
                if type == "audio": 
                    fname = filePath('audio')
                    dstpath = f"{songdir}/{fname}.ogg"
                    if os.path.isfile(dstpath):
                        logging.info("Audio %s.ogg already exists, skipping", fname)
                        return
                    if os.path.isfile(f"{songpath}/{id}/{fname}.ogg"): # songs/songid/base.ogg
                        logging.info("Audio %s.ogg found in songs", fname)
                        srcpath = f"{songpath}/{id}/{fname}.ogg" 
                    elif os.path.isfile(f"{dlpath}/{fname}"): # dl/songid_audio_n
                        logging.info("Audio %s found in dl", fname)
                        srcpath = f"{dlpath}/{fname}" 
                    elif os.path.isfile(f"{dlpath}/{id}"): 
                        logging.info("Audio %s found in dl", fname)
                        srcpath = f"{dlpath}/{id}" # dl/songid 
                    else:
                        logging.warning("%s audio %s.ogg not found!", id, fname)
                        raise FileNotFoundError()
                
                if type == "jacket":
                    fname = filePath('jacket')
                    dstpath = f"{songdir}/{fname}.jpg"
                    if os.path.isfile(dstpath):
                        logging.info("Jacket %s.jpg already exists, skipping", fname)
                        return

                    srcpath = f"{songpath}/{id}" # songs/songid 
                    if dataGet('remote_dl'):
                        srcpath = f"{songpath}/dl_{id}" # songs/dl_songid
                    for filename in os.listdir(srcpath):
                        fpath = os.path.join(srcpath, filename)
                        pattern = r"^.*" + re.escape(fname) + r"\.jpg$"
                        if os.path.isfile(fpath) and re.fullmatch(pattern,fpath):
                            logging.info("Jacket %s.jpg found in songs", fname)
                            srcpath = fpath
                            break
                    else:
                        logging.warning("%s jacket %s.jpg not found!", id, fname)
                        raise FileNotFoundError()
                shutil.copy(srcpath, dstpath)
            
            def bgpath(bg):
                bg = dataGet(bg)
                songidentifiers[songset]["bgs"].add(bg)
                return f"../../Pack/{publisher}.{songset}/{bg}.jpg"

            def chartConstant(id, ratingclass):
                with open("cc.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    try:
                        cc = data.get(id).get('difficulties').get(f'{ratingclass}')
                        if cc == None:
                            raise KeyError
                        return cc
                    except KeyError:
                        print(f"!!! KEY ERROR ON AISLE: MY {id} !!!")
                        return diff.get('rating')

            projformatted = (
                f"- chartPath: {diff.get('ratingClass')}.aff\n" 
                f"  audioPath: {filePath('audio')}.ogg\n"
                f"  jacketPath: {filePath('jacket')}.jpg\n"
                f"  baseBpm: {dataGet('bpm_base')}\n"
                f"  bpmText: {dataGet('bpm')}\n"
                f"  syncBaseBpm: false\n"
                f"  backgroundPath: {bgpath('bg')}\n"
                f"  title: {dataGet('title_localized')}\n"
                f"  composer: {dataGet('artist')}\n"
                f"  charter: {dataGet('chartDesigner')}\n"
                f"  illustrator: {dataGet('jacketDesigner')}\n"
                f"  difficulty: {rating()}\n"
                f"  chartConstant: {chartConstant(id, diff.get('ratingClass'))}\n"
                f"  difficultyColor: {diffColor(diff.get('ratingClass'))}\n"
                f"{get_skin(dataGet('bg'), dataGet('side'))}\n"
                f"  previewStart: {dataGet('audioPreview')}\n"
                f"  previewEnd: {dataGet('audioPreviewEnd')}\n"
            )
            
            try: 
                copyFiles("chart")
                copyFiles("audio")
            except FileNotFoundError:
                continue
            try:
                copyFiles("jacket")
            except FileNotFoundError:
                pass
            with open(proj, encoding="utf8", mode="a") as f:
                f.write(projformatted)
            
    def writeIndex():
        identifier = f"{publisher}.{id}"
        songformat = (
            f"- directory: {id}\n" # /song
            f"  identifier: {identifier}\n" # publisher.song['id']
            f"  settingsFile: {id}.arcproj\n" 
            f"  version: {version}\n" # version
            f"  type: level\n"
        )
        
        songidentifiers[songset]["identifiers"].add(identifier)
        
        with open(indexyml, encoding="utf8", mode="a") as f:
            f.write(songformat)

    makeChart()
    writeIndex()

for pack in packlist:
    def makepack(pack):
    
        def makeimg(name): # TODO: check if pillow is installed and if not, ask if user would like to continue without pack images
            dstpath = f"{packdir}/pack.png"
            srcpath = f"{songpath}/pack/1080_select_{name}.png"
            if not os.path.isfile(srcpath):
                raise FileNotFoundError()
            
            width = 314
            height = 756

            image = Image.open(srcpath)
            size = tuple(int(i * 1.18) for i in image.size)
            box = (
                (size[0]/2)-(width/2),
                size[1]-height,
                ((size[0]/2)+(width/2)),
                size[1]
            )
            image = image.resize(size)
            image = image.crop(box)
            
            image.save(dstpath)

        packid = pack.get('id')
        packdir = f"{outdir}/{packid}"
        if not os.path.exists(packdir):   
            packyml = f"{packdir}/pack.yml"
            identifier = f"{publisher}.{packid}"

            packformat = (
                f"packName: {pack.get('name_localized')['en']}\n"
                f"imagePath: pack.png\n"
                f"levelIdentifiers:\n"
            )
            packindexformat = (
                f"- directory: {packid}\n" # /pack
                f"  identifier: {identifier}\n" # publisher.pack['id']
                f"  settingsFile: pack.yml\n" 
                f"  version: {version}\n" # version
                f"  type: pack\n"
            )

            if not os.path.exists(packdir):
                os.mkdir(packdir)
            with open(packyml, encoding="utf8", mode="x") as f:
                f.write(packformat)
            with open(indexyml, encoding="utf8", mode="a") as f:
                f.write(packindexformat)
            makeimg(packid)
    def copyBGs(bgs: set, src: str, dest: str):
        for bg in bgs:
            fname = f"{bg}.jpg"
            bgsrc = f"{src}/{fname}"
            bgdst = f"{dest}/{fname}"
            if os.path.isfile(bgdst):
                logging.info("bg %s already exists, skipping", bg)
                continue
            if os.path.isfile(bgsrc):
                logging.info("bg %s found in bgs", bg)
                shutil.copy(bgsrc, bgdst)
            else:
                logging.warning("bg %s not found!", bg)
                continue
    if isinstance(songidentifiers.get(pack.get('id'), {}).get("identifiers"), set): # does songidentifiers have entries for pack
        packid = pack.get('id')
        packdir = f"{outdir}/{packid}"
        bgs:set = songidentifiers.get(packid, {}).get("bgs")
        
        makepack(pack)
        copyBGs(bgs, bgpath, packdir)

        packyml = f"{packdir}/pack.yml"
        with open(packyml, encoding="utf8", mode="a") as f:
            for identifier in songidentifiers.get(packid, {}).get("identifiers"):
                f.write(f"  - {identifier}\n")

def make_arcpkg(base_name, base_dir, verbose=0, dry_run=0, 
                  logger=None, owner=None, group=None, root_dir=None):
    
    # Based on code from the Python standard library module "shutil"
    # originally licensed under the Python Software Foundation License (PSFL)
    # See https://docs.python.org/3/license.html

    import zipfile  # late import for breaking circular dependency

    zip_filename = base_name + ".arcpkg"
    archive_dir = os.path.dirname(base_name)

    if archive_dir and not os.path.exists(archive_dir):
        if logger is not None:
            logger.info("creating %s", archive_dir)
        if not dry_run:
            os.makedirs(archive_dir)

    if logger is not None:
        logger.info("creating '%s' and adding '%s' to it",
                    zip_filename, base_dir)

    if not dry_run:
        with zipfile.ZipFile(zip_filename, "w",
                             compression=zipfile.ZIP_STORED) as zf: # not actually compressing anything since it takes double the time for just 200MB of savings
            arcname = os.path.normpath(base_dir)
            if root_dir is not None:
                base_dir = os.path.join(root_dir, base_dir)
            base_dir = os.path.normpath(base_dir)
            if arcname != os.curdir:
                zf.write(base_dir, arcname)
                if logger is not None:
                    logger.info("adding '%s'", base_dir)
            for dirpath, dirnames, filenames in os.walk(base_dir):
                arcdirpath = dirpath
                if root_dir is not None:
                    arcdirpath = os.path.relpath(arcdirpath, root_dir)
                arcdirpath = os.path.normpath(arcdirpath)
                for name in sorted(dirnames):
                    path = os.path.join(dirpath, name)
                    arcname = os.path.join(arcdirpath, name)
                    zf.write(path, arcname)
                    if logger is not None:
                        logger.info("adding '%s'", path)
                for name in filenames:
                    path = os.path.join(dirpath, name)
                    path = os.path.normpath(path)
                    if os.path.isfile(path):
                        arcname = os.path.join(arcdirpath, name)
                        zf.write(path, arcname)
                        if logger is not None:
                            logger.info("adding '%s'", path)

    if root_dir is not None:
        zip_filename = os.path.abspath(zip_filename)
    return zip_filename
shutil.register_archive_format('arcpkg', make_arcpkg, description='arcpkg')

fname = f"{publisher}"
i = 1
while os.path.isfile(fname + ".arcpkg"):
    fname = f"{publisher}_{i}"
    i += 1

print("Creating arcpkg...")
shutil.make_archive(fname, 'arcpkg', outdir)
shutil.rmtree(outdir)

print(f"Done! {fname}.arcpkg created")
print("Finished in %.2f seconds" % (time.time() - start_time))