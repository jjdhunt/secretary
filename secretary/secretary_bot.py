from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import os
from dotenv import load_dotenv
from openai import OpenAI
from io import StringIO
from datetime import datetime
from typing import Annotated, Any, List, Optional

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

def _strip_special(s:str, prefixes:Optional[List[str]]=[], suffixes:Optional[List[str]]=[]) -> str:
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

def extract_tasks(message: Annotated[str, "The user message content to extract tasks from"]):
    """
    Given a message from a user that mentions action items or tasks, this function extracts a list of individual tasks.
    """
    current_datetime_string = datetime.now().strftime('%Y-%m-%d')
    system_message = sm.extract_action_items
    system_message += f'\nThe current date and time is {current_datetime_string}.\n'
    existing_labels_str = ', '.join(todo.get_labels().keys())
    comment = f'{message}\n\nExisting Labels:\n{existing_labels_str}'
    response, _ = get_completion(comment=comment, system_message=system_message)
    tasks = json.loads(_clean_response_json(response))
    for i, task in enumerate(tasks):
        task['id'] = i
    return tasks

def merge_tasks(existing_tasks: list[dict[Any]],
                new_tasks: list[dict[Any]]):
    """
    Identify novel tasks in the new_tasks list. Return a list of the novel tasks.
    """
    existing_tasks_json = json.dumps(existing_tasks)
    new_tasks_json = json.dumps(new_tasks)
    system_message = sm.merge_tasks
    comment = f'Existing Tasks:\n{existing_tasks_json}\n\nPotential New Tasks:\n{new_tasks_json}\n'
    response, _ = get_completion(comment=comment, system_message=system_message)
    response_dict = json.loads(_clean_response_json(response))
    novel_task_ids = response_dict["novel_tasks_ids"]
    novel_tasks = [task for task in new_tasks if task['id'] in novel_task_ids]
    return novel_tasks

def update_existing_tasks(message: str,
                          existing_tasks: list[dict[Any]]):
    """
    Given a message from a user that may refer to some tasks, update the appropriate tasks.
    """
    tasks_json = json.dumps(existing_tasks)
    current_datetime_string = datetime.now().strftime('%Y-%m-%d')
    system_message = sm.update_tasks
    system_message += f'\nThe current date and time is {current_datetime_string}.\n'
    content = f'Tasks:\n{tasks_json}\nComment:\n{message}'
    tools = [trello.tools['update_card_description']['schema'],
             trello.tools['update_card_due']['schema'],
             trello.tools['update_card_completion']['schema'],
             trello.tools['add_label_to_card']['schema'],
             ]
    _, tool_calls = get_completion(comment=content,
                                   system_message=system_message,
                                   tools=tools)
    
    updated_tasks = []
    if tool_calls is not None:
        # Iterate through tool calls
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            func = trello.tools[func_name]['callable']
            existing_tasks = func(**arguments)
            updated_tasks.append(existing_tasks)
    
    return updated_tasks


def answer_questions_about_tasks(question: Annotated[str, "The user's question(s) to be answers."],
                                 tasks: list[dict[Any]]) -> str:
    '''
    Answer a question about to-do tasks.
    '''
    tasks_json = json.dumps(tasks)
    current_datetime_string = datetime.now().strftime('%Y-%m-%d')
    system_message = sm.answer_task_questions
    system_message += f'\nThe current date and time is {current_datetime_string}.'
    content = f'Tasks:\n{tasks_json}\nComment:\n{question}'
    response, _ = get_completion(comment=content, system_message=system_message)
    return response

def get_user_name(userID):
    uname = app.client.users_profile_get(user=userID) 
    return uname['profile']['real_name_normalized']

def handle_message(message, say):

    say("I hear you, let me think...")

    user_name = get_user_name(message['user'])
    msg = f"From: {user_name}\n{message['text']}"
        
    # Retrieve existing tasks
    existing_tasks = todos.get_relevant_tasks(msg)

    # Answer questions about tasks
    answer = answer_questions_about_tasks(msg, existing_tasks)
    if answer not in {'""', ''}:
        say(answer)
        return
    
    # Update existing tasks
    updated_tasks = update_existing_tasks(msg, existing_tasks)
    if len(updated_tasks)>0:
        card_urls = [task['url'] for task in updated_tasks]
        # send updated card urls to user
        if len(updated_tasks)==1: say("I updated this existing task:\n" + "\n".join(card_urls))
        else: say("I updated these existing tasks:\n"  + "\n".join(card_urls))

    # Find new tasks in the message
    new_tasks = extract_tasks(msg)
    existing_tasks = todos.get_relevant_tasks(msg) # Tasks may have been updated so retrieve them again
    new_tasks = merge_tasks(existing_tasks, new_tasks)
    if len(new_tasks)>0:
        card_urls = todos.add_new_tasks(new_tasks)
        # send new card urls to user
        if len(new_tasks)==1: say("I identified this new task:\n" + "\n".join(card_urls))
        else: say("I identified these new tasks:\n"  + "\n".join(card_urls))
    
    say("OK, I'm gonna go mine some bitcoins, let me know if you need anything.")

@app.event("message")
def handle_message_events(body, say):
    handle_message(body['event'], say)

if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()