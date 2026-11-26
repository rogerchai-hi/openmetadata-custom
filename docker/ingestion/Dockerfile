FROM openmetadata/ingestion:1.12.9 AS builder

WORKDIR /wheels

COPY ./wheels .

RUN pip wheel /wheels/evidently-0.7.15+datadrift.2-py3-none-any.whl -c /wheels/constraints.txt --wheel-dir=/wheels


FROM openmetadata/ingestion:1.12.9 AS runner

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-deps /wheels/*.whl

COPY ./tmp /tmp
WORKDIR /datadrift_report
RUN python /tmp/report_catalog.py

USER root
RUN rm -rf /tmp/report_catalog.py
RUN rm -rf /wheels
USER airflow
# 回到預設值
WORKDIR /opt/airflow