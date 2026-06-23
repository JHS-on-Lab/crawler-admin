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

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

APP_ENV="${APP_ENV:-dev}"
ENV_FILE="${PROJECT_ROOT}/.env.${APP_ENV}"
PORT="${PORT:-8000}"

LOG_DIR="${HOME}/apps/data/crawler-admin/logs"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "오류: 환경 설정 파일을 찾을 수 없습니다: ${ENV_FILE}"
    echo "  APP_ENV=${APP_ENV} 로 실행 중입니다."
    echo "  서버에 .env.${APP_ENV} 파일이 있는지 확인하세요."
    exit 1
fi

mkdir -p "${LOG_DIR}"

CONTAINER_NAME="crawler-admin"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "▶ 기존 컨테이너 제거: ${CONTAINER_NAME}"
    docker rm -f "${CONTAINER_NAME}"
fi

IMAGE="crawler-admin:latest"

echo "▶ 컨테이너 시작: ${CONTAINER_NAME}"
echo "  이미지   : ${IMAGE}"
echo "  환경설정 : ${ENV_FILE}"
echo "  포트     : ${PORT}:8000"
echo "  로그     : ${LOG_DIR}"
echo ""

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
