# Tier 1 reproduction image for the StatsPAI JSS submission.
#
# The Python environment is pinned exactly: the base image by digest and
# every package by requirements-jss-lock.txt (the environment in which the
# submission's artifacts were regenerated). System packages (TeX Live,
# pandoc, poppler) come from Debian bookworm unpinned; they only typeset the
# PDF and do not enter any number.
#
# Build context is the StatsPAI repository root:
#   docker build -f Paper-JSS/replication/Dockerfile -t statspai-jss .
#   docker run --rm statspai-jss            # Tier 1
FROM python:3.10.20-slim-bookworm@sha256:019e31cc1f52e4139d338bca44f27b71339a9da261738fd80fab9cf4595152fc

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential git make pandoc poppler-utils latexmk \
        texlive-latex-base texlive-latex-recommended texlive-latex-extra \
        texlive-fonts-recommended texlive-bibtex-extra \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
COPY Paper-JSS/requirements-jss-lock.txt /tmp/requirements-jss-lock.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements-jss-lock.txt

COPY pyproject.toml README.md CHANGELOG.md LICENSE paper.bib ./
COPY src ./src
COPY scripts ./scripts
COPY tests ./tests
COPY tools ./tools
COPY docs ./docs
COPY Paper-JSS ./Paper-JSS
RUN python -m pip install --no-cache-dir --no-deps -e .

WORKDIR /work/Paper-JSS
CMD ["python", "replication/reproduce.py", "--clean"]
