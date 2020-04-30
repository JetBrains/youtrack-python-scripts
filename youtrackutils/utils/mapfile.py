import json
import os
import sys
import io

default_mapping_filename = 'mapping.json'


def dump_map_file(mapping_data, mapping_filename=None):
    if not mapping_filename:
        mapping_filename = default_mapping_filename
    if os.path.isfile(mapping_filename):
        print("Mapping file already exists: " +
              os.path.abspath(mapping_filename))
        sys.exit(1)
    try:
        with io.open(mapping_filename, mode='w', encoding='utf-8') as f:
            f.write(unicode(json.dumps(mapping_data, ensure_ascii=False, sort_keys=True, indent=4)))
        print("Mapping file has been written to " +
              os.path.abspath(mapping_filename))
    except (IOError, OSError) as e:
        print("Failed to write mapping file: " + str(e))
        sys.exit(1)


def load_map_file(mapping_filename=None):
    if not mapping_filename:
        mapping_filename = default_mapping_filename
    try:
        with io.open(mapping_filename, mode='r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, IOError) as e:
        print("Failed to read mapping file: " + str(e))
        sys.exit(1)
    except (KeyError, ValueError) as e:
        print("Bad mapping file: " + str(e))
        sys.exit(1)
