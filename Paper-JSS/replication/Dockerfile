FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        make \
        pandoc \
        poppler-utils \
        texlive-latex-base \
        texlive-latex-recommended \
        texlive-latex-extra \
        texlive-fonts-recommended \
        texlive-bibtex-extra \
        latexmk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work

# Build context is the StatsPAI repository root:
#   docker build -f Paper-JSS/replication/Dockerfile -t statspai-jss .
COPY pyproject.toml README.md README_CN.md CHANGELOG.md LICENSE ./
COPY src ./src
COPY scripts ./scripts
COPY tests ./tests
COPY docs ./docs
COPY Paper-JSS ./Paper-JSS

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install . \
    && python -m pip install -r Paper-JSS/requirements-jss.txt

WORKDIR /work/Paper-JSS

CMD ["make", "reproduce-jss-full"]
