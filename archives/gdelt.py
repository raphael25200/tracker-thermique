import requests
from deep_translator import GoogleTranslator
from datetime import datetime

def recuperer_articles(mot_cle="conflict", nombre=10):
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": mot_cle,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": nombre
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    }

    response = requests.get(url, params=params, headers=headers)

    if response.status_code != 200:
        print(f"DEBUG - status_code: {response.status_code}")
        print(f"DEBUG - texte: {response.text[:300]}")
        return None, "GDELT n'a pas répondu correctement (peut-être une limite de requêtes atteinte, réessaie dans quelques minutes)."

    try:
        data = response.json()
    except ValueError:
        return None, "Réponse invalide de GDELT (probablement une limite de requêtes atteinte)."

    articles = data.get('articles', [])
    resultats = []

    for article in articles:
        try:
            titre_traduit = GoogleTranslator(source='auto', target='fr').translate(article['title'])
        except Exception:
            titre_traduit = article['title']  # si la traduction échoue, on garde l'original

        date_brute = article['seendate']  # format "20260626T211500Z"
        date_convertie = datetime.strptime(date_brute, "%Y%m%dT%H%M%SZ").date()

        resultats.append({
            "titre": titre_traduit,
            "date": date_convertie,
            "zone": article.get('sourcecountry', 'Inconnu'),
            "source_url": article['url'],
            "domain": article['domain']
        })

    return resultats, None