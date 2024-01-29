from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import os
from dotenv import load_dotenv
# import re
from openai import OpenAI
import chat_system_messages as sm
import chat_tools as ct
import pandas as pd
from tabulate import tabulate
import re

load_dotenv()

# https://github.com/slackapi/bolt-python#creating-an-app
SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
SLACK_APP_TOKEN = os.environ['SLACK_APP_TOKEN']
app = App(token=SLACK_BOT_TOKEN)

client = OpenAI(
    # Defaults to os.environ.get("OPENAI_API_KEY")
    # Otherwise use: api_key="Your_API_Key",
)

database = pd.DataFrame(columns=['topic', 'type', 'date', 'requestor', 'actor', 'summary', 'details'])

def get_completion(comment, system_message, model_class='gpt-3.5', tools=None, tool_choice=None, temperature=0):
    model = 'gpt-4-1106-preview'

    models = {'gpt-3.5': 'gpt-3.5-turbo-1106',
              'gpt-4': 'gpt-4-1106-preview'}
    
    model_max_tokens = {'gpt-4-1106-preview': 128000,
                        'gpt-3.5-turbo-1106': 16000}

    model = models[model_class]

    if tool_choice is not None and tool_choice != 'auto':
        tool_choice = {"type": "function", "function": {"name": tool_choice}}
        
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
                                                    ]
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

def update_database(json_string):
    global database
    df = pd.read_json(json_string, orient='records')
    database = pd.concat([database, df], ignore_index=True)

def split_string_on_newline(s, n):
    lines = s.split('\n')
    chunks = []
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 <= n:
            current_chunk += (line + '\n')
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line + '\n'

    if current_chunk:
        chunks.append(current_chunk)

    return chunks

def split_table_into_rows(table_str):
    delimiters = ['├', '┤\n']
    pattern = "|".join(map(re.escape, delimiters))
    lines = re.split(pattern, table_str)
    header = lines[0] + '├' + lines[1] + '┤\n'
    return header, lines[2::2]

def handle_message(message, say):
    action = message['text'].strip().lower()
    if action == 'summarize':
        summary = "TODO: handle action"
        say(summary)
    else:
        user_name = get_user_name(message['user'])
        msg = f"From: {user_name}\n{message['text']}"
        response, _ = get_completion(comment=msg, system_message=sm.extract_action_items, model_class='gpt-4')
        response, _ = get_completion(response, system_message=sm.correct_json_syntax, model_class='gpt-3.5')
        update_database(response)
        global database
        if database.shape[0]>0:
            database_str = tabulate(database, headers='keys', tablefmt='rounded_grid', maxcolwidths=50)
            header, rows = split_table_into_rows(database_str)
            for i, row in enumerate(rows):
                if i==0:
                    row = header + row
                say(f"```{row}```") # three backticks formats the message as code block

def get_user_name(userID):
    #TODO implement a cache of user names here
    uname = app.client.users_profile_get(user=userID) 
    return uname['profile']['real_name_normalized']
        
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