from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz
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
    ai.add_function_to_tools(tools, tasks.update_task_completion)
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
            elif func_name=='update_task_completion':
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

    if message:
        convo_global.add_message('assistant', message)
        if say: say(message)

def say_card_links(say, comment_single, comment_multiple, cards):
    if len(cards)>0:
        card_links = [f"  {i+1}. <{card['url']}|{card['name']}>" for i, card in enumerate(cards)]
        if len(card_links)==1: say_on_the_record(say, f"{comment_single}\n" + "\n".join(card_links).lstrip('  1. '))
        else: say_on_the_record(say, f"{comment_multiple}\n"  + "\n".join(card_links))


def talk_through_tasks(say, updated_cards, created_cards, done_cards):

    # Tell the user about updated tasks
    say_card_links(say, "Great! I marked this task as done (and deleted it):", "Cool, I marked these tasks as done (and deleted them):", done_cards)

    if (len(created_cards) >= 1) and (len(updated_cards) >= 1):
        say_on_the_record(say, "I updated some and I created some. Let me tell you about the updates first...")

    # Tell the user about updated tasks
    say_card_links(say, "I updated this task:", "I updated these tasks:", updated_cards)

    # Follow up on updated tasks with no due date
    cards_to_follow_up_on = [card for card in updated_cards if card['due'] is None]
    if len(cards_to_follow_up_on) > 0:
        if (len(cards_to_follow_up_on) == 1) and (len(updated_cards) == 1):
            say_on_the_record(say, "When I was updating that task I noticed it doesn't have a due date, probably my mistake. Can you give me a due date for it?")
        elif (len(cards_to_follow_up_on) == len(updated_cards)) & (len(updated_cards) == 2):
            say_on_the_record(say, "When I was updating those I noticed that neither of them have due dates! Suggestions??")
        elif (len(cards_to_follow_up_on) == len(updated_cards)):
            say_on_the_record(say, "When I was updating those, I was shocked to see none of them have due dates :flushed: don't know how that happened. Could you help me out and give me some suggestions? :pray:")
        else:
            say_card_links(say, "I couldn't figure out a due date for this one. What should it be?", "When I was updating them, I noticed some didn't have due dates! Don't know how that happened. Could you give me some suggestions on due dates for these: :pray:", cards_to_follow_up_on)

    if (len(created_cards) >= 1) and (len(updated_cards) >= 1):
        say_on_the_record(say, "Now on to my creations...")

    # Tell the user about created tasks
    say_card_links(say, "I created this task:", "I created these tasks:", created_cards)

    # Follow up on created cards with no due date
    cards_to_follow_up_on = [card for card in created_cards if card['due'] is None]
    if len(cards_to_follow_up_on) > 0:
        if (len(cards_to_follow_up_on) == 1) and (len(created_cards) == 1):
            say_on_the_record(say, "Can you give me a due date for it? :smile:")
        elif (len(cards_to_follow_up_on) == len(created_cards)):
            say_on_the_record(say, "but none have due dates. Could you give me some due dates for them? :pray:")
        else:
            say_card_links(say, "I couldn't figure out a due date for this one. What should it be?", "I wasn't sure about the due dates for these though. Any suggestions?", cards_to_follow_up_on)


def handle_message(user_name, message_text, say=None):
    global convo_global

    if message_text == 'clear':
        convo_global.clear()
        if say: say('(My mind is a blank slate)')
        return

    # say("(I hear you, let me think...)")

    convo_global.keep_last(6)

    msg = f"From {user_name}:\n{message_text}"
    convo_global.add_message('user', msg)

    response, created_cards, updated_cards, done_cards, tools_called = process_user_message(convo_global.messages)

    if say: say_on_the_record(say, response)

    talk_through_tasks(say, updated_cards, created_cards, done_cards)

    # say("(OK, I'm gonna go mine some bitcoins, let me know if you need anything)")

    return response, tools_called

@app.event("message")
def handle_message_events(body, say):
    global user_time_zone_global

    if 'text' not in body['event']:
        return
    
    user_name = get_user_name(body['event']['user'])
    user_time_zone_global = get_user_timezone(body['event']['user'])

    handle_message(user_name,
                   body['event']['text'],
                   say)

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ['SLACK_APP_TOKEN'])
    handler.start()