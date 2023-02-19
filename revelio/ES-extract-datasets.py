#!/usr/bin/env python
# coding: utf-8

# Extract Datasets from ElasticSearch endpoint with GrimoireLab data

# Import the corresponding Python modules:

import unittest
import json
import time

import pandas as pd

import urllib3
urllib3.disable_warnings()

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, A
from dateutil.relativedelta import relativedelta


# ElasticSearch endpoint URL and index (or alias) where the data is stored

client = Elasticsearch(["http://127.0.0.1:9200"])

GIT_INDEX = "git"

# ## Extraction of author information
# 
# The query is asking for the following information:
# 
# * Per author:
#   * Get is SortingHat's unique identifier, `author_uuid`.
#   * Get the boolean value of marked as bot, `author_bot`. 
# * Get the following metrics: 
#     * Number of contributions (Git commits or GitHub Issues, Pull Requests and comments)

# Git

def years_to_ranges(date_start, date_end, years_back_limit):
    # Date format='%Y-%m-%dT%H:%M%:%S.%fZ', example 2019-02-12T21:29:34.000Z
    # Date_end - Date_start < 1 year?
    if date_start:
        dt_start = pd.to_datetime(date_start, infer_datetime_format=True) 
    if date_end:
        dt_end = pd.to_datetime(date_end, infer_datetime_format=True) 
    
    date_ranges = []
    dt_aux = dt_end
    while (pd.Timedelta(dt_aux - dt_start).days > 365):
        new_dt_start = dt_aux - relativedelta(years=1)
        date_ranges.append((new_dt_start, dt_aux))
        dt_aux = new_dt_start
    date_ranges.append((dt_start, dt_aux))

    return date_ranges


def years_to_month_ranges(date_start, date_end):
    # Date format='%Y-%m-%dT%H:%M%:%S.%fZ', example 2019-02-12T21:29:34.000Z
    if date_start:
        dt_start = pd.to_datetime(date_start, infer_datetime_format=True) 
    if date_end:
        dt_end = pd.to_datetime(date_end, infer_datetime_format=True) 
    
    date_ranges = []
    dt_aux = dt_end
    while (pd.Timedelta(dt_aux - dt_start).days > 30):
        new_dt_start = dt_aux - relativedelta(days=30)
        date_ranges.append((new_dt_start, dt_aux))
        dt_aux = new_dt_start
    date_ranges.append((dt_start, dt_aux))

    return date_ranges


date_ranges = years_to_month_ranges('2008-01-01', '2021-09-15')
for date_range in date_ranges:
    print(date_range)

start_time = time.time()
print(start_time)

all_results = []
for date_range in date_ranges:
    s = Search(using=client, index=GIT_INDEX)\
            .filter('range', grimoire_creation_date={'gte': date_range[0], 'lt': date_range[1]})
    author_uuid = A('terms', field='author_uuid.keyword')
    author_bot = A('terms', field='author_bot')
    author_aggs = [
        {'by_author_uuid': author_uuid},
        {'by_author_bot': author_bot}
    ]
    s.aggs.metric('num_commits', 'cardinality', field='hash.keyword')\
          .bucket('by_author', "composite", sources=author_aggs, size=50000)

    s.extra(track_total_hits=True)
    
    result = s.execute()
    result = result.to_dict()["aggregations"]
    query_results = result['by_author']['buckets']
    print("Number of results: ", len(query_results))
    
    all_results.append(query_results)


# Unroll the JSON results for each of the hits and convert it into a Dataframe


clean_results = {}
for query_results in all_results:
    for item in query_results:
        author_uuid = str(item['key']['by_author_uuid'])
        author_bot = item['key']['by_author_bot']
        doc_count = item['doc_count']

        try: 
            author_data = clean_results[author_uuid]
            author_data['doc_count'] += doc_count 
        except KeyError:
            author_data = {}
            author_data['author_uuid'] = author_uuid
            author_data['author_bot'] = author_bot
            author_data['doc_count'] = doc_count

        clean_results[author_uuid] = author_data


# To get a fully clean Dataframe, make sure all the column types match with the ones they should have. To make the information more legible, some columns are renamed:


df_results = pd.DataFrame.from_dict(clean_results, orient='index').reset_index(drop=True)

df_results.astype({'author_uuid': str, 'author_bot': bool})


# ### Export initial user Dataframe from Git data



export_df = False
df_export_path = 'datasets'

if export_df:
    df_results.to_csv('{}/df_git_authors.csv'.format(df_export_path), index=False, header=True)


# ## Extraction of Git data
# 
# For each contributor's unique identifier (`author_uuid`), we are retrieving the following information from each of its commits:
# * Number of files modifies
# * Number of lines added
# * Number of lines removed
# * UTC date of the commit
# * Repository the commit was submitted to
# * Commit message
# * Committer name
# * Commit hash (unique identifier)


def get_value_or_default(field_name, result):
    result_value = None
    if result[field_name]:
        result_value = result[field_name]
        
    return result_value


list_identities = set(df_results['author_uuid'])

bot_map = {'true': True, 'false': False}

git_author_uuid = A('terms', field='author_uuid.keyword')
git_hash = A('terms', field='hash.keyword')
git_files = A('terms', field='files')
git_lines_added = A('terms', field='lines_added')
git_lines_removed = A('terms', field='lines_removed')
git_utc_commit = A('terms', field='utc_commit')
git_grimoire_creation_date = A('terms', field='grimoire_creation_date')
git_commit_date_weekday = A('terms', field='commit_date_weekday')
git_message = A('terms', field='message.keyword')
git_commit_name = A('terms', field='Commit_name.keyword')
git_commit_uuid = A('terms', field='Commit_uuid.keyword')
git_repo_name = A('terms', field='repo_name.keyword')
git_author_name = A('terms', field='author_name.keyword')
git_author_bot = A('terms', field='author_bot')
git_author_date = A('terms', field='author_date')
git_time_to_commit_hours = A('terms', field='time_to_commit_hours')
git_aggs = [
    {'author_uuid': git_author_uuid},
    {'hash': git_hash},
    {'files': git_files}, 
    {'lines_added': git_lines_added},
    {'lines_removed': git_lines_removed},
    {'utc_commit': git_utc_commit},
    {'grimoire_creation_date': git_grimoire_creation_date},
    {'commit_date_weekday': git_commit_date_weekday},
    {'message': git_message},
    {'commit_name': git_commit_name},
    {'commit_uuid': git_commit_uuid},
    {'repo_name': git_repo_name},
    {'author_name': git_author_name},
    {'author_bot': git_author_bot},
    {'author_date': git_author_date},
    {'time_to_commit_hours': git_time_to_commit_hours},
]

for cur_author_uuid in list_identities:
    git_data = []
    print('Executing the queries for the author ', cur_author_uuid)
    for date_range in date_ranges:
        print('\tExecuting the queries for the range: ', date_range[0], '-', date_range[1])

        filter_author_uuid = {'author_uuid.keyword': cur_author_uuid}

        s_git = Search(using=client, index=GIT_INDEX)\
                      .filter('range', grimoire_creation_date={'gte': date_range[0], 'lt': date_range[1]})\
                      .filter('term', **filter_author_uuid)
        s_git.aggs.metric('num_commits', 'cardinality', field='hash.keyword')\
                  .bucket('commits', "composite", sources=git_aggs, size=10000)

        s_git.extra(track_total_hits=True)
        response = s_git.execute()
        response = response.to_dict()["aggregations"]
        query_results = response['commits']['buckets']
        for result in query_results:
            clean_result = {}
            result = result['key']
            clean_result['git__hash'] = str(result['hash'])
            clean_result['git__lines_added'] = result['lines_added']
            clean_result['git__lines_removed'] = result['lines_removed']
            clean_result['git__files'] = result['files']
            
            # Get the key_as_string attribute from this result
            clean_result['git__utc_commit'] = result['utc_commit']
            clean_result['git__grimoire_creation_date'] = result['grimoire_creation_date']
            clean_result['git__commit_date_weekday'] = result['commit_date_weekday']
            clean_result['git__commit_name'] = get_value_or_default('commit_name', result)
            clean_result['git__commit_uuid'] = get_value_or_default('commit_uuid', result)
            clean_result['git__message'] = get_value_or_default('message', result)
            clean_result['git__time_to_commit_hours'] = result['time_to_commit_hours']
            clean_result['git__repo_name'] = result['repo_name']
            clean_result['author_uuid'] = result['author_uuid']
            clean_result['author_bot'] = result['author_bot']
            clean_result['author_name'] = get_value_or_default('author_name', result)
            clean_result['author_date'] = result['author_date']

            git_data.append(clean_result)

    export_json = True
    if export_json:
        file_path = './data'
        file_name = '{}/git_data_{}.json'.format(file_path, cur_author_uuid)
        with open(file_name, 'w') as ofile:
            json.dump(git_data, ofile, indent=4)
        print('Exported data from {}'.format(cur_author_uuid))

print("--- {} seconds ---".format(time.time() - start_time))
print('Done')

