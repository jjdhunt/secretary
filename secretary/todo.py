import os
from pathlib import Path
import pandas as pd
from tabulate import tabulate
import re
from io import StringIO
from dotenv import load_dotenv
from openai import OpenAI
import numpy as np
from typing import Optional, Union, List, Tuple

class Todo:

    df = None

    def __init__(self, database:str=None):
        '''
        database - a string to the database, a parquet file 
        '''

        self.database = database
        self.__load_database()

        # Create the openai client
        load_dotenv()
        # Defaults to os.environ.get("OPENAI_API_KEY"), otherwise use: api_key="API_Key",
        self.client = OpenAI()

    def save_database(self):
        if self.database is not None and self.df is not None:
            output_file_path = Path(self.database)
            output_file_path.parent.mkdir(parents=True, exist_ok=True)
            self.df.to_parquet(self.database)

    def __load_database(self):
        if self.database is not None and os.path.exists(self.database):
            self.df = pd.read_parquet(self.database)
        else:
            self.df = pd.DataFrame(columns=['status', 'tags', 'type', 'due date', 'requestor', 'actor', 'summary', 'notes', 'embedding'])

    def get_task_similarity(self, content):
        content_embedding = self.get_embedding(content)

        def dist(embedding):
            dot_product = np.dot(embedding, content_embedding)
            norm_vec1 = np.linalg.norm(embedding)
            norm_vec2 = np.linalg.norm(content_embedding)
            similarity = dot_product / (norm_vec1 * norm_vec2)
            return similarity
        
        similarity = self.df['embedding'].apply(dist)

        return similarity

    def get_similar_tasks(self, content, similarity_threshold):
        similarity = self.get_task_similarity(content)
        return self.df[similarity >= similarity_threshold]

    def get_similar_tasks_as_json(self, content, similarity_threshold):
        df = self.get_similar_tasks(content, similarity_threshold)
        df = df.drop(columns=['embedding'])
        return df.to_json(orient='index', indent=4)
    
    def get_embedding(self, content):
        response = self.client.embeddings.create(input = content, model="text-embedding-3-small")
        embedding = np.array(response.data[0].embedding)
        return embedding
    
    def __get_df_row_embedding(self,row):
        '''

        '''
        excluded_columns = ['status', 'embeddding']
        row = row.drop(excluded_columns, errors='ignore') # make sure to never reembbed an embedding, if there is one in the row
        json = row.to_json()
        return self.get_embedding(json)

    def add_new_task_to_database(self, tasks_df: pd.DataFrame) -> List[int]:
        """
        Given a dataframe of new tasks add them to the database and return a
        list of the indexes of the added tasks.
        """
        # embed new tasks
        tasks_df['embedding'] = tasks_df.apply(lambda x: self.__get_df_row_embedding(x), axis=1)
        tasks_df['status'] = 'incomplete'
        self.df = pd.concat([self.df, tasks_df], ignore_index=True)
        self.save_database()
        n_new_tasks = tasks_df.shape[0]
        return self.df.tail(n_new_tasks).index.values.tolist()

    def update_tasks_in_database(self, tasks_df: pd.DataFrame) -> List[int]:
        """
        Given a dataframe of tasks, replace the existing tasks with the same indexes.
        Return a list of the indexes of the updated tasks.
        """
        # embed new tasks
        tasks_df['embedding'] = tasks_df.apply(lambda x: self.__get_df_row_embedding(x), axis=1)
        self.df.loc[tasks_df.index] = tasks_df
        self.save_database()
        return tasks_df.index.values.tolist()

    def number_of_entries(self):
        return self.df.shape[0]

    def print_todo_list(self, task_indexes: Optional[Union[int, List[int]]] = None) -> Tuple[str, List[str]]:
        """
        Print the tasks as a text table.
        Optionally filter by task indexes.
        The table includes a header and rows for each task.

        Parameters
        ----------
        task_indexes : Optional[Union[int, List[int]]], optional
            Indexes of tasks to include in the printout. If None, all tasks are included.

        Returns
        -------
        Tuple[str, List[str]]
            A tuple containing two elements:
            - The table header as a string.
            - A list of strings, each representing a row in the table for a task.

        Notes
        -----
        - The 'embedding' column is always excluded from the output.
        - If `task_indexes` is provided, only the tasks corresponding to those indexes are included.
        """

        df_to_print = self.df.drop(columns=['embedding'], errors='ignore')
        if task_indexes is not None:
            df_to_print = df_to_print.iloc[task_indexes]
        header, tasks = print_df_as_text_table(df_to_print)
        return header, tasks
        
    # Were we to update the embedding on a selection of rows we could do:
    # df.loc[condition, :] = df.loc[condition, :].apply(apply_function, axis=1)

    # def _split_string_on_newline(s, n):
    #     lines = s.split('\n')
    #     chunks = []
    #     current_chunk = ""

    #     for line in lines:
    #         if len(current_chunk) + len(line) + 1 <= n:
    #             current_chunk += (line + '\n')
    #         else:
    #             if current_chunk:
    #                 chunks.append(current_chunk)
    #             current_chunk = line + '\n'

    #     if current_chunk:
    #         chunks.append(current_chunk)

    #     return chunks

def __split_table_into_rows(table_str):
    delimiters = ['├', '┤\n']
    pattern = "|".join(map(re.escape, delimiters))
    lines = re.split(pattern, table_str)
    header = lines[0] + '├' + lines[1] + '┤\n'
    return header, lines[2::2]

def print_df_as_text_table(df):
        '''
        Prints the df to a textual table format with one row per task.
        A header string and a list of task strings is returned. Printing the header
        followed by each entry in the task list will make a pretty table.
        '''
        database_str = tabulate(df, headers='keys', tablefmt='rounded_grid', maxcolwidths=40)
        header, tasks = __split_table_into_rows(database_str)
        return header, tasks

def to_boolean(value):
    if pd.isnull(value):
        return False  # Converts NaN values to False
    if str(value).lower() in ['True', 'true', '1', 'yes', 'completed', 'done',
                              '*True*', '*true*', '*1*', '*yes*', '*completed*', '*done*']:
        return True
    else:
        return False