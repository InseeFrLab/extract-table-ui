# Application Streamlit pour le téléchargement des comptes sociaux et l'extraction du tableau des filiales et participations

## Mise en route

Avant de lancer l'application, installer les dépendances avec `./setup.sh` et `pip install -r requirements.txt`, puis renseigner les variables d'environnement:

- `TEST_INPI_USERNAME`: nom d'utilisation du compte INPI;
- `TEST_INPI_PASSWORD`: mot de passe du compte INPI;
- `MLFLOW_TRACKING_URI`: URI du MLflow tracking server utilisé;
- `MLFLOW_S3_ENDPOINT_URL`: nom du endpoint S3 pour MLflow.

Puis lancer l'application avec `streamlit run main.py --server.port=8501 --server.address=0.0.0.0` par exemple.

## Briques

- Récupération de documents: la brique de récupération de documents repose sur [ce dépôt](https://github.com/InseeFrLab/ca-document-querier/). La classe `DocumentQuerier` permet de faire des appels à une API de l'INPI pour récupérer simplement des comptes annuels des entreprises;
- Sélection de page: à partir d'un document récupéré via l'API de l'INPI, une brique permet de détecter la page sur laquelle figure le tableau des filiales et 
participations lorsqu'un tel tableau existe dans le document. Cette brique est implémentée grâce [au module ca_extract/page_selection de ce dépôt](https://github.com/InseeFrLab/extraction-comptes-sociaux/tree/19eb0a18c204ffe96df9440e07359694e4f086ac);
- A partir d'une page sélectionnée grâce à la brique précédente, une brique permet d'extraire le contenu des tableaux de la page. Elle est implémentée grâce 
[au module ca_extract/extraction de ce dépôt](https://github.com/InseeFrLab/extraction-comptes-sociaux/tree/19eb0a18c204ffe96df9440e07359694e4f086ac).

## Modèles utilisé

- Pour la brique de sélection de page, un classifieur `fastText` entraîné sur des données ad hoc est utilisé;
- Pour la brique d'extraction, un modèle TableTransformer pré-entraîné sur les données de PubTables-1M est utilisé.
