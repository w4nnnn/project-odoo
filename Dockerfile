FROM odoo:19

USER root
RUN apt-get update && apt-get install -y --no-install-recommends wkhtmltopdf && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --break-system-packages imgkit
USER odoo
