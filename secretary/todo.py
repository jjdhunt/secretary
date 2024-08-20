import os
from pathlib import Path
import pandas as pd
from tabulate import tabulate
import re
from io import StringIO
from dotenv import load_dotenv
from openai import OpenAI
import numpy as np
from typing import Optional, Union, List, Tuple

import secretary.trello as trello
    
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
    boards = trello.get_boards()
    board_id = trello.find_dict_by_name(boards, 'Secretary')['id']
    cards = trello.get_cards_on_board(board_id)
    return cards

def get_labels():
    boards = trello.get_boards()
    board_id = trello.find_dict_by_name(boards, 'Secretary')['id']
    labels = trello.get_labels_on_board(board_id)
    labels = {label['name']: label['id'] for label in labels if label['name']!=''}
    return labels

def create_labels(names: list[str]):
    """
    Find the ids of existing labels, or create new labels.
    """
    label_ids = []
    boards = trello.get_boards()
    board_id = trello.find_dict_by_name(boards, 'Secretary')['id']
    existing_labels = get_labels()
    for name in names:
        name = name.lower()
        if name in existing_labels:
            label_ids.append(existing_labels[name])
        elif name not in ['nan', 'nan', 'none', 'null']:
            label_ids.append(trello.create_label(board_id, name)['id'])
    return label_ids

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

    def add_new_tasks(self, tasks) -> List[int]:
        """
        Given a list of new tasks, add them to the database and return a
        list of the indexes of the added tasks.
        """
        # make a new trello card for each task
        boards = trello.get_boards()
        board_id = trello.find_dict_by_name(boards, 'Secretary')['id']
        cards = []
        for task in tasks:
            # "topics": <a list of topic(s)>,
            # "type": <one of [question, action_item]>,
            # "due_date": <the due date, if any, formatted as "YYYY-MM-DD">,
            # "requestor": <the person(s) the request is coming from>,
            # "actor": <who should do the thing>,
            # "summary": <a very concise summary of the item>,
            # "notes": <direct quotes of all relevant information in the text needed to complete the task>
            lists = trello.get_lists_on_board(board_id)
            list_dict = trello.find_dict_by_name(lists, task['type'])
            if not list_dict:
                list_dict = trello.create_list(board_id, name=task['type'])
            list_id = list_dict['id']
            if isinstance(task['requestor'], str):
                description = f"Requestor: {task['requestor']}\nActor: {task['actor']}\n\n{task['notes']}"
            else:
                description = task['notes']
            label_ids = create_labels(task['topics'])
            response = trello.create_card(list_id,
                                          name=task['summary'],
                                          description=description,
                                          due=task['due_date'],
                                          label_ids=label_ids)
            cards.append(response)

        # TODO: embed the new tasks and record the embeddings
        return cards