#!/usr/bin/env bash
# ----------------------------------------------------------------
# build.sh — Docker 이미지를 빌드한다.
#
# 사용법:
#   ./deploy/build.sh           # 태그를 생략하면 "latest" 로 빌드
#   ./deploy/build.sh v1.2.3    # 버전 태그를 직접 지정
# ----------------------------------------------------------------

set -e

IMAGE_NAME="crawler-admin"
TAG="${1:-latest}"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "▶ 빌드 시작: ${IMAGE_NAME}:${TAG}"
echo "  프로젝트 루트: ${PROJECT_ROOT}"

# APP_UID/APP_GID 는 이 서버의 crawler-admin 배포 계정 UID/GID(1000)로
# 고정한다. run.sh 는 --user 를 따로 지정하지 않고 이미지가 빌드 시점에
# 갖게 된 이 값을 그대로 상속해 실행한다.
docker build \
    --build-arg APP_UID=1000 --build-arg APP_GID=1000 \
    -t "${IMAGE_NAME}:${TAG}" \
    "${PROJECT_ROOT}"

echo ""
echo "✓ 빌드 완료: ${IMAGE_NAME}:${TAG}"
echo ""
echo "다음 단계:"
echo "  컨테이너 시작 → ./deploy/run.sh"
echo "  이미지 확인   → docker images ${IMAGE_NAME}"
