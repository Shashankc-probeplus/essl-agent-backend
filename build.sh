#!/bin/bash
# ============================================================================
# Build Script for ESSL Agent Backend
# ============================================================================
# This script automates the process of building the executable
#
# Usage: ./build.sh
#
# What it does:
# 1. Checks if PyInstaller is installed
# 2. Cleans previous builds
# 3. Builds the executable using PyInstaller
# 4. Displays the output location
# ============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}ESSL Agent Backend - Build Script${NC}"
echo -e "${BLUE}============================================${NC}"

# ============================================================================
# Step 1: Check Prerequisites
# ============================================================================

echo -e "\n${YELLOW}Checking prerequisites...${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python3 found: $(python3 --version)${NC}"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}❌ pip3 is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ pip3 found${NC}"

# Check if PyInstaller is installed
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  PyInstaller not found. Installing...${NC}"
    pip3 install pyinstaller
fi

echo -e "${GREEN}✓ PyInstaller is installed${NC}"

# ============================================================================
# Step 2: Verify Required Files
# ============================================================================

echo -e "\n${YELLOW}Verifying required files...${NC}"

REQUIRED_FILES=(
    "launcher.py"
    "essl-agent.spec"
    "app/main.py"
    "requirements.txt"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -e "$file" ]; then
        echo -e "${RED}❌ Missing required file: $file${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Found: $file${NC}"
done

# ============================================================================
# Step 3: Install Dependencies
# ============================================================================

echo -e "\n${YELLOW}Installing dependencies...${NC}"
pip3 install -r requirements.txt --quiet

echo -e "${GREEN}✓ Dependencies installed${NC}"

# ============================================================================
# Step 4: Clean Previous Builds
# ============================================================================

echo -e "\n${YELLOW}Cleaning previous builds...${NC}"

# Remove previous build artifacts
rm -rf build/
rm -rf dist/
rm -rf __pycache__/
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

echo -e "${GREEN}✓ Cleaned previous builds${NC}"

# ============================================================================
# Step 5: Build the Executable
# ============================================================================

echo -e "\n${YELLOW}Building executable...${NC}"
echo -e "${BLUE}This may take a few minutes...${NC}\n"

# Build using PyInstaller with the spec file
python3 -m PyInstaller essl-agent.spec --clean

# ============================================================================
# Step 6: Verify Build Success
# ============================================================================

if [ ! -d "dist/essl-agent" ]; then
    echo -e "${RED}❌ Build failed - dist/essl-agent directory not created${NC}"
    exit 1
fi

# Check for the executable
if [ -f "dist/essl-agent/essl-agent" ] || [ -f "dist/essl-agent/essl-agent.exe" ]; then
    echo -e "\n${GREEN}============================================${NC}"
    echo -e "${GREEN}✅ Build Successful!${NC}"
    echo -e "${GREEN}============================================${NC}"
    
    echo -e "\n${BLUE}Output location:${NC}"
    echo -e "  $(pwd)/dist/essl-agent/"
    
    echo -e "\n${BLUE}Next steps:${NC}"
    echo -e "  1. Copy the ${YELLOW}dist/essl-agent/${NC} folder"
    echo -e "  2. Add a ${YELLOW}.env${NC} file with customer configuration"
    echo -e "  3. Package as zip for distribution"
    
    echo -e "\n${BLUE}Package structure:${NC}"
    echo -e "  essl-agent/"
    echo -e "  ├── essl-agent (or essl-agent.exe)"
    echo -e "  ├── _internal/ (bundled dependencies)"
    echo -e "  └── .env (add this for each customer)"
    
    echo -e "\n${YELLOW}Tip: Use package_customer.sh to automate customer packaging${NC}"
    echo -e "${GREEN}============================================${NC}"
else
    echo -e "${RED}❌ Build failed - executable not found${NC}"
    exit 1
fi
