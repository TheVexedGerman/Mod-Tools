FROM localhost:6880/reddit-bots/3.11-buster-opencv

RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /home/python

RUN git clone https://github.com/TheVexedGerman/Mod-Tools.git .

RUN pip install --no-cache-dir -r requirements.txt
COPY praw.ini credentials.json ./

CMD [ "bash", "/home/python/new_stream_comment_automod_save_start.sh"]