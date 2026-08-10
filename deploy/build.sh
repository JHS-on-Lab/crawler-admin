#!/usr/bin/env bash
# ----------------------------------------------------------------
# build.sh — Docker 이미지를 빌드한다.
#
# 사용법:
#   ./deploy/build.sh           # 태그를 생략하면 "latest" 로 빌드
#   ./deploy/build.sh v1.2.3    # 버전 태그를 직접 지정
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
GAR_HOST="${GAR_LOCATION}-docker.pkg.dev"
IMAGE_NAME="${GAR_HOST}/${GCP_PROJECT_ID}/${GAR_REPOSITORY}/${IMAGE_NAME}"
#IMAGE_NAME="crawler-admin"
TAG="${1:-latest}"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"


# 빌드 시작 
echo "▶ 빌드 시작: ${IMAGE_NAME}:${TAG}"
echo "  프로젝트 루트: ${PROJECT_ROOT}"

# APP_UID/APP_GID 를 빌드하는 사람(호스트 계정)의 UID/GID로 맞춘다. 배포
# 계정 하나로 build→run 을 항상 순서대로 실행하는 운영 방식이라, run.sh 가
# --user 를 따로 지정하지 않고 이 값을 그대로 상속해도 항상 일치한다.
# (--build-arg 를 안 주고 수동으로 docker build 만 하는 경우를 대비해
# Dockerfile 의 ARG 기본값은 이 서버의 실제 배포 계정 값인 1000으로 둔다.)
docker build \
    --build-arg APP_UID="$(id -u)" --build-arg APP_GID="$(id -g)" \
    -t "${IMAGE_NAME}:${TAG}" \
    "${PROJECT_ROOT}"

echo ""
echo "✓ 빌드 완료: ${IMAGE_NAME}:${TAG}"
echo ""
echo "다음 단계:"
echo "  컨테이너 시작 → ./deploy/run.sh"
echo "  이미지 확인   → docker images ${IMAGE_NAME}"
