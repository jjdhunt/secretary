from dotenv import load_dotenv 
import os
import requests
import json
from typing import Any, Optional
from datetime import datetime

load_dotenv()

TRELLO_API_KEY = os.environ['TRELLO_API_KEY']
TRELLO_OAUTH_TOKEN = os.environ['TRELLO_OAUTH_TOKEN']

def _find_dict_by_name(dict_list, target_name):
    for d in dict_list:
        if d.get('name') == target_name:
            return d
    return None
    
def create_board(name: str):
    url = "https://api.trello.com/1/boards/"

    query = {
        'name': name,
        'key': TRELLO_API_KEY,
        'token': TRELLO_OAUTH_TOKEN
    }

    response = requests.request(
        "POST",
        url,
        params=query
    )

    return json.loads(response.text)['id']

def delete_board(board_id: str):
    url = f"https://api.trello.com/1/boards/{board_id}"

    query = {
        'key': TRELLO_API_KEY,
        'token': TRELLO_OAUTH_TOKEN
    }

    response = requests.request(
        "DELETE",
        url,
        params=query
    )
 
def get_boards():
    url = 'https://api.trello.com/1/members/me/boards'

    query = {
        'key': TRELLO_API_KEY,
        'token': TRELLO_OAUTH_TOKEN
    }

    response = requests.get(url, params=query)
    return response.json()

def get_board_id(board_name: str):
    boards = get_boards()
    return _find_dict_by_name(boards, board_name)['id']

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

def get_list_id(board_id: str, list_name: str):
    lists = get_lists_on_board(board_id)
    list_dict = _find_dict_by_name(lists, list_name)
    if not list_dict:
        return None
    return list_dict['id']

def create_list(board_id: str,
                name: str):
    # https://developer.atlassian.com/cloud/trello/rest/api-group-lists/#api-lists-post
    url = "https://api.trello.com/1/lists"

    query = {
    'name': name,
    'idBoard': board_id,
    'key': os.environ['TRELLO_API_KEY'],
    'token': os.environ['TRELLO_OAUTH_TOKEN']
    }

    response = requests.request(
    "POST",
    url,
    params=query
    )

    return json.loads(response.text)

def get_labels_on_board(board_id: str):
    url = f"https://api.trello.com/1/boards/{board_id}/labels"

    headers = {
    "Accept": "application/json"
    }

    query = {
    'key': TRELLO_API_KEY,
    'token': TRELLO_OAUTH_TOKEN,
    'limit': 1000,
    }

    response = requests.request(
    "GET",
    url,
    headers=headers,
    params=query
    )

    return json.loads(response.text)

def create_label(board_id: str,
                 name: str,
                 color: str = 'sky'):
    url = f"https://api.trello.com/1/boards/{board_id}/labels"

    headers = {
    "Accept": "application/json"
    }

    query = {
    'name': name,
    'color': color,
    'idBoard': board_id,
    'key': TRELLO_API_KEY,
    'token': TRELLO_OAUTH_TOKEN,
    }

    response = requests.request(
    "POST",
    url,
    headers=headers,
    params=query
    )

    return json.loads(response.text)

def get_cards_on_board(board_id: str):
    url = f"https://api.trello.com/1/boards/{board_id}/cards"

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

def get_card(card_id: str):
    url = f"https://api.trello.com/1/cards/{card_id}"

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

def create_card(list_id: str,
                name: str,
                description: str = '',
                label_ids: list[str] = [],
                due: Optional[str] = None) -> dict[str, Any]:
    # https://developer.atlassian.com/cloud/trello/rest/api-group-cards/#api-cards-post
    url = "https://api.trello.com/1/cards"

    headers = {
    "Accept": "application/json"
    }

    query = {
    'name': name,
    'desc': description,
    'idList': list_id,
    'idLabels': label_ids,
    'key': os.environ['TRELLO_API_KEY'],
    'token': os.environ['TRELLO_OAUTH_TOKEN']
    }

    if due: query['due'] = due

    response = requests.request(
    "POST",
    url,
    headers=headers,
    params=query
    )

    return json.loads(response.text)


def delete_card(id: str):
    url = f"https://api.trello.com/1/cards/{id}"

    query = {
        'key': TRELLO_API_KEY,
        'token': TRELLO_OAUTH_TOKEN
    }

    response = requests.request(
        "DELETE",
        url,
        params=query
    )

    return json.loads(response.text)

def update_card(id: str,
                update_field: str,
                updated_value: Any):
    """
    Update the description of a card.
    """
    # https://developer.atlassian.com/cloud/trello/rest/api-group-cards/#api-cards-post
    url = f"https://api.trello.com/1/cards/{id}"

    headers = {
    "Accept": "application/json"
    }

    query = {
    update_field: updated_value,
    'key': os.environ['TRELLO_API_KEY'],
    'token': os.environ['TRELLO_OAUTH_TOKEN']
    }

    response = requests.request(
    "PUT",
    url,
    headers=headers,
    params=query
    )

    return json.loads(response.text)