from dotenv import load_dotenv 
import os
import requests
import json

load_dotenv()

TRELLO_API_KEY = os.environ['TRELLO_API_KEY']
TRELLO_OAUTH_TOKEN = os.environ['TRELLO_OAUTH_TOKEN']

def find_dict_by_name(dict_list, target_name):
    for d in dict_list:
        if d.get('name') == target_name:
            return d
    return None

def get_boards():
    url = 'https://api.trello.com/1/members/me/boards'

    query = {
        'key': TRELLO_API_KEY,
        'token': TRELLO_OAUTH_TOKEN
    }

    response = requests.get(url, params=query)
    return response.json()

def get_lists_on_board(board_id: str):
    url = f"https://api.trello.com/1/boards/{board_id}/lists"

    headers = {
    "Accept": "application/json"
    }

    query = {
    'key': TRELLO_API_KEY,
    'token': TRELLO_OAUTH_TOKEN
    }

    response = requests.request(
    "GET",
    url,
    headers=headers,
    params=query
    )

    return json.loads(response.text)

def create_card(list_id: str, name: str):
    url = "https://api.trello.com/1/cards"

    
    headers = {
    "Accept": "application/json"
    }

    query = {
    'name': name,
    'idList': list_id,
    'key': os.environ['TRELLO_API_KEY'],
    'token': os.environ['TRELLO_OAUTH_TOKEN']
    }

    response = requests.request(
    "POST",
    url,
    headers=headers,
    params=query
    )

    return json.loads(response.text)