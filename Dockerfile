# ----------------------------------------------------------------
# 베이스 이미지: python:3.12-slim
#
# FastAPI + Jinja2 웹 서버. 브라우저 렌더링 불필요 → 경량 이미지 사용.
# ----------------------------------------------------------------
FROM python:3.12-slim

ARG APP_UID=1000
ARG APP_GID=1000

WORKDIR /app

# ----------------------------------------------------------------
# 타임존: 서울(KST)
# ----------------------------------------------------------------
ENV TZ=Asia/Seoul
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 이 서버의 crawler-admin 배포 계정 UID/GID(1000, build.sh가 --build-arg 로
# 전달)로 작업용 계정을 만든다. deploy/run.sh 는 --user 를 따로 지정하지
# 않고 이미지가 빌드 시점에 갖게 된 이 계정을 그대로 상속해 실행한다.
RUN groupadd --gid "${APP_GID}" appgroup \
    && useradd \
        --uid "${APP_UID}" \
        --gid "${APP_GID}" \
        --create-home \
        --shell /bin/bash \
        appuser \
    && chown -R appuser:appgroup /app

# ----------------------------------------------------------------
# Python 패키지 설치
# ----------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ----------------------------------------------------------------
# 애플리케이션 코드 복사
#
# .env 는 민감 정보 없는 공통 기본값만 담고 있어 이미지에 포함한다.
# .env.dev / .env.prod 는 이미지에 넣지 않는다 (.dockerignore 로 제외).
#   → 환경별 접속 정보는 컨테이너 실행 시 --env-file 로 주입한다.
# ----------------------------------------------------------------
COPY --chown=appuser:appgroup app/ app/
COPY --chown=appuser:appgroup .env .

ENV HOME=/home/appuser

USER appuser

# ----------------------------------------------------------------
# 웹 서버 포트
# ----------------------------------------------------------------
EXPOSE 8000

# ----------------------------------------------------------------
# CMD / ENTRYPOINT 없음
#
# 실행 명령은 docker run 인자 또는 docker-compose command 로 지정한다.
# ----------------------------------------------------------------
