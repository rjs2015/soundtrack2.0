import json
from flask import Flask, jsonify, request, render_template, redirect, session
import spotipy
import spotipy.util as util

import requests
import base64
import urllib

import numpy as np
import pandas as pd
import pickle

# model and sample df in memory
# Load in pickled models
with open('playlist_models.p','r') as f: 
    model_matrix = pickle.load(f)

# Load in song data
spotify_data = pickle.load(open('spotify_data.p', 'r'))
artist_song_data = pickle.load(open('artist_song_data.p', 'r'))
    
# Initialize playlist variables
playlist = []   
categories = ['Party','Chill','Sleep','Workout','Travel']
old_category = ''
breakdown_dict = {'Chill': 0, 'Party': 0, 'Sleep': 0, 'Travel': 0, 'Workout': 0}
artist_info = []
playlist_tracks = []

# Initialize the app
app = Flask(__name__)
# app.secret_key = ''

# Spotify authorization setup
# Client Keys
# CLIENT_ID = ''
# CLIENT_SECRET = ''

# Spotify URLS
SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/authorize'
SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token'
SPOTIFY_API_BASE_URL = 'https://api.spotify.com'
API_VERSION = 'v1'
SPOTIFY_API_URL = '{}/{}'.format(SPOTIFY_API_BASE_URL, API_VERSION)


# Parameters
CLIENT_SIDE_URL = 'http://52.55.179.229:80'
# CLIENT_SIDE_URL = 'http://52.55.179.229:5000'
REDIRECT_URI = CLIENT_SIDE_URL
# REDIRECT_URI = '{}/callback/q'.format(CLIENT_SIDE_URL)
SCOPE = 'playlist-modify-public playlist-modify-private'
STATE = ''
SHOW_DIALOG_bool = True
SHOW_DIALOG_str = str(SHOW_DIALOG_bool).lower()


auth_query_parameters = {
    'response_type': 'code',
    'redirect_uri': REDIRECT_URI,
    'scope': SCOPE,
    # 'state': STATE,
    # 'show_dialog': SHOW_DIALOG_str,
    'client_id': CLIENT_ID
}

# Homepage
@app.route('/')
def index():
    
    global REDIRECT_URI, CLIENT_ID, CLIENT_SECRET, SPOTIFY_TOKEN_URL, 
    global SPOTIFY_API_URL, playlist_tracks, old_category, playlist
    
    try:
        len(session['playlist_tracks'])    
    except:
        pass
    
    playlist = []
    
    try:
        auth_token = request.args['code']
        code_payload = {
	        'grant_type': 'authorization_code',
	        'code': str(auth_token),
	        'redirect_uri': REDIRECT_URI
        }
        base64encoded = base64.b64encode('{}:{}'.format(CLIENT_ID, CLIENT_SECRET))
        headers = {'Authorization': 'Basic {}'.format(base64encoded)}
        post_request = requests.post(SPOTIFY_TOKEN_URL, data=code_payload, headers=headers)

        response_data = json.loads(post_request.text)
        access_token = response_data['access_token']  
        authorization_header = {'Authorization':'Bearer {}'.format(access_token)}
        spotify = spotipy.Spotify(auth=access_token)
        user_profile_api_endpoint = '{}/me'.format(SPOTIFY_API_URL)
        profile_response = requests.get(user_profile_api_endpoint, headers=authorization_header)
        profile_data = json.loads(profile_response.text)
        username = profile_data['uri'].split(':')[-1]
        new_playlist = spotify.user_playlist_create(username, old_category + ' Playlist', True)
        

        spotify.user_playlist_add_tracks(username, new_playlist.get('id'), list(session['playlist_tracks']))
        return render_template('index.html')        
    
    except:
        return render_template('index.html')

@app.route('/main/', methods=['POST'])
def score():

    ''' Compile playlist with songs from artists, ranked by category alignment '''

    data = request.json

    global playlist, breakdown_dict, old_category, artist_info, spotify_data, gracenote_data
    global artist_song_data, auth_query_parameters, SPOTIFY_AUTH_URL, playlist_tracks

    length = data['info'][0]
    try:
        new_category = data['info'][1]
        artist = data['info'][2]
    except:
        pass

    if length == -1:
        url_args = '&'.join(['{}={}'.format(key,urllib.quote(val)) for key,val in auth_query_parameters.iteritems()])
        auth_url = '{}/?{}'.format(SPOTIFY_AUTH_URL, url_args)
        auth_dict = {'auth':auth_url}
        return jsonify(auth_dict)

    else:
    
        if artist=='clear':

    # If user cleared playlist, reset variables to initial values        

            playlist = pd.DataFrame()
            breakdown_dict = {'Chill': 0, 'Party': 0, 'Sleep': 0, 'Travel': 0, 'Workout': 0,'playlist_info': 'No songs - add some artists!'}
            artist_info = []

        else:

    # Otherwise, if a new artist is added, fetch that artist's tracks from psql database, and use predicted 
    # probabilities for tracks of belonging to each category to measure song alignment to each one

            try:
                previous_artists = playlist.index.levels[3]
            except:
                previous_artists = []

            if artist not in previous_artists:

                artist_info.append(artist)

                song_ids = artist_song_data[artist_song_data['artist_name']==artist]['id']
                data = spotify_data[spotify_data['id'].isin(song_ids)]
                data = pd.merge(data, artist_song_data, on='id', how='inner')

                data = data.groupby('id', as_index=False).first()
                data = data.set_index(['id','name','artist','artist_name']).drop(['popularity','cutoff'],axis=1)

    # Create (if currently empty) or extend a playlist based on the user specified artists. For each song,
    # predict alignment to each category using predict_proba from the pickled models.  When a user chooses a 
    # category, we will sort on this metric to return songs most aligned to that category for their playlist

                if len(playlist)==0:

                    playlist = pd.DataFrame(index=data.index)

                    for cat in categories:
                        playlist[cat] = pd.Series(model_matrix[cat].predict_proba(data)[:,1],
                        	index=data.index, name=cat)

                else:

                    playlist_extension =  pd.DataFrame(index=data.index)

                    for cat in categories:
                        playlist_extension[cat] = pd.Series(model_matrix[cat].predict_proba(data)[:,1],
                                index=data.index,name=cat)

                    playlist = pd.concat([playlist,playlist_extension])

    # Re-sort tracks only if the category changes or a new artist is added (to avoid unnecessary sorting
    # when the slider is moved).  Calculate the playlist's total category alignment scores to 
    # create the visualization blob, captured in 'playlist_breakdown'.

            if (new_category!=old_category) or (artist not in previous_artists):
                playlist.sort_values(new_category,ascending=False,inplace=True)
                old_category = new_category  

            playlist_breakdown = playlist[:min(length,len(playlist))].sum()
            playlist_breakdown = playlist_breakdown/playlist_breakdown.max()

            breakdown_dict = {}

            for cat in categories:
                breakdown_dict[cat] = round(playlist_breakdown[cat],2)

    # Create preformatted text blobs containing artists and contents of playlist, for display
    # in the application

            playlist_songs = playlist.index.get_level_values('name')
            playlist_info = []
            line = []
            for i in range(length):
                line.append(str(min(i+1,len(playlist_songs))) + '. ' + playlist_songs[i])
                if len('   '.join(line)) > 40:
                    line = '   '.join(line) + '\n'
                    playlist_info.extend(line)
                    line=[]
                elif i==length-1:
                    line = '   '.join(line)
                    playlist_info.extend(line)
            playlist_info = ''.join(playlist_info)

            playlist_artists = []
            line = []

            for artist in artist_info:
                playlist_artists.append(artist + '\n\n')

            playlist_artists = ''.join(playlist_artists)

            breakdown_dict['playlist_info'] = playlist_info
            breakdown_dict['artist_info'] = playlist_artists
            
            session['playlist_tracks'] = list(playlist.index.get_level_values('id')[:length])

        return jsonify(breakdown_dict)


# Start the app server
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
