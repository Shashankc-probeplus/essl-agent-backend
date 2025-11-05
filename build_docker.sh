#!/bin/bash
# =============================================================================
# Docker Build Script for ESSL Agent Backend
# =============================================================================
# This script builds the executable using Docker, avoiding Python shared
# library issues on the host system
#
# Usage: ./build_docker.sh
#
# Advantages:
# - No need to fix host Python installation
# - Consistent build environment
# - Works even if host Python lacks shared libraries
# - Easy to reproduce builds
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}ESSL Agent Backend - Docker Build${NC}"
echo -e "${BLUE}============================================${NC}"

# =============================================================================
# Step 1: Check Docker Installation
# =============================================================================

echo -e "\n${YELLOW}Checking Docker installation...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    echo -e "\n${BLUE}Install Docker:${NC}"
    echo -e "  Ubuntu/Debian: sudo apt install docker.io"
    echo -e "  Or visit: https://docs.docker.com/engine/install/"
    exit 1
fi

echo -e "${GREEN}✓ Docker found: $(docker --version)${NC}"

# Check if Docker daemon is running
if ! docker ps &> /dev/null; then
    echo -e "${RED}❌ Docker daemon is not running${NC}"
    echo -e "\n${BLUE}Start Docker:${NC}"
    echo -e "  sudo systemctl start docker"
    echo -e "  Or: sudo dockerd"
    exit 1
fi

echo -e "${GREEN}✓ Docker daemon is running${NC}"

# =============================================================================
# Step 2: Verify Required Files
# =============================================================================

echo -e "\n${YELLOW}Verifying required files...${NC}"

REQUIRED_FILES=(
    "launcher.py"
    "essl-agent.spec"
    "app/main.py"
    "requirements.txt"
    "Dockerfile.build"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -e "$file" ]; then
        echo -e "${RED}❌ Missing required file: $file${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Found: $file${NC}"
done

# =============================================================================
# Step 3: Clean Previous Builds
# =============================================================================

echo -e "\n${YELLOW}Cleaning previous builds...${NC}"

rm -rf build/
rm -rf dist/
rm -rf __pycache__/
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

echo -e "${GREEN}✓ Cleaned previous builds${NC}"

# =============================================================================
# Step 4: Build Docker Image
# =============================================================================

echo -e "\n${YELLOW}Building Docker image...${NC}"
echo -e "${BLUE}This may take a few minutes on first run...${NC}\n"

if docker build -f Dockerfile.build -t essl-builder . ; then
    echo -e "\n${GREEN}✓ Docker image built successfully${NC}"
else
    echo -e "\n${RED}❌ Docker image build failed${NC}"
    exit 1
fi

# =============================================================================
# Step 5: Build Executable in Container
# =============================================================================

echo -e "\n${YELLOW}Building executable in Docker container...${NC}"
echo -e "${BLUE}This may take a few minutes...${NC}\n"

# Run the container
# --rm: Remove container after it exits
# -v: Mount dist/ directory so we can access the output
if docker run --rm -v "$(pwd)/dist:/app/dist" essl-builder ; then
    echo -e "\n${GREEN}✓ Executable built successfully${NC}"
else
    echo -e "\n${RED}❌ Build failed inside Docker container${NC}"
    exit 1
fi

# =============================================================================
# Step 6: Verify Build Success
# =============================================================================

if [ ! -d "dist/essl-agent" ]; then
    echo -e "${RED}❌ Build failed - dist/essl-agent directory not created${NC}"
    exit 1
fi

# Check for the executable
if [ -f "dist/essl-agent/essl-agent" ]; then
    echo -e "\n${GREEN}============================================${NC}"
    echo -e "${GREEN}✅ Build Successful!${NC}"
    echo -e "${GREEN}============================================${NC}"
    
    echo -e "\n${BLUE}Output location:${NC}"
    echo -e "  $(pwd)/dist/essl-agent/"
    
    echo -e "\n${BLUE}Executable details:${NC}"
    ls -lh dist/essl-agent/essl-agent
    
    echo -e "\n${BLUE}Next steps:${NC}"
    echo -e "  1. Copy the ${YELLOW}dist/essl-agent/${NC} folder"
    echo -e "  2. Add a ${YELLOW}.env${NC} file with customer configuration"
    echo -e "  3. Package as zip for distribution"
    
    echo -e "\n${BLUE}Package structure:${NC}"
    echo -e "  essl-agent/"
    echo -e "  ├── essl-agent (Linux executable)"
    echo -e "  ├── _internal/ (bundled dependencies)"
    echo -e "  └── .env (add this for each customer)"
    
    echo -e "\n${YELLOW}Tip: Use package_customer.sh to automate customer packaging${NC}"
    echo -e "${GREEN}============================================${NC}"
else
    echo -e "${RED}❌ Build failed - executable not found${NC}"
    exit 1
fi

# =============================================================================
# Optional: Test the executable
# =============================================================================

echo -e "\n${YELLOW}Would you like to test the executable? (y/n)${NC}"
read -r response

if [[ "$response" =~ ^[Yy]$ ]]; then
    echo -e "\n${BLUE}Testing executable...${NC}"
    echo -e "${YELLOW}(Press Ctrl+C to stop the test server)${NC}\n"
    
    cd dist/essl-agent/
    ./essl-agent
fi
