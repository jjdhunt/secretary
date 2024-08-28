import numpy as np
from typing import Annotated
from datetime import datetime, timedelta
import pytz
from typing import Annotated, Any

import secretary.utils_trello as utils_trello
import secretary.utils_openai as ai

BOARD_NAME = 'Secretary'

def convert_time_to_iso8601_string(datetime_str: Annotated[str, 'datetime in YYYY-MM-DD HH:MM:SS +UTC_offset format']):
    # Try to convert the input string into a datetime. Will fail if it is not formatted as "YYYY-MM-DD HH:MM:SS +UTC"
    try:
        local = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S %z')
    except:
        return None
    
    # Convert to UTC
    utc_dt = local.astimezone(pytz.utc)
    
    # Format to ISO 8601
    return utc_dt.isoformat()


def convert_iso8601_to_local_string(utc_time_str, timezone_str):

    # Try to convert the input string into a datetime. Will fail if it is not formatted as ISO
    try:
        if utc_time_str.endswith('Z'):
            utc_time_str = utc_time_str[:-1] + '+00:00'
        utc_time = datetime.fromisoformat(utc_time_str)
    except:
        return None
    
    # Ensure the datetime object is aware (has timezone info)
    if utc_time.tzinfo is None:
        utc_time = pytz.utc.localize(utc_time)

    # Convert to the specified local timezone
    local_tz = pytz.timezone(timezone_str)
    local_time = utc_time.astimezone(local_tz)

    # Format the local time as a string "YYYY-MM-DD HH:MM:SS +UTC"
    return local_time.strftime('%Y-%m-%d %H:%M:%S %z')


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


def get_tasks(timezone_str: Annotated[str, "A string giving the time zone to represent the tasks' time in, eg. 'America/Los_Angeles'"] = 'UTC'):
    """
    Get all tasks on the BOARD_NAME board, with their due dates in local time zone.
    """
    board_id = utils_trello.get_board_id(board_name=BOARD_NAME)
    cards = utils_trello.get_cards_on_board(board_id)
    for card in cards:
        card['due'] = convert_iso8601_to_local_string(card['due'], timezone_str)
    return cards

def overdue(timezone_str: Annotated[str, "A string giving the time zone to use as a reference for 'today', eg. 'America/Los_Angeles'"] = 'UTC'):
    """
    Get all overdue tasks.
    """
    board_id = utils_trello.get_board_id(board_name=BOARD_NAME)
    cards = utils_trello.get_cards_on_board(board_id)
    
    now = datetime.now(pytz.timezone(timezone_str))

    filtered_cards = []
    for card in cards:
        utc_time_str = card['due'][:-1] + '+00:00'
        utc_time = datetime.fromisoformat(utc_time_str)
        card['due'] = convert_iso8601_to_local_string(card['due'], timezone_str)
        if now > utc_time:
            filtered_cards.append(card)

    return filtered_cards

def get_tasks_between_dates(start_datetime: datetime, end_datetime: datetime, timezone_str: Annotated[str, "A string giving the time zone to represent the tasks' time in, eg. 'America/Los_Angeles'"] = 'UTC'):
    board_id = utils_trello.get_board_id(board_name=BOARD_NAME)
    cards = utils_trello.get_cards_on_board(board_id)
    
    filtered_cards = []
    for card in cards:
        utc_time_str = card['due'][:-1] + '+00:00'
        utc_time = datetime.fromisoformat(utc_time_str)
        card['due'] = convert_iso8601_to_local_string(card['due'], timezone_str)
        if start_datetime <= utc_time <= end_datetime:
            filtered_cards.append(card)

    return filtered_cards

def due_today(timezone_str: Annotated[str, "A string giving the time zone to use as a reference for 'today', eg. 'America/Los_Angeles'"] = 'UTC'):
    """
    Get the tasks due today, midnight to midnight in the specified timezone.
    """
    now = datetime.now(pytz.timezone(timezone_str))
    lastnight_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tonight_midnight = lastnight_midnight + timedelta(days=1)
    return get_tasks_between_dates(lastnight_midnight, tonight_midnight, timezone_str)

def due_earlier_today(timezone_str: Annotated[str, "A string giving the time zone to use as a reference for 'today', eg. 'America/Los_Angeles'"] = 'UTC'):
    """
    Get the tasks that were due earlier today, between midnight in the specified timezone and now.
    """
    now = datetime.now(pytz.timezone(timezone_str))
    lastnight_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return get_tasks_between_dates(lastnight_midnight, now, timezone_str)

def due_later_today(timezone_str: Annotated[str, "A string giving the time zone to use as a reference for 'today', eg. 'America/Los_Angeles'"] = 'UTC'):
    """
    Get the tasks due later today, between now and midnight in the specified timezone.
    """
    now = datetime.now(pytz.timezone(timezone_str))
    lastnight_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tonight_midnight = lastnight_midnight + timedelta(days=1)
    return get_tasks_between_dates(now, tonight_midnight, timezone_str)

def due_tomorrow(timezone_str: Annotated[str, "A string giving the time zone to use as a reference for 'today', eg. 'America/Los_Angeles'"] = 'UTC'):
    """
    Get the tasks due tomorrow, midnight to midnight in the specified timezone.
    """
    now = datetime.now(pytz.timezone(timezone_str))
    tomorrow_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    tomorrow_end = tomorrow_midnight + timedelta(days=1)
    return get_tasks_between_dates(tomorrow_midnight, tomorrow_end, timezone_str)

def due_this_week(timezone_str: Annotated[str, "A string giving the time zone to use as a reference for 'today', eg. 'America/Los_Angeles'"] = 'UTC'):
    """
    Get the tasks due this week, between midnight Monday morning and midnight Sunday night in the specified timezone.
    """
    now = datetime.now(pytz.timezone(timezone_str))
    lastnight_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_this_week = lastnight_midnight - timedelta(lastnight_midnight.weekday())
    end_of_this_week = start_of_this_week + timedelta(days=7)
    return get_tasks_between_dates(start_of_this_week, end_of_this_week, timezone_str)

def get_labels():
    board_id = utils_trello.get_board_id(board_name=BOARD_NAME)
    labels = utils_trello.get_labels_on_board(board_id)
    labels = {label['name']: label['id'] for label in labels if label['name']!=''}
    return labels


def eager_get_label_ids(names: list[str]):
    """
    Given a list of label names, find the ids of those that exist already, or create new labels and get their ids.
    """
    label_ids = []
    board_id = utils_trello.get_board_id(board_name=BOARD_NAME)
    existing_labels = get_labels()
    for name in names:
        name = name.lower()
        if name in existing_labels:
            label_ids.append(existing_labels[name])
        elif name not in ['nan', 'nan', 'none', 'null']:
            label_ids.append(utils_trello.create_label(board_id, name)['id'])
    return label_ids


def eager_get_list_id(list_name: str):
    """
    Given a list name, find its id if it exists on the board already, or create it on that board and get its id.
    """
    board_id = utils_trello.get_board_id(board_name=BOARD_NAME)
    list_id = utils_trello.get_list_id(board_id, list_name)
    if not list_id:
        list_id = utils_trello.create_list(board_id, list_name)['id']
    return list_id


def update_task_description(id: Annotated[str, 'The id of the task to update'],
                            updated_description: Annotated[str, 'A new description to replace the old one with.']):
    """
    Update the description of a task.
    """
    return utils_trello.update_card(id=id, update_field='desc', updated_value=updated_description)


def update_task_due_date(id: Annotated[str, 'The id of the task to update'],
                         updated_due_date: Annotated[str, 'The new due date, formatted as "YYYY-MM-DD HH:MM:SS +<UTC offset>"']):
    """
    Set or update the due date of a task.
    """
    due_date_utc = convert_time_to_iso8601_string(updated_due_date)
    return utils_trello.update_card(id=id, update_field='due', updated_value=due_date_utc)


def update_task_completion(id: Annotated[str, 'The id of the task to update'],
                           is_complete: Annotated[str, 'The new status. "true" is done/completed, "false" is incomplete.']):
    """
    Change the completion status of a task.
    """
    if is_complete == 'true':
        card = utils_trello.get_card(card_id=id)
        utils_trello.delete_card(id=id)
        return card
    return utils_trello.update_card(id=id, update_field='closed', updated_value=is_complete)


def mark_task_completed(id: Annotated[str, 'The id of the task that is completed']):
    """
    Mark a task as completed.
    """
    card = utils_trello.get_card(card_id=id)
    utils_trello.delete_card(id=id)
    return card

def add_label_to_task(id: Annotated[str, 'The id of the task to update'],
                      label_names: Annotated[list[str], 'The names of the label(s) to add to the task']):
    """
    Add one or more label(s) to a task.
    """
    label_names = [label_name.lower() for label_name in label_names]
    label_ids_to_add = eager_get_label_ids(label_names)
    card = utils_trello.get_card(id)
    label_ids_on_card = card['idLabels']
    label_ids = list(set(label_ids_to_add + label_ids_on_card))
    return utils_trello.update_card(id=id, update_field='idLabels', updated_value=label_ids)


def get_relevant_tasks(content,
                       timezone_str: Annotated[str, "A string giving the time zone to represent the tasks' time in."]):
    tasks = get_tasks(timezone_str)
    tasks = clean_tasks(tasks)
    # similar_task_threshold = 0.3 # a bit of ad-hoc testing showed about 0.2 is a good threshold
    # similarity = get_task_similarity(tasks, content) #TODO
    return tasks 


def get_task_similarity(tasks, content):
    content_embedding = ai.get_embedding(content)

    def dist(embedding):
        dot_product = np.dot(embedding, content_embedding)
        norm_vec1 = np.linalg.norm(embedding)
        norm_vec2 = np.linalg.norm(content_embedding)
        similarity = dot_product / (norm_vec1 * norm_vec2)
        return similarity
    
    similarity = 0 #TODO 

    return similarity


def add_new_tasks(tasks) -> list[dict[str, Any]]:
    """
    Given a list of new tasks, create trello cards for them and return the cards as dicts.
    """
    # make a new trello card for each task
    cards = []
    for task in tasks:
        list_id = eager_get_list_id(list_name=task['type'])
        if isinstance(task['requestor'], str):
            description = f"Requestor: {task['requestor']}\nActor: {task['actor']}\n\n{task['notes']}"
        else:
            description = task['notes']
        label_ids = eager_get_label_ids(task['topics'])
        due_date_utc = convert_time_to_iso8601_string(task['due_date'])
        response = utils_trello.create_card(list_id,
                                        name=task['summary'].rstrip('.'), # no periods on the end of card names just because it looks nicer w/o them
                                        description=description,
                                        due=due_date_utc,
                                        label_ids=label_ids)
        cards.append(response)

    # TODO: embed the new tasks and record the embeddings
    return cards