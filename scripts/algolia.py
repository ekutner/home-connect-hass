import argparse
import json

from algoliasearch.configs import SearchConfig
from algoliasearch.search_client import SearchClient

parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)

global_parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, add_help=False)
global_parser.add_argument("app_id")
global_parser.add_argument("api_key")
global_parser.add_argument("index")

commands = parser.add_subparsers(dest='command', title='Commands', help='Command to execute')
upload = commands.add_parser('upload', parents=[global_parser], help='Upload a file')
upload.add_argument("--file")
upload.add_argument("--clear", action="store_true", default=False)


args, remain = parser.parse_known_args()
print(args)

def upload(index, filename:str, clear:bool) -> None:


    with open(filename, encoding="UTF-8") as f:
        data = json.load(f)
    #     data = f.read()
    if clear:
        index.clear_objects()
        print("Cleared the index")

    # chunk_size = 1000
    # list_chunked = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

    # for chunk in list_chunked:
    #     index.save_objects(chunk,  {'autoGenerateObjectIDIfNotExist': True})
    print(f"Uploading {len(data)} records")
    index.save_objects(data,  {'autoGenerateObjectIDIfNotExist': True})


config = SearchConfig(args.app_id, args.api_key)
config.batch_size = 1000

client = SearchClient.create_with_config(config)
index = client.init_index(args.index)

if args.command=='upload':
    upload(index, args.file, args.clear)
