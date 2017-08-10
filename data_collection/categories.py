import pandas as pd
import spotipy
import spotipy.util as util
from collections import defaultdict

token = util.prompt_for_user_token('',
                                   client_id='d2d20e4e462c41b8ba0503d13ae78184', 
                                   client_secret='11ad3e11e173449287faa4edd469e012',
                                   redirect_uri='https://github.com/rjs2015')
spotify = spotipy.Spotify(auth=token)
category_map = {1:'Party', 2:'Workout', 3:'Chill', 4:'Sleep', 5:'Travel'}

def get_category_playlists(country='US', cat_limit=40, playlist_limit=50):
    '''Get Spotify categories and associated playlists'''
    categories = {category['name']: category['id'] for category in 
                  spotify.categories(country=country, limit=cat_limit)['categories']['items']}
    
    playlists = defaultdict(dict)
    for cat_name, cat_id in categories.iteritems():
        try:
            for playlist in spotify.category_playlists(cat_id, limit=playlist_limit)['playlists']['items']:
                playlists[cat_name][playlist['name']] = playlist['id'] 
        except spotipy.SpotifyException:
            pass
    
    return playlists


def get_playlist_tracks(playlist_id, track_limit=100):
    '''Get tracks for Spotify playlists'''    
    try:
        tracks = spotify.user_playlist_tracks('spotify', playlist_id, limit=track_limit)['items']
        track_dict = {track['track']['name']: track['track']['id'] for track in tracks}
    except spotipy.SpotifyException:
        track_dict = {}
        
    return {playlist_id: track_dict}


def get_category_tracks(category_map):
    '''Get tracks for specified Spotify categories'''
    category_playlists = get_category_playlists()
    category_tracks = defaultdict(dict)    
    for category, playlists in category_playlists.iteritems():
        if category in category_map.values():
            for playlist_name, playlist_id in playlists.iteritems():
                category_tracks[category][playlist_name] = get_playlist_tracks(playlist_id)
    
    return category_tracks


def get_audio_feature_df(category_tracks):  
    '''
    Get a dataframe of audio features for all tracks in a category subset
    
    De-dup within, but not across, categories (e.g. same song can be both 'Chill' and 'Sleep')    
    '''       
    track_feature_list = []

    for category, playlists in category_tracks.iteritems():
        unique_category_track_ids = set()
        for playlist_name, playlist_contents in playlists.iteritems():
            for playlist_id, tracks in playlist_contents.iteritems():
                
                # De-dup tracks within category and update category track set
                track_ids = set(tracks.values()).difference(unique_category_track_ids)
                unique_category_track_ids.update(track_ids)
                
                if len(track_ids) > 0:
                    features = spotify.audio_features(tracks=track_ids)
                    for track_info in features:
                        track_info['category'] = category
                    track_feature_list.extend(features)
    
    return pd.DataFrame(track_feature_list)


def chunks(l, n):
    return [l[i:i+n] for i in range(0, len(l), n)]


def append_extra_track_info(audio_feature_df):
    '''Add general track information from Spotify to audio feature df'''
    all_extra_info = []

    for track_chunk in chunks(audio_feature_df['id'].unique(), 50):
        for track in spotify.tracks(track_chunk)['tracks']:
            extra_info = {}
            extra_info['id'] = track['id']            
            extra_info['artist'] = {artist['id']: artist['name'].encode('ascii', 'ignore') 
                                    for artist in track['artists']}
            extra_info['title'] = track['name'].encode('ascii', 'ignore')
            extra_info['explicit'] = track['explicit']
            all_extra_info.append(extra_info)

    return pd.merge(audio_feature_df, pd.DataFrame(all_extra_info))


def generate_category_tracks_df(category_map=category_map):
    category_tracks = get_category_tracks(category_map)    
    audio_feature_df = get_audio_feature_df(category_tracks)    
    category_tracks_df = append_extra_track_info(audio_feature_df)
    
    return category_tracks_df
