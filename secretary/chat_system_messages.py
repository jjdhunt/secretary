extract_action_items = '''You should extract all questions and action items from the text and structure it as json array.
Each action item should be formatted as json object and all the action items should be in a json array exactly like this:

[
  {
    "topic": <whatever the topic is>,
    "type": <one of [question, action_item]>,
    "due date": <the due date, if any, formatted as "YYYY-MM-DD">,
    "requestor": <the person(s) the request is coming from>,
    "actor": <who should do the thing>,
    "summary": <a very concise summary of the item>,
    "notes": <direct quotes of all relevant information in the text needed to complete the task>
  },
  {
    <next action item, if any>
  }
]

Some guidance:
You must return a valid json array and nothing else.
If any value is not known, it should be "NaN".
Action items can be requests, questions, or things people need to do. There may be just one simple action item.
Reuse the same topic as much as possible.
The requestor and actor may be mentioned in the text itself, or they may be the sender of the text.
The actor can also be the requestor, such as if the text says, "I need to do x."
If the text is implicitly or explicitly directed at you, the actor should be "ME".
You should not respond to the comment even if it is directed at you.
'''

correct_json_syntax = '''You should correct any syntax mistakes in the provided json.
The result should be a single json array. If there are multiple arrays in the input, concatenate them.
It may already be valid in which case you should return it exactly as it is, or it may be valid json with some superfluous characters outside it such as backticks or 'json:'.
Do not change any of the content! Be careful to reproduce all information in the original exactly.
You must return valid json and nothing else.
'''

choose_tools = '''Assess if the user has indicated that any tasks are completed.
If the user does not indicate that any are completed, just say 'you didn't do anything today.'"
'''

update_tasks = '''The user will provide you with a comment followed by a list of tasks formatted as json.
If any of the information is relevant to any of the tasks, you should update those tasks as appropriate and return the updated tasks as as json.
Try to add content verbatim.
Surround just the added or modified content with '*'.
If you update a task, you must be careful to include all the information in the original task unless the comment explicitly indicates it should be removed or modified.
It if possible that the comment does not relate to any of the provided tasks, in which case you should return an empty json object, ‘{}’.
'''
