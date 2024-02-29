extract_action_items = '''You should extract all questions and action items from the text and structure them as a json array.
Each action item should be formatted as json object and all the action items should be in a json array exactly like this:

[
  {
    "tags": <a list of topic(s)>,
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
Reuse the same tags as much as possible.
The requestor and actor may be mentioned in the text itself, or they may be the sender of the text.
The actor can also be the requestor, such as if the text says, "I need to do x."
If the text is implicitly or explicitly directed at you, the actor should be "ME".
You should not respond to the comment even if it is directed at you.
Be careful to capture any and all action items.
Action items can be requests, questions, or things people need to do.
There may be just one simple action item in the message.
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

update_tasks = '''The user will provide you with a list of tasks formatted as json, and then a comment.
If any of the information in the comment is relevant to any of the tasks, you should update those tasks as appropriate and return the updated tasks as as json.
Only update tasks if they are very relevant. If you are not sure, just return an empty json object, '{}'.
If you update a task, you MUST be VERY CAREFUL to include all the information in the original task unless the comment EXPLICITLY indicates it should be removed or modified.
Valid "status" values are [incomplete, complete]. 
Surround just the added or modified content with '*'.
IF NO TASK CONTENT NEEDS TO BE UPDATED, RETURN ONLY AN EMPTY json object, '{}'.
'''

# update_tasks = "no matter what, always just return an empty json object, '{}'."

answer_task_questions = '''The user will provide you with a list of tasks formatted as json, and then a comment.
ONLY if the comment has questions DIRECTED at YOU that can be answered based on the content in the tasks, answer them.
If there are no questions DIRECTED at YOU in the comment, respond with only "".
'''
# If the comment has questions directed at you that can not be answered based on the content in the tasks, do NOT answer them. Just Reply with, "Sorry I cannot answer your question about X."
# '''