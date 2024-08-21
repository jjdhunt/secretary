from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import os
from dotenv import load_dotenv
from openai import OpenAI
from io import StringIO
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Optional

import json
import sys
sys.path.append('../secretary')

import secretary.system_messages as sm
import secretary.chat_tools as ct
import secretary.todo as todo
import secretary.trello as trello

load_dotenv()

# https://github.com/slackapi/bolt-python#creating-an-app
SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
SLACK_APP_TOKEN = os.environ['SLACK_APP_TOKEN']
app = App(token=SLACK_BOT_TOKEN)

client = OpenAI(
    # Defaults to os.environ.get("OPENAI_API_KEY")
    # Otherwise use: api_key="API_Key",
)

todos = todo.Todo()

class Messages():

    def __init__(self):
        self.messages = []

    def clear(self):
        self.messages = []

    def add_message(self, role: Literal['user', 'assistant'], message: str):
        message = {"role": role, "content": message}
        self.messages.append(message)

convo = Messages()

secretary_tools = {}

def get_completion(comment, system_message, model_class='best', tools=None, temperature=0):

    models = {'fast': 'gpt-4o-mini',
              'best': 'gpt-4o'}

    completion = client.chat.completions.create(
                                                model=models[model_class],
                                                temperature=temperature,
                                                tools=tools,
                                                messages=[
                                                    {"role": "system", "content": system_message},
                                                    {"role": "user", "content": comment}
                                                ],
                                                )
    return completion.choices[0].message.content, completion.choices[0].message.tool_calls

def get_conversation_completion(messages, model_class='best', tools=None, temperature=0):

    models = {'fast': 'gpt-4o-mini',
              'best': 'gpt-4o'}

    completion = client.chat.completions.create(
                                                model=models[model_class],
                                                temperature=temperature,
                                                tools=tools,
                                                messages=messages,
                                                )
    return completion.choices[0].message.content, completion.choices[0].message.tool_calls

def _strip_special(s:str, prefixes:Optional[list[str]]=[], suffixes:Optional[list[str]]=[]) -> str:
    for prefix in prefixes:
        if s.startswith(prefix):
            s = s[len(prefix):]
    for suffix in suffixes:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    return s

def _clean_response_json(json_str):
    # Clean up the json string. Gpt can add unwanted decorators and things.
    prefixes = ["```json"]
    suffixes = ["```"]
    json_str = _strip_special(json_str, prefixes, suffixes)
    return json_str

def identify_novel_tasks(existing_tasks: list[dict[Any]],
                new_tasks: list[dict[Any]]):
    """
    Identify novel tasks in the new_tasks list. Return a list of the novel tasks.
    """
    existing_tasks_json = json.dumps(existing_tasks)
    new_tasks_json = json.dumps(new_tasks)
    comment = f'Existing Tasks:\n{existing_tasks_json}\n\nPotential New Tasks:\n{new_tasks_json}\n'
    response, _ = get_completion(comment=comment, system_message=sm.identify_novel_tasks)
    response_dict = json.loads(_clean_response_json(response))
    novel_task_ids = response_dict["novel_tasks_ids"]
    novel_tasks = [task for task in new_tasks if task['id'] in novel_task_ids]
    return novel_tasks

def filter_tasks(tasks: list[dict[Any]]):
    """
    Filter the tasks list. Return a list of the the unfiltered tasks.
    """
    tasks_json = json.dumps(tasks)
    comment = f'{tasks_json}\n'
    response, _ = get_completion(comment=comment, system_message=sm.filter_tasks)
    response_dict = json.loads(_clean_response_json(response))
    task_ids = response_dict["unfiltered_tasks_ids"]
    unfiltered_tasks = [task for task in tasks if task['id'] in task_ids]
    return unfiltered_tasks

@ct.tools_function(secretary_tools)
def extract_tasks(message: Annotated[str, "The verbatim user message content to extract tasks from. This should include all content and context relevant to the task(s)."]):
    """
    Given raw unformatted content from a user that mentions action items, tasks, or to-dos, this function extracts individual tasks in a structured format.
    """

    current_datetime_string = datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %I:%M:%S %p %Z')
    system_message = sm.extract_action_items
    system_message += f'\nThe current date and time is {current_datetime_string}.'
    existing_labels_str = ', '.join(todo.get_labels().keys())
    comment = f'{message}\n\nExisting Labels:\n{existing_labels_str}'
    response, _ = get_completion(comment=comment, system_message=system_message)
    new_tasks = json.loads(_clean_response_json(response))
    for i, task in enumerate(new_tasks):
        task['id'] = i

    if len(new_tasks)>0:
        existing_tasks = todos.get_relevant_tasks(message) # Tasks may have been updated so retrieve them again
        new_tasks = identify_novel_tasks(existing_tasks, new_tasks)
    if len(new_tasks)>0:
        new_tasks = filter_tasks(new_tasks)

    new_cards = todos.add_new_tasks(new_tasks)

    return new_cards

def process_user_message(messages: list[Any]):
    """
    Given a message from a user, decide what to do and do it.
    """
    # Retrieve existing tasks
    existing_tasks = todos.get_relevant_tasks(messages)
    tasks_json = json.dumps(existing_tasks)
    current_datetime_string = datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %I:%M:%S %p %Z')

    system_message = sm.base_secretary
    system_message += f'\nThe current date and time is {current_datetime_string}.'

    full_messages = [{"role": "system", "content": system_message}]
    full_messages += [{"role": "user", "content": f'Existing Tasks:\n{tasks_json}'}]
    full_messages += messages

    combined_tools = {**todo.tools, **secretary_tools}
    tool_schemas = [combined_tools[name]['schema'] for name in combined_tools]
    response, tool_calls = get_conversation_completion(messages=full_messages,
                                                tools=tool_schemas)
    
    updated_cards = []
    if tool_calls is not None:
        # Iterate through tool calls
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            func = combined_tools[func_name]['callable']
            card = func(**arguments)
            if isinstance(card, list):
                updated_cards += card
            else:
                updated_cards.append(card)
    
    return response, updated_cards

def get_user_name(userID):
    uname = app.client.users_profile_get(user=userID) 
    return uname['profile']['real_name_normalized']

def say_on_the_record(say, message):
    if message:
        convo.add_message('assistant', message)
        say(message)

def handle_message(message, say):

    if message['text'] == 'clear':
        convo.clear()
        say('(My mind is a blank slate)')
        return
    
    say("I hear you, let me think...")

    user_name = get_user_name(message['user'])
    msg = f"From: {user_name}\n{message['text']}"

    convo.add_message('user', msg)

    response, updated_cards = process_user_message(convo.messages)
    say_on_the_record(say, response)

    if len(updated_cards)>0:
        card_urls = [card['url'] for card in updated_cards]
        # send updated card urls to user
        if len(updated_cards)==1: say_on_the_record(say, "I created/updated this task:\n" + "\n".join(card_urls))
        else: say_on_the_record(say, "I created/updated these tasks:\n"  + "\n".join(card_urls))
    
    say("(OK, I'm gonna go mine some bitcoins, let me know if you need anything)")

@app.event("message")
def handle_message_events(body, say):
    handle_message(body['event'], say)

if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()