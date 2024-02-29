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
from typing import List, Optional

import sys
sys.path.append('../secretary')

import secretary.system_messages as sm
import secretary.chat_tools as ct
import secretary.todo as todo

load_dotenv()

# https://github.com/slackapi/bolt-python#creating-an-app
SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
SLACK_APP_TOKEN = os.environ['SLACK_APP_TOKEN']
app = App(token=SLACK_BOT_TOKEN)

similar_task_threshold = 0.3 # a bit of ad-hoc testing showed about 0.2 is a good threshold

# Interaction flow:
# 0. Retrieve related existing tasks that are semantically similar (TODO: and keyword search) to comment.
# 1. TODO: Answer questions about existing tasks.
#       a. Provide related existing tasks and ask gpt to answer any questions in the comment about them [PROMPT: answer_task_questions].
#       b. Send any answers to the user.
# 2. Use the whole comment to update retrieved tasks.
#       a. Provide related existing tasks in json format to gpt along with new user comment and ask it to update the task(s) based on the comment [PROMPT: update_tasks].
#       b. TODO: Provide the original and updated task(s) to user for confirmation of update.
#       c. TODO: If user confirms, replace old task(s) with updated task(s) and reembed the updated task(s).
# 3. Extract tasks from comment [PROMPT: extract_action_items].
# 4. TODO: Iterate over new tasks for the secretary.
#       a. First ask gpt to select a tool [PROMPT: select_secretary_task_tool].
#          Secretary tools: show_tasks([all, open, closed, for_actor, from_requestor, due_by(date)]),
#       b. Execute specified tools.
#       c. If no tool is identified for the secretary task, report to the user 'Sorry, I don't know how to do that.'

# We won't do step 5 now. For now we will assume we do only step 2 or 3 but not both of them.
# 5. TODO: Iterate over new non-secretary tasks.
#       a. For each task, find semantically similar existing tasks. These should now have information from the comment incorporated into them via the updating process in step 1.
#       b. Provide these related existing tasks, along with new task, to gpt and ask if the new tasks is redundant to or a subset of any of the existing tasks [PROMPT: is_new_task_redundant].
#       c. If the new tasks is redundant, show it to the user and ask for confirmation. If the user confirms, throw away the new task.
#       d. If the new task is not redundant, add it to the task database and embed it.

client = OpenAI(
    # Defaults to os.environ.get("OPENAI_API_KEY")
    # Otherwise use: api_key="API_Key",
)

todos = todo.Todo('data/tasks_database')

def get_completion(comment, system_message, model_class='gpt-3.5', tools=None, tool_choice=None, temperature=0, force_json:bool=False):

    models = {'gpt-3.5': 'gpt-3.5-turbo-1106',
              'gpt-4': 'gpt-4-1106-preview'}
    
    model_max_tokens = {'gpt-3.5-turbo-1106': 16000,
                        'gpt-4-1106-preview': 128000
                       }

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

# def parse_direct_mention(message_text):
#     """
#         Finds a direct mention (a mention that is at the beginning) in message text
#         and returns the user ID which was mentioned. If there is no direct mention, returns None
#     """
#     matches = re.search("<@(|[WU].+?)>(.*)", message_text)
#     # the first group contains the username, the second group contains the remaining message
#     return (matches.group(1), matches.group(2).strip()) if matches else (None, message_text)

def extract_tasks(message, current_datetime_string=None) -> pd.DataFrame:
    '''
    current_datetime_string - a datetime formated as 'Y-m-d'
    '''
    if current_datetime_string==None:
        current_datetime_string = datetime.now().strftime('%Y-%m-%d')
    system_message = sm.extract_action_items
    system_message += f'\nThe current date and time is {current_datetime_string}.\n'
    response, _ = get_completion(comment=message, system_message=system_message, model_class='gpt-4')
    df = pd.read_json(StringIO(_clean_response_json(response)), orient='records')
    return df

def update_tasks(message, tasks_json, current_datetime_string=None) -> pd.DataFrame:
    '''
    current_datetime_string - a datetime formated as 'Y-m-d H:M:S'
    '''
    if current_datetime_string==None:
        current_datetime_string = datetime.now().strftime('%Y-%m-%d')
    system_message = sm.update_tasks
    system_message += f'\nThe current date and time is {current_datetime_string}.\n'
    content = f'Tasks:\n{tasks_json}\nComment:\n{message}'
    response, _ = get_completion(comment=content, system_message=system_message, model_class='gpt-4')
    df = pd.read_json(StringIO(_clean_response_json(response)), orient='index')
    return df

def answer_questions_about_tasks(message, tasks_json, current_datetime_string=None) -> str:
    '''
    current_datetime_string - a datetime formated as 'Y-m-d H:M:S'
    '''
    if current_datetime_string==None:
        current_datetime_string = datetime.now().strftime('%Y-%m-%d')
    system_message = sm.answer_task_questions
    system_message += f'\nThe current date and time is {current_datetime_string}.'
    content = f'Tasks:\n{tasks_json}\nComment:\n{message}'
    response, _ = get_completion(comment=content, system_message=system_message, model_class='gpt-4')
    return response

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

    say("I hear you, let me think...")

    user_name = get_user_name(message['user'])
    msg = f"From: {user_name}\n{message['text']}"

    # Find related existing tasks
    similar_tasks_json = todos.get_similar_tasks_as_json(msg, similar_task_threshold)

    # Answer questions about tasks
    answer = answer_questions_about_tasks(msg, similar_tasks_json)
    if answer not in {'""', ''}:
        say(answer)
        return
    
    # Ask gpt to updated related existing tasks based on the message
    say("Let me see if there are any existing tasks I should update...")
    updated_tasks_df = update_tasks(msg, similar_tasks_json)
    if updated_tasks_df.shape[0]>0:
        # TODO: ask user for confirmation before updating
        updated_tasks_indexes = updated_tasks_df.index.values.tolist()
        updated_tasks_str = ', '.join([str(i) for i in updated_tasks_indexes])
        if len(updated_tasks_indexes)==1: say(f"I updated existing task {updated_tasks_str}:")
        else: say(f"I updated existing tasks {updated_tasks_str}:")
        for idx in updated_tasks_indexes:
            df_old = todos.df.drop(columns=['embedding'], errors='ignore').loc[idx]
            print(df_old)
            df_new = updated_tasks_df.loc[idx]
            print(df_new)
            task_update_pair = pd.concat([df_old, df_new], axis=1).T
            task_update_pair.reset_index(drop=True, inplace=True)
            print(task_update_pair)
            header, tasks = todo.print_df_as_text_table(task_update_pair)
            say_tasks(say, header, tasks)
        # updated_tasks_indexes = todos.update_tasks_in_database(updated_tasks_df)
        # updated_tasks_str = ', '.join([str(i) for i in updated_tasks_indexes])
        # if len(updated_tasks_indexes)==1: say(f"I updated existing task {updated_tasks_str}")
        # else: say(f"I updated existing tasks {updated_tasks_str}")
        # header, tasks = todos.print_todo_list(task_indexes=updated_tasks_indexes)
        # say_tasks(say, header, tasks)
        return
        
    # Find new tasks in the message
    say("I don't see any relevant existing tasks, let me see if you mentioned any new ones...")
    new_tasks = extract_tasks(msg)
    if new_tasks.shape[0]>0:
        if new_tasks.shape[0]==1: say("I identified this new task:")
        else: say("I identified these new tasks:")
        new_tasks_indexes = todos.add_new_task_to_database(new_tasks)
        if todos.number_of_entries()>0:
            # TODO: determine if user is on mobile and send task tables as images. Or otherwise make tables nice and more adaptive to display.
            header, tasks = todos.print_todo_list(task_indexes=new_tasks_indexes)
            say_tasks(say, header, tasks)
    else:
        say("Nope, I don't see any.")
    
    say("OK, I'm gonna go mine some bitcoins, let me know if you need anything.")
        
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