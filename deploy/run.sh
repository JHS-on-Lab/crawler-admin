#!/usr/bin/env bash
# ----------------------------------------------------------------
# run.sh — crawler-admin 컨테이너를 실행한다.
#
# 사용법:
#   ./deploy/run.sh
#
# APP_ENV 환경변수:
#   서버에 'export APP_ENV=dev' 를 .bashrc 에 설정해두면 자동으로 읽힌다.
#   설정하지 않은 경우 기본값은 "dev".
# ----------------------------------------------------------------

set -e
# deployment.env 로드 
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_ENV_FILE="${SCRIPT_DIR}/deployment.env"

if [[ ! -f "${DEPLOYMENT_ENV_FILE}" ]]; then
    echo "ERROR: 배포 설정 파일이 없습니다: ${DEPLOYMENT_ENV_FILE}" >&2
    exit 1
fi

source "${DEPLOYMENT_ENV_FILE}"


# 변수 설정 
CONTAINER_NAME=$1
PORT="${2:-8000}"
ENV_FILE=$3
IMAGE=$4

BASE_OUTPUT_DIR="/data001/crawler/apps/data"
LOG_DIR="${BASE_OUTPUT_DIR}/${CONTAINER_NAME}/logs"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "오류: 환경 설정 파일을 찾을 수 없습니다: ${ENV_FILE}"
    echo "  APP_ENV=${APP_ENV} 로 실행 중입니다."
    echo "  서버에 .env.${APP_ENV} 파일이 있는지 확인하세요."
    exit 1
fi

mkdir -p "${LOG_DIR}"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "▶ 기존 컨테이너 제거: ${CONTAINER_NAME}"
    docker rm -f "${CONTAINER_NAME}"
fi

echo "▶ 컨테이너 시작: ${CONTAINER_NAME}"
echo "  이미지   : ${IMAGE}"
echo "  환경설정 : ${ENV_FILE}"
echo "  포트     : ${PORT}:8000"
echo "  로그     : ${LOG_DIR}"
echo ""

# --user 를 명시하지 않는다 — 이미지가 build.sh 에서 빌드한 사람의 UID/GID로
# appuser 를 만들고 USER appuser 로 고정돼 있어(Dockerfile 참고), 여기서
# 따로 지정하지 않아도 그 계정을 그대로 상속해 실행된다. 배포 계정 하나로
# build→run 을 항상 순서대로 실행하는 운영 방식이라 항상 일치한다.
docker run \
    --detach \
    --name "${CONTAINER_NAME}" \
    --restart unless-stopped \
    --env-file "${ENV_FILE}" \
    -e APP_ENV="${APP_ENV}" \
    -p "${PORT}:8000" \
    -v "${LOG_DIR}:/app/logs" \
    "${IMAGE}" \
    python -m app

echo "✓ 시작 완료: ${CONTAINER_NAME}"
echo ""
echo "확인 명령어:"
echo "  실시간 로그   → docker logs -f ${CONTAINER_NAME}"
echo "  상태 확인     → docker ps | grep ${CONTAINER_NAME}"
echo "  브라우저 접속 → http://localhost:${PORT}"
echo "  컨테이너 중지 → docker stop ${CONTAINER_NAME}"
