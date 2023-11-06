import copy
import json
from collections import OrderedDict
from os import path
from glob import glob

TRANSLATIONS_PATH = "custom_components/home_connect_alt/translations"


def sync(o1:dict, o2:dict, path1:str, path2:str) -> bool:
    o1_changes = False
    o2_changes = False

    o1_keys = sorted(o1.keys())
    o2_keys = sorted(o2.keys())

    i1 = 0
    i2 = 0
    while i1<len(o1_keys) and i2<len(o2_keys):
        k1 = o1_keys[i1]
        k2 = o2_keys[i2]
        v1 = o1[k1]
        v2 = o2[k2]

        if k1 == k2:
            if not isinstance(v1, dict) and not isinstance(v2, dict):
                i1 += 1
                i2 += 1
            elif isinstance(v1, dict) and isinstance(v2, dict):
                sync(v1, v2, f"{path1}.{k1}", f"{path2}.{k2}")
                i1 += 1
                i2 += 1
            else:
                print(f"Mismatched types in {path1} and {path2}")

        elif k1 > k2:
            print(f"adding {k2} to {path1}")
            o1[k2] = v2
            o1_changes = True
            i2 += 1
        else:
            print(f"adding {k1} to {path2}")
            o2[k1] = v1
            o2_changes = True
            i1 += 1
    return o1_changes or o2_changes

def cleanup(o:dict, keys:list[str]):
    '''Delete a list of keys from a dictionary'''
    for key in keys:
        o.pop(key, None)

files = glob(f"{TRANSLATIONS_PATH}/*.json")

with open(f"{TRANSLATIONS_PATH}/en.json", encoding="utf-8") as f:
    en = json.load(f, object_pairs_hook=OrderedDict)

sync(en["entity"]["sensor"], en["entity"]["select"], "en.entity.sensor", "en.entity.select")

en_changed = False
for file in files:
    basefile = path.splitext(path.basename(file))[0]
    if not basefile == "en":
        with open(file, encoding="utf-8", mode="r") as f:
            translation = json.load(f)

        # Sync between the EN sensor and translation sensor nodes to fill-in any missing translations
        sync(en["entity"]["sensor"], translation["entity"]["sensor"], "en.entity.sensor", f"{basefile}.entity.sensor")
        # Sync between the sensor and select nodes, just in case someone didn't follow the instructions
        sync(translation["entity"]["sensor"], translation["entity"]["select"], f"{basefile}.entity.sensor", f"{basefile}.entity.select")
        # overwrite the select translations with sensro translations
        translation["entity"]["select"] = copy.deepcopy(translation["entity"]["sensor"])

        # Clean up redundant nodes
        cleanup(translation["entity"]["select"], ["homeconnect_status"])

        with open(file, encoding="utf-8", mode="w") as f:
            json.dump(translation, f, indent=2, sort_keys=False, ensure_ascii=False)

with open(f"{TRANSLATIONS_PATH}/en.json", encoding="utf-8", mode="w") as f:
    json.dump(en, f, indent=2, sort_keys=True, ensure_ascii=False)






