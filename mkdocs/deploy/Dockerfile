# Imagen de construcción de la documentación (mkdocs/ de ol_new_apps).
FROM python:3.12-slim
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
ENV NO_MKDOCS_2_WARNING=1 DISABLE_MKDOCS_2_WARNING=true
WORKDIR /src
