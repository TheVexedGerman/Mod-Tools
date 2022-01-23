import datetime
import json
import os
import praw
import psycopg2
import re
import requests
import traceback
import youtube_dl

import new_stream_save as nss


def authenticate():
    print("Authenticating...")
    reddit = praw.Reddit(
        # 'thevexedgermanbot'
        'sachimod'
    )
    print("Authenticated as {}".format(reddit.user.me()))
    return reddit

def compile_regexes():
    # Rule 5 comment reporting
    regexes = []
    return [re.compile(p, flags=re.IGNORECASE | re.MULTILINE) for p in regexes]


def match_automod_removal_regexes(regexes, text):
    for regex in regexes:
        match = regex.search(text)
        if match:
            return True
    return False


def auto_approve_threshold_comments(comment, cursor):
    if len(comment.mod_reports) > 1:
        return
    if len(comment.user_reports) > 0:
        return
    if comment.mod_reports and comment.mod_reports[0][1] == "AutoModerator" and comment.mod_reports[0][0] == 'Comments require manual review':
        cursor.execute("SELECT sum(CASE WHEN approved = true THEN 1 ELSE 0 END), sum(CASE WHEN approved = false THEN 1 ELSE 0 END) FROM comment_removals WHERE author = %s AND ignore = false", (str(comment.author),))
        approved, removed = cursor.fetchone()
        if (isinstance(removed, int) and removed == 0) or not removed:
            if (isinstance(approved, int) and approved >= 0) or not approved:
                comment.mod.approve()
        elif isinstance(removed, int) and removed > 0:
            comment.report(f"{approved}/{removed} manually approved/removed so far")



def approve_and_report_if_normally_approved_commenter(comment, cursor, regexes):
    try:
        if comment.banned_by:
            pass
    except:
        return
    if comment.banned_by != 'AutoModerator':
        return
    if match_automod_removal_regexes(regexes, comment.body):
        return
    cursor.execute("SELECT sum(CASE WHEN approved = true THEN 1 ELSE 0 END), sum(CASE WHEN approved = false THEN 1 ELSE 0 END) FROM comment_removals WHERE author = %s", (str(comment.author),))
    approved, removed = cursor.fetchone()
    print(f"New comment from {comment.author} Approvals: {approved} Removals: {removed}")
    if removed == 0:
        # Auto approve and report after 5 approvals without any removals
        if approved > 3:
            comment.mod.approve()
            comment.report(f"Auto whitelist comment report: {approved} manual approved so far for user")
        # Auto approve after 50 approvals without any removals
        if approved > 20:
            comment.mod.approve()

def load_json():
    if not os.path.isfile("credentials.json"):
        json_obj = {}
    else:
        with open("credentials.json", "r") as f:
            json_obj = json.loads(f.read())
    return json_obj

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
    # regexes = compile_regexes()

    # for item in reddit.subreddit("Animemes").stream.comments():
    for item in reddit.subreddit("mod").mod.stream.modqueue():
        # actions if item is comment
        if item.name[:2] == 't1':
            cursor.execute("INSERT INTO comments (id, author, body, created_utc, name, parent_id, link_id, score) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING", (item.id, str(item.author), item.body, nss.convert_time(item.created_utc), item.name, item.parent_id, item.link_id, item.score))
            db.commit()
            cursor.execute("SELECT * FROM posts WHERE id = %s", (item.submission.id,))
            exists = cursor.fetchall()
            if not exists:
                try:
                    nss.insert_into_db_and_download(cursor, db, item.submission, reddit)
                except:
                    print(f"failed to insert submission {item.submission.id} from {item.id}")
                    print(traceback.format_exc())
            print(item.id)
            # approve_and_report_if_normally_approved_commenter(item, cursor, regexes)
            # auto_approve_threshold_comments(item, cursor)

            # nss.check_previous_sub_participation(item, cursor)
        # actions if item is post
        elif item.name[:2] == 't3':
            cursor.execute("SELECT * FROM posts WHERE id = %s", (item.id,))
            exists = cursor.fetchall()
            if not exists:
                try:
                    nss.insert_into_db_and_download(cursor, db, item, reddit)
                except:
                    print(f"failed to insert submission {item.id}")
                    print(traceback.format_exc())
            # nss.check_previous_sub_participation(item, cursor)
            print(item.id)

    cursor.close()
    db.close()

if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception as e:
            print(traceback.format_exc())
	# main()