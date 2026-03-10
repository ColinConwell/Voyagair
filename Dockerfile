FROM python:3.11-slim AS backend

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
COPY data/ data/
RUN pip install --no-cache-dir .

FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY --from=backend /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend /usr/local/bin /usr/local/bin
COPY --from=backend /app /app
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

EXPOSE 8000
CMD ["uvicorn", "voyagair.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
