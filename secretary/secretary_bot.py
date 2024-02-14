from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import os
from dotenv import load_dotenv
# import re
from openai import OpenAI
import pandas as pd
from tabulate import tabulate
import re
from io import StringIO
from datetime import datetime

import sys
sys.path.append('../secretary')

import secretary.chat_system_messages as sm
import secretary.chat_tools as ct
import secretary.todo as todo

load_dotenv()

# https://github.com/slackapi/bolt-python#creating-an-app
SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
SLACK_APP_TOKEN = os.environ['SLACK_APP_TOKEN']
app = App(token=SLACK_BOT_TOKEN)

# Interaction flow:
# 1. User sends comment
#       a.  To simplify things initially we will assume each comment is a complete thought.
#           Later, we can add logic to watch for 'user-typing' events and have a timeout, and/or ask gpt 'has the user completed their thought?'.
# 2. Extract tasks from comment [PROMPT: extract_action_items].
# 3. Iterate over new tasks, starting with all secretary tasks.
#       a. For each task, find semantically similar existing tasks. Provide these along with new task to gpt.
#       b. For secretary tasks,
#           i.   First ask gpt to select a tool [PROMPT: select_secretary_task_tool].
#                Secretary tools: show_tasks([all, open, closed, for_actor, from_requestor, due_by(date)]),
#           ii.  Execute tools.
#       c. For non-tool secretary tasks and all non-secretary tasks:
#           i. Ask if the new task is related to any of the similar existing task(s) [PROMPT: identify_related_existing_tasks].
#           ii. If yes, ask it to merge/update the indicated existing task(s) based on the new task [PROMPT: update_existing_task_items].
#               a. Show the user the old task, the new task, and the old task updated with the new task and ask for confirmation.
#               b. If user confirms, replace old task with updated tasks and reembed the updated task.
# 4. For remaining new tasks (tasks not used to update existing tasks, and secretary tasks not used to trigger tools):
#       a. If they are secretary tasks, notify the user "I don't know how to do X."
#       b. If they are non-secretary tasks, embed the updated task.

# Buuut...
# This could result in orphaned tasks. For example, if the user says "I bought eggs" this might not be identified as an action item,
# and so it would not be used to update the relevant task. Should the entire comment be given to gpt to ask if it 
# should be used to update existing tasks?

# Another version of interaction flow:
# 1. Use the whole comment to update retrieved tasks.
#       a. Retrieve semantically similar tasks.
#       b. Provide these in json format to gpt along with new user coment and ask it to update the task(s) based on the comment [PROMPT: update_tasks].
#       c. Provide the original and updated task(s) to user for confirmation of update.
#       d. If user confirms, replace old task(s) with updated task(s) and reembed the updated task(s).
# 2. Extract tasks from comment [PROMPT: extract_action_items].
# 3. Iterate over new tasks for the secretary.
#       a. First ask gpt to select a tool [PROMPT: select_secretary_task_tool].
#          Secretary tools: show_tasks([all, open, closed, for_actor, from_requestor, due_by(date)]),
#       b. Execute specified tools.
#       c. If no tool is identified for the secretary task, report to the user 'Sorry, I don't know how to do that.'
# 4. Iterate over new non-secretary tasks.
#       a. For each task, find semantically similar existing tasks. These should now have information from the comment incorporated into them via the updating process in step 1.
#       b. Provide these related existing tasks, along with new task, to gpt and ask if the new tasks is redundant to or a subset of any of the existing tasks [PROMPT: is_new_task_redundant].
#       c. If the new tasks is redundant, show it to the user and ask for confirmation. If the user confirms, throw away the new task.
#       d. If the new task is not redundant, add it to the task database and embed it.

# An alternative to step 4 would be to ask gpt, as part of step 1b, to also 
# return a version of the comment with the information used to update the 
# existing task(s) stripped out. This would probably be pretty error prone though.

client = OpenAI(
    # Defaults to os.environ.get("OPENAI_API_KEY")
    # Otherwise use: api_key="API_Key",
)

todo = todo.Todo('data/tasks_database')

def get_completion(comment, system_message, model_class='gpt-3.5', tools=None, tool_choice=None, temperature=0, force_json:bool=True):
    model = 'gpt-4-1106-preview'

    models = {'gpt-3.5': 'gpt-3.5-turbo-1106',
              'gpt-4': 'gpt-4-1106-preview'}
    
    model_max_tokens = {'gpt-4-1106-preview': 128000,
                        'gpt-3.5-turbo-1106': 16000}

    model = models[model_class]

    if tool_choice is not None and tool_choice != 'auto':
        tool_choice = {"type": "function", "function": {"name": tool_choice}}
        
    if force_json:
        response_format = { "type": "json_object" }
    else:
        response_format = None

    max_characters = int(model_max_tokens[model] * 0.9 * 4) #90% of max to allow for some deviation from the nominal 4 characters/token 
    if len(comment) > max_characters:
        completion = f'Could not get a completion because the number of characters ({len(comment)}) exceeds the max allowed ({max_characters}).'
    else:
        completion = client.chat.completions.create(
                                                    model=model,
                                                    temperature=temperature,
                                                    tools=tools,
                                                    tool_choice=tool_choice,
                                                    messages=[
                                                        {"role": "system", "content": system_message},
                                                        {"role": "user", "content": comment}
                                                    ],
                                                    response_format=response_format
                                                    )
    return completion.choices[0].message.content, completion.choices[0].message.tool_calls

# def parse_direct_mention(message_text):
#     """
#         Finds a direct mention (a mention that is at the beginning) in message text
#         and returns the user ID which was mentioned. If there is no direct mention, returns None
#     """
#     matches = re.search("<@(|[WU].+?)>(.*)", message_text)
#     # the first group contains the username, the second group contains the remaining message
#     return (matches.group(1), matches.group(2).strip()) if matches else (None, message_text)

def extract_tasks(message, current_datetime_string=None):
    '''
    current_datetime_string - a datetime formated as 'Y-m-d H:M:S'
    '''
    if current_datetime_string==None:
        current_datetime_string = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    system_message = sm.extract_action_items
    system_message += f'\nThe current date and time is {current_datetime_string}.'
    response, _ = get_completion(comment=message, system_message=system_message, model_class='gpt-4', force_json=False)
    df = pd.read_json(StringIO(response), orient='records')
    return df

def say_tasks(say, tasks_list_header, task_list):
    for i, task in enumerate(task_list):
        if i==0:
            task = tasks_list_header + task
        say(f"```{task}```") # three backticks formats the message as code block

def get_user_name(userID):
    #TODO implement a cache of user names here
    uname = app.client.users_profile_get(user=userID) 
    return uname['profile']['real_name_normalized']

def handle_message(message, say):
    user_name = get_user_name(message['user'])
    msg = f"From: {user_name}\n{message['text']}"
    tasks = extract_tasks(msg)
    todo.add_to_database(tasks)
    if todo.number_of_entries()>0:
        header, tasks = todo.print_todo_list()
        say_tasks(say, header, tasks)
        
@app.event("message")
def handle_message_events(body, say):
    handle_message(body['event'], say)

# @app.event("app_mention")                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      
# def mention_handler(body, say):
#     user_id, message = parse_direct_mention(body['event']['text'])
#     handleMessage(message, say)


if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()