FROM python:3.11-slim

WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# install poetry
RUN pip install --no-cache-dir poetry

# copy deps
COPY pyproject.toml poetry.lock* ./

# install deps only (no package install)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# copy app
COPY . .

RUN mkdir -p static/sessions static/cars

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
