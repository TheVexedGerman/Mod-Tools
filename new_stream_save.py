import json
import uuid
import requests
import praw
import psycopg2
import datetime
import youtube_dl
import numpy as np
import cv2 as cv
from bs4 import BeautifulSoup
import os
import traceback


def authenticate():
    print("Authenticating...")
    reddit = praw.Reddit(
        'sachimod'
    )
    print("Authenticated as {}".format(reddit.user.me()))
    return reddit

def hash(image):
    if image is None:
        return None
    image = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    resized = cv.resize(image, (9, 8))
    if np.all(resized == resized[0,0]):
        return None
    diff = resized[:, 1:] > resized [:, :-1]
    # the hash is returned as an array of 64 bits
    return diff.astype(int).flatten()

def get_opencv_img_from_buffer(buffer):
    if buffer[:3] == b'GIF':
        name = str(uuid.uuid4())
        open(f"/tmp/{name}.gif", 'wb').write(buffer)
        cap = cv.VideoCapture(f"/tmp/{name}.gif")
        os.remove(f"/tmp/{name}.gif")
        ret, image = cap.read()
        cap.release()
        if ret:
            return image
    bytes_as_np_array = np.frombuffer(buffer, dtype=np.uint8)
    return cv.imdecode(bytes_as_np_array, cv.IMREAD_COLOR)

def convert_time(time):
    if time:
        return datetime.datetime.utcfromtimestamp(time)
    return None

def get_old_ids(cursor):
    cursor.execute("select id from posts ORDER BY created_utc desc limit 200")
    already_scanned = cursor.fetchall()
    id_set = set()
    for entry in already_scanned:
        id_set.update(entry)
    return id_set


def download_vreddit(submission):
    ensure_path_validity(submission.id)
    download_path = f"images/{submission.id[:3]}/{submission.id}.mp4"
    download(submission.url, download_path)


def download(download_url, download_path):
    RATELIMIT = 2000000
    MAX_FILESIZE = 262144000
    try:
        ydl_opts = {
            'outtmpl': download_path,
            # 'format': 'bestvideo',        #uncomment for video without audio only, see youtube-dl documentation
            'max_filesize': MAX_FILESIZE,
            'ratelimit': RATELIMIT,
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([download_url])
        return download_path

    except Exception as e:
        print('ERROR: Downloading failed.')
        print(e)
        return ""

def ensure_path_validity(submission_id):
    if not os.path.exists(f"images/{submission_id[:3]}"):
        os.mkdir(f"images/{submission_id[:3]}")

def imgur_to_direct_link(image_url):
	imgur = requests.get(image_url)
	soup = BeautifulSoup(imgur.text, features="html.parser")
	try:
		direct_link = soup.find('link', rel="image_src").get('href')
	except:
		direct_link = ''
	return direct_link

def check_previous_participation(submission):
    for item in submission.author.new(limit=100):
        bad_subs_list = ['NuxTaku', 'lostpause']
        if item.subreddit.name in bad_subs_list:
            submission.mod.remove()
            return

def check_previous_sub_participation(submission, cursor):
    cursor.execute("SELECT count(*) FROM posts WHERE author = %s AND created_utc < '2020-08-03'", (submission.author.name,))
    previous_participation = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM comments WHERE author = %s AND created_utc < '2020-08-03'", (submission.author.name,))
    previous_participation += cursor.fetchone()[0]
    if previous_participation > 0:
        return True
    else:
        submission.mod.remove()
        return False


def insert_into_db_and_download(cursor, db, submission, reddit):
    cursor.execute("insert into posts (author, created_utc, distinguished, edited, id, is_self, link_flair_text, locked, name, num_comments, over_18, score, selftext, spoiler, stickied, subreddit, title, url, permalink) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING", (submission.author.name, convert_time(submission.created_utc), submission.distinguished, convert_time(submission.edited), submission.id, submission.is_self, submission.link_flair_text, submission.locked, submission.name, submission.num_comments, submission.over_18, submission.score, submission.selftext, submission.spoiler, submission.stickied, submission.subreddit.display_name, submission.title, submission.url, submission.permalink))
    db.commit()
    if not submission.is_self:
        image = None
        if (submission.url[-3:] == 'png' or submission.url[-3:] == 'jpg' or submission.url[-3:] == 'gif'):
            ensure_path_validity(submission.id)
            image = requests.get(submission.url)
            open(f"images/{submission.id[:3]}/{submission.id}.{submission.url[-3:]}", 'wb').write(image.content)
        elif submission.url[8:17] == 'v.redd.it':
            download_vreddit(submission)
            image = requests.get(submission.preview['images'][0]['source']['url'])
        elif (submission.url[8:14] == 'imgur.' and submission.url[17:20] == '/a/') or (submission.url[8:16] == 'i.imgur.' and submission.url[19:22] == '/a/'):
            ensure_path_validity(submission.id)
            image = requests.get(imgur_to_direct_link(submission.url))
            open(f"images/{submission.id[:3]}/{submission.id}.{submission.url[-3:]}", 'wb').write(image.content)

        if not image:
            ensure_path_validity(submission.id)
            image = requests.get(submission.thumbnail)
            open(f"images/{submission.id[:3]}/{submission.id}_prev.{'jpg' if image.headers['content-type'] == 'image/jpeg' else 'png'}", 'wb').write(image.content)
        img = get_opencv_img_from_buffer(image.content)

        hash_array = hash(img)
        if hash_array is not None:
            hash_string = np.array2string(hash_array, separator='')[1:-1]
            cursor.execute("UPDATE posts SET image_hash = %s WHERE id = %s", (hash_string, submission.id))
            db.commit()
            # check for double posts by looking at a single user, the title being the same, the hash being the same and created within 5 minutes.
            cursor.execute("SELECT id FROM posts WHERE author = %s AND title = %s AND created_utc > %s AND created_utc < %s AND image_hash = %s", (submission.author.name, submission.title, convert_time(submission.created_utc) - datetime.timedelta(minutes=5), convert_time(submission.created_utc), hash_string))
            previous_posts = cursor.fetchall()
            if len(previous_posts) > 0:
                submission.mod.remove()
                submission.flair.select('222002f0-4f96-11e8-9c8f-0e384ac6db5e', text="Rule 9: Double Post")
                print("Post removed for double post")

            #Auto remove image hashes.
            cursor.execute("SELECT hash FROM auto_remove_hashes WHERE hash = %s", (hash_string,))
            illegal_hash = cursor.fetchall()
            if len(illegal_hash) > 0:
                submission.mod.remove()
            
        cursor.execute("SELECT id FROM posts WHERE author = %s AND created_utc > %s AND created_utc < %s AND NOT EXISTS(SELECT * FROM modlog WHERE target_fullname = concat('t3_', posts.id) AND action = 'removelink')", (submission.author.name, convert_time(submission.created_utc) - datetime.timedelta(minutes=60), convert_time(submission.created_utc)))
        previous_posts = cursor.fetchall()
        if len(previous_posts) > 4:
            submission.mod.remove()
            submission.flair.select('95631c5a-b251-11ea-af3a-0e237e78f4dd')
            print("Post removed for being over the posting limit")


    # print(f"Author: {submission.author}\n UTC Time: {submission.created_utc}\n Destinguished: {submission.distinguished}\n Edited: {submission.edited}\n ID: {submission.id}\n Is Self: {submission.is_self}\n Link Flair: {submission.link_flair_text}\n Locked: {submission.locked}\n Name: {submission.name}\n Num Comments: {submission.num_comments}\n Over 18: {submission.over_18}\n Permalink: {submission.permalink}\n Selftext: {submission.selftext}\n Spoiler: {submission.spoiler}\n Stickied: {submission.stickied}\n Subreddit: {submission.subreddit}\n Title: {submission.title}\n URL: {submission.url}")
    print(f"Author: {submission.author}\n ID: {submission.id}\n Title: {submission.title}\n URL: {submission.url}")
    print(f"Current time: {datetime.datetime.now().time()}")
    print(reddit.auth.limits)


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

    for submission in reddit.subreddit("Animemes").stream.submissions():
        cursor.execute("SELECT * FROM posts WHERE id = %s", (submission.id,))
        exists = cursor.fetchall()
        if exists:
            continue
        insert_into_db_and_download(cursor, db, submission, reddit)
        # check_previous_sub_participation(submission, cursor)
    cursor.close()
    db.close()

if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception as e:
            print(traceback.format_exc())
	# main()