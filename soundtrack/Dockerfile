FROM tiangolo/uwsgi-nginx-flask:flask

COPY requirements.txt /tmp/

# RUN wget -q https://repo.continuum.io/miniconda/Miniconda2-4.1.11-Linux-x86_64.sh
# RUN /bin/bash Miniconda2-4.1.11-Linux-x86_64.sh -b -p /opt/conda
# RUN rm Miniconda-latest-Linux-x86_64.sh
# RUN /opt/conda/bin/conda install -y -q conda-build
# ENV PATH /opt/conda/bin:$PATH

# RUN which python

RUN pip install -U pip
RUN pip install -r /tmp/requirements.txt

RUN python -m pip install --upgrade pip
# RUN pip install numpy
RUN pip install --user scipy
RUN pip install scipy
RUN pip install spotipy
RUN pip install Flask-Session

#COPY playlist_db /tmp/

#RUN apt-get update
#RUN apt-get --yes install postgresql postgresql-contrib
#USER postgres
#RUN /etc/init.d/postgresql start \
#    && psql --command "CREATE USER rsingh WITH SUPERUSER PASSWORD 'rsingh';" \
#    && psql --command "CREATE DATABASE playlist;" \
#    && psql playlist < /tmp/playlist_db

COPY ./app /app




