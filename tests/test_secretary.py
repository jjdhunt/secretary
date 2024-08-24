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
    # Perform your test using the board_id
    assert board_id is not None
    # Other test logic here

def test_extracting_a_simple_task(test_board):

    message_content = "Silvia needs to buy eggs tomorrow by 11pm."
    message = "From: Jack\n" + message_content

    tasks = sb.extract_tasks_base(message)

    # gpt should capture the whole message contents as notes since it is short.
    assert tasks[0]['notes'] == message_content

    # # gpt should extract the due date.
    current_time = datetime.now(timezone.utc)
    time_plus_one_day = current_time + timedelta(days=1)
    formatted_time = time_plus_one_day.strftime("%Y-%m-%d") + ' 23:00:00 +0000'
    assert tasks[0]['due_date'] == formatted_time

    # gpt should extract the requestor
    assert tasks[0]['requestor'] == 'Jack'

    # gpt should extract the actor
    assert tasks[0]['actor'] == 'Silvia'


# def test_question_answering():
#     import sys
#     sys.path.append('../secretary')
#     from secretary import tasks
#     import secretary.secretary_slack_bot as sb

#     comment = 'From: Jack\nHow many "steves estate" tasks are open?'

#     todos = tasks.Todo('tests/data/tasks_database')
#     similar_tasks_json = todos.get_similar_tasks_as_json(comment, 0.3)
#     answer = sb.answer_questions_about_tasks(comment, similar_tasks_json, current_datetime_string="2024-02-11")
#     assert (
#         '6' in answer or
#         'six' in answer
#     )