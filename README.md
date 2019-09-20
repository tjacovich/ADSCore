# ADS Core

This microservice serves HTML pages for the core aspects of ADS:

- Quick search:
    - Modern, classic and paper forms
    - List of results with links to full text/ref. citations
    - Sort
- Abstracts
    - Export single records to BibTeX
    - Full text links
- Integration with ADS Full:
    - Javascript hydration in abstracts (i.e., same content served to users and crawlers)
    - Easy switch to ADS Full from ADS Core
    - Re-use user token if already present
- Mobile friendly

[ADS Full](https://github.com/adsabs/bumblebee) is an extra layer around ADS Core with more complete/advanced functionalities.

## Run

Execute:

```
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
python wsgi.py
```

Access: [http://127.0.0.1:4000/](http://127.0.0.1:4000/)

## Redis

If instead of a fake redis (i.e., `REDIS_URL` with `fakeredis://:@localhost:6379/0` in `config.py`), a real one needs to be used ((i.e., `REDIS_URL` with `redis://:@localhost:6379/0`)), it is possible to easily install one in localhost with docker:

```
docker run --name redis -p 6379:6379 -d redis
```
