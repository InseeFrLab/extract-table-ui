ARG BASE_IMAGE=python:3.11-slim
# Passed from Github Actions
ARG GIT_VERSION_TAG=unspecified
ARG GIT_COMMIT_MESSAGE=unspecified
ARG GIT_VERSION_HASH=unspecified

FROM $BASE_IMAGE

WORKDIR /app

# Set the tag version as an environment variable for the runtime
ENV DEPLOYMENT_VERSION=${GIT_VERSION_TAG}

RUN echo "Deployment version is: ${DEPLOYMENT_VERSION}"

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt

RUN pip3 install -r requirements.txt

COPY app/ .

EXPOSE 8501

# Healthcheck command
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "Accueil.py", "--server.port=8501", "--server.address=0.0.0.0"]
