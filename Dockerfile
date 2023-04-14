# Utilise une image Python 3.9
FROM python:3.9-slim-buster

# Définit le répertoire de travail comme /app
WORKDIR /app

# Copie le fichier requirements.txt dans le conteneur
COPY requirements.txt .

# Installe les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copie les fichiers de l'application dans le conteneur
COPY . .

# Expose le port 8501 pour Streamlit
EXPOSE 8501

# Lance l'application Streamlit
CMD ["streamlit", "run", "data_post.py"]