import datetime
import json
import os
import praw
import psycopg2
import requests
import traceback
import youtube_dl

import new_stream_save as nss


def authenticate():
    print("Authenticating...")
    reddit = praw.Reddit(
        'thevexedgermanbot'
        # 'sachimod'
    )
    print("Authenticated as {}".format(reddit.user.me()))
    return reddit

def load_json():
    if not os.path.isfile("credentials.json"):
        json_obj = {}
    else:
        with open("credentials.json", "r") as f:
            json_obj = json.loads(f.read())
    return json_obj

def assign_team(comment, cursor, db_conn):
    if comment.parent_id not in ['t3_x6nzyf', 't1_in7uew2']:
        return
    if 'sachi' in comment.body.lower():
        team = "Sachi"
    elif 'snek' in comment.body.lower() or 'snake' in comment.body.lower():
        team = "Snake"
    else:
        return
    cursor.execute("SELECT team FROM user_teams WHERE author = %s", (str(comment.author),))
    exists = cursor.fetchone()
    if exists:
        return
    cursor.execute("INSERT INTO user_teams (author, team) VALUES (%s, %s)", (str(comment.author), team))
    db_conn.commit()
    comment.reply(f"You've been added to Team {team}")

def main():
    creds = load_json()
    reddit = authenticate()
    db = psycopg2.connect(
        host = creds['db_host'],
        database = creds['db_database'],
        user = creds['db_user'],
        password = creds['db_password']
    )
    cursor = db.cursor()

    for comment in reddit.subreddit("Animemes").stream.comments():
        cursor.execute("INSERT INTO comments (id, author, body, created_utc, name, parent_id, link_id, score) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING", (comment.id, str(comment.author), comment.body, nss.convert_time(comment.created_utc), comment.name, comment.parent_id, comment.link_id, comment.score))
        db.commit()
        cursor.execute("SELECT * FROM posts WHERE id = %s", (comment.submission.id,))
        exists = cursor.fetchall()
        if not exists:
            try:
                nss.insert_into_db_and_download(cursor, db, comment.submission, reddit)
            except:
                print(f"failed to insert submission {comment.submission.id} from {comment.id}")
                print(traceback.format_exc())
        print(comment.id)
        # nss.check_previous_sub_participation(comment, cursor)
        assign_team(comment, cursor, db)

    cursor.close()
    db.close()

if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception as e:
            pass
	# main()