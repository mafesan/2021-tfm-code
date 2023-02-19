#!/usr/bin/env python
# coding: utf-8

# Building the classifier's input

import json
import os
import time

import numpy as np
import pandas as pd


import urllib3
urllib3.disable_warnings()


# ## Custom methods
def git_message_is_signed(x):
    return 'Signed-off-by:' in x


def message_words_len(x):
    return len(x.split())


def is_weekend(x):
    # x is an integer
    # Weekday from 1 to 7, 6 and 7 are weekend days
    is_weekend = x >= 6
    return is_weekend


def get_ratio(num_partial, num_total):
    ratio = num_partial / num_total
    return ratio


def load_json(json_path):
    with open(json_path, 'r') as jfile:
        return json.load(jfile)


def interquartile_range(x):
    iqr = x.quantile(0.75) - x.quantile(0.25)
    return iqr


start_time = time.time()
print(start_time)

# Load initial data
df_path = './data'
git_data_files = os.listdir(df_path)

# Building the Git Dataframe

# Load Git data from ES from a JSON file
df_git = pd.DataFrame()

for json_file in git_data_files:
    print('Loading file {}'.format(json_file))
    json_to_load = '{}/{}'.format(df_path, json_file)
    author_git_data = load_json(json_to_load)
    if not author_git_data:
        print('\tSkipping empty file {}'.format(json_file))
        continue

    df_git_author = pd.DataFrame(author_git_data)
    num_commits = df_git_author['git__hash'].count()

    if num_commits < 10:
        print('\tSkipping author with less than 10 commits {}'.format(json_file))
        continue

    df_git_author["git__utc_commit"] = pd.to_datetime(df_git_author['git__utc_commit'], infer_datetime_format=True)
    df_git_author = df_git_author.astype({"git__message": str})

    df_git_author["is_merge_commit"] = df_git_author['git__files'] == 0
    df_git_author["len_commit_message"] = df_git_author["git__message"].apply(lambda x: len(x))
    df_git_author["len_words_commit_message"] = df_git_author["git__message"].apply(lambda x: message_words_len(x))
    df_git_author["is_commit_signed"] = df_git_author["git__message"].apply(lambda x: git_message_is_signed(x))
    df_git_author["is_weekend_commit"] = df_git_author["git__commit_date_weekday"].apply(lambda x: is_weekend(x))

# Group data by author_uuid

    df_git_commits = {}
    df_git_commits['git__num_merge_commits'] = df_git_author['is_merge_commit'].sum()
    df_git_commits['git__num_weekend_commits'] = df_git_author['is_weekend_commit'].sum()
    df_git_commits['git__num_signed_commits'] = df_git_author['is_commit_signed'].sum()
    df_git_commits['git__num_commits'] = df_git_author['git__hash'].nunique()

    df_git_commits['git__num_repos'] = df_git_author['git__repo_name'].nunique()

    df_git_commits['git__ratio_merge_commits'] = get_ratio(df_git_commits['git__num_merge_commits'],
                                                           df_git_commits['git__num_commits'])
    df_git_commits['git__ratio_weekend_commits'] = get_ratio(df_git_commits['git__num_weekend_commits'],
                                                             df_git_commits['git__num_commits'])
    df_git_commits['git__ratio_signed_commits'] = get_ratio(df_git_commits['git__num_signed_commits'], 
                                                            df_git_commits['git__num_commits'])

    df_git_commits['git__median_files'] = df_git_author['git__files'].median()
    df_git_commits['git__iqr_files'] = interquantile_range(df_git_author['git__files'])

    df_git_commits['git__median_lines_added'] = df_git_author['git__lines_added'].median()
    df_git_commits['git__iqr_lines_added'] = interquantile_range(df_git_author['git__lines_added'])

    df_git_commits['git__median_lines_removed'] = df_git_author[['git__lines_removed']].median()
    df_git_commits['git__iqr_lines_removed'] = interquantile_range(df_git_author['git__lines_removed'])

    df_git_commits['git__median_len_commit_message'] = df_git_author['len_commit_message'].median()
    df_git_commits['git__iqr_len_commit_message'] = interquantile_range(df_git_author['len_commit_message'])

    df_git_commits['git__median_len_words_commit_message'] = df_git_author['len_words_commit_message'].median()
    df_git_commits['git__iqr_len_words_commit_message'] = interquantile_range(df_git_author['len_words_commit_message'])

    df_git_commits['author_uuid'] = df_git_author['author_uuid'][0]
    df_git_commits['author_name'] = df_git_author['author_name'][0]
    df_git_commits['author_bot'] = df_git_author['author_bot'][0]

    df_aux = pd.DataFrame.from_dict(df_git_commits, orient='columns')
    df_git = df_git.append(df_aux, ignore_index=True)


# Export DF to JSON

print("Exporting file...")

export_path = './datasets'
df_git.to_json('{}/df_git.json'.format(export_path), orient='records', lines=True)

print("--- {} seconds ---".format(time.time() - start_time))
print('Done')
