from sqlalchemy import create_engine
import billboard
import datetime

import spotipy
import spotipy.util as util
import pygn
from time import sleep
from fuzzywuzzy import fuzz

token = util.prompt_for_user_token('',
                                   client_id='', 
                                   client_secret='',
                                   redirect_uri='')
spotify = spotipy.Spotify(auth=token)

gracenote_clientID = '' 
gracenote_userID = pygn.register(gracenote_clientID)
dt_fmt = '%Y-%m-%d'

# The following code creates tables to store song data for use in the playlist application.
# A PostreSQL database must exist with the specified 'database_name'. Tables are initialized
# based on pickled sample tables, and data inserted through queries to the Spotify
# and Gracenote APIs.

database_name = ''
engine = create_engine('postgresql://username:password@...' + database_name)

artist_songs_table_sample = pickle.load(open('artist_songs_table_sample.p', 'r'))
gracenote_song_data_table_sample = pickle.load(open('gracenote_song_data_table_sample.p', 'r'))
spotify_song_data_table_sample = pickle.load(open('spotify_song_data_table_sample.p', 'r'))

artist_songs_table_sample.to_sql(name='artist_songs',con=engine)
spotify_song_data_table_sample.to_sql(name='spotify_song_data',con=engine)
gracenote_song_data_table_sample.to_sql(name='gracenote_song_data',con=engine)

def fetch_song_info(chart, start_date, end_date):
    
    '''Fetch weekly chart data and Spotify information for each track on Billboard Charts
       between specified dates.  Returns a dataframe with chart contents for each week'''
    
    dates = [datetime.datetime.strptime(end_date, dt_fmt) - datetime.timedelta(7)]
    while min(dates) - datetime.timedelta(7) >= datetime.datetime.strptime(start_date, dt_fmt):
        dates.append(dates[-1] - datetime.timedelta(7))

    charts_data = {}
    for i in dates:
        search_date = i.strftime(format=dt_fmt)
        week = billboard.ChartData(chart, date=search_date, fetch=True, quantize=True).date
        charts = billboard.ChartData(chart, date=search_date, fetch=True, quantize=True)
        charts_data[week] = charts

    charts_df_data = []

    for k, v in charts_data.iteritems():
        for song in v:
            df_data = {}
            df_data['week'] = k
            df_data['rank'] = song.rank
            df_data['title'] = song.title
            df_data['artist'] = song.artist
            df_data['chart'] = chart    
            df_data['id'] = song.spotifyID
            charts_df_data.append(df_data)

    charts_df = pd.DataFrame(charts_df_data)
    return charts_df

def chunks(l, n):
    n = max(1, n)
    return [l[i:i+n] for i in range(0, len(l), n)]

def get_popular_artists(charting_tracks):
    '''Get artists for popular songs from Billboard Charts to create
       a SQL database of music for the final application'''
    artist_ids = []

    for tracks in chunks(charting_tracks.id.unique(),25):
        try:
            spotify_info = spotify.tracks(tracks)
            for track in spotify_info['tracks']:
                if track['artists'][0]['id'] not in artist_ids:
                    artist_ids.append(track['artists'][0]['id'])
        except:
            pass
    
    return artist_ids

def populate_sql(artist_id, spotify, gracenote_clientID, gracenote_userID):
    '''Populate the psql database with song data for specified artist, pulling data
       from Spotify and Gracenote APIs'''

    # For each artist, get all of their albums (including singles)

    artist_query = pd.read_sql_query("SELECT DISTINCT artist FROM artist_songs",con=engine)
    if artist_id not in list(artist_query.artist):
        offset = 0
        album_compilation = []
        search_albums = [i['id'] for i in spotify.artist_albums(artist_id,limit=50,offset=offset)['items']]
        album_compilation.extend(search_albums)

        while len(search_albums)>0:
            offset += 50
            search_albums = [i['id'] for i in spotify.artist_albums(artist_id,limit=50,offset=offset)['items']]
            album_compilation.extend(search_albums)

    # Get all tracks for each album                   

        search_tracks = {}

        for albums in chunks(album_compilation,20):
            for album in spotify.albums(albums)['albums']:
                for track in album['tracks']['items']:
                    for artist in track['artists']:
                        if artist['id'] == artist_id:
                            search_tracks[track['name'].lower()] = track['id']

    # Get features for each track (and discard tracks without feature information)

        playlist_features = []

        for tracks in chunks(search_tracks.values(),100):
            playlist_features.extend(spotify.audio_features(tracks))

        playlist_nonempty_idx = [idx for idx,features in enumerate(playlist_features) if features!=None]
        final_tracks = [search_tracks.keys()[i] for i in playlist_nonempty_idx]
        playlist_features = [playlist_features[i] for i in playlist_nonempty_idx]

    # Filter songs by popularity to reduce covers, remixes, and other song versions that may
    # add too much noise (*ba dum tss*)

        playlist_songs = pd.DataFrame(playlist_features).drop(['analysis_url','track_href',
                                                               'type','uri'],axis=1)

        playlist_songs['name'] = final_tracks
        playlist_songs = playlist_songs.groupby(['id', 'name']).mean().fillna(0)

        popularity_info = []

        for tracks in chunks(playlist_songs.index.levels[0],25):
            for track in spotify.tracks(tracks)['tracks']:
                popularity_info.append({'id':track['id'],
                                        'popularity':track['popularity'],
                                        'artist':artist_id,
                                        'explicit':track['explicit']})

        popularity_info = pd.DataFrame(popularity_info)
        playlist_songs = pd.merge(playlist_songs.reset_index(),popularity_info,how='left')

    # Use median song popularity by artist as a cutoff               

        popularity_cutoff = playlist_songs.groupby(['artist'],as_index=False).popularity.median()
        popularity_cutoff.columns = ['artist','cutoff']
        playlist_songs = pd.merge(playlist_songs,popularity_cutoff,how='left')
        playlist_songs['artist_name'] = spotify.artist(artist_id)['name']
        playlist_songs = playlist_songs[playlist_songs.popularity>playlist_songs.cutoff].set_index(
            ['id','name','artist','artist_name'])

    # Now, for this artist we have a dataframe containing Spotify track data for songs above median
    # popularity.  We add Gracenote data in the following lines.

        gn_data = []

        for track in list(playlist_songs.index):
            artist_name = track[-1]
            song_name = track[1]
            spotify_id = track[0]

    # Use fuzzy matching to align Gracenote search results with Spotify tracks.
    # Collect artist_type, genre, and mood (primary and secondary) from Gracenote, 
    # where available

            pygn_results = pygn.search(clientID=gracenote_clientID, userID=gracenote_userID, 
                                       artist = artist_name, track = song_name)
            if fuzz.ratio(pygn_results['track_title'],song_name) > 50:
                info_dict = {}
                features = ['artist_type','genre','mood']
                for feature in features:
                    if len(pygn_results[feature])>0:
                        info_dict[feature] = pygn_results[feature]['1']['TEXT']
                        if feature == 'genre':
                            info_dict[feature + '_2'] = pygn_results[feature]['2']['TEXT']
                    else:
                        info_dict[feature] = np.nan
                        if feature == 'genre':
                            info_dict[feature + '_2'] = np.nan

                gn_data.append({ 'id':spotify_id,
                                 'artist_type_1':info_dict['artist_type'],
                                 'genre_1':info_dict['genre'],
                                 'genre_2':info_dict['genre_2'],
                                 'mood_1':info_dict['mood'],
                                 'album_year':pygn_results['album_year'],
                                 'album_title':pygn_results['album_title'],
                                 'gn_track_id':pygn_results['track_gnid'] 
                               })

    # Reorganize Spotify and Gracenote data into three tables for psql database.
    # Append to existing tables (which were set up previously)

        gn_data = pd.DataFrame(gn_data)      
        compiled_data = pd.merge(playlist_songs.reset_index(), gn_data, how='left')

        artist_songs = compiled_data[['id','name','artist','artist_name']]
        spotify_song_data = compiled_data[['id','artist','acousticness','danceability','duration_ms',
                                       'energy','instrumentalness','key','liveness',
                                       'loudness','mode','speechiness','tempo',
                                       'time_signature', 'valence', 'explicit',
                                       'popularity','cutoff']]
        gracenote_song_data = compiled_data[['id','artist','album_title','album_year','artist_type_1',
                                             'genre_1','genre_2','gn_track_id','mood_1']]

        artist_songs.to_sql(name='artist_songs',con=engine,if_exists='append')
        spotify_song_data.to_sql(name='spotify_song_data',con=engine,if_exists='append')
        gracenote_song_data.to_sql(name='gracenote_song_data',con=engine,if_exists='append')

        sleep(1)

    # Refresh Spotify and Gracenote tokens, which may have expired during this process              

        token = util.prompt_for_user_token('',client_id='', 
                       client_secret='',
                      redirect_uri='')
        spotify = spotipy.Spotify(auth=token)

        gracenote_userID = pygn.register(gracenote_clientID)
      
charting_tracks = fetch_song_info('hot-100','2015-01-01', '2016-01-01')
popular_artists = get_popular_artists(charting_tracks)
populate_sql(popular_artists[0], spotify, gracenote_clientID, gracenote_userID)  