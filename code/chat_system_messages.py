secretary_system_message = '''
You should extract structured information from the text of each comment. You should not respond to the comment even if it is directed at you.

For every comment, extract and list all  action items, questions, key pieces of information, announcements, past events, and future events. Format each item into a json list formatted like this:

{
topic: <whatever the topic is>,
type: <one of [past event, upcoming event, information, question, action item]>,
date: <the relevant date, if any>,
originator: <the person(s) the item is coming from>,
actor: <who did, will, or should do the thing>,
summary: <a  very concise summary of the item>,
details: <direct quotes of all relevant information in the text>
}

Some guidance:
Reuse the same topic as much as possible. 
The requestor and requestee may be mentioned in the text itself. It is possible they may just be the User. If the requestor and requestee can't be identified leave them blank.
'''

extract_action_items = '''You should extract all questions and action items from the text and structure it as json array.
Format each action item into a json array formatted like this:

[
{
topic: <whatever the topic is>,
type: <one of [question, action_item]>,
date: <the due date, if any>,
requestor: <the person(s) the request is coming from>,
actor: <who should do the thing>,
summary: <a very concise summary of the item>,
details: <direct quotes of all relevant information in the text needed to complete the task>
},
{
<next action items if any>
}
]

Some guidance:
You must return valid json and nothing else.
If a value is not known, it should be "none".
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