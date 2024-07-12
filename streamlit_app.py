#imports
import streamlit as st
import requests
import pandas as pd
import os
import io
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup
# from google.oauth2 import id_token
# from google.auth.transport import requests

################### Supporting Functions

def get_channel_id_by_name(api_key, channel_name):
    url = 'https://www.googleapis.com/youtube/v3/search'
    params = {
        'part': 'id',
        'q': channel_name,
        'type': 'channel',
        'key': api_key,
        'fields': 'items(id(channelId))'
    }

    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f'Error: {response.status_code} - {response.text}')
        return None
    
    data = response.json()
    
    if 'items' not in data or len(data['items']) == 0:
        print(f'No channel found for name: {channel_name}')
        return None
    
    return data['items'][0]['id']['channelId']

def get_uploads_playlist_id(api_key, channel_id):
    url = 'https://www.googleapis.com/youtube/v3/channels'
    params = {
        'part': 'contentDetails',
        'id': channel_id,
        'key': api_key
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f'Error: {response.status_code} - {response.text}')
        return None
    
    data = response.json()
    
    if 'items' not in data or len(data['items']) == 0:
        print(f'No details found for channel ID: {channel_id}')
        return None
    
    uploads_playlist_id = data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    return uploads_playlist_id

def get_video_links_from_playlist(api_key, playlist_id):
    video_links = []
    url = 'https://www.googleapis.com/youtube/v3/playlistItems'
    params = {
        'part': 'snippet',
        'playlistId': playlist_id,
        'maxResults': 50,
        'key': api_key
    }
    
    while True:
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            print(f'Error: {response.status_code} - {response.text}')
            break
        
        data = response.json()
        
        for item in data['items']:
            video_id = item['snippet']['resourceId']['videoId']
            video_links.append(f'https://www.youtube.com/watch?v={video_id}')
        
        if 'nextPageToken' in data:
            params['pageToken'] = data['nextPageToken']
        else:
            break
    
    return video_links

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
    
##### Generation Function
def create_excel_file(channelid):
    output = io.BytesIO()

    my_bar = st.progress(0, text='Processing YouTube Channels.....')
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        total_channels = len(channelid)
        current_channel = 0

        for key, value in channelid.items():

            playlist_id = get_uploads_playlist_id(API_KEY, value)
            url_list = get_video_links_from_playlist(API_KEY, playlist_id)

            video_details = {
                'Views': [],
                'Title': [],
                'URL': [],
                'Transcript': []
            }

            for idx, url in enumerate(url_list):
                video_id = url.split('watch?v=')[-1]
                title, view_count = get_video_title_and_views(url)
                transcript = get_video_transcript(video_id)

                if transcript:
                    video_details['Title'].append(title)
                    video_details['Views'].append(view_count)
                    video_details['URL'].append(url)
                    video_details['Transcript'].append(transcript)

                # Update progress for each video
                progress = ((current_channel / total_channels) + (idx + 1) / (len(url_list) * total_channels)) / 100
                my_bar.progress(progress, text=f"Processing Video {idx+1} of {len(url_list)} for {key}.....")

            df = pd.DataFrame(video_details)
            df.to_excel(writer, sheet_name=key, index=False)

            # Update progress for each channel
            current_channel += 1
            my_bar.progress((current_channel / total_channels), text=f"Processing Channel {current_channel} of {total_channels}.....")

    output.seek(0)
    my_bar.progress(1, text="Operation complete.")
    return output

#################### API Setup

default_api_key = 'AIzaSyA8JrcWDxjQ6j--UqJh3SxD2gECSmS5pBA'
API_KEY = st.text_input("Enter your YouTube API Key", value=default_api_key, type="password")
API_service_name = 'youtube'
API_version = 'v3'
youtube = build(API_service_name, API_version, developerKey=API_KEY)

########## UI Start

st.title("YouTube Transcript Generator")
st.write("For Heeyo")
st.write("Note, a channel without an ID or videos without transcripts will be skipped")

option = st.selectbox(
    "Select input type",
    ["YouTube Channel URL", "Upload txt file with URLs"],
    index=0,
    key="input_type",
    help="Choose whether to input a single YouTube channel URL or upload a .txt file with multiple URLs"
)

if option == "YouTube Channel URL":
    channel_url = st.text_input("Enter YouTube Channel URL", key="channel_url")
    urls = [channel_url] if channel_url else []
elif option == "Upload txt file with URLs":
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

usernames = []
for i in urls:
    usernames.append(i.split('@')[1])

channelid = {}
for u in usernames:
    id = get_channel_id_by_name(API_KEY, u)
    if id is not None:
        channelid[u] = id
    else:
        continue

#################### MAIN

if st.button("Submit"):
    if not urls:
        st.error("Please provide at least one YouTube channel URL.")
    elif not API_KEY:
        st.error("Please provide your YouTube API key.")
    else:
        excel_file = create_excel_file(channelid)

        st.download_button(
            label="Download Excel file",
            data=excel_file,
            file_name="channel_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )