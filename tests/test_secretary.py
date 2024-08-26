from datetime import datetime, timedelta, timezone
import pytest
import sys

sys.path.append('../secretary')
from secretary.utils_trello import create_board, delete_board  # Import the functions
import secretary.secretary_slack_bot as sb
import secretary.tasks as tasks
tasks.BOARD_NAME = 'Test'

# Fixture to create and delete a board
@pytest.fixture
def test_board():
    # Setup: Create the board
    board_id = create_board('Test')
    
    # Provide the board_id to the test function
    yield board_id
    
    # Teardown: Delete the board
    delete_board(board_id)


def test_board_creation(test_board):
    board_id = test_board
    assert board_id is not None


def test_extracting_vauge_tasks(test_board):
    # Depending on the prompting, for short vague tasks, Secretary sometimes does not capture them and especially struggles with capturing the From: user info.
    message_content = "I need to make dinner soon"
    message = "From: Jack\n" + message_content
    current_user_local_time = "2024-08-20 17:00:00 +0000"
    tasks = sb.extract_tasks_base(message, current_user_local_time)

    assert tasks[0]['notes'] == message_content
    assert tasks[0]['requestor'] == 'Jack'
    assert tasks[0]['actor'] == 'Jack'
    assert tasks[0]['type'] == 'Action Items'

    message_content = "Need to buy shoes."
    message = "From: Jack\n" + message_content
    current_user_local_time = "2024-08-20 09:00:00 +0000"
    tasks = sb.extract_tasks_base(message, current_user_local_time)

    assert tasks[0]['notes'] == message_content
    assert tasks[0]['requestor'] == 'Jack'
    assert tasks[0]['actor'] == 'Jack'
    assert tasks[0]['type'] == 'Action Items'


def test_extracting_due_date(test_board):
    message_content = "Silvia needs to email Zurich and Jay the day after tomorrow by 11pm."
    message = "From: Jack\n" + message_content
    current_user_local_time = "2024-08-20 12:00:00 +0000"
    tasks = sb.extract_tasks_base(message, current_user_local_time)

    assert tasks[0]['notes'] == message_content
    assert tasks[0]['due_date'] == "2024-08-22 23:00:00 +0000"
    assert tasks[0]['requestor'] == 'Jack'
    assert tasks[0]['actor'] == 'Silvia'
    assert tasks[0]['type'] == 'Action Items'


def test_extracting_legalese_email(test_board):
    with open('legalese_email.txt', 'r') as file:
        text = file.read()

    message_content = text
    message = "From: Jack\n" + message_content
    current_user_local_time = "2024-08-20 12:00:00 +0000"
    tasks = sb.extract_tasks_base(message, current_user_local_time)

    # These are quotes relevant to each of the distinct tasks in the the legalese email that Secretary should identify
    task_notes = ['final 1040 income tax return',
                   'how much income and/or interest has been earned so far on the account proceeds',
                   'have you closed all the accounts and deposited the funds into the estate account',
                   'payment to Truist',
                   'contents have been removed']
    
    assert len(tasks) == len(task_notes)
    for task in tasks:
        assert task['actor'] == 'Jack'
        assert task['requestor'] in ['Susan Brode', 'Bob']
        assert any(substring in task['notes'] for substring in task_notes)


def test_processing_user_messages(test_board):
    # Starting with an empty board
    cards = tasks.get_tasks()
    assert len(cards) == 0

    # Test that Secretary extracts one task from a simple task message
    responses, tools_called = sb.handle_message('Jack', 'I should go shopping and buy some bacon and eggs today.')
    cards = tasks.get_tasks()
    assert responses['initial'] is None
    assert len(tools_called) == 1
    assert tools_called[0] == 'extract_tasks'
    assert len(cards) == 1
    assert responses['follow_up'] is None

    # Test that Secretary extracts one task from a slightly more complicated message
    responses, tools_called = sb.handle_message('Jack', "Silvia needs to finish her paper draft by the end of the month, or else she'll miss her submission deadline!")
    cards = tasks.get_tasks()
    assert responses['initial'] is None
    assert len(tools_called) == 1
    assert tools_called[0] == 'extract_tasks'
    assert len(cards) == 2
    assert responses['follow_up'] is None

    # Test answering a question by retrieving the task from the database
    tools_called = sb.handle_message('Jack', 'clear') # clear conversation history so Secretary has to look at the tasks, not the conversation
    assert len(sb.convo_global.messages) == 0
    responses, tools_called = sb.handle_message('Jack', 'What do I need to buy at the store?')
    assert responses['initial'] is not None
    assert 'bacon' in responses['initial'].lower()
    assert 'eggs' in responses['initial'].lower()
    assert len(tools_called) == 0
    assert responses['follow_up'] is None

    # Test calling the label tool
    responses, tools_called = sb.handle_message('Jack', "Please add the label 'brunch' to my shopping task")
    assert responses['initial'] is None
    assert len(tools_called) == 1
    assert tools_called[0] == 'add_label_to_task'

    # Test updating description the label tool
    responses, tools_called = sb.handle_message('Jack', "Please add cheese to my shopping")
    assert responses['initial'] is None
    assert len(tools_called) == 1
    assert tools_called[0] == 'update_task_description'

    # Test answering a question by retrieving the task from the database, and make sure that Secretary added cheese to the card as we just asked.
    tools_called = sb.handle_message('Jack', 'clear') # clear conversation history so Secretary has to look at the tasks, not the conversation
    assert len(sb.convo_global.messages) == 0
    responses, tools_called = sb.handle_message('Jack', 'What do I need to buy at the store?')
    assert responses['initial'] is not None
    assert 'bacon' in responses['initial'].lower()
    assert 'eggs' in responses['initial'].lower()
    assert 'cheese' in responses['initial'].lower()
    assert len(tools_called) == 0
    assert responses['follow_up'] is None

    # Test giving the Secretary information about a partial completion to which it should confirm completion and should not mark the task as complete
    tools_called = sb.handle_message('Jack', 'clear') # clear conversation history so Secretary has to look at the tasks, not the conversation
    assert len(sb.convo_global.messages) == 0
    responses, tools_called = sb.handle_message('Jack', "I bought eggs.")
    cards = tasks.get_tasks()
    assert responses['initial'] is not None
    assert len(tools_called) == 0
    assert len(cards) == 2

    # Test marking tasks as complete, in which case they should be removed from the board
    tools_called = sb.handle_message('Jack', 'clear') # clear conversation history so Secretary has to look at the tasks, not the conversation
    assert len(sb.convo_global.messages) == 0
    responses, tools_called = sb.handle_message('Jack', "I finished the grocery shopping!")
    cards = tasks.get_tasks()
    assert len(tools_called) == 1
    assert tools_called[0] == 'mark_task_completed'
    assert responses['initial'] is None
    assert len(cards) == 1

def test_task_creation_follow_up(test_board):
    # Starting with an empty board
    cards = tasks.get_tasks()
    assert len(cards) == 0

    # Test that Secretary extracts one task from a simple task message
    responses, tools_called = sb.handle_message('Bill', "Hello, Peter. Uh, could you give me those TPS reports ASAP? Mmmkay?")
    cards = tasks.get_tasks()
    assert responses['initial'] is None
    assert len(tools_called) == 1
    assert tools_called[0] == 'extract_tasks'
    assert len(cards) == 1
    assert 'Requestor: Bill' in cards[0]['desc']
    assert 'Actor: Peter' in cards[0]['desc']
    assert 'TPS reports' in cards[0]['desc']
    # Secretary should have followed up about the task to ask for a due date.
    # The follow up should have referred to the dateless task as LIST_OF_TASKS on its own line, something like
    # "I could not figure out due dates for\nLIST_OF_TASKS\nCould you give me a suggestion?"
    assert '\nLIST_OF_TASKS\n' in responses['follow_up']