#imports
import streamlit as st
import requests
import pandas as pd
import re
import scrapetube
import io
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup
from config import DEFAULT_API_KEY


# from google.oauth2 import id_token
# from google.auth.transport import requests

################### Supporting Functions

def get_video_title_and_views(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        title = soup.find('title').text
        view_count_tag = soup.find('meta', attrs={'itemprop': 'interactionCount'})
        view_count = int(view_count_tag['content'])

        return title, view_count
    except Exception as e:
        print(f"Could not fetch details for URL {url}: {e}")
        return None, None

def get_video_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " | ".join([entry['text'] for entry in transcript])
        return transcript_text
    except Exception as e:
        print(f"Could not fetch transcript for video {video_id}: {e}")
        return None
    
def get_channel_id(username):
    response = requests.get(f"https://www.youtube.com/@{username}/about")
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        match = re.search(r'"externalId":"(UC[\w-]+)"', str(soup))
        if match:
            return match.group(1)
    
    return None
    
##### Generation Function
def create_excel_file(channelid):
    output = io.BytesIO()

    my_bar = st.progress(0, text='Processing YouTube Channels.....')
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        total_channels = len(channelid)
        current_channel = 0

        for key, value in channelid.items():
            playlist_id = "UU" + value[2:]
            urls = []
            videos = scrapetube.get_playlist(playlist_id)
            for video in videos:
                urls.append(f"https://www.youtube.com/watch?v={video['videoId']}")

            video_details = {
                'Views': [],
                'Title': [],
                'URL': [],
                'Transcript': []
            }

            for idx, url in enumerate(urls):
                video_id = url.split('watch?v=')[-1]
                title, view_count = get_video_title_and_views(url)
                transcript = get_video_transcript(video_id)

                if transcript:
                    video_details['Title'].append(title)
                    video_details['Views'].append(view_count)
                    video_details['URL'].append(url)
                    video_details['Transcript'].append(transcript)

                # Update progress for each video
                progress = ((current_channel / total_channels) + (idx + 1) / (len(urls) * total_channels)) / 100
                my_bar.progress(progress, text=f"Processing Video {idx+1} of {len(urls)} for {key}.....")

            df = pd.DataFrame(video_details)
            df.to_excel(writer, sheet_name=key, index=False)

            # Update progress for each channel
            current_channel += 1
            my_bar.progress((current_channel / total_channels), text=f"Processed Channel {current_channel} of {total_channels}.....")

    output.seek(0)
    my_bar.progress(100, text="Operation complete.")
    my_bar.empty()
    return output

#################### API Setup

# API_KEY = st.text_input("Enter your YouTube API Key", value=DEFAULT_API_KEY, type="password")
# API_service_name = 'youtube'
# API_version = 'v3'
# youtube = build(API_service_name, API_version, developerKey=API_KEY)

########## UI Start

st.title("YouTube Transcript Generator")
st.markdown("Note, a **channel without an ID** or **videos without transcripts** will be *skipped*")
st.markdown("Channel Url Format: https://www.youtube.com/@username or https://www.youtube.com/{id}")

option = st.radio(
    "Select input type",
    ["Enter YouTube Channel URLs", "Upload TXT file with URLs"],
    index=0,
    key="input_type",
    help="Format: One full URL per line"
)

urls = []

if option == "Enter YouTube Channel URLs":
    channel_url = st.text_area("Enter YouTube Channel URLs or Playlists")
    urls = channel_url.splitlines()
elif option == "Upload TXT file with URLs":
    uploaded_file = st.file_uploader("Upload a .txt file with YouTube Channel URLs", type=["txt"], key="file_upload")
    urls = []
    if uploaded_file is not None:
        urls = uploaded_file.read().decode('utf-8').splitlines()

video_details = {
        'Views': [],
        'Title': [],
        'URL': [],
        'Transcript': []
}

channelid = {}
for url in urls:
    if "@" in url:
        channelid[url.split('@')[1]] = get_channel_id(url.split('@')[1])
    else:
        channelid[url.split('channel/')[1]] = url.split('channel/')[1]

#################### MAIN

if st.button("Submit"):
    if not urls:
        st.error("Please provide at least one YouTube channel URL.")
    else:
        excel_file = create_excel_file(channelid)
        st.download_button(
            label="Download Excel file",
            data=excel_file,
            file_name="channel_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )