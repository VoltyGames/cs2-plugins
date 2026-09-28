# The CI toolchain (voltmod/.github/actions/setup-toolchain), baked once for local Linux builds.
FROM registry.gitlab.steamos.cloud/steamrt/sniper/sdk:latest

RUN echo 'deb https://repo.steampowered.com/steamrt3/apt sniper_beta main contrib non-free' \
  > /etc/apt/sources.list.d/steamrt-beta.list \
  && apt-get -o Acquire::Check-Valid-Until=false update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  ccache gcc-14-monolithic git ninja-build zstd \
  && rm -rf /var/lib/apt/lists/*

# Install git-lfs, which is required for some dependency repositories
ADD https://github.com/git-lfs/git-lfs/releases/download/v3.6.1/git-lfs-linux-amd64-v3.6.1.tar.gz /tmp/git-lfs.tar.gz
RUN tar -xzf /tmp/git-lfs.tar.gz -C /tmp \
  && install /tmp/git-lfs-3.6.1/git-lfs /usr/local/bin/git-lfs \
  && rm -rf /tmp/git-lfs*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Everything that should survive between runs lives in the /cache volume.
ENV CONAN_HOME=/cache/conan \
  CCACHE_DIR=/cache/ccache \
  CCACHE_MAXSIZE=5G \
  CCACHE_SLOPPINESS=pch_defines,time_macros,locale,include_file_ctime,include_file_mtime \
  CCACHE_BASEDIR=/ \
  CCACHE_NOHASHDIR=1 \
  UV_CACHE_DIR=/cache/uv \
  UV_PYTHON_INSTALL_DIR=/cache/python \
  UV_LINK_MODE=copy \
  UV_PROJECT_ENVIRONMENT=/cache/deploy-venv

WORKDIR /work
