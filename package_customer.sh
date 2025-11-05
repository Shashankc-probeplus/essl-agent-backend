#!/bin/bash
# ============================================================================
# Customer Package Creator for ESSL Agent Backend
# ============================================================================
# This script creates a customer-specific package with their configuration
#
# Usage: ./package_customer.sh <customer_name> <server_url> <agent_id>
#
# Example: 
#   ./package_customer.sh "acme-corp" "https://api.acme.com" "AGENT001"
#
# What it does:
# 1. Copies the built executable
# 2. Creates custom .env file with customer details
# 3. Adds README with instructions
# 4. Creates a zip file ready for download
# ============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Validate Input Arguments
# ============================================================================

if [ $# -ne 3 ]; then
    echo -e "${RED}❌ Invalid arguments${NC}"
    echo -e "\n${BLUE}Usage:${NC}"
    echo -e "  $0 <customer_name> <server_url> <agent_id>"
    echo -e "\n${BLUE}Example:${NC}"
    echo -e "  $0 'acme-corp' 'https://api.acme.com' 'AGENT001'"
    exit 1
fi

CUSTOMER_NAME=$1
SERVER_URL=$2
AGENT_ID=$3

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Customer Package Creator${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Customer: ${YELLOW}$CUSTOMER_NAME${NC}"
echo -e "${BLUE}Server URL: ${YELLOW}$SERVER_URL${NC}"
echo -e "${BLUE}Agent ID: ${YELLOW}$AGENT_ID${NC}"
echo -e "${BLUE}============================================${NC}"

# ============================================================================
# Step 1: Verify Build Exists
# ============================================================================

echo -e "\n${YELLOW}Verifying build exists...${NC}"

if [ ! -d "dist/essl-agent" ]; then
    echo -e "${RED}❌ Build not found. Please run ./build.sh first${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Build found${NC}"

# ============================================================================
# Step 2: Create Package Directory
# ============================================================================

echo -e "\n${YELLOW}Creating package directory...${NC}"

PACKAGE_DIR="packages/${CUSTOMER_NAME}_essl-agent"
mkdir -p "$PACKAGE_DIR"

echo -e "${GREEN}✓ Created: $PACKAGE_DIR${NC}"

# ============================================================================
# Step 3: Copy Executable and Dependencies
# ============================================================================

echo -e "\n${YELLOW}Copying executable and dependencies...${NC}"

# Copy entire dist/essl-agent folder
cp -r dist/essl-agent/* "$PACKAGE_DIR/"

echo -e "${GREEN}✓ Copied executable and dependencies${NC}"

# ============================================================================
# Step 4: Create Custom .env File
# ============================================================================

echo -e "\n${YELLOW}Creating custom .env file...${NC}"

cat > "$PACKAGE_DIR/.env" << EOF
# ESSL Agent Backend Configuration
# Customer: $CUSTOMER_NAME
# Generated: $(date)

# Server URL - The backend server this agent will connect to
SERVER_URL=$SERVER_URL

# Agent ID - Unique identifier for this agent
AGENT_ID=$AGENT_ID

# Optional: Server host and port (uncomment to override defaults)
# HOST=0.0.0.0
# PORT=8000
EOF

echo -e "${GREEN}✓ Created .env file${NC}"

# ============================================================================
# Step 5: Create README
# ============================================================================

echo -e "\n${YELLOW}Creating README...${NC}"

cat > "$PACKAGE_DIR/README.txt" << 'EOF'
================================================================================
                    ESSL Agent Backend - Installation Guide
================================================================================

QUICK START
-----------
1. Extract all files from this archive to a folder
2. Double-click the executable file to start the server:
   - Windows: essl-agent.exe
   - Linux/Mac: essl-agent (or ./essl-agent from terminal)
3. The server will start automatically

CONFIGURATION
-------------
The .env file contains your configuration:
- SERVER_URL: The backend server URL
- AGENT_ID: Your unique agent identifier

To modify configuration:
1. Open .env file with a text editor (Notepad, TextEdit, etc.)
2. Update the values
3. Save the file
4. Restart the application

TROUBLESHOOTING
---------------
Problem: "Permission denied" error on Linux/Mac
Solution: Make the file executable
  chmod +x essl-agent
  ./essl-agent

Problem: ".env file not found"
Solution: Ensure .env file is in the same folder as the executable

Problem: Port already in use
Solution: Edit .env file and add:
  PORT=8001
(or any other available port number)

SYSTEM REQUIREMENTS
-------------------
- Windows 10 or later / Linux / macOS
- No Python installation required
- Minimum 100MB free disk space
- Network connection to reach SERVER_URL

SUPPORT
-------
For technical support, please contact your system administrator.

================================================================================
EOF

echo -e "${GREEN}✓ Created README.txt${NC}"

# ============================================================================
# Step 6: Create Zip Archive
# ============================================================================

echo -e "\n${YELLOW}Creating zip archive...${NC}"

ZIP_NAME="packages/${CUSTOMER_NAME}_essl-agent.zip"

# Change to packages directory to create cleaner zip structure
cd packages
zip -r -q "${CUSTOMER_NAME}_essl-agent.zip" "${CUSTOMER_NAME}_essl-agent"
cd ..

echo -e "${GREEN}✓ Created: $ZIP_NAME${NC}"

# ============================================================================
# Step 7: Display Summary
# ============================================================================

echo -e "\n${GREEN}============================================${NC}"
echo -e "${GREEN}✅ Package Created Successfully!${NC}"
echo -e "${GREEN}============================================${NC}"

echo -e "\n${BLUE}Package Location:${NC}"
echo -e "  📦 $(pwd)/$ZIP_NAME"

echo -e "\n${BLUE}Package Contents:${NC}"
echo -e "  ├── essl-agent (executable)"
echo -e "  ├── _internal/ (dependencies)"
echo -e "  ├── .env (customer configuration)"
echo -e "  └── README.txt (instructions)"

echo -e "\n${BLUE}Package Size:${NC}"
du -sh "$ZIP_NAME" | awk '{print "  " $1}'

echo -e "\n${BLUE}Configuration:${NC}"
echo -e "  Customer: $CUSTOMER_NAME"
echo -e "  Server: $SERVER_URL"
echo -e "  Agent ID: $AGENT_ID"

echo -e "\n${YELLOW}Next Steps:${NC}"
echo -e "  1. Test the package by extracting and running it"
echo -e "  2. Upload $ZIP_NAME to your distribution platform"
echo -e "  3. Send download link to $CUSTOMER_NAME"

echo -e "\n${GREEN}============================================${NC}"
