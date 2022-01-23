FROM localhost:6880/reddit-bots/3.9-buster-opencv

WORKDIR /home/python

RUN git clone https://github.com/TheVexedGerman/Mod-Tools.git .

RUN pip install --no-cache-dir -r requirements.txt
COPY praw.ini credentials.json ./

CMD [ "bash", "/home/python/new_stream_comment_automod_save_start.sh"]