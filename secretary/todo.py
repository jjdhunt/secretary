import os
from pathlib import Path
import pandas as pd
from tabulate import tabulate
import re
from io import StringIO
from dotenv import load_dotenv
from openai import OpenAI
import numpy as np
from typing import Annotated, Any, Optional, Union, List, Tuple

import secretary.trello as trello
import secretary.chat_tools as ct

tools = {}

def clean_tasks(cards):
    """Given a list of card dicts, remove the entries in the cards for which the value is None or an empty list."""
    # Function to check if an entry in a card should be removed
    def should_remove(value):
        return value is None or value == [] or value == {}

    def clean_dict(d):
        # Recursively clean the dictionary
        return {k: (clean_dict(v) if isinstance(v, dict) else v) 
                for k, v in d.items() if not should_remove(v)}

    # Iterate and filter the dictionaries
    cleaned_cards = [clean_dict(d) for d in cards]

    # Because some dicts can have empty dicts as members, we need to do multiple passes
    cleaned_cards = [clean_dict(d) for d in cleaned_cards]

    # Finally ,filter to just these fields, if they are still present
    keys_to_keep = ['id', 'name', 'desc', 'closed', 'url', 'email', 'due']
    cleaned_cards = [{k: d[k] for k in keys_to_keep if k in d} for d in cleaned_cards]

    return cleaned_cards

def get_tasks():
    board_id = trello.get_board_id(board_name='Secretary')
    cards = trello.get_cards_on_board(board_id)
    return cards

def get_labels():
    board_id = trello.get_board_id(board_name='Secretary')
    labels = trello.get_labels_on_board(board_id)
    labels = {label['name']: label['id'] for label in labels if label['name']!=''}
    return labels

def eager_get_label_ids(names: list[str]):
    """
    Given a list of label names, find the ids of those that exist already, or create new labels and get their ids.
    """
    label_ids = []
    board_id = trello.get_board_id(board_name='Secretary')
    existing_labels = get_labels()
    for name in names:
        name = name.lower()
        if name in existing_labels:
            label_ids.append(existing_labels[name])
        elif name not in ['nan', 'nan', 'none', 'null']:
            label_ids.append(trello.create_label(board_id, name)['id'])
    return label_ids

def eager_get_list_id(board_name: str, list_name: str):
    """
    Given board and a list name, find its id if it exists on the board already, or create it on that board and get its id.
    """
    board_id = trello.get_board_id(board_name)
    list_id = trello.get_list_id(board_id, list_name)
    if not list_id:
        list_id = trello.create_list(board_id, list_name)['id']
    return list_id

@ct.tools_function(tools)
def update_task_description(id: Annotated[str, 'The id of the task to update'],
                            updated_description: Annotated[str, 'A new description to replace the old one with.']):
    """
    Update the description of a task.
    """
    return trello.update_card(id=id, update_field='desc', updated_value=updated_description)


@ct.tools_function(tools)
def update_task_due_date(id: Annotated[str, 'The id of the task to update'],
                         updated_due_date: Annotated[str, 'The new due date, formatted as "YYYY-MM-DD"']):
    """
    Update the due date of a task.
    """
    return trello.update_card(id=id, update_field='due', updated_value=updated_due_date)


@ct.tools_function(tools)
def update_task_completion(id: Annotated[str, 'The id of the task to update'],
                           is_complete: Annotated[str, 'The new status. "true" is done/completed, "false" is incomplete.']):
    """
    Change the completion status of a task.
    """
    return trello.update_card(id=id, update_field='closed', updated_value=is_complete)


@ct.tools_function(tools)
def add_label_to_task(id: Annotated[str, 'The id of the task to update'],
                      label_names: Annotated[list[str], 'The names of the label(s) to add to the task']):
    """
    Add one or more label(s) to a task.
    """
    label_names = [label_name.lower() for label_name in label_names]
    label_ids_to_add = eager_get_label_ids(label_names)
    card = trello.get_card(id)
    label_ids_on_card = card['idLabels']
    label_ids = list(set(label_ids_to_add + label_ids_on_card))
    return trello.update_card(id=id, update_field='idLabels', updated_value=label_ids)

class Todo:

    def __init__(self):
        # Create the openai client
        load_dotenv()
        # Defaults to os.environ.get("OPENAI_API_KEY"), otherwise use: api_key="API_Key",
        self.client = OpenAI()

    def get_relevant_tasks(self, content):
        tasks = get_tasks()
        tasks = clean_tasks(tasks)
        # similar_task_threshold = 0.3 # a bit of ad-hoc testing showed about 0.2 is a good threshold
        # similarity = self.get_task_similarity(tasks, content) #TODO
        return tasks 
    
    def get_task_similarity(self, tasks, content):
        content_embedding = self.get_embedding(content)

        def dist(embedding):
            dot_product = np.dot(embedding, content_embedding)
            norm_vec1 = np.linalg.norm(embedding)
            norm_vec2 = np.linalg.norm(content_embedding)
            similarity = dot_product / (norm_vec1 * norm_vec2)
            return similarity
        
        similarity = 0 #TODO

        return similarity

    def get_embedding(self, content):
        response = self.client.embeddings.create(input = content, model="text-embedding-3-small")
        embedding = np.array(response.data[0].embedding)
        return embedding

    def add_new_tasks(self, tasks) -> list[int]:
        """
        Given a list of new tasks, add them to the database and return a
        list of the indexes of the added tasks.
        """
        # make a new trello card for each task
        cards = []
        for task in tasks:
            list_id = eager_get_list_id(board_name='Secretary', list_name=task['type'])
            if isinstance(task['requestor'], str):
                description = f"Requestor: {task['requestor']}\nActor: {task['actor']}\n\n{task['notes']}"
            else:
                description = task['notes']
            label_ids = eager_get_label_ids(task['topics'])
            response = trello.create_card(list_id,
                                          name=task['summary'],
                                          description=description,
                                          due=task['due_date'],
                                          label_ids=label_ids)
            cards.append(response)

        # TODO: embed the new tasks and record the embeddings
        return cards