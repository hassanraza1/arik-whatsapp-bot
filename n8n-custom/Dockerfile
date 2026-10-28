FROM n8nio/n8n:latest
USER root
RUN echo '#!/bin/sh' > /usr/local/bin/n8n-start.sh && \
    echo 'export N8N_RESTRICT_FILE_ACCESS_TO=/' >> /usr/local/bin/n8n-start.sh && \
    echo 'exec n8n "$@"' >> /usr/local/bin/n8n-start.sh && \
    chmod +x /usr/local/bin/n8n-start.sh
USER node
