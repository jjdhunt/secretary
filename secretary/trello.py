from dotenv import load_dotenv 
import os
import requests
import json
from typing import Annotated, Optional
from datetime import datetime

import secretary.chat_tools as ct

load_dotenv()

TRELLO_API_KEY = os.environ['TRELLO_API_KEY']
TRELLO_OAUTH_TOKEN = os.environ['TRELLO_OAUTH_TOKEN']

tools = {}

def find_dict_by_name(dict_list, target_name):
    for d in dict_list:
        if d.get('name') == target_name:
            return d
    return None

def _is_valid_date(date_str):
    """
    Check that a string in a date in YYYY-MM-DD format
    """
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False
    
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
                due: Optional[str] = None):
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
    if isinstance(due, str) & _is_valid_date(due): query['due'] = due

    response = requests.request(
    "POST",
    url,
    headers=headers,
    params=query
    )

    return json.loads(response.text)

@ct.tools_function(tools)
def update_card_description(id: Annotated[str, 'The id of the task card to update'],
                updated_description: Annotated[str, 'A new description to replace the old one with.'],
                ):
    """
    Update the description of a card.
    """
    # https://developer.atlassian.com/cloud/trello/rest/api-group-cards/#api-cards-post
    url = f"https://api.trello.com/1/cards/{id}"

    headers = {
    "Accept": "application/json"
    }

    query = {
    'desc': updated_description,
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

@ct.tools_function(tools)
def update_card_due(id: Annotated[str, 'The id of the task card to update'],
                updated_due_date: Annotated[str, 'The new due date formatted as "YYYY-MM-DD"'],
                ):
    """
    Update the due date of a card.
    """
    # https://developer.atlassian.com/cloud/trello/rest/api-group-cards/#api-cards-post
    url = f"https://api.trello.com/1/cards/{id}"

    headers = {
    "Accept": "application/json"
    }

    query = {
    'due': updated_due_date,
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

@ct.tools_function(tools)
def update_card_completion(id: Annotated[str, 'The id of the task card to update'],
                is_complete: Annotated[str, 'The new status. "true" is done/completed, "false" is incomplete.'],
                ):
    """
    Change the completion status of a card.
    """
    # https://developer.atlassian.com/cloud/trello/rest/api-group-cards/#api-cards-post
    url = f"https://api.trello.com/1/cards/{id}"

    headers = {
    "Accept": "application/json"
    }

    query = {
    'closed': is_complete,
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

@ct.tools_function(tools)
def add_label_to_card(id: Annotated[str, 'The id of the task card to update'],
                      label_name: Annotated[str, 'The name of the label to add to the card'],
                ):
    """
    Add a label to a card.
    """
    label_name = label_name.lower()
    #TODO:
    card = get_card(id)
    label_ids = card['idLabels']

    board_id = card['idBoard']
    labels = get_labels_on_board(board_id)
    # check if the label already exists on the board
    label_id = None
    for label in labels:
        if label['name'] == label_name: # then a label with this name exists on the board already
            if label['id'] in label_ids: # then a label of this name is already on the card, so we're done
                return
            label_id = label['id']
    if label_id is None: # if no existing label was found on the board, make a new one
        label_id = create_label(board_id, label_name)['id']
    
    label_ids.append(label_id)

    url = f"https://api.trello.com/1/cards/{id}"

    headers = {
    "Accept": "application/json"
    }

    query = {
    'idLabels': label_ids,
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