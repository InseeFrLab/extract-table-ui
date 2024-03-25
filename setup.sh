#!/bin/bash
# Installing packages
sudo ln -fs /usr/share/zoneinfo/America/New_York /etc/localtime

sudo apt-get update && sudo apt-get upgrade -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y tzdata
sudo dpkg-reconfigure --frontend noninteractive tzdata

sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:alex-p/tesseract-ocr-devel
sudo apt-get update
sudo apt install -y python3-opencv tesseract-ocr tesseract-ocr-fra poppler-utils ghostscript python3-tk

# Create results dir 
mkdir -p results/ocr

# Import stopwords
pip install nltk
python - <<'END_SCRIPT'
import nltk
nltk.download('stopwords')
END_SCRIPT
