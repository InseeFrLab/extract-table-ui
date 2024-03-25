ARG BASE_IMAGE=inseefrlab/onyxia-python-pytorch
FROM $BASE_IMAGE

WORKDIR /app

COPY setup.sh .

RUN ./setup.sh

COPY requirements.txt requirements.txt

ENV PATH="${PATH}:/home/onyxia/.local/bin"

RUN pip3 install -r requirements.txt --user

COPY app/main.py .

COPY app/utils.py .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
