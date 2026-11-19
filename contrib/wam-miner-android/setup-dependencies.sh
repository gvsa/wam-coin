#!/usr/bin/env sh

# Exit immediately if a command exits with a non-zero status
set -e

# Install Linux native build tools (needed on both dev machines and runners)
sudo apt-get update
sudo apt-get install -y wget unzip \
    build-essential libtool autotools-dev automake pkg-config bsdmainutils \
    cmake curl git python3 \
    libevent-dev libboost-dev libsqlite3-dev

# Check if Java is installed, JAVA_HOME is set, and major version is >= 17 (needed by modern sdkmanager)
NEED_JDK17=0
if [ -z "${JAVA_HOME:-}" ] || ! command -v java >/dev/null 2>&1; then
    NEED_JDK17=1
else
    JAVA_MAJOR=$(java -version 2>&1 | awk -F '"' '/version/ {print $2}' | awk -F '.' '{if ($1 == "1") print $2; else print $1}')
    if [ -z "$JAVA_MAJOR" ] || [ "$JAVA_MAJOR" -lt 17 ]; then
        echo "Detected Java version ${JAVA_MAJOR:-unknown} (< 17). Modern sdkmanager requires JDK 17+."
        NEED_JDK17=1
    fi
fi

if [ "$NEED_JDK17" -eq 1 ]; then
    echo "Installing openjdk-17-jdk..."
    sudo apt-get install -y openjdk-17-jdk
    JDK17_PATH=$(dirname "$(dirname "$(readlink -f /usr/lib/jvm/java-17-openjdk-*/bin/java | head -n 1)")")
    if [ -d "$JDK17_PATH" ]; then
        export JAVA_HOME="$JDK17_PATH"
        export PATH="$JAVA_HOME/bin:$PATH"
        echo "Set JAVA_HOME to '$JAVA_HOME'."
    fi
else
    echo "JAVA_HOME is set to '$JAVA_HOME' (Java $JAVA_MAJOR). Skipping JDK installation."
fi

# 1. Bootstrap Android Command Line Tools only if ANDROID_HOME is completely missing
if [ -z "${ANDROID_HOME:-}" ]; then
    echo "ANDROID_HOME is not set. Setting up local Android SDK..."
    export ANDROID_HOME="$HOME/Android/Sdk"
    mkdir -p "$ANDROID_HOME/cmdline-tools"

    if [ ! -d "$ANDROID_HOME/cmdline-tools/latest" ]; then
        echo "Downloading Android Command Line Tools..."
        wget -q --show-progress https://dl.google.com/android/repository/commandlinetools-linux-6200805_latest.zip
        unzip -q commandlinetools-linux-11076708_latest.zip -d "$ANDROID_HOME/cmdline-tools"
        mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"
        rm commandlinetools-linux-11076708_latest.zip
    fi
fi

# Locate sdkmanager (handles both local SDK and GitHub runner /usr/local/lib/android/sdk)
SDKMGR="$(command -v sdkmanager || echo "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager")"

# Use sudo only if ANDROID_HOME is not writable by the current user (e.g., GitHub runners)
SUDO_SDK=""
if [ ! -w "$ANDROID_HOME" ]; then
    SUDO_SDK="sudo"
fi

# Always verify & install SDK 33, Build-Tools 33.0.2, CMake 3.22.1, and NDK 21.4.7075529
if [ ! -d "$ANDROID_HOME/ndk/21.4.7075529" ] || \
   [ ! -d "$ANDROID_HOME/cmake/3.22.1" ] || \
   [ ! -d "$ANDROID_HOME/platforms/android-33" ] || \
   [ ! -d "$ANDROID_HOME/build-tools/33.0.2" ]; then
    echo "Installing Android SDK 33, NDK 21.4.7075529, and CMake 3.22.1 into $ANDROID_HOME..."
    (yes || true) | $SUDO_SDK env JAVA_HOME="$JAVA_HOME" "$SDKMGR" --sdk_root="$ANDROID_HOME" --licenses >/dev/null
    $SUDO_SDK env JAVA_HOME="$JAVA_HOME" "$SDKMGR" --sdk_root="$ANDROID_HOME" \
        "build-tools;33.0.2" \
        "platform-tools" \
        "platforms;android-33" \
        "cmake;3.22.1" \
        "ndk;21.4.7075529"
else
    echo "Android SDK 33, NDK 21.4.7075529, and CMake 3.22.1 are already installed."
fi