from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz
import threading
import time
from typing import Annotated, Any

import json
import sys
sys.path.append('../secretary')

import secretary.system_messages as sm
import secretary.utils_openai as ai
import secretary.tasks as tasks

load_dotenv()

# https://github.com/slackapi/bolt-python#creating-an-app
app = App(token=os.environ['SLACK_BOT_TOKEN'])

convo_global = ai.Messages()
user_time_zone_global = 'UTC'
user_id_global = None
user_name_global = None

def extract_tasks_base(message: Annotated[str, "The message content to extract tasks from."],
                       current_user_local_time: Annotated[str, "The user's local datetime formatted as '%Y-%m-%d %H:%M:%S %z'"]) -> list[Any]:
    """
    Given raw unformatted content from a user that mentions action items, tasks, or to-dos,
    this function extracts individual tasks in a structured format.
    """
    system_message = sm.extract_action_items
    system_message += f'\nThe current date and time is {current_user_local_time}.'
    existing_labels_str = ', '.join(tasks.get_labels().keys())
    comment = f'{message}\n\nExisting Labels:\n{existing_labels_str}'
    response, _ = ai.get_completion(comment=comment, system_message=system_message)
    new_tasks = json.loads(ai.clean_response_json(response))
    return new_tasks

def extract_tasks(message: Annotated[str, "The verbatim user message content to extract tasks from. This should include all content and context relevant to the task(s)."]) -> list[Any]:
    """
    Given raw unformatted content from a user that mentions action items, tasks, or to-dos, this function extracts individual tasks in a structured format.
    """
    global user_time_zone_global
    current_user_local_time = datetime.now(pytz.timezone(user_time_zone_global)).strftime('%Y-%m-%d %H:%M:%S %z')
    new_tasks = extract_tasks_base(message, current_user_local_time)
    new_cards = tasks.add_new_tasks(new_tasks)
    return new_cards

def task_follow_up(tasks):
    """
    Given tasks without due dates, ask for due dates.
    """
    global user_time_zone_global
    global convo_global

    # Build the system and user messages
    tasks_json = json.dumps(tasks)
    system_message = sm.follow_up_on_tasks
    current_user_local_time = datetime.now(pytz.timezone(user_time_zone_global)).strftime('%Y-%m-%d %H:%M:%S %z')
    system_message += f'\nThe current date and time is {current_user_local_time}.'
    full_messages = [{"role": "system", "content": system_message}]
    full_messages += [{"role": "user", "content": f'Tasks:\n{tasks_json}'}]
    full_messages += convo_global.messages
    # Get the response/tool calls from the Chat API
    response, _ = ai.get_conversation_completion(messages=full_messages)

    return response

def process_user_message(messages: list[Any]):
    """
    Given a message from a user, decide what to do and then do it.
    """
    global user_time_zone_global

    # Build the system and user messages
    existing_tasks = tasks.get_relevant_tasks(messages, user_time_zone_global)
    tasks_json = json.dumps(existing_tasks)
    system_message = sm.base_secretary
    current_user_local_time = datetime.now(pytz.timezone(user_time_zone_global)).strftime('%Y-%m-%d %H:%M:%S %z')
    system_message += f'\nThe current date and time is {current_user_local_time}.'
    full_messages = [{"role": "system", "content": system_message}]
    full_messages += [{"role": "user", "content": f'Existing Tasks:\n{tasks_json}'}]
    full_messages += messages

    # Build the tools
    tools = {}
    ai.add_function_to_tools(tools, tasks.update_task_description)
    ai.add_function_to_tools(tools, tasks.update_task_due_date)
    ai.add_function_to_tools(tools, tasks.mark_task_completed)
    ai.add_function_to_tools(tools, tasks.add_label_to_task)
    ai.add_function_to_tools(tools, extract_tasks)
    tool_schemas = [tools[name]['schema'] for name in tools]

    # Get the response/tool calls from the Chat API
    response, tool_calls = ai.get_conversation_completion(messages=full_messages,
                                                          tools=tool_schemas)
    
    created_cards = []
    updated_cards = []
    done_cards = []
    tools_called = []
    if tool_calls is not None:
        # Iterate through tool calls
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            tools_called.append(func_name)
            arguments = json.loads(tool_call.function.arguments)
            func = tools[func_name]['callable']
            card = func(**arguments)
            if func_name=='extract_tasks':
                created_cards += card # extract_tasks return a list of tasks
            elif func_name=='mark_task_completed':
                done_cards.append(card)
            else:
                updated_cards.append(card)
    
    return response, created_cards, updated_cards, done_cards, tools_called

def get_user_name(userID) -> str:
    response = app.client.users_profile_get(user=userID)
    return response['profile']['real_name_normalized']

def get_user_timezone(userID) -> str:
    response = app.client.users_info(user=userID)
    user_info = response['user']
    return user_info.get('tz', 'Unknown Timezone')
    
def say_on_the_record(say, message):
    global convo_global

    if message and len(message)>0:
        convo_global.add_message('assistant', message)
        if say: say(message)

def format_card_links(cards) -> str:
    if len(cards)==1:
        card_links = [f"<{card['url']}|{card['name']}>" for card in cards]
        return "\n".join(card_links)
    elif len(cards)>1:
        card_links = [f"  {i+1}. <{card['url']}|{card['name']}>" for i, card in enumerate(cards)]
        return "\n".join(card_links)
    return ""

def card_link_description(cards, comment_single: str = "", comment_multiple: str = ""):
    card_links = format_card_links(cards)
    if len(cards)==1:
        if comment_single == "":
            return card_links
        else:
            return f"{comment_single}\n" + card_links
    elif len(cards)>1:
        if comment_multiple == "":
            return card_links
        else:
            return f"{comment_multiple}\n"  + card_links
    return ""


def morning_push_update():
    """
    Send an update to the user (the global user_id_global) about the status of their tasks
    due today and overdue.
    """
    global user_id_global
    global user_name_global
    due_later_today = tasks.due_later_today()
    overdue = tasks.overdue()
    app.client.chat_postMessage(channel=user_id_global, text=f"Good morning {user_name_global}!")
    if (len(due_later_today) == 0) & (len(overdue) == 0):
        msg = f"Relax, you don't have anything to do today :beach_with_umbrella:"
    else: 
        if len(due_later_today) > 0:
            msg = card_link_description(due_later_today,
                                        f"You have only this one task to do later today:",
                                        f"You have these tasks to do later today:")
            app.client.chat_postMessage(channel=user_id_global, text=msg)
        if len(overdue) > 0:
            msg = card_link_description(overdue,
                                        f"Just a reminder, you have only this one overdue task...",
                                        f"Just a reminder, you have these overdue tasks...")
            app.client.chat_postMessage(channel=user_id_global, text=msg)
    
def evening_push_update():
    """
    Send an update to the user (the global user_id_global) about the status of their work today.
    """
    app.client.chat_postMessage(channel=user_id_global, text=f"Good night {user_name_global} :yawning_face:, really nice work today.")

def handle_message(user_name, message_text, say=None):
    global convo_global

    if message_text.strip().lower() == 'clear':
        convo_global.clear()
        if say: say('(My mind is a blank slate)')
        return
    
    if message_text.strip().lower() == 'overdue':
        # msg = f"From {user_name}:\nWhat tasks are overdue?"
        # convo_global.add_message('user', msg)
        # card_link_description(say, tasks.overdue(), "This is the only overdue task:", "These tasks are overdue:")
        morning_push_update()
        return

    # say("(I hear you, let me think...)")

    convo_global.keep_last(6)

    responses = {'initial': None,
                 'follow_up': None}
    
    msg = f"From {user_name}:\n{message_text}"
    convo_global.add_message('user', msg)
    
    response, created_cards, updated_cards, done_cards, tools_called = process_user_message(convo_global.messages)
    responses['initial'] = response

    say_on_the_record(say, response)

    # Tell the user about completed, updated, and created tasks
    card_description = card_link_description(done_cards, "Great! I marked this task as done (and deleted it):", "Cool, I marked these tasks as done (and deleted them):")
    say_on_the_record(say, card_description)
    card_description = card_link_description(updated_cards, "I updated this task:", "I updated these tasks:")
    say_on_the_record(say, card_description)
    card_description = card_link_description(created_cards, "I created this task:", "I created these tasks:")
    say_on_the_record(say, card_description)

    # Follow up on tasks with no due date
    cards_without_due_dates = [card for card in updated_cards if card['due'] is None] + [card for card in created_cards if card['due'] is None]
    if len(cards_without_due_dates)>0:
        follow_up_response = task_follow_up(cards_without_due_dates)
        if follow_up_response:
            say_on_the_record(say, follow_up_response.replace("LIST_OF_TASKS", format_card_links(cards_without_due_dates)))
        responses['follow_up'] = follow_up_response

    # say("(OK, I'm gonna go mine some bitcoins, let me know if you need anything)")

    return responses, tools_called

@app.event("message")
def handle_message_events(body, say):
    global user_time_zone_global
    global user_id_global
    global user_name_global

    if 'text' not in body['event']:
        return
    
    user_id_global = body['event']['user']
    user_name_global = get_user_name(body['event']['user'])
    user_time_zone_global = get_user_timezone(body['event']['user'])

    handle_message(user_name_global,
                   body['event']['text'],
                   say)

def scheduled_daily_function_execution(target_time: str, fcn: callable):
    """Run a task function every day at the target time (HH:MM) in the specified time zone."""
    print(f"The function {fcn} will be run everyday at {target_time}")
    while True:
        # Get the current time in the user's time zone
        current_user_local_time = datetime.now(pytz.timezone(user_time_zone_global))
        if current_user_local_time.strftime("%H:%M") == target_time:
            fcn()  # Execute the function
            time.sleep(60)  # Avoid multiple executions within the same minute
        time.sleep(30)  # Check every 30 seconds

if __name__ == "__main__":
    # Start the scheduling thread with time zone support
    morning_push_update_thread = threading.Thread(target=scheduled_daily_function_execution, args=("07:00", morning_push_update), daemon=True)
    evening_push_update_thread = threading.Thread(target=scheduled_daily_function_execution, args=("22:30", evening_push_update), daemon=True)
    
    morning_push_update_thread.start()
    evening_push_update_thread.start()

    # Start the Slack app
    handler = SocketModeHandler(app, os.environ['SLACK_APP_TOKEN'])
    handler.start()